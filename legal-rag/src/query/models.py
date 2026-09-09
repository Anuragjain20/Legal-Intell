"""Query analysis and representation models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QueryIntent(Enum):
    """Identified intent of the query."""

    DEFINITION = "definition"
    OBLIGATION = "obligation"
    RIGHT = "right"
    CONDITION = "condition"
    PROCEDURE = "procedure"
    SCOPE = "scope"
    TEMPORAL = "temporal"
    CROSS_REFERENCE = "cross_reference"
    GENERAL_INQUIRY = "general_inquiry"


@dataclass(frozen=True)
class LegalTermSignal:
    """Detected legal term or exact phrase in query."""

    term: str
    confidence: float
    is_quoted: bool = False
    potential_section: str | None = None


@dataclass(frozen=True)
class QuerySignal:
    """Semantic signal extracted from query for retrieval."""

    signal: str
    weight: float
    category: str


@dataclass(frozen=True)
class NormalizedQuery:
    """Query representation after analysis and normalization.

    Preserves the original query while adding retrieval-ready analysis.
    """

    original: str
    normalized: str
    intent: QueryIntent
    legal_terms: list[LegalTermSignal] = field(default_factory=list)
    retrieval_signals: list[QuerySignal] = field(default_factory=list)
    exact_matches: list[str] = field(default_factory=list)
    has_negation: bool = False
    has_temporal_constraint: bool = False
    query_length: int = 0
    processing_time_ms: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_length", len(self.original.split()))
