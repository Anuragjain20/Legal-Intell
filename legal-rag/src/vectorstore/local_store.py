"""Persistent local vector store implementation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from src.vectorstore.base import SearchResult, VectorRecord
from src.vectorstore.exceptions import VectorDimensionMismatchError


@dataclass
class LocalVectorStore:
    """A lightweight persistent vector store for local development.

    Records are persisted to a JSON file so the index survives application restarts.
    Duplicate indexing is deterministic: records are upserted by ``chunk_id``.
    """

    storage_dir: Path
    dimension: int

    def __post_init__(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.storage_dir / "index.json"
        self._records_by_chunk_id: dict[str, VectorRecord] = {}
        self._load()

    def add(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._validate_record(record)
            self._records_by_chunk_id[record.chunk_id] = record
        self._save()

    def delete_document(self, document_id: str) -> int:
        chunk_ids_to_delete = [
            chunk_id for chunk_id, record in self._records_by_chunk_id.items() if record.document_id == document_id
        ]
        for chunk_id in chunk_ids_to_delete:
            del self._records_by_chunk_id[chunk_id]
        self._save()
        return len(chunk_ids_to_delete)

    def get_by_chunk_id(self, chunk_id: str) -> VectorRecord | None:
        return self._records_by_chunk_id.get(chunk_id)

    def list_document_ids(self) -> list[str]:
        return sorted({record.document_id for record in self._records_by_chunk_id.values()})

    def search(self, vector: list[float], top_k: int = 5) -> list[SearchResult]:
        # Retrieval is intentionally out of scope for this story.
        raise NotImplementedError("Vector search belongs to the retrieval story.")

    def _validate_record(self, record: VectorRecord) -> None:
        if len(record.vector) != self.dimension:
            raise VectorDimensionMismatchError(
                f"Vector dimension mismatch: expected {self.dimension}, got {len(record.vector)}."
            )

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        stored_dimension = raw.get("dimension", self.dimension)
        if stored_dimension != self.dimension:
            raise VectorDimensionMismatchError(
                f"Persisted index dimension {stored_dimension} does not match configured dimension {self.dimension}."
            )
        for item in raw.get("records", []):
            record = VectorRecord(**item)
            self._validate_record(record)
            self._records_by_chunk_id[record.chunk_id] = record

    def _save(self) -> None:
        payload = {
            "dimension": self.dimension,
            "records": [asdict(record) for record in self._records_by_chunk_id.values()],
        }
        self.index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


