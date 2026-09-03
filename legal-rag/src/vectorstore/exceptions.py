"""Vector store exceptions."""

from __future__ import annotations


class VectorStoreError(ValueError):
    """Base error for vector store failures."""


class VectorDimensionMismatchError(VectorStoreError):
    """Raised when an indexed vector has the wrong size."""


