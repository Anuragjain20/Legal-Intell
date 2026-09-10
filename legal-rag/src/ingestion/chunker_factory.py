"""Maps a chunking-method name to a concrete Chunker instance.

Mirrors _build_retriever in scripts/run_evaluation.py: one small function
as the single place that translates a config string into a pipeline
component.
"""

from __future__ import annotations

from pathlib import Path

from src.config.settings import Settings
from src.ingestion.chunker import Chunker, LegalChunker
from src.ingestion.llm_semantic_chunker import LLMChunkerConfig, LLMClient, LLMSemanticChunker
from src.ingestion.recursive_chunker import RecursiveCharacterChunker, RecursiveChunkerConfig

CHUNKING_METHODS = ("legal", "recursive", "llm_semantic")


def build_chunker(
    settings: Settings,
    *,
    llm_client: LLMClient | None = None,
    llm_cache_dir: Path | None = None,
    method: str | None = None,
) -> Chunker:
    """Build the Chunker for `method` (defaults to settings.chunking_method)."""
    resolved_method = method or settings.chunking_method

    if resolved_method == "legal":
        return LegalChunker()

    if resolved_method == "recursive":
        return RecursiveCharacterChunker(
            RecursiveChunkerConfig(
                chunk_size=settings.recursive_chunk_size,
                chunk_overlap=settings.recursive_chunk_overlap,
            )
        )

    if resolved_method == "llm_semantic":
        if llm_client is None:
            raise ValueError("llm_semantic chunking requires an llm_client.")
        return LLMSemanticChunker(
            llm_client,
            LLMChunkerConfig(
                window_pages=settings.llm_chunker_window_pages,
                cache_dir=llm_cache_dir,
            ),
        )

    raise ValueError(f"Unknown chunking_method: {resolved_method!r} (expected one of {CHUNKING_METHODS})")
