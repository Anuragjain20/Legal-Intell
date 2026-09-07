"""Retrieval request/response models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.retrieval.exceptions import EmptyQueryError
from src.vectorstore.base import VectorRecord


@dataclass
class RetrievalRequest:
    """Structured retrieval request with filters and configuration."""

    query: str
    top_k: int = 5
    document_ids: list[str] | None = None
    document_types: list[str] | None = None
    date_range: tuple[datetime, datetime] | None = None

    def __post_init__(self) -> None:
        if not self.query or not self.query.strip():
            raise EmptyQueryError("Query must not be blank.")
        if self.date_range is not None:
            raise NotImplementedError("Date range filtering is not yet supported.")


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked retrieval result with preserved source metadata and scores."""

    rank: int
    score: float
    retrieval_method: str
    record: VectorRecord


@dataclass(frozen=True)
class RetrievalResponse:
    """Response envelope carrying retrieval metadata and results."""

    chunks: list[RetrievedChunk]
    embedding_model: str
    embedding_version: str
    retrieval_method: str
    total_searched: int


# Legacy alias for backward compatibility
RetrievalResult = RetrievedChunk

