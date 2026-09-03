"""Build structured context from retrieval results."""

from __future__ import annotations

from dataclasses import dataclass

from src.generation.models import ContextSource, GenerationContext
from src.retrieval.models import RetrievalResult


@dataclass
class ContextBuilder:
    """Convert ranked retrieval results into source-separated context blocks."""

    max_sources: int = 5
    max_context_chars: int = 6000

    def build(self, question: str, results: list[RetrievalResult]) -> GenerationContext:
        selected = results[: self.max_sources]
        sources: list[ContextSource] = []
        rendered_blocks: list[str] = []
        remaining = self.max_context_chars

        for result in selected:
            source = ContextSource(
                rank=result.rank,
                document_id=result.record.document_id,
                chunk_id=result.record.chunk_id,
                page_number=result.record.page_number,
                section=result.record.section,
                heading=result.record.heading,
                text=result.record.text,
                score=result.score,
            )
            block = self._render_source(source)
            if len(block) > remaining:
                if not sources:
                    rendered_blocks.append(self._truncate_block(block, remaining))
                    sources.append(source)
                break
            sources.append(source)
            rendered_blocks.append(block)
            remaining -= len(block)

        rendered_context = "\n\n".join(rendered_blocks)
        return GenerationContext(question=question, sources=sources, rendered_context=rendered_context)

    def _render_source(self, source: ContextSource) -> str:
        section_line = f"Section: {source.section}" if source.section else "Section: N/A"
        heading_line = f"Heading: {source.heading}" if source.heading else "Heading: N/A"
        return (
            f"SOURCE {source.rank}\n"
            f"Document: {source.document_id}\n"
            f"Chunk: {source.chunk_id}\n"
            f"Page: {source.page_number}\n"
            f"{section_line}\n"
            f"{heading_line}\n"
            f"Score: {source.score:.4f}\n\n"
            f"{source.text}"
        )

    def _truncate_block(self, block: str, limit: int) -> str:
        if limit <= 0:
            return ""
        if len(block) <= limit:
            return block
        return block[: max(0, limit - 3)] + "..."
