"""Data models for retrieval evaluation.

Defines the evaluation dataset structure and metrics calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QueryCategory(Enum):
    """Query types in legal retrieval."""

    DEFINITION = "definition"  # What does X mean?
    SECTION_SPECIFIC = "section_specific"  # What's in section X?
    OBLIGATION = "obligation"  # What are the obligations?
    CONDITION = "condition"  # What triggers/requires X?
    PROCEDURE = "procedure"  # How do we do X?
    CROSS_REFERENCE = "cross_reference"  # How does X relate to Y?
    TEMPORAL = "temporal"  # When does X happen?
    IDENTIFIER = "identifier"  # Find specific section/error code
    NEGATION = "negation"  # What are NOT the obligations?


class QueryDifficulty(Enum):
    """Query difficulty for stratified analysis."""

    EASY = "easy"  # Term appears literally in text
    MEDIUM = "medium"  # Requires some inference
    HARD = "hard"  # Requires semantic reasoning


@dataclass(frozen=True)
class EvaluationQuery:
    """A query with ground truth for evaluation."""

    query_id: str
    question: str
    category: QueryCategory
    difficulty: QueryDifficulty

    # Ground truth
    expected_document_id: str
    expected_document_name: str
    expected_section: str  # e.g., "2(d)(i)"
    expected_chunk_ids: list[str]  # Relevant chunk IDs in order of relevance

    # Metadata
    keywords: list[str]  # Key terms in query
    has_exact_identifier: bool  # Query has exact section/code reference
    has_negation: bool
    has_temporal_constraint: bool


@dataclass(frozen=True)
class RetrievedChunkForEval:
    """A chunk returned by retriever during evaluation."""

    rank: int
    chunk_id: str
    document_id: str
    score: float
    is_relevant: bool = False  # Set during evaluation


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    """Result of evaluating a single query."""

    query_id: str
    query: str
    category: QueryCategory
    difficulty: QueryDifficulty
    retriever_name: str
    top_k: int

    # Retrieved chunks (in rank order)
    retrieved_chunks: list[RetrievedChunkForEval]

    # Metrics
    recall_at_k: float  # % of relevant chunks found in top-k
    precision_at_k: float  # % of retrieved chunks that were relevant
    mrr: float  # Reciprocal rank of first relevant chunk
    ndcg_at_k: float  # Normalized Discounted Cumulative Gain
    latency_ms: float

    # Diagnostics
    found_relevant: bool  # Was any relevant chunk found?
    first_relevant_rank: int | None  # What rank was first relevant chunk?
    all_relevant_chunk_ids: list[str]  # Expected relevant chunks
    matched_chunk_ids: list[str]  # Which ones we found


@dataclass(frozen=True)
class RetrievalExperimentMetrics:
    """Aggregate metrics across query set."""

    retriever_name: str
    num_queries: int

    # Aggregate metrics
    avg_recall_at_5: float
    avg_recall_at_10: float
    avg_recall_at_20: float

    avg_precision_at_5: float
    avg_precision_at_10: float
    avg_precision_at_20: float

    avg_mrr: float
    avg_ndcg_at_5: float
    avg_ndcg_at_10: float
    avg_ndcg_at_20: float

    avg_latency_ms: float

    # Stratified by category
    metrics_by_category: dict[str, RetrievalExperimentMetrics | None] = None

    # Stratified by difficulty
    metrics_by_difficulty: dict[str, RetrievalExperimentMetrics | None] = None

    # Failure cases
    num_failures_top_5: int = 0  # Queries where relevant not in top-5
    num_failures_top_10: int = 0
    num_failures_top_20: int = 0

    failure_categories: dict[str, int] | None = None  # Which categories had failures?


@dataclass(frozen=True)
class ExperimentMatrixRow:
    """One row in the experiment matrix."""

    retriever: str  # Dense, BM25, Hybrid, Hybrid+Context, Hybrid+Reranker
    recall_at_5: float
    recall_at_10: float
    recall_at_20: float
    precision_at_5: float
    precision_at_10: float
    precision_at_20: float
    mrr: float
    ndcg_at_5: float
    ndcg_at_10: float
    ndcg_at_20: float
    latency_ms: float
    num_queries: int


@dataclass(frozen=True)
class ExperimentMatrix:
    """Full experiment matrix across retrieval strategies."""

    rows: list[ExperimentMatrixRow]

    def to_markdown_table(self) -> str:
        """Render as markdown table."""
        lines = [
            "| Retriever | Recall@5 | Recall@10 | Recall@20 | Precision@5 | Precision@10 | Precision@20 | MRR | nDCG@5 | nDCG@10 | nDCG@20 | Latency |",
            "|-----------|----------|-----------|-----------|-------------|-------------|-------------|-----|--------|---------|---------|---------|",
        ]

        for row in self.rows:
            line = (
                f"| {row.retriever} "
                f"| {row.recall_at_5:.1%} "
                f"| {row.recall_at_10:.1%} "
                f"| {row.recall_at_20:.1%} "
                f"| {row.precision_at_5:.1%} "
                f"| {row.precision_at_10:.1%} "
                f"| {row.precision_at_20:.1%} "
                f"| {row.mrr:.3f} "
                f"| {row.ndcg_at_5:.3f} "
                f"| {row.ndcg_at_10:.3f} "
                f"| {row.ndcg_at_20:.3f} "
                f"| {row.latency_ms:.1f}ms |"
            )
            lines.append(line)

        return "\n".join(lines)

    def csv_header(self) -> str:
        """CSV header for export."""
        return "Retriever,Recall@5,Recall@10,Recall@20,Precision@5,Precision@10,Precision@20,MRR,nDCG@5,nDCG@10,nDCG@20,Latency_ms"

    def to_csv(self) -> str:
        """Export as CSV."""
        lines = [self.csv_header()]
        for row in self.rows:
            line = (
                f"{row.retriever},"
                f"{row.recall_at_5:.4f},"
                f"{row.recall_at_10:.4f},"
                f"{row.recall_at_20:.4f},"
                f"{row.precision_at_5:.4f},"
                f"{row.precision_at_10:.4f},"
                f"{row.precision_at_20:.4f},"
                f"{row.mrr:.6f},"
                f"{row.ndcg_at_5:.6f},"
                f"{row.ndcg_at_10:.6f},"
                f"{row.ndcg_at_20:.6f},"
                f"{row.latency_ms:.2f}"
            )
            lines.append(line)
        return "\n".join(lines)
