"""Persistent Chroma implementation of the local vector-store interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.vectorstore.base import SearchResult, VectorRecord
from src.vectorstore.exceptions import VectorDimensionMismatchError


@dataclass
class ChromaVectorStore:
    """Store vectors locally in a persistent Chroma collection."""

    storage_dir: Path
    dimension: int
    collection_name: str = "legal_rag"

    def __post_init__(self) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise ImportError("ChromaVectorStore requires 'chromadb'.") from exc

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.storage_dir))
        self._collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        for record in records:
            self._validate_vector(record.vector)

        self._collection.upsert(
            ids=[record.chunk_id for record in records],
            embeddings=[record.vector for record in records],
            documents=[record.text for record in records],
            metadatas=[self._metadata(record) for record in records],
        )

    def delete_document(self, document_id: str) -> int:
        matches = self._collection.get(where={"document_id": document_id}, include=[])
        ids = matches.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def get_by_chunk_id(self, chunk_id: str) -> VectorRecord | None:
        result = self._collection.get(ids=[chunk_id], include=["documents", "metadatas", "embeddings"])
        if not result.get("ids"):
            return None
        return self._record(result, 0)

    def list_document_ids(self) -> list[str]:
        result = self._collection.get(include=["metadatas"])
        return sorted({metadata["document_id"] for metadata in result.get("metadatas", [])})

    def search(self, vector: list[float], top_k: int = 5) -> list[SearchResult]:
        self._validate_vector(vector)
        if top_k <= 0 or self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[vector],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances", "embeddings"],
        )
        return [
            SearchResult(record=self._record(result, index, nested=True), score=1 - distance)
            for index, distance in enumerate(result["distances"][0])
        ]

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self.dimension:
            raise VectorDimensionMismatchError(
                f"Vector dimension mismatch: expected {self.dimension}, got {len(vector)}."
            )

    @staticmethod
    def _metadata(record: VectorRecord) -> dict[str, Any]:
        return {
            "document_id": record.document_id,
            "page_number": record.page_number,
            "section": record.section or "",
            "heading": record.heading or "",
            "embedding_model": record.embedding_model,
            "embedding_version": record.embedding_version,
            "document_name": record.document_name or "",
            "category": record.category or "",
        }

    @staticmethod
    def _record(result: dict[str, Any], index: int, nested: bool = False) -> VectorRecord:
        values = lambda key: result[key][0][index] if nested else result[key][index]
        metadata = values("metadatas")
        return VectorRecord(
            chunk_id=values("ids"),
            document_id=metadata["document_id"],
            vector=list(values("embeddings")),
            text=values("documents"),
            page_number=int(metadata["page_number"]),
            section=metadata["section"] or None,
            heading=metadata["heading"] or None,
            embedding_model=metadata["embedding_model"],
            embedding_version=metadata["embedding_version"],
            document_name=metadata["document_name"] or None,
            category=metadata.get("category") or None,
        )
