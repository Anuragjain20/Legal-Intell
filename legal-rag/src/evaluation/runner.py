"""Build a retriever for (retrieval_method, chunking_method) and run the
evaluation harness against it, producing the same manifest+summary+
case_results shape scripts/run_evaluation.py writes to
data/eval_runs/<timestamp>/results.json.

Extracted so both the CLI script and the API's POST /evaluate endpoint
(src/api/main.py) share exactly one implementation of "which retriever
does this method name build" and "what does a result file look like" -
duplicating that logic between a script and a FastAPI route would let
them silently drift.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.evaluation.harness import EvaluationSummary, build_relevant_chunk_index, load_dataset, run_evaluation
from src.evaluation.retriever_adapters import (
    BM25RetrieverAdapter,
    HybridRetrieverAdapter,
    RerankedHybridRetrieverAdapter,
)
from src.retrieval.bm25_baseline import BM25Retriever
from src.retrieval.dense_baseline import DenseRetriever
from src.retrieval.hybrid_retrieval import HybridRetriever
from src.retrieval.reranking import QueryTermOverlapReranker, RankerPipeline
from src.retrieval.retriever import Retriever
from src.vectorstore.chroma_store import ChromaVectorStore

RETRIEVAL_METHODS = ("dense", "bm25", "hybrid", "hybrid_rerank")
DEFAULT_TOP_K = 5


def chroma_dir_for_chunking_method(data_dir: Path, chunking_method: str) -> Path:
    return data_dir / "chroma" if chunking_method == "legal" else data_dir / f"chroma_{chunking_method}"


def git_commit_sha(app_dir: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=app_dir, text=True).strip()
    except Exception:  # noqa: BLE001 - manifest field is best-effort
        return "unknown"


def build_retriever(retrieval_method: str, settings: Settings, chroma_dir: Path):
    """Return (retriever, similarity_threshold_or_None, embedding_provider, vector_store).

    Only dense retrieval's threshold is a cosine similarity comparable to
    settings.similarity_threshold - every other method returns None so the
    confidence-gate rate is reported honestly as not applicable.

    vector_store is returned too so callers can build the ground-truth
    relevant-chunk index (harness.build_relevant_chunk_index) from the same
    index this retriever queries, without opening a second ChromaVectorStore
    against the same directory.
    """
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())

    if retrieval_method == "dense":
        retriever = Retriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            similarity_threshold=settings.similarity_threshold,
        )
        return retriever, settings.similarity_threshold, embedding_provider, vector_store

    records = vector_store.get_all()
    bm25_retriever = BM25Retriever(chunks=records)

    if retrieval_method == "bm25":
        return BM25RetrieverAdapter(bm25_retriever=bm25_retriever), None, embedding_provider, vector_store

    dense_retriever = DenseRetriever(embedding_provider=embedding_provider, vector_store=vector_store)
    hybrid_retriever = HybridRetriever(dense_retriever=dense_retriever, bm25_retriever=bm25_retriever)

    if retrieval_method == "hybrid":
        return HybridRetrieverAdapter(hybrid_retriever=hybrid_retriever), None, embedding_provider, vector_store

    ranker_pipeline = RankerPipeline(QueryTermOverlapReranker())
    return (
        RerankedHybridRetrieverAdapter(hybrid_retriever=hybrid_retriever, ranker_pipeline=ranker_pipeline),
        None,
        embedding_provider,
        vector_store,
    )


@dataclass
class EvaluationRunResult:
    summary: EvaluationSummary
    output: dict


def run_and_build_output(
    *,
    app_dir: Path,
    retrieval_method: str,
    chunking_method: str,
    top_k: int = DEFAULT_TOP_K,
) -> EvaluationRunResult:
    """Run one evaluation and build the exact dict written to results.json."""
    data_dir = app_dir / "data"
    dataset_path = data_dir / "evaluation_dataset.json"
    chroma_dir = chroma_dir_for_chunking_method(data_dir, chunking_method)

    settings = Settings.from_env(app_dir / ".env")
    retriever, gate_threshold, embedding_provider, vector_store = build_retriever(
        retrieval_method, settings, chroma_dir
    )
    chunks_by_document = build_relevant_chunk_index(vector_store)

    dataset = load_dataset(dataset_path)
    summary = run_evaluation(retriever, dataset, gate_threshold, chunks_by_document, top_k=top_k)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_sha": git_commit_sha(app_dir),
        "embedding_model": embedding_provider.model_name,
        "embedding_version": embedding_provider.model_version,
        "retrieval_method": retrieval_method,
        "chunking_method": chunking_method,
        "similarity_threshold": gate_threshold,
        "dataset_version": dataset["metadata"]["version"],
        "dataset_total_questions": len(dataset["questions"]),
        "top_k": top_k,
    }

    output = {
        "manifest": manifest,
        "summary": {
            "total_cases": summary.total_cases,
            "in_corpus_cases": summary.in_corpus_cases,
            "unanswerable_cases": summary.unanswerable_cases,
            "overall": summary.overall,
            "by_question_type": summary.by_question_type,
            "unanswerable_confidence_gate_rate": summary.unanswerable_confidence_gate_rate,
        },
        "case_results": [
            {
                "case_id": r.case_id,
                "question_type": r.question_type,
                "is_out_of_corpus": r.is_out_of_corpus,
                "retrieved_chunk_ids": r.retrieved_chunk_ids,
                "relevant_chunk_ids": r.relevant_chunk_ids,
                "top_score": r.top_score,
                "refused": r.refused,
                "error": r.error,
                "recall_at_k": r.recall_at_k,
                "precision_at_5": r.precision_at_5,
                "mrr": r.mrr,
            }
            for r in summary.case_results
        ],
    }

    return EvaluationRunResult(summary=summary, output=output)


def write_results(data_dir: Path, output: dict) -> Path:
    run_dir = data_dir / "eval_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.json"
    import json

    results_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return results_path
