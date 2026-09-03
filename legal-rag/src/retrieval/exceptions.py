"""Retrieval exceptions."""

from __future__ import annotations


class RetrievalError(ValueError):
    """Base retrieval error."""


class EmptyQueryError(RetrievalError):
    """Raised when the user query is blank."""


class NoRelevantResultsError(RetrievalError):
    """Raised when no retrieved chunks meet the relevance threshold."""

