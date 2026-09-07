"""Retrieval evaluation framework.

Provides evaluation dataset, metrics calculation, and experiment matrix generation.
"""

from src.evaluation.evaluator import EvaluationCase, EvaluationResults, RetrievalEvaluator, RetrievalMetric
from src.evaluation.metrics import (
    calculate_all_metrics,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_k,
    find_first_relevant_rank,
)
from src.evaluation.models import (
    EvaluationQuery,
    ExperimentMatrix,
    ExperimentMatrixRow,
    QueryCategory,
    QueryDifficulty,
    RetrievalEvaluationResult,
    RetrievalExperimentMetrics,
    RetrievedChunkForEval,
)

__all__ = [
    "EvaluationCase",
    "EvaluationResults",
    "RetrievalEvaluator",
    "RetrievalMetric",
    "calculate_recall_at_k",
    "calculate_precision_at_k",
    "calculate_mrr",
    "calculate_ndcg_at_k",
    "find_first_relevant_rank",
    "calculate_all_metrics",
    "EvaluationQuery",
    "QueryCategory",
    "QueryDifficulty",
    "RetrievedChunkForEval",
    "RetrievalEvaluationResult",
    "RetrievalExperimentMetrics",
    "ExperimentMatrixRow",
    "ExperimentMatrix",
]
