"""Text normalization and span matching for evaluation ground truth.

Legal source PDFs carry OCR/extraction noise - smart quotes, en/em dashes,
and stray whitespace inside words. Ground-truth spans in the evaluation
dataset are copied verbatim from extracted chunk text, so matching them
back against retrieved chunks needs the same normalization on both sides,
or a byte-for-byte match will spuriously fail on cosmetic differences.
"""

from __future__ import annotations

import re

_SMART_QUOTES = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
}
_DASHES = {
    "–": "-",
    "—": "-",
}
_WHITESPACE_RE = re.compile(r"\s+")

SPAN_SEPARATOR = " ||| "
DOCUMENT_SEPARATOR = "; "


def normalize_text(text: str) -> str:
    """Fold cosmetic OCR/typographic variation so spans compare reliably."""
    for src, dst in _SMART_QUOTES.items():
        text = text.replace(src, dst)
    for src, dst in _DASHES.items():
        text = text.replace(src, dst)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip().lower()


def split_multi_span(value: str) -> list[str]:
    """Split a dataset field that may hold one value or several `|||`-joined parts."""
    return [part.strip() for part in value.split(SPAN_SEPARATOR)]


def span_matches(span: str, text: str) -> bool:
    """True if the normalized span appears verbatim inside the normalized text."""
    if not span or not text:
        return False
    return normalize_text(span) in normalize_text(text)


def any_span_matches(span: str, texts: list[str]) -> bool:
    """True if the span matches at least one of the given texts."""
    return any(span_matches(span, text) for text in texts)
