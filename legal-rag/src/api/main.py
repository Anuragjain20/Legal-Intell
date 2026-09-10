"""FastAPI backend: ingestion, retrieval, and generation as REST endpoints.

This is the real service layer for the RAG pipeline - it owns the embedding
model, vector store, and LLM client as process-lifetime singletons (built
once in the lifespan handler, not per request). The Streamlit app is a thin
HTTP client over this API; it must not import src.* pipeline modules itself,
since ChromaVectorStore opens a SQLite-backed PersistentClient that is not
safe for two processes to write to concurrently.
"""

from __future__ import annotations

import glob
import json
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.cases.registry import CaseNotFoundError, CaseRegistry
from src.evaluation.runner import run_and_build_output, write_results
from src.generation.exceptions import GenerationError
from src.ingestion.chunker_factory import CHUNKING_METHODS
from src.ingestion.exceptions import ChunkingError, UploadValidationError
from src.retrieval.exceptions import NoRelevantResultsError, RetrievalError
from src.services import build_services
from src.vectorstore.service import VectorIndexService

APP_DIR = Path(__file__).resolve().parent.parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.services = build_services(APP_DIR)
    app.state.eval_runs = {}
    app.state.eval_lock = threading.Lock()
    app.state.cases = CaseRegistry(APP_DIR / "data" / "cases.json")
    yield


