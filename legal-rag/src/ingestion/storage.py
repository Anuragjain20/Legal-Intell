"""Local storage for uploaded documents."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.ingestion.models import DocumentMetadata


def normalize_category(category: str | None) -> str:
    """Return a safe, readable folder name for a document category."""
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", (category or "").strip()).strip(" .")
    return cleaned or "uncategorized"


class DocumentStorage:
    """Persist validated documents to local disk."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes, document_id: str, category: str | None) -> Path:
        safe_name = Path(filename).name
        if not safe_name:
            raise ValueError("Filename must contain a file name.")
        category_dir = self.storage_dir / normalize_category(category)
        category_dir.mkdir(parents=True, exist_ok=True)
        destination = category_dir / f"{document_id}-{safe_name}"
        destination.write_bytes(content)
        return destination


class DocumentRegistry:
    """Small JSON-backed document catalog for the local MVP."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, metadata: DocumentMetadata) -> None:
        documents = self._load()
        entry = asdict(metadata)
        entry["upload_timestamp"] = metadata.upload_timestamp.isoformat()
        documents[metadata.document_id] = entry
        self.registry_path.write_text(
            json.dumps({"documents": list(documents.values())}, indent=2), encoding="utf-8"
        )

    def list_all(self) -> list[DocumentMetadata]:
        entries = self._load()
        return [
            DocumentMetadata(**{**entry, "upload_timestamp": datetime.fromisoformat(entry["upload_timestamp"])})
            for entry in entries.values()
        ]

    def _load(self) -> dict[str, dict]:
        if not self.registry_path.exists():
            return {}
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        return {entry["document_id"]: entry for entry in payload.get("documents", [])}
