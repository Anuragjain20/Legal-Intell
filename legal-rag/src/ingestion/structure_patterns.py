"""Deterministic legal-structure patterns.

Patterns are tried in explicit precedence order (most specific first).
They identify a line; they do not chunk, embed, or rewrite source text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs"}

_SECTION_LETTER_RE = re.compile(r"^(\d+[A-Za-z]?)\(([a-z])\)\s+(.+)$", re.IGNORECASE)
_NESTED_CLAUSE_RE = re.compile(
    r"^\((ii|iii|iv|ix|vi|vii|viii|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)\)\s+(.+)$",
    re.IGNORECASE,
)
_LETTERED_RE = re.compile(r"^\(([a-z])\)\s+(.+)$")
_CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
_PART_RE = re.compile(r"^PART\s+([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
_ARTICLE_RE = re.compile(r"^Article\s+([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
_RULE_RE = re.compile(r"^Rule\s+([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
_REGULATION_RE = re.compile(r"^Regulation\s+([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
_SCHEDULE_RE = re.compile(
    r"^(?:THE\s+)?(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+SCHEDULE\b\s*[:.\-]?\s*(.*)$"
    r"|^(?:THE\s+)?SCHEDULE\s+([IVXLCDM]+|\d+[A-Za-z]?|[A-Z])\b\s*[:.\-]?\s*(.*)$"
    r"|^SCHEDULE\b\s*[:.\—–-]?\s*(.*)$",
    re.IGNORECASE,
)
_ANNEXURE_RE = re.compile(
    r"^ANNEXURE\s+([IVXLCDM]+|\d+[A-Za-z]?|[A-Z])\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
_KEYWORD_SECTION_RE = re.compile(
    r"^(Section|Clause|Appendix)\s+([IVXLCDM]+|\d+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
_FRONTMATTER_RE = re.compile(
    r"^(PREAMBLE|WHEREAS|RECITALS?|OBJECT OF THE ACT|LONG TITLE|PURPOSES|FINDINGS|INTENT|"
    r"TABLE OF CONTENTS|INTRODUCTORY REMARKS)\b",
    re.IGNORECASE,
)
_DOTTED_NUMBER_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){1,4})\.?\s+(.+)$")
_SIMPLE_NUMBER_RE = re.compile(r"^(\d{1,3}[A-Za-z]?)\.(?:\s+|(?=[A-Z“\"']))(.+)$")
_EMDASH_SPLIT_RE = re.compile(r"\s*\.\s*[\u2014\u2013]\s*|\s*[\u2014\u2013]\s*")
_PAGE_NUMBER_RE = re.compile(r"^(?:Page\s+)?\d{1,4}$", re.IGNORECASE)
_DATE_LINE_RE = re.compile(r"^\[?\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\]?$")
_CITATION_LINE_RE = re.compile(r"^(AIR|SCC|SCR|All\s+ER)\b", re.IGNORECASE)
_FOOTNOTE_RE = re.compile(
    r"^(Subs\.|Ins\.|Omitted|Added|Vide\b|For the Statement|See e\.g)",
    re.IGNORECASE,
)
_NARRATIVE_START_RE = re.compile(r"^(The|This|It|We|I|A|An)\b")
_KNOWN_HEADINGS = {
    "DEFINITIONS",
    "CONFIDENTIALITY",
    "TERMINATION",
    "GOVERNING LAW",
    "PAYMENT",
    "NOTICES",
    "INDEMNITY",
    "REPRESENTATIONS",
    "WARRANTIES",
    "FACTS",
    "ISSUES",
    "JUDGMENT",
    "ORDER",
    "REASONS",
    "ANALYSIS",
    "HELD",
}


@dataclass(frozen=True)
class DetectedStructure:
    type: str
    identifier: str | None
    title: str
    level: int
    confidence: float


@dataclass(frozen=True)
class DocumentSignals:
    has_chapters: bool = False
    has_parts: bool = False
    has_articles: bool = False
    has_rules: bool = False
    has_schedules: bool = False
    has_section_keywords: bool = False

    @property
    def statutory(self) -> bool:
        return self.has_chapters or self.has_parts or self.has_articles or self.has_rules or self.has_section_keywords


def passes_basic_heading_shape(text: str) -> bool:
    if not text or len(text) > 70:
        return False
    if text.endswith((".", ",", ";", ":")):
        return False
    words = text.split()
    return bool(words) and len(words) <= 10


def is_allcaps_heading(text: str) -> bool:
    text = text.strip()
    if not passes_basic_heading_shape(text):
        return False
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def is_heading_like(text: str) -> bool:
    text = text.strip()
    if is_allcaps_heading(text):
        return True
    if not passes_basic_heading_shape(text):
        return False

    def word_ok(word: str) -> bool:
        core = word.strip("\"'()")
        if not core:
            return True
        return core.lower() in _SMALL_WORDS or core[0].isupper()

    return all(word_ok(word) for word in text.split())


def is_noise_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return True
    if set(text) <= {"_", "-", "—", "–", ".", " "}:
        return True
    if _PAGE_NUMBER_RE.match(text) or _DATE_LINE_RE.match(text) or _CITATION_LINE_RE.match(text):
        return True
    return False


def split_statute_title(remainder: str) -> tuple[str, str | None]:
    match = _EMDASH_SPLIT_RE.search(remainder)
    if not match:
        return remainder.strip(), None
    title = remainder[: match.start()].strip(" .")
    body = remainder[match.end() :].strip()
    if not title or not body or len(title.split()) > 20:
        return remainder.strip(), None
    return title, body


def looks_like_narrative(text: str) -> bool:
    candidate = split_statute_title(text)[0]
    if _FOOTNOTE_RE.match(candidate):
        return True
    words = candidate.split()
    if len(words) > 22:
        return True
    if _NARRATIVE_START_RE.match(candidate) and len(words) >= 6:
        return True
    return False


def collect_signals(lines: list[str]) -> DocumentSignals:
    has_chapters = has_parts = has_articles = has_rules = has_schedules = has_section_keywords = False
    for raw in lines:
        line = raw.strip()
        if _CHAPTER_RE.match(line):
            has_chapters = True
        elif _PART_RE.match(line):
            has_parts = True
        elif _ARTICLE_RE.match(line):
            has_articles = True
        elif _RULE_RE.match(line) or _REGULATION_RE.match(line):
            has_rules = True
        elif _SCHEDULE_RE.match(line) or _ANNEXURE_RE.match(line):
            has_schedules = True
        elif _KEYWORD_SECTION_RE.match(line) or _SECTION_LETTER_RE.match(line):
            has_section_keywords = True
    return DocumentSignals(
        has_chapters=has_chapters,
        has_parts=has_parts,
        has_articles=has_articles,
        has_rules=has_rules,
        has_schedules=has_schedules,
        has_section_keywords=has_section_keywords,
    )


def match_section_letter(line: str) -> DetectedStructure | None:
    match = _SECTION_LETTER_RE.match(line)
    if not match:
        return None
    number, letter, remainder = match.groups()
    identifier = f"{number}({letter.lower()})"
    return DetectedStructure("section", identifier, remainder.strip(), 2, 1.0)


def match_nested_clause(line: str) -> DetectedStructure | None:
    match = _NESTED_CLAUSE_RE.match(line)
    if not match:
        return None
    roman, remainder = match.groups()
    identifier = f"({roman.lower()})"
    return DetectedStructure("nested_clause", identifier, remainder.strip(), 4, 1.0)


def match_lettered_subsection(line: str) -> DetectedStructure | None:
    match = _LETTERED_RE.match(line)
    if not match:
        return None
    letter, remainder = match.groups()
    identifier = f"({letter})"
    return DetectedStructure("subsection", identifier, remainder.strip(), 3, 1.0)


def match_chapter(line: str) -> DetectedStructure | None:
    match = _CHAPTER_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    title = remainder.strip() or line.strip()
    return DetectedStructure("chapter", identifier, title, 1, 1.0)


def match_part(line: str) -> DetectedStructure | None:
    match = _PART_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    title = remainder.strip() or line.strip()
    return DetectedStructure("part", identifier, title, 1, 1.0)


def match_article(line: str) -> DetectedStructure | None:
    match = _ARTICLE_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    title = remainder.strip() or line.strip()
    return DetectedStructure("article", identifier, title, 2, 1.0)


def match_rule(line: str) -> DetectedStructure | None:
    match = _RULE_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    title = remainder.strip() or line.strip()
    return DetectedStructure("rule", identifier, title, 2, 1.0)


def match_regulation(line: str) -> DetectedStructure | None:
    match = _REGULATION_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    title = remainder.strip() or line.strip()
    return DetectedStructure("regulation", identifier, title, 2, 1.0)


def match_schedule(line: str) -> DetectedStructure | None:
    match = _SCHEDULE_RE.match(line)
    if not match:
        return None
    ordinal, after_ordinal, numbered, after_numbered, bare = match.groups()
    if ordinal:
        identifier = ordinal.upper()
        title = (after_ordinal or "").strip() or line.strip()
    elif numbered:
        identifier = numbered
        title = (after_numbered or "").strip() or line.strip()
    else:
        identifier = "SCHEDULE"
        title = (bare or "").strip() or line.strip()
    return DetectedStructure("schedule", identifier, title, 1, 1.0)


def match_annexure(line: str) -> DetectedStructure | None:
    match = _ANNEXURE_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    title = remainder.strip() or line.strip()
    return DetectedStructure("annexure", identifier, title, 1, 1.0)


def match_keyword_section(line: str) -> DetectedStructure | None:
    match = _KEYWORD_SECTION_RE.match(line)
    if not match:
        return None
    keyword, number, remainder = match.groups()
    structure_type = "clause" if keyword.lower() == "clause" else "section"
    title = remainder.strip() or line.strip()
    return DetectedStructure(structure_type, number, title, 2, 1.0)


def match_frontmatter(line: str) -> DetectedStructure | None:
    match = _FRONTMATTER_RE.match(line)
    if not match:
        return None
    label = match.group(1).upper().replace(" ", "_")
    return DetectedStructure("frontmatter", label, line.strip(), 0, 1.0)


def match_dotted_number(line: str) -> DetectedStructure | None:
    match = _DOTTED_NUMBER_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    return DetectedStructure("section", identifier, remainder.strip(), 2, 1.0)


def match_simple_number(line: str) -> DetectedStructure | None:
    match = _SIMPLE_NUMBER_RE.match(line)
    if not match:
        return None
    identifier, remainder = match.groups()
    remainder = remainder.strip()
    if looks_like_narrative(remainder):
        return None
    title, body = split_statute_title(remainder)
    if body:
        return DetectedStructure("section", identifier, title, 2, 0.95)
    if is_heading_like(remainder):
        return DetectedStructure("section", identifier, remainder, 2, 1.0)
    return DetectedStructure("section", identifier, remainder, 2, 0.8)


def match_allcaps_heading(line: str) -> DetectedStructure | None:
    if not is_allcaps_heading(line):
        return None
    text = line.strip()
    confidence = 1.0 if text in _KNOWN_HEADINGS else 0.7
    heading_type = "heading"
    if text in {"FACTS", "ISSUES", "JUDGMENT", "ORDER", "REASONS", "ANALYSIS", "HELD"}:
        heading_type = "judgment_heading"
    return DetectedStructure(heading_type, None, text, 1, confidence)


_PATTERNS: tuple[Callable[[str], DetectedStructure | None], ...] = (
    match_section_letter,
    match_nested_clause,
    match_lettered_subsection,
    match_chapter,
    match_part,
    match_article,
    match_rule,
    match_regulation,
    match_schedule,
    match_annexure,
    match_keyword_section,
    match_frontmatter,
    match_dotted_number,
    match_simple_number,
    match_allcaps_heading,
)


def match_line(line: str) -> DetectedStructure | None:
    """Return the first matching structure for a stripped line, or None."""
    if is_noise_line(line):
        return None
    for matcher in _PATTERNS:
        detected = matcher(line)
        if detected is not None:
            return detected
    return None


def accept_numbered_section(detected: DetectedStructure, signals: DocumentSignals) -> bool:
    """Simple numbered paragraphs need statutory context unless they look like headings."""
    if detected.type != "section" or "(" in (detected.identifier or "") or "." in (detected.identifier or ""):
        return True
    if detected.confidence >= 0.95:
        return True
    if is_heading_like(detected.title):
        return True
    return signals.statutory
