"""FastAPI backend: ingestion, retrieval, and generation as REST endpoints.

This is the real service layer for the RAG pipeline - it owns the embedding
model, vector store, and LLM client as process-lifetime singletons (built
once in the lifespan handler, not per request). The Streamlit app is a thin
HTTP client over this API; it must not import src.* pipeline modules itself,
since ChromaVectorStore opens a SQLite-backed PersistentClient that is not
safe for two processes to write to concurrently.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.generation.exceptions import GenerationError
from src.ingestion.exceptions import UploadValidationError
from src.retrieval.exceptions import NoRelevantResultsError, RetrievalError
from src.services import build_services

APP_DIR = Path(__file__).resolve().parent.parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.services = build_services(APP_DIR)
    yield


app = FastAPI(title="Legal RAG API", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str
    top_k: int = 8


class CitationOut(BaseModel):
    citation_id: int
    document_name: str
    page_number: int
    section: str | None
    heading: str | None


class QueryResponse(BaseModel):
    refused: bool
    answer: str | None = None
    model: str | None = None
    citations: list[CitationOut] = []
    trace: dict[str, Any]


class IngestResponse(BaseModel):
    filename: str
    category: str
    chunks_indexed: int


class HealthResponse(BaseModel):
    status: str
    indexed_chunks: int
    embedding_model: str


def _build_retrieval_trace(question: str, results: list) -> dict[str, Any]:
    return {
        "step": "1. Embedding & Retrieval",
        "status": "complete",
        "retrieved_count": len(results),
        "top_result_score": f"{results[0].score:.4f}" if results else "N/A",
        "results": [
            {
                "rank": r.rank,
                "document": r.record.document_name or r.record.document_id,
                "page": r.record.page_number,
                "section": r.record.section or "N/A",
                "heading": r.record.heading or "N/A",
                "score": f"{r.score:.4f}",
                "snippet": r.record.text[:100] + "..." if len(r.record.text) > 100 else r.record.text,
            }
            for r in results
        ],
    }


def _build_context_trace(result) -> dict[str, Any]:
    return {
        "step": "2. Building Context",
        "status": "complete",
        "sources_selected": len(result.used_context.sources),
        "context_length": len(result.used_context.rendered_context),
        "sources": [
            {
                "rank": s.rank,
                "document": s.document_name or s.document_id,
                "page": s.page_number,
                "section": s.section or "N/A",
                "heading": s.heading or "N/A",
                "score": f"{s.score:.4f}",
            }
            for s in result.used_context.sources
        ],
    }


def _build_generation_trace(result) -> dict[str, Any]:
    return {
        "step": "3. LLM Generation",
        "status": "complete",
        "model": result.model,
        "citations_found": len(result.citations or []),
        "answer_length": len(result.answer),
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    services = app.state.services
    indexed_chunks = services.retriever.vector_store._collection.count()
    return HealthResponse(
        status="ok",
        indexed_chunks=indexed_chunks,
        embedding_model=services.settings.embedding_model,
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...), category: str = Form("general")) -> IngestResponse:
    services = app.state.services
    content = await file.read()

    try:
        metadata, extraction, chunks = services.upload_service.upload(
            filename=file.filename, content=content, category=category
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail=f"{metadata.filename} has no extractable text. Scanned PDFs need OCR support.",
        )

    embedded = services.embedding_service.embed_chunks(chunks)
    services.index_service.index_embeddings(embedded)

    return IngestResponse(filename=metadata.filename, category=category, chunks_indexed=len(chunks))


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    services = app.state.services

    if not services.settings.deepseek_api_key:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY is not configured on the server.")

    try:
        results = services.retriever.retrieve(request.question, top_k=request.top_k)
    except NoRelevantResultsError:
        return QueryResponse(
            refused=True,
            trace={"question": request.question, "steps": [{"step": "1. Embedding & Retrieval", "status": "no results above threshold"}]},
        )
    except RetrievalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trace_steps = [_build_retrieval_trace(request.question, results)]

    try:
        result = services.generation_service.answer(request.question, results)
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    trace_steps.append(_build_context_trace(result))
    trace_steps.append(_build_generation_trace(result))

    citations = [
        CitationOut(
            citation_id=c.citation_id,
            document_name=c.document_name,
            page_number=c.page_number,
            section=c.section,
            heading=c.heading,
        )
        for c in (result.citations or [])
    ]

    return QueryResponse(
        refused=False,
        answer=result.answer,
        model=result.model,
        citations=citations,
        trace={"question": request.question, "steps": trace_steps},
    )
