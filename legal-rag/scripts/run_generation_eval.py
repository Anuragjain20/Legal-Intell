"""Run the generation-faithfulness evaluation and write a reproducible result.

Unlike scripts/run_evaluation.py (retrieval only), this runs the full
pipeline end to end - hybrid retrieval, then a real DeepSeek call per
question - so it requires a funded DEEPSEEK_API_KEY. It measures, without
an LLM judge:
  - groundedness: did the model produce a resolved citation rather than
    declining or citing nothing?
  - citation faithfulness: does at least one cited source actually contain
    the dataset's expected_answer_span (same verbatim-span ground truth as
    the retrieval harness)?
  - unresolved-citation rate: how often the model referenced a source that
    didn't exist in its context (a direct hallucination signal).
  - unanswerable refusal rate: on the 5 out-of-corpus questions, did the
    pipeline (retrieval gate or the LLM's own grounding instruction)
    decline to answer?

Output is written to data/eval_runs/<UTC timestamp>/generation_results.json
with the same manifest style as the retrieval evaluations.

Usage:
    python scripts/run_generation_eval.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from src.evaluation.generation_harness import load_dataset, run_generation_evaluation  # noqa: E402
from src.services import build_services  # noqa: E402

DATA_DIR = APP_DIR / "data"
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
    services = build_services(APP_DIR)

    if not services.settings.deepseek_api_key:
        print("DEEPSEEK_API_KEY is not set - the generation eval makes a real LLM call per")
        print("question and cannot run without it. Set it in .env and re-run.")
        return

    dataset = load_dataset(DATASET_PATH)
    summary = run_generation_evaluation(services.retriever, services.generation_service, dataset, top_k=TOP_K)

    print("Generation evaluation (faithfulness, no LLM judge)")
    print("=" * 60)
    print(f"Total cases: {summary.total_cases}  (in-corpus: {summary.in_corpus_cases}, unanswerable: {summary.unanswerable_cases})")
    print()
    print(f"Groundedness rate:            {summary.groundedness_rate:.4f}")
    print(f"Citation faithfulness rate:   {summary.citation_faithfulness_rate:.4f}")
    print(f"Unresolved-citation rate:     {summary.unresolved_citation_rate:.4f}")
    print(f"Unanswerable refusal rate:    {summary.unanswerable_refusal_rate:.4f}")

    errors = [r for r in summary.case_results if r.error]
    if errors:
        print(f"\n{len(errors)} case(s) raised an unexpected error:")
        for r in errors:
            print(f"  {r.case_id}: {r.error}")

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_sha": _git_commit_sha(),
        "embedding_model": services.settings.embedding_model,
        "retrieval_method": "hybrid",
        "llm_model": services.settings.deepseek_model,
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
            "groundedness_rate": summary.groundedness_rate,
            "citation_faithfulness_rate": summary.citation_faithfulness_rate,
            "unresolved_citation_rate": summary.unresolved_citation_rate,
            "unanswerable_refusal_rate": summary.unanswerable_refusal_rate,
        },
        "case_results": [
            {
                "case_id": r.case_id,
                "question_type": r.question_type,
                "is_out_of_corpus": r.is_out_of_corpus,
                "refused": r.refused,
                "insufficient_evidence": r.insufficient_evidence,
                "error": r.error,
                "citations_resolved": r.citations_resolved,
                "citations_unresolved": r.citations_unresolved,
                "cited_span_faithful": r.cited_span_faithful,
            }
            for r in summary.case_results
        ],
    }

    run_dir = DATA_DIR / "eval_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "generation_results.json"
    results_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote results to {results_path}")


if __name__ == "__main__":
    main()
