"""Upload-related exceptions."""


class UploadValidationError(ValueError):
    """Raised when an uploaded document fails validation."""


class ChunkingError(RuntimeError):
    """Raised when a chunking strategy cannot produce valid chunks."""


class LLMChunkingFailure(ChunkingError):
    """Raised when LLM-based chunking fails to call out, parse, or locate boundaries."""
