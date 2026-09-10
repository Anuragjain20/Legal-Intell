"""Run a retrieval evaluation and write a reproducible result.

Loads data/evaluation_dataset.json, retrieves with the requested method,
computes Recall@1/3/5, Precision@5, and MRR overall and per question type,
and - for dense retrieval only - reports whether the retriever's own
similarity threshold would correctly withhold an answer on the unanswerable
cases. BM25's unbounded scores and hybrid's ~0.03-scale RRF scores aren't
comparable to the 0.35 cosine-similarity threshold, so the confidence-gate
rate is reported as null for those methods rather than computed against a
threshold that doesn't apply to their score scale.

Output is written to data/eval_runs/<UTC timestamp>/results.json together
with a manifest of everything needed to reproduce the run: retrieval
method, embedding model and version, dataset version, top_k, and the git
commit this was run against.

Usage:
    python scripts/run_evaluation.py --method dense
    python scripts/run_evaluation.py --method bm25
    python scripts/run_evaluation.py --method hybrid
    python scripts/run_evaluation.py --method hybrid_rerank
    python scripts/run_evaluation.py --method hybrid --chunking-method recursive

--chunking-method only selects which per-method Chroma directory to read
from (data/chroma for "legal", data/chroma_<method> otherwise) - this
script never chunks anything itself, it only evaluates retrieval over an
already-indexed collection (see scripts/ingest.py --chunking-method).

The retriever-building and result-formatting logic lives in
src/evaluation/runner.py, shared with the API's POST /evaluate endpoint
(src/api/main.py) so both have exactly one implementation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from src.evaluation.runner import (  # noqa: E402
    RETRIEVAL_METHODS,
    run_and_build_output,
    write_results,
)
from src.ingestion.chunker_factory import CHUNKING_METHODS  # noqa: E402

DATA_DIR = APP_DIR / "data"
TOP_K = 5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--method", choices=RETRIEVAL_METHODS, default="dense", help="Retrieval method to evaluate")
    parser.add_argument(
        "--chunking-method",
        choices=CHUNKING_METHODS,
        default="legal",
        help="Which chunking method's Chroma index to evaluate against (default: legal). "
        "Evaluation never chunks anything itself - this only selects the pre-indexed collection.",
    )
    args = parser.parse_args()

    run_result = run_and_build_output(
        app_dir=APP_DIR,
        retrieval_method=args.method,
        chunking_method=args.chunking_method,
        top_k=TOP_K,
    )
    summary = run_result.summary

    print(f"Retrieval evaluation ({args.method}, chunking={args.chunking_method})")
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
    if summary.unanswerable_confidence_gate_rate is None:
        print("Unanswerable confidence-gate rate: N/A (not comparable to a cosine-similarity threshold for this method)")
    else:
        print(f"Unanswerable confidence-gate rate: {summary.unanswerable_confidence_gate_rate:.4f}")
    errors = [r for r in summary.case_results if r.error]
    if errors:
        print(f"\n{len(errors)} case(s) raised an unexpected error:")
        for r in errors:
            print(f"  {r.case_id}: {r.error}")

    results_path = write_results(DATA_DIR, run_result.output)
    print(f"\nWrote results to {results_path}")


if __name__ == "__main__":
    main()
