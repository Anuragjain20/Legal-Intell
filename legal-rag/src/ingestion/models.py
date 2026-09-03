"""Data models for document uploads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    filename: str
    file_type: str
    file_size: int
    upload_timestamp: datetime
    storage_path: str


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str
    extraction_status: str
    document_id: str
    filename: str
    storage_path: str


@dataclass(frozen=True)
class Chunk:
    """A retrievable unit of legal text with whatever structural context was detected.

    ``section`` and ``heading`` are ``None`` when no structural signal was found for
    this text — they are never invented. ``end_page_number`` differs from
    ``page_number`` only when the chunk's text spans a page boundary.
    """

    chunk_id: str
    document_id: str
    page_number: int
    end_page_number: int
    section: str | None
    heading: str | None
    text: str
