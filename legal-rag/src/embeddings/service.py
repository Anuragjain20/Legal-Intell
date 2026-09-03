"""Batch embedding service for legal chunks."""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.base import EmbeddedChunk, EmbeddingProvider
from src.embeddings.providers import EmptyTextError
from src.ingestion.models import Chunk


@dataclass
class EmbeddingService:
    """Convert chunks into vectors without coupling callers to a backend."""

    provider: EmbeddingProvider

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        if not chunks:
            return []

        texts = [chunk.text for chunk in chunks]
        vectors = self.provider.embed_documents(texts)

        if len(vectors) != len(chunks):
            raise ValueError("Provider returned a different number of vectors than chunks.")

        embedded_chunks: list[EmbeddedChunk] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._validate_dimension(vector)
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk=chunk,
                    embedding=list(vector),
                    embedding_model=self.provider.model_name,
                    embedding_version=self.provider.model_version,
                )
            )
        return embedded_chunks

    def embed_text(self, text: str) -> list[float]:
        return self.provider.embed_query(text)

    def embedding_dimension(self) -> int:
        return self.provider.embedding_dimension

    def _validate_dimension(self, vector: list[float]) -> None:
        expected = self.provider.embedding_dimension
        if len(vector) != expected:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected}, got {len(vector)}."
            )


__all__ = ["EmbeddingService", "EmbeddedChunk", "EmptyTextError"]