app = FastAPI(title="Legal RAG API", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str
    top_k: int = 8
    case_id: str | None = None


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
    case_id: str | None = None


class IngestResponse(BaseModel):
    filename: str
    category: str
    chunking_method: str
    chunks_indexed: int


class HealthResponse(BaseModel):
    status: str
    indexed_chunks: int
    embedding_model: str
    chunking_method: str
    available_chunking_methods: list[str]


class EvaluateRequest(BaseModel):
    retrieval_method: Literal["dense", "bm25", "hybrid", "hybrid_rerank"] = "hybrid"
    chunking_method: Literal["legal", "recursive", "llm_semantic"] = "legal"
    top_k: int = 5


class EvaluateSubmitResponse(BaseModel):
    run_id: str
    status: str


class EvaluateStatusResponse(BaseModel):
    run_id: str
    status: str
    retrieval_method: str
    chunking_method: str
    error: str | None = None
    results_path: str | None = None
    summary: dict[str, Any] | None = None


class EvaluationRunListEntry(BaseModel):
    run_dir: str
    manifest: dict[str, Any]
    summary: dict[str, Any]


class DocumentOut(BaseModel):
    document_id: str
    filename: str
    category: str | None


class CaseOut(BaseModel):
    case_id: str
    name: str
    description: str | None
    document_ids: list[str]


class CreateCaseRequest(BaseModel):
    name: str
    description: str | None = None


class AddDocumentToCaseRequest(BaseModel):
    document_id: str


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
    indexed_chunks = services.vector_store._collection.count()
    return HealthResponse(
        status="ok",
        indexed_chunks=indexed_chunks,
        embedding_model=services.settings.embedding_model,
        chunking_method=services.settings.chunking_method,
        available_chunking_methods=list(CHUNKING_METHODS),
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    category: str = Form("general"),
    chunking_method: str = Form("legal"),
) -> IngestResponse:
    """Ingest a document under the requested chunking method.

    Every method in CHUNKING_METHODS is built once at startup, each pointed
    at its own Chroma directory (see src/services.py chroma_dir_for_method),
    so routing an upload to a different method here never opens the same
    Chroma path from two writers - it opens a different, independent one.
    Querying (POST /query) always reads the server's default/primary method
    (services.retriever), matching how the CLI's default ingest and the
    live production index have always worked.
    """
    services = app.state.services
    if chunking_method not in CHUNKING_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown chunking_method {chunking_method!r}; expected one of {CHUNKING_METHODS}.",
        )

    upload_service = services.upload_services_by_method[chunking_method]
    vector_store = services.vector_stores_by_method[chunking_method]
    content = await file.read()

    try:
        metadata, extraction, chunks = upload_service.upload(
            filename=file.filename, content=content, category=category
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ChunkingError as exc:
        raise HTTPException(status_code=502, detail=f"Chunking failed: {exc}") from exc

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail=f"{metadata.filename} has no extractable text. Scanned PDFs need OCR support.",
        )

    embedded = services.embedding_service.embed_chunks(chunks)
    VectorIndexService(store=vector_store).index_embeddings(embedded)

    if chunking_method == services.settings.chunking_method:
        # Only the server's default/query-time index needs its BM25 half
        # rebuilt - BM25Retriever has no incremental update path, and the
        # other methods' stores aren't wired into any live retriever.
        services.rebuild_bm25_index()

    return IngestResponse(
        filename=metadata.filename,
        category=category,
        chunking_method=chunking_method,
        chunks_indexed=len(chunks),
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """Answer a question, optionally scoped to a single case's documents.

    When case_id is set, retrieval is restricted to that case's document_ids
    (via HybridQueryRetriever's filters param - see src/retrieval/
    hybrid_query_retriever.py). A case_id that doesn't resolve to a known
    case, or resolves to a case with no documents attached yet, returns the
    same refused/empty shape as "no results above threshold" rather than
    silently falling back to an unscoped global search - a wrong or empty
    case_id should never look like it searched everything.
    """
    services = app.state.services

    if not services.settings.deepseek_api_key:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY is not configured on the server.")

    filters: dict[str, Any] | None = None
    if request.case_id is not None:
        case = app.state.cases.get(request.case_id)
        if case is None or not case.document_ids:
            return QueryResponse(
                refused=True,
                case_id=request.case_id,
                trace={
                    "question": request.question,
                    "steps": [{"step": "1. Embedding & Retrieval", "status": "case has no associated documents"}],
                },
            )
        filters = {"document_ids": case.document_ids}

    try:
        results = services.retriever.retrieve(request.question, top_k=request.top_k, filters=filters)
    except NoRelevantResultsError:
        return QueryResponse(
            refused=True,
            case_id=request.case_id,
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
        case_id=request.case_id,
    )


def _run_evaluation_job(run_id: str, retrieval_method: str, chunking_method: str, top_k: int) -> None:
    """Runs inside FastAPI's BackgroundTasks - i.e. still the one API
    process, never a spawned subprocess, so any Chroma directory it opens
    is opened by the same single writer as everything else in this app."""
    run_record = app.state.eval_runs[run_id]
    with app.state.eval_lock:
        run_record["status"] = "running"
        try:
            result = run_and_build_output(
                app_dir=APP_DIR,
                retrieval_method=retrieval_method,
                chunking_method=chunking_method,
                top_k=top_k,
            )
            results_path = write_results(APP_DIR / "data", result.output)
            run_record["status"] = "done"
            run_record["results_path"] = str(results_path)
            run_record["summary"] = result.output["summary"]
        except Exception as exc:  # noqa: BLE001 - report the failure via the status endpoint
            run_record["status"] = "failed"
            run_record["error"] = f"{type(exc).__name__}: {exc}"


@app.post("/evaluate", response_model=EvaluateSubmitResponse)
def submit_evaluation(request: EvaluateRequest, background_tasks: BackgroundTasks) -> EvaluateSubmitResponse:
    """Submit an evaluation run as a background job and return immediately.

    A full run over the dataset routinely exceeds typical HTTP client
    timeouts (the Streamlit UI's included), so this never runs synchronously
    - poll GET /evaluate/{run_id} for status and the summary once done.
    """
    run_id = uuid.uuid4().hex
    app.state.eval_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "retrieval_method": request.retrieval_method,
        "chunking_method": request.chunking_method,
        "error": None,
        "results_path": None,
        "summary": None,
    }
    background_tasks.add_task(
        _run_evaluation_job, run_id, request.retrieval_method, request.chunking_method, request.top_k
    )
    return EvaluateSubmitResponse(run_id=run_id, status="pending")


