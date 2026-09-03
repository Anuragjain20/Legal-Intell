"""Vector store abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VectorRecord:
    """A stored vector and its source metadata."""

    chunk_id: str
    document_id: str
    vector: list[float]
    text: str
    page_number: int
    section: str | None
    heading: str | None
    embedding_model: str
    embedding_version: str


@dataclass(frozen=True)
class SearchResult:
    """Placeholder result type for future retrieval integration."""

    record: VectorRecord
    score: float


class VectorStore(Protocol):
    """Storage abstraction for indexed embeddings."""

    @property
    def dimension(self) -> int:
        ...

    def add(self, records: list[VectorRecord]) -> None:
        ...

    def delete_document(self, document_id: str) -> int:
        ...

    def get_by_chunk_id(self, chunk_id: str) -> VectorRecord | None:
        ...

    def list_document_ids(self) -> list[str]:
        ...

    def search(self, vector: list[float], top_k: int = 5) -> list[SearchResult]:
        ...

