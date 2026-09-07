"""Citation mapping and source attribution."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.generation.models import GenerationContext
from src.retrieval.models import RetrievalResult


SOURCE_REF_PATTERN = re.compile(r"\[SOURCE_(\d+)\]")


@dataclass(frozen=True)
class Citation:
    """A trusted citation derived from retrieved source metadata."""

    citation_id: int
    source_id: str
    document_id: str
    document_name: str
    page_number: int
    chunk_id: str
    section: str | None
    heading: str | None


@dataclass(frozen=True)
class CitationMapping:
    """Result of resolving model source references against trusted metadata."""

    citations: list[Citation]
    unresolved_source_ids: list[str]
    referenced_source_ids: list[str]


@dataclass
class CitationMapper:
    """Resolve model references to trusted citations from the generation context."""

    def map(self, answer: str, context: GenerationContext) -> CitationMapping:
        source_lookup = {f"SOURCE_{source.rank}": source for source in context.sources}
        referenced_source_ids = self._extract_source_ids(answer)
        unresolved_source_ids: list[str] = []
        citations: list[Citation] = []
        seen_source_ids: set[str] = set()

        for source_id in referenced_source_ids:
            if source_id in seen_source_ids:
                continue
            source = source_lookup.get(source_id)
            if source is None:
                unresolved_source_ids.append(source_id)
                continue
            citations.append(
                Citation(
                    citation_id=source.rank,
                    source_id=source_id,
                    document_id=source.document_id,
                    document_name=getattr(source, "document_name", None) or source.document_id,
                    page_number=source.page_number,
                    chunk_id=source.chunk_id,
                    section=source.section,
                    heading=source.heading,
                )
            )
            seen_source_ids.add(source_id)

        return CitationMapping(
            citations=citations,
            unresolved_source_ids=unresolved_source_ids,
            referenced_source_ids=referenced_source_ids,
        )

    def _extract_source_ids(self, answer: str) -> list[str]:
        return [f"SOURCE_{match}" for match in SOURCE_REF_PATTERN.findall(answer)]
