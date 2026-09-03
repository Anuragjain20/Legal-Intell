"""Generation exceptions."""

from __future__ import annotations


class GenerationError(RuntimeError):
    """Base generation error."""


class EmptyQuestionError(GenerationError):
    """Raised when the question is blank."""


class InsufficientEvidenceError(GenerationError):
    """Raised when retrieval does not provide enough grounded evidence."""


class GenerationFailure(GenerationError):
    """Raised when the LLM backend fails unexpectedly."""

