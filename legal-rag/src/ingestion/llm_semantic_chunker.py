"""LLM-driven semantic chunking.

An LLM is asked to propose where a window of pages should be cut into
topically/clausally coherent chunks. The model never sees, and never
returns, the chunk text itself — it returns short anchor strings (the
first few words of each proposed chunk). The chunker locates each anchor
in the original page text with a forward-only substring search and always
slices the original string between anchors. This keeps a model that
paraphrases, "corrects", or normalizes text from ever silently altering
what gets indexed as this document's content — the boundary decision is
the model's; the text is always the source's.

Pages are batched into windows (default 3 pages/call) rather than one call
per paragraph, since a call-per-paragraph policy would mean thousands of
LLM round trips across a real corpus. Boundary decisions are cached to
disk per (document_id, window_index, model_name) so a failure partway
through a large ingest doesn't force re-paying for already-processed
windows on retry.

A call that fails, times out, or returns unparseable JSON raises
LLMChunkingFailure immediately. An individual anchor that cannot be located
even after normalization is skipped (its proposed boundary is dropped, the
window's other boundaries are kept) rather than failing the whole
document - but skips are bounded: if more than MAX_SKIPPED_ANCHOR_RATE of
all anchors across a document are skipped, the document raises
LLMChunkingFailure, since a chunker discarding most of its own boundaries
is silently degrading into something close to no-boundary chunking. This
is a bounded degradation of *how many* LLM-proposed boundaries survive,
never a substitution of a different chunking strategy - the chunker never
falls back to size- or structure-based splitting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from src.ingestion.exceptions import LLMChunkingFailure
from src.ingestion.models import Chunk, DocumentPage

_ANCHOR_WORDS = 7
MAX_SKIPPED_ANCHOR_RATE = 0.05

_SMART_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}
_DASHES = {"–": "-", "—": "-"}
_REPLACEMENT_CHARS = {"�": "'"}  # PDF-extraction mojibake for an unrepresentable glyph - almost always an apostrophe


class LLMClient(Protocol):
    model_name: str

    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class LLMChunkerConfig:
    window_pages: int = 3
    cache_dir: Path | None = None


class LLMSemanticChunker:
    """Splits extracted pages into chunks at LLM-proposed semantic boundaries."""

    def __init__(self, llm_client: LLMClient, config: LLMChunkerConfig | None = None) -> None:
        self.llm_client = llm_client
        self.config = config or LLMChunkerConfig()

    def chunk(
        self, *, document_id: str, pages: list[DocumentPage], category: str | None = None
    ) -> list[Chunk]:
        if not pages:
            return []

        windows = self._window_pages(pages)
        chunks: list[Chunk] = []
        total_anchors = 0
        total_skipped = 0
        for window_index, window in enumerate(windows):
            window_text = self._join_window(window)
            if not window_text.strip():
                continue
            anchors = self._get_boundaries(document_id, window_index, window_text)
            pieces, skipped = self._slice_by_anchors(window_text, anchors)
            self._write_cache(document_id, window_index, anchors)
            total_anchors += len(anchors)
            total_skipped += skipped
            for piece_text in pieces:
                stripped = piece_text.strip()
                if not stripped or not any(ch.isalnum() for ch in stripped):
                    continue
                page_number = window[0].page_number
                end_page_number = window[-1].page_number
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

        if total_anchors > 0:
            skip_rate = total_skipped / total_anchors
            if skip_rate > MAX_SKIPPED_ANCHOR_RATE:
                raise LLMChunkingFailure(
                    f"Document {document_id!r}: {total_skipped}/{total_anchors} LLM-proposed anchors "
                    f"({skip_rate:.1%}) could not be located even after normalization - exceeds the "
                    f"{MAX_SKIPPED_ANCHOR_RATE:.0%} skip budget. Ingestion aborted rather than silently "
                    "chunking on a mostly-fallback boundary set."
                )

        return chunks

    def _window_pages(self, pages: list[DocumentPage]) -> list[list[DocumentPage]]:
        size = self.config.window_pages
        return [pages[i : i + size] for i in range(0, len(pages), size)]

    @staticmethod
    def _join_window(window: list[DocumentPage]) -> str:
        return "\n\n".join(p.text for p in window)

    def _get_boundaries(self, document_id: str, window_index: int, window_text: str) -> list[str]:
        """Return this window's anchor proposals, from cache if present.

        The cache holds raw LLM output (a JSON-parseable list of anchor
        strings) - it is valid to reuse regardless of whether every anchor
        turns out to be locatable, since matching against source text is
        deterministic and re-run fresh by _slice_by_anchors on every call.
        This means a retry after a skip-budget failure (see chunk()) never
        re-calls the LLM for windows it already has anchors for.
        """
        cached = self._read_cache(document_id, window_index)
        if cached is not None:
            return cached

        prompt = self._build_prompt(window_text)
        try:
            raw_response = self.llm_client.generate(prompt)
        except Exception as exc:
            raise LLMChunkingFailure(
                f"LLM call failed for document {document_id!r} window {window_index}: {exc}"
            ) from exc

        return self._parse_anchors(raw_response, document_id, window_index)

    @staticmethod
    def _build_prompt(window_text: str) -> str:
        return (
            "You are splitting a legal document excerpt into topically or clausally "
            "coherent chunks for retrieval. Do NOT reproduce or rewrite any text. "
            "Instead, return a JSON array of short anchor strings, one per chunk "
            f"boundary, each being the first {_ANCHOR_WORDS} words verbatim of where "
            "that chunk should start (including the very first chunk). Anchors must "
            "appear in the text in the same order as in the original, and must be "
            "copied exactly (same spelling, punctuation, and spacing) from the text "
            "below.\n\n"
            "Return ONLY a JSON array of strings, nothing else.\n\n"
            f"TEXT:\n{window_text}"
        )

    @staticmethod
    def _parse_anchors(raw_response: str, document_id: str, window_index: int) -> list[str]:
        match = re.search(r"\[.*\]", raw_response, re.DOTALL)
        if not match:
            raise LLMChunkingFailure(
                f"LLM returned no JSON array for document {document_id!r} window {window_index}: "
                f"{raw_response[:200]!r}"
            )
        try:
            anchors = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMChunkingFailure(
                f"LLM returned unparseable JSON for document {document_id!r} window {window_index}: {exc}"
            ) from exc

        if not isinstance(anchors, list) or not all(isinstance(a, str) and a.strip() for a in anchors):
            raise LLMChunkingFailure(
                f"LLM returned a non-list-of-strings for document {document_id!r} window {window_index}."
            )
        return anchors

    @staticmethod
    def _normalize_with_offsets(text: str) -> tuple[str, list[int]]:
        """Fold cosmetic PDF-extraction noise (smart quotes, dashes, mojibake,
        whitespace runs) the same way src/evaluation/matching.normalize_text
        does for span-matching, but also return offsets[i] = the original
        `text` index that normalized character i came from - so a match found
        in normalized space can be mapped back to an exact original offset.
        Dropped characters (e.g. a mojibake replacement char) contribute no
        normalized output but do not shift subsequent offsets.
        """
        out_chars: list[str] = []
        offsets: list[int] = []
        for i, ch in enumerate(text):
            mapped = _SMART_QUOTES.get(ch, _DASHES.get(ch, _REPLACEMENT_CHARS.get(ch, ch)))
            for out_ch in mapped:
                out_chars.append(out_ch)
                offsets.append(i)
        normalized = "".join(out_chars)
        # Collapse whitespace runs to a single space, keeping the offset of
        # the run's first original character. Deliberately does NOT try to
        # remove single mid-word spaces (a rarer font-kerning artifact,
        # e.g. "c ertain" for "certain") - collapsing any lowercase-lowercase
        # space would just as readily merge two distinct words ("cat sat"
        # -> "catsat"), turning a narrow fix into a source of false matches.
        # A mid-word-kerning anchor instead falls to the bounded skip in
        # _slice_by_anchors/chunk (see MAX_SKIPPED_ANCHOR_RATE).
        collapsed_chars: list[str] = []
        collapsed_offsets: list[int] = []
        prev_was_space = False
        for ch, off in zip(normalized, offsets):
            is_space = ch.isspace()
            if is_space and prev_was_space:
                continue
            collapsed_chars.append(" " if is_space else ch)
            collapsed_offsets.append(off)
            prev_was_space = is_space
        return "".join(collapsed_chars), collapsed_offsets

    @classmethod
    def _find_anchor(cls, window_text: str, norm_text: str, norm_offsets: list[int], anchor: str, search_from: int) -> int:
        """Locate `anchor` at or after original-text offset `search_from`,
        by normalizing both sides the same way ground-truth spans are
        matched elsewhere in this codebase (see src/evaluation/matching.py)
        and mapping the match back to an exact offset in the original
        string. The chunker always slices `window_text` at the offset
        returned here, never anything derived from the anchor itself."""
        norm_anchor, _ = cls._normalize_with_offsets(anchor)
        norm_anchor = norm_anchor.strip().lower()
        if not norm_anchor:
            return -1

        # Find where search_from (an original-text offset) falls in normalized space.
        norm_search_from = 0
        for j, off in enumerate(norm_offsets):
            if off >= search_from:
                norm_search_from = j
                break
        else:
            norm_search_from = len(norm_offsets)

        norm_idx = norm_text.lower().find(norm_anchor, norm_search_from)
        if norm_idx == -1 or norm_idx >= len(norm_offsets):
            return -1
        return norm_offsets[norm_idx]

    @classmethod
    def _slice_by_anchors(cls, window_text: str, anchors: list[str]) -> tuple[list[str], int]:
        """Returns (pieces, skipped_anchor_count)."""
        if not anchors:
            return [window_text], 0

        norm_text, norm_offsets = cls._normalize_with_offsets(window_text)

        offsets: list[int] = []
        search_from = 0
        skipped = 0
        for anchor in anchors:
            idx = cls._find_anchor(window_text, norm_text, norm_offsets, anchor, search_from)
            if idx == -1 or (offsets and idx <= offsets[-1]):
                skipped += 1
                continue
            offsets.append(idx)
            search_from = idx + 1

        if not offsets:
            return [window_text], skipped

        pieces: list[str] = []
        if offsets[0] > 0:
            pieces.append(window_text[: offsets[0]])
        for i, start in enumerate(offsets):
            end = offsets[i + 1] if i + 1 < len(offsets) else len(window_text)
            pieces.append(window_text[start:end])
        return pieces, skipped

    def _cache_path(self, document_id: str, window_index: int) -> Path | None:
        if self.config.cache_dir is None:
            return None
        safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", self.llm_client.model_name)
        return self.config.cache_dir / safe_model / document_id / f"window_{window_index:04d}.json"

    def _read_cache(self, document_id: str, window_index: int) -> list[str] | None:
        path = self._cache_path(document_id, window_index)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, document_id: str, window_index: int, anchors: list[str]) -> None:
        path = self._cache_path(document_id, window_index)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(anchors), encoding="utf-8")
