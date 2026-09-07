"""Generation response models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextSource:
    """A structured source block passed to the model."""

    rank: int
    document_id: str
    chunk_id: str
    page_number: int
    section: str | None
    heading: str | None
    text: str
    score: float
    document_name: str | None = None


@dataclass(frozen=True)
class GenerationContext:
    """Structured prompt context assembled from retrieval results."""

    question: str
    sources: list[ContextSource]
    rendered_context: str


@dataclass(frozen=True)
class GenerationResult:
    """A grounded answer and the context that produced it."""

    answer: str
    model: str
    used_context: GenerationContext
    citations: list["Citation"] | None = None
    unresolved_source_ids: list[str] | None = None
    insufficient_evidence: bool = False
