"""Adaptive structure detection for legal documents.

Detects whatever structural signals are actually present in the text —
numbering (``1.1``, ``Article 5``), lexical headings (``TERMINATION``,
``FACTS``), and paragraph boundaries — and falls back gracefully when a
signal isn't there. Contracts, statutes, judgments, and unstructured
notices all look different, so nothing here assumes a fixed section
format, and nothing here invents a heading or section number that the
text doesn't actually contain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.ingestion.models import DocumentPage

_SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs"}

# Dotted/multi-level numbering ("1.1", "2.3.4") is a strong, low-noise signal, so a
# trailing period is optional. A bare single-level number ("1 DEFINITIONS") is common
# in ordinary prose too (dates, quantities), so it's only treated as numbering when
# followed by a period, matching the conventional "1. Clause text" list style.
_DOTTED_NUMBER_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){1,4})\.?\s+(.+)$")
_SIMPLE_NUMBER_RE = re.compile(r"^(\d{1,3})\.\s+(.+)$")

# Word-form numbering ("Article 1", "Section 5", "Clause 7", "Chapter I", "Part A").
# Anchored at line start so it doesn't fire on inline references like "...as set out
# in section 5 above" appearing mid-paragraph.
_KEYWORD_NUMBER_RE = re.compile(
    r"^(Article|Section|Clause|Chapter|Part|Schedule|Appendix)\s+"
    r"([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DetectedParagraph:
    """A semantic unit of text plus whatever structural context was detected for it."""

    text: str
    page_number: int
    end_page_number: int
    section: str | None
    heading: str | None


@dataclass(frozen=True)
class NumberingMatch:
    section: str
    # None means the line *is* the section marker itself (e.g. "Section 1", "CHAPTER I")
    # with no trailing title text on the same line.
    remainder: str | None


def _passes_basic_heading_shape(text: str) -> bool:
    if not text or len(text) > 70:
        return False
    if text.endswith((".", ",", ";", ":")):
        return False
    words = text.split()
    return bool(words) and len(words) <= 10


def _is_allcaps_heading(text: str) -> bool:
    text = text.strip()
    if not _passes_basic_heading_shape(text):
        return False
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _is_heading_like(text: str) -> bool:
    """A short line, in ALL CAPS or Title Case, with no sentence-ending punctuation.

    Title Case is only accepted here, not in bare (unnumbered) heading detection:
    a numbering signal ("7.1 Termination for Cause") already anchors the line as
    structural, whereas an isolated Title Case line in the wild ("Paragraph A") is
    too easily confused with ordinary content.
    """
    text = text.strip()
    if _is_allcaps_heading(text):
        return True
    if not _passes_basic_heading_shape(text):
        return False

    def word_ok(word: str) -> bool:
        core = word.strip("\"'()")
        if not core:
            return True
        if core.lower() in _SMALL_WORDS:
            return True
        return core[0].isupper()

    return all(word_ok(word) for word in text.split())


class NumberingDetector:
    """Detects numbered headings/clauses: ``1.``, ``1.1``, ``Article 1``, ``Section 5``."""

    def match(self, line: str) -> NumberingMatch | None:
        for pattern in (_DOTTED_NUMBER_RE, _SIMPLE_NUMBER_RE):
            m = pattern.match(line)
            if m:
                return NumberingMatch(section=m.group(1), remainder=m.group(2).strip())

        m = _KEYWORD_NUMBER_RE.match(line)
        if m:
            _keyword, number, remainder = m.groups()
            remainder = remainder.strip()
            return NumberingMatch(section=number, remainder=remainder or None)

        return None


class HeadingDetector:
    """Detects lexical headings with no explicit numbering, e.g. ``FACTS``, ``DEFINITIONS``.

    Restricted to ALL CAPS: an isolated Title Case line has no numbering to
    corroborate it as structural, so it's left as ordinary paragraph text instead of
    being invented as a heading. See ``_is_heading_like`` for the numbered case.
    """

    def match(self, line: str) -> str | None:
        return line.strip() if _is_allcaps_heading(line) else None


class ParagraphDetector:
    """Groups raw text into paragraphs, splitting on blank lines."""

    def split(self, text: str) -> list[str]:
        return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


class StructureDetector:
    """Combines numbering/heading/paragraph signals into an ordered list of paragraphs.

    Falls back to plain paragraph boundaries when no headings or numbering are
    detected anywhere in the document, and never fabricates section/heading
    metadata that wasn't actually observed.
    """

    def __init__(self) -> None:
        self._numbering = NumberingDetector()
        self._heading = HeadingDetector()

    def detect(self, pages: list[DocumentPage]) -> list[DetectedParagraph]:
        results: list[DetectedParagraph] = []
        current_heading: str | None = None
        current_section: str | None = None
        last_line_was_heading = False

        buffer_lines: list[str] = []
        buffer_start_page: int | None = None
        buffer_end_page: int | None = None

        def flush() -> None:
            nonlocal buffer_lines, buffer_start_page, buffer_end_page
            text = "\n".join(buffer_lines).strip()
            if text and buffer_start_page is not None:
                results.append(
                    DetectedParagraph(
                        text=text,
                        page_number=buffer_start_page,
                        end_page_number=buffer_end_page or buffer_start_page,
                        section=current_section,
                        heading=current_heading,
                    )
                )
            buffer_lines = []
            buffer_start_page = None
            buffer_end_page = None

        def start_heading(text: str, section: str | None) -> None:
            nonlocal current_heading, current_section, last_line_was_heading
            # A numbered heading immediately followed by an unnumbered title line on
            # the next line (e.g. "CHAPTER I" / "PRELIMINARY") is one heading split
            # across lines by the PDF layout, so it's merged. An unnumbered line
            # followed by a numbered one ("SERVICES AGREEMENT" / "1. DEFINITIONS") is
            # a document title followed by its first real section — merging those
            # would fabricate a heading that appears nowhere in the text, so it isn't.
            if last_line_was_heading and current_section is not None and section is None:
                current_heading = f"{current_heading} {text}".strip()
            else:
                current_heading = text
                current_section = section
            last_line_was_heading = True

        for page in pages:
            for raw_line in page.text.splitlines():
                line = raw_line.strip()

                if not line:
                    flush()
                    last_line_was_heading = False
                    continue

                numbering_match = self._numbering.match(line)
                if numbering_match:
                    if numbering_match.remainder is None:
                        flush()
                        start_heading(line, numbering_match.section)
                        continue

                    if _is_heading_like(numbering_match.remainder):
                        flush()
                        start_heading(numbering_match.remainder, numbering_match.section)
                        continue

                    # Numbered but not heading-like text ("1.1 \"Services\" means...")
                    # starts a new clause under the current heading rather than
                    # replacing it.
                    flush()
                    current_section = numbering_match.section
                    buffer_start_page = page.page_number
                    buffer_end_page = page.page_number
                    buffer_lines.append(line)
                    last_line_was_heading = False
                    continue

                bare_heading = self._heading.match(line)
                if bare_heading:
                    flush()
                    start_heading(bare_heading, None)
                    continue

                last_line_was_heading = False
                if buffer_start_page is None:
                    buffer_start_page = page.page_number
                buffer_end_page = page.page_number
                buffer_lines.append(line)

        flush()
        return results
