"""Embedding abstractions for chunk-to-vector conversion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.ingestion.models import Chunk


@dataclass(frozen=True)
class EmbeddedChunk:
    """A chunk paired with the vector and model metadata used to create it."""

    chunk: Chunk
    embedding: list[float]
    embedding_model: str
    embedding_version: str


class EmbeddingProvider(Protocol):
    """Interface for any embedding backend."""

    model_name: str
    model_version: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query or document string."""

    @property
    def embedding_dimension(self) -> int:
        """Return the output dimensionality for this provider."""

