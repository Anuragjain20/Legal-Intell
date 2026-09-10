"""Recursive-character-splitter-with-overlap chunking.

The standard RAG baseline: no legal-structure awareness at all. Pages are
concatenated into one string, recursively split on a cascade of separators
(paragraph breaks, then line breaks, then sentence breaks, then spaces),
backing off to the next separator only when a piece still exceeds
chunk_size, then a modest word-boundary overlap is applied between adjacent
pieces. This exists to be compared against LegalChunker, not to reimplement
it — structural metadata (section, heading, etc.) is deliberately left
unset since nothing in this chunker detects it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.ingestion.models import Chunk, DocumentPage

_DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ")


@dataclass(frozen=True)
class RecursiveChunkerConfig:
    chunk_size: int = 1200
    chunk_overlap: int = 150
    separators: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_SEPARATORS)


@dataclass(frozen=True)
class _PageSpan:
    page_number: int
    start: int
    end: int  # exclusive


class RecursiveCharacterChunker:
    """Splits extracted pages into fixed-size, overlapping chunks with no structure awareness."""

    def __init__(self, config: RecursiveChunkerConfig | None = None) -> None:
        self.config = config or RecursiveChunkerConfig()

    def chunk(
        self, *, document_id: str, pages: list[DocumentPage], category: str | None = None
    ) -> list[Chunk]:
        if not pages:
            return []

        text, page_spans = self._concatenate(pages)
        if not text.strip():
            return []

        pieces = self._split(text, self.config.chunk_size)
        pieces = self._apply_overlap(pieces)

        chunks: list[Chunk] = []
        for piece_text, start, end in pieces:
            stripped = piece_text.strip()
            if not any(ch.isalnum() for ch in stripped):
                continue
            page_number, end_page_number = self._pages_for_range(page_spans, start, end)
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:{len(chunks):04d}",
                    document_id=document_id,
                    page_number=page_number,
                    end_page_number=end_page_number,
                    section=None,
                    heading=None,
                    text=stripped,
                    document_name=pages[0].filename if pages else None,
                    category=category,
                )
            )
        return chunks

    @staticmethod
    def _concatenate(pages: list[DocumentPage]) -> tuple[str, list[_PageSpan]]:
        parts: list[str] = []
        spans: list[_PageSpan] = []
        offset = 0
        for index, page in enumerate(pages):
            if index > 0:
                parts.append("\n\n")
                offset += 2
            start = offset
            parts.append(page.text)
            offset += len(page.text)
            spans.append(_PageSpan(page_number=page.page_number, start=start, end=offset))
        return "".join(parts), spans

    @staticmethod
    def _pages_for_range(spans: list[_PageSpan], start: int, end: int) -> tuple[int, int]:
        overlapping = [s.page_number for s in spans if s.start < end and s.end > start]
        if not overlapping:
            # Range fell entirely within an inter-page separator; attribute to the
            # nearest preceding page, falling back to the first page.
            preceding = [s.page_number for s in spans if s.start <= start]
            page = preceding[-1] if preceding else spans[0].page_number
            return page, page
        return min(overlapping), max(overlapping)

    def _split(self, text: str, chunk_size: int) -> list[tuple[str, int, int]]:
        """Recursively split text into (piece, start_offset, end_offset) tuples covering it exactly."""
        return self._pack_by_separator(text, 0, len(text), chunk_size, list(self.config.separators))

    def _pack_by_separator(
        self, text: str, base: int, length: int, chunk_size: int, separators: list[str]
    ) -> list[tuple[str, int, int]]:
        segment = text[base : base + length]
        if len(segment) <= chunk_size:
            return [(segment, base, base + length)] if segment else []

        if not separators:
            return self._split_by_raw_size(text, base, length, chunk_size)

        sep, rest_separators = separators[0], separators[1:]
        raw_parts = segment.split(sep)

        pieces: list[tuple[str, int, int]] = []
        current_start = base
        cursor = base
        current_len = 0
        for i, part in enumerate(raw_parts):
            part_with_sep = part if i == len(raw_parts) - 1 else part + sep
            part_len = len(part_with_sep)

            if current_len and current_len + part_len > chunk_size:
                pieces.append((text[current_start:cursor], current_start, cursor))
                current_start = cursor
                current_len = 0

            if part_len > chunk_size:
                if current_len:
                    pieces.append((text[current_start:cursor], current_start, cursor))
                pieces.extend(
                    self._pack_by_separator(text, cursor, part_len, chunk_size, rest_separators)
                )
                cursor += part_len
                current_start = cursor
                current_len = 0
                continue

            cursor += part_len
            current_len += part_len

        if current_len:
            pieces.append((text[current_start:cursor], current_start, cursor))

        return [(t, s, e) for t, s, e in pieces if t.strip()]

    @staticmethod
    def _split_by_raw_size(text: str, base: int, length: int, chunk_size: int) -> list[tuple[str, int, int]]:
        pieces: list[tuple[str, int, int]] = []
        start = base
        end_bound = base + length
        while start < end_bound:
            end = min(start + chunk_size, end_bound)
            pieces.append((text[start:end], start, end))
            start = end
        return pieces

    def _apply_overlap(self, pieces: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
        overlap_size = self.config.chunk_overlap
        if len(pieces) <= 1 or overlap_size <= 0:
            return pieces

        result = [pieces[0]]
        for i in range(1, len(pieces)):
            prev_text, _, _ = pieces[i - 1]
            text, start, end = pieces[i]
            overlap = prev_text[-overlap_size:]
            space_idx = overlap.find(" ")
            if space_idx != -1:
                overlap = overlap[space_idx + 1 :]
            merged_text = f"{overlap} {text}".strip() if overlap else text
            result.append((merged_text, start, end))
        return result
