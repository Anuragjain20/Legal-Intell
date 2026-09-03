"""Indexing service for embedding records."""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.base import EmbeddedChunk
from src.vectorstore.base import VectorRecord, VectorStore


@dataclass
class VectorIndexService:
    """Transform embedded chunks into vector-store records."""

    store: VectorStore

    def index_embeddings(self, embedded_chunks: list[EmbeddedChunk]) -> None:
        if not embedded_chunks:
            return

        records = [
            VectorRecord(
                chunk_id=item.chunk.chunk_id,
                document_id=item.chunk.document_id,
                vector=list(item.embedding),
                text=item.chunk.text,
                page_number=item.chunk.page_number,
                section=item.chunk.section,
                heading=item.chunk.heading,
                embedding_model=item.embedding_model,
                embedding_version=item.embedding_version,
            )
            for item in embedded_chunks
        ]
        self.store.add(records)

    def delete_document(self, document_id: str) -> int:
        return self.store.delete_document(document_id)


