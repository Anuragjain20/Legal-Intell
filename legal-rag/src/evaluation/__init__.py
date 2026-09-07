"""Retrieval evaluation: metrics, span matching, and the evaluation harness."""

from src.evaluation.harness import CaseResult, EvaluationSummary, evaluate_case, load_dataset, run_evaluation
from src.evaluation.matching import any_span_matches, normalize_text, span_matches, split_multi_span
from src.evaluation.metrics import (
    calculate_all_metrics,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_k,
    find_first_relevant_rank,
)

__all__ = [
    "CaseResult",
    "EvaluationSummary",
    "evaluate_case",
    "load_dataset",
    "run_evaluation",
    "span_matches",
    "any_span_matches",
    "split_multi_span",
    "normalize_text",
    "calculate_recall_at_k",
    "calculate_precision_at_k",
    "calculate_mrr",
    "calculate_ndcg_at_k",
    "find_first_relevant_rank",
    "calculate_all_metrics",
]
