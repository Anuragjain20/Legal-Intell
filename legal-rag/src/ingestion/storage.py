"""Local storage for uploaded documents."""

from __future__ import annotations

from pathlib import Path


class DocumentStorage:
    """Persist validated documents to local disk."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> Path:
        destination = self.storage_dir / filename
        destination.write_bytes(content)
        return destination
