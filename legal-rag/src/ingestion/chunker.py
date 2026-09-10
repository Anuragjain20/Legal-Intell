"""Legal-aware chunking.

Structure first: paragraphs are grouped by whatever heading the structure
detector found (or no heading at all, if none was present). Within a group,
paragraphs are packed into chunks up to a target size without splitting a
paragraph unless it alone is too large — in which case it falls back to
sentence splitting, and then to a raw size-based split as a last resort.
A modest overlap is added between chunks that were produced by splitting a
single oversized group, to preserve boundary context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from src.ingestion.models import Chunk, DocumentPage
from src.ingestion.structure_detector import DetectedParagraph, StructureDetector
from src.ingestion.section_parser import parse_section_structure

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class Chunker(Protocol):
    """Any strategy that splits extracted pages into indexable Chunk objects."""

    def chunk(
        self, *, document_id: str, pages: list[DocumentPage], category: str | None = None
    ) -> list[Chunk]: ...


@dataclass(frozen=True)
class ChunkerConfig:
    target_chunk_size: int = 1200
    max_chunk_size: int = 1600
    overlap_size: int = 150
    min_chunk_size: int = 40


@dataclass(frozen=True)
class _ChunkMeta:
    page_number: int
    end_page_number: int
    section: str | None
    heading: str | None


class LegalChunker:
    """Splits extracted pages into legal-aware chunks with preserved structure metadata."""

    def __init__(self, config: ChunkerConfig | None = None) -> None:
        self.config = config or ChunkerConfig()
        self._structure_detector = StructureDetector()

    def chunk(self, *, document_id: str, pages: list[DocumentPage], category: str | None = None) -> list[Chunk]:
        paragraphs = self._structure_detector.detect(pages)
        groups = self._group_by_heading(paragraphs)

        pieces: list[tuple[str, _ChunkMeta]] = []
        for group in groups:
            pieces.extend(self._chunk_group(group))

        chunks: list[Chunk] = []
        for text, meta in pieces:
            text = text.strip()
            if not any(ch.isalnum() for ch in text):
                continue

            # Parse hierarchical section structure
            parsed = parse_section_structure(meta.section)

            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:{len(chunks):04d}",
                    document_id=document_id,
                    page_number=meta.page_number,
                    end_page_number=meta.end_page_number,
                    section=meta.section,
                    heading=meta.heading,
                    text=text,
                    document_name=pages[0].filename if pages else None,
                    category=category,
                    section_number=parsed.section_number,
                    subsection=parsed.subsection,
                    clause=parsed.clause,
                    structure_path=parsed.structure_path if parsed.structure_path else None,
                )
            )
        return chunks

    @staticmethod
    def _group_by_heading(paragraphs: list[DetectedParagraph]) -> list[list[DetectedParagraph]]:
        """Group consecutive paragraphs that share the same structural context.

        Both heading and section must match: many legal sections carry no
        separate heading line (heading=None) but do have distinct section
        identifiers, and grouping on heading alone would silently merge
        unrelated sections together.
        """
        groups: list[list[DetectedParagraph]] = []
        for para in paragraphs:
            if (
                groups
                and groups[-1][-1].heading == para.heading
                and groups[-1][-1].section == para.section
            ):
                groups[-1].append(para)
            else:
                groups.append([para])
        return groups

    def _chunk_group(self, paragraphs: list[DetectedParagraph]) -> list[tuple[str, _ChunkMeta]]:
        cfg = self.config
        pieces: list[tuple[str, _ChunkMeta]] = []
        current: list[DetectedParagraph] = []

        def group_len(paras: list[DetectedParagraph]) -> int:
            if not paras:
                return 0
            return sum(len(p.text) for p in paras) + 2 * (len(paras) - 1)

        def flush() -> None:
            nonlocal current
            if current:
                text = "\n\n".join(p.text for p in current)
                pieces.append((text, self._merge_meta(current)))
            current = []

        for para in paragraphs:
            if len(para.text) > cfg.max_chunk_size:
                flush()
                meta = self._meta_from_paragraph(para)
                for sub_text in self._split_oversized(para.text):
                    pieces.append((sub_text, meta))
                continue

            prospective = current + [para]
            if current and group_len(prospective) > cfg.target_chunk_size:
                flush()
                prospective = [para]
            current = prospective

        flush()
        pieces = self._merge_short_pieces(pieces)
        return self._apply_overlap(pieces)

    def _merge_short_pieces(self, pieces: list[tuple[str, _ChunkMeta]]) -> list[tuple[str, _ChunkMeta]]:
        """Fold a too-short trailing fragment into the chunk before it, when there is one.

        A short piece with no predecessor (e.g. a whole section that's just one brief
        real paragraph, like a one-line notices clause) is left standalone rather than
        dropped — it's genuine, citable content, just naturally small.
        """
        min_size = self.config.min_chunk_size
        merged: list[tuple[str, _ChunkMeta]] = []
        for text, meta in pieces:
            if merged and len(text) < min_size:
                prev_text, prev_meta = merged[-1]
                combined_text = f"{prev_text}\n\n{text}"
                if len(combined_text) <= self.config.max_chunk_size:
                    merged[-1] = (
                        combined_text,
                        _ChunkMeta(prev_meta.page_number, meta.end_page_number, prev_meta.section, prev_meta.heading),
                    )
                    continue
            merged.append((text, meta))
        return merged

    @staticmethod
    def _meta_from_paragraph(para: DetectedParagraph) -> _ChunkMeta:
        return _ChunkMeta(para.page_number, para.end_page_number, para.section, para.heading)

    @staticmethod
    def _merge_meta(paragraphs: list[DetectedParagraph]) -> _ChunkMeta:
        first, last = paragraphs[0], paragraphs[-1]
        return _ChunkMeta(first.page_number, last.end_page_number, first.section, first.heading)

    def _split_oversized(self, text: str) -> list[str]:
        """Section -> paragraph already failed; fall back to sentence, then raw size."""
        cfg = self.config
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]

        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > cfg.max_chunk_size:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(self._split_by_size(sentence))
                continue

            candidate = f"{current} {sentence}".strip() if current else sentence
            if current and len(candidate) > cfg.target_chunk_size:
                pieces.append(current)
                current = sentence
            else:
                current = candidate

        if current:
            pieces.append(current)

        return pieces or self._split_by_size(text)

    def _split_by_size(self, text: str) -> list[str]:
        size = self.config.target_chunk_size
        pieces: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            pieces.append(text[start:end].strip())
            start = end
        return [p for p in pieces if p]

    def _apply_overlap(self, pieces: list[tuple[str, _ChunkMeta]]) -> list[tuple[str, _ChunkMeta]]:
        overlap_size = self.config.overlap_size
        if len(pieces) <= 1 or overlap_size <= 0:
            return pieces

        result = [pieces[0]]
        for i in range(1, len(pieces)):
            prev_text, _ = pieces[i - 1]
            text, meta = pieces[i]
            overlap = prev_text[-overlap_size:]
            space_idx = overlap.find(" ")
            if space_idx != -1:
                overlap = overlap[space_idx + 1 :]
            merged_text = f"{overlap} {text}".strip() if overlap else text
            result.append((merged_text, meta))
        return result
