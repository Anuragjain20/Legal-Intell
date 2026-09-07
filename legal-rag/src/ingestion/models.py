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
    category: str | None = None
    source_path: str | None = None


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

    Hierarchical metadata for nested sections:
    - For "2(d)": section_number="2", subsection="d", structure_path=["2", "d"]
    - For "2(d)(i)": section_number="2", subsection="d", clause="i", structure_path=["2", "d", "i"]
    """

    chunk_id: str
    document_id: str
    page_number: int
    end_page_number: int
    section: str | None
    heading: str | None
    text: str
    document_name: str | None = None
    category: str | None = None
    section_number: str | None = None
    subsection: str | None = None
    clause: str | None = None
    structure_path: list[str] | None = None
