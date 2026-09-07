"""Run the dense-retrieval baseline evaluation and write a reproducible result.

Loads data/evaluation_dataset.json, retrieves with the same Retriever the
app uses, computes Recall@1/3/5, Precision@5, and MRR overall and per
question type, and reports whether the retriever's own similarity
threshold would correctly withhold an answer on the unanswerable cases.

Output is written to data/eval_runs/<UTC timestamp>/results.json together
with a manifest of everything needed to reproduce the run: embedding model
and version, retrieval method, dataset version, top_k, and the git commit
this was run against.

Usage:
    python scripts/run_evaluation.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from src.config.settings import Settings  # noqa: E402
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider  # noqa: E402
from src.embeddings.service import EmbeddingService  # noqa: E402
from src.evaluation.harness import load_dataset, run_evaluation  # noqa: E402
from src.retrieval.retriever import Retriever  # noqa: E402
from src.vectorstore.chroma_store import ChromaVectorStore  # noqa: E402

DATA_DIR = APP_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma"
DATASET_PATH = DATA_DIR / "evaluation_dataset.json"
TOP_K = 5


def _git_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=APP_DIR, text=True
        ).strip()
    except Exception:  # noqa: BLE001 - manifest field is best-effort
        return "unknown"


def main() -> None:
    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=CHROMA_DIR, dimension=embedding_service.embedding_dimension())
    retriever = Retriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        similarity_threshold=settings.similarity_threshold,
    )

    dataset = load_dataset(DATASET_PATH)
    summary = run_evaluation(retriever, dataset, settings.similarity_threshold, top_k=TOP_K)

    print("Retrieval evaluation (dense baseline)")
    print("=" * 60)
    print(f"Total cases: {summary.total_cases}  (in-corpus: {summary.in_corpus_cases}, unanswerable: {summary.unanswerable_cases})")
    print()
    print("Overall:")
    for key, value in summary.overall.items():
        print(f"  {key:16s} {value}")
    print()
    print("By question type:")
    for q_type, metrics in sorted(summary.by_question_type.items()):
        print(f"  {q_type} (n={metrics['count']}):")
        for key in ("recall_at_1", "recall_at_3", "recall_at_5", "precision_at_5", "mrr"):
            print(f"    {key:16s} {metrics[key]:.4f}")
    print()
    print(f"Unanswerable confidence-gate rate: {summary.unanswerable_confidence_gate_rate:.4f}")
    errors = [r for r in summary.case_results if r.error]
    if errors:
        print(f"\n{len(errors)} case(s) raised an unexpected error:")
        for r in errors:
            print(f"  {r.case_id}: {r.error}")

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_sha": _git_commit_sha(),
        "embedding_model": embedding_provider.model_name,
        "embedding_version": embedding_provider.model_version,
        "retrieval_method": "dense",
        "similarity_threshold": settings.similarity_threshold,
        "dataset_version": dataset["metadata"]["version"],
        "dataset_total_questions": len(dataset["questions"]),
        "top_k": TOP_K,
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

    run_dir = DATA_DIR / "eval_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.json"
    results_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote results to {results_path}")


if __name__ == "__main__":
    main()
