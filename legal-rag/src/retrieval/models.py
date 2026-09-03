"""Retrieval result models."""

from __future__ import annotations

from dataclasses import dataclass

from src.vectorstore.base import VectorRecord


@dataclass(frozen=True)
class RetrievalResult:
    """A ranked retrieval result with preserved source metadata."""

    rank: int
    score: float
    record: VectorRecord

