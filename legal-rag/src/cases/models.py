"""Data model for a case - a named collection of already-ingested documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Case:
    case_id: str
    name: str
    description: str | None
    created_at: datetime
    document_ids: list[str] = field(default_factory=list)