@app.get("/evaluate/runs", response_model=list[EvaluationRunListEntry])
def list_evaluation_runs() -> list[EvaluationRunListEntry]:
    """List completed evaluation runs by reading data/eval_runs/*/results.json
    directly - this covers runs written by the CLI (scripts/run_evaluation.py)
    as well as ones triggered from this API, since both write the same
    manifest+summary+case_results shape to the same directory.

    Registered before /evaluate/{run_id} - Starlette matches routes in
    registration order, and a {run_id} path parameter would otherwise
    greedily swallow the literal "runs" segment.
    """
    data_dir = APP_DIR / "data"
    entries: list[EvaluationRunListEntry] = []
    for results_path in sorted(glob.glob(str(data_dir / "eval_runs" / "*" / "results.json"))):
        try:
            payload = json.loads(Path(results_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entries.append(
            EvaluationRunListEntry(
                run_dir=Path(results_path).parent.name,
                manifest=payload.get("manifest", {}),
                summary=payload.get("summary", {}),
            )
        )
    entries.sort(key=lambda e: e.run_dir, reverse=True)
    return entries


@app.get("/evaluate/{run_id}", response_model=EvaluateStatusResponse)
def get_evaluation_status(run_id: str) -> EvaluateStatusResponse:
    run_record = app.state.eval_runs.get(run_id)
    if run_record is None:
        raise HTTPException(status_code=404, detail=f"No evaluation run with id {run_id!r}.")
    return EvaluateStatusResponse(**run_record)


@app.get("/documents", response_model=list[DocumentOut])
def list_documents() -> list[DocumentOut]:
    """List every ingested document, for the Cases tab's document picker.

    Backed by the same DocumentRegistry (data/documents.json) the default
    upload service already writes to on every POST /ingest - not a separate
    catalog, so this always reflects what's actually indexed.
    """
    services = app.state.services
    documents = services.upload_service.registry.list_all()
    return [
        DocumentOut(document_id=d.document_id, filename=d.filename, category=d.category) for d in documents
    ]


@app.post("/cases", response_model=CaseOut)
def create_case(request: CreateCaseRequest) -> CaseOut:
    case = app.state.cases.create(request.name, request.description)
    return CaseOut(case_id=case.case_id, name=case.name, description=case.description, document_ids=case.document_ids)


@app.get("/cases", response_model=list[CaseOut])
def list_cases() -> list[CaseOut]:
    cases = app.state.cases.list_all()
    return [
        CaseOut(case_id=c.case_id, name=c.name, description=c.description, document_ids=c.document_ids)
        for c in cases
    ]


@app.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: str) -> CaseOut:
    case = app.state.cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No case with id {case_id!r}.")
    return CaseOut(case_id=case.case_id, name=case.name, description=case.description, document_ids=case.document_ids)


@app.post("/cases/{case_id}/documents", response_model=CaseOut)
def add_document_to_case(case_id: str, request: AddDocumentToCaseRequest) -> CaseOut:
    """Associate an already-ingested document with a case.

    Association only - the document is not re-ingested or re-chunked, and
    the same document_id may be attached to any number of cases (e.g. a
    shared precedent cited across several matters). See src/cases/registry.py.
    """
    try:
        case = app.state.cases.add_document(case_id, request.document_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"No case with id {case_id!r}.") from None
    return CaseOut(case_id=case.case_id, name=case.name, description=case.description, document_ids=case.document_ids)


@app.delete("/cases/{case_id}/documents/{document_id}", response_model=CaseOut)
def remove_document_from_case(case_id: str, document_id: str) -> CaseOut:
    try:
        case = app.state.cases.remove_document(case_id, document_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"No case with id {case_id!r}.") from None
    return CaseOut(case_id=case.case_id, name=case.name, description=case.description, document_ids=case.document_ids)
