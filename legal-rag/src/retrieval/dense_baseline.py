"""Dense retrieval baseline with detailed instrumentation for experimentation.

This module focuses on the core dense retrieval pipeline independently:
- Query embedding
- Vector search
- Score recording
- Latency measurement
- Index metadata tracking

No reranking, no filtering—pure dense search with full observability.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.embeddings.base import EmbeddingProvider
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.vectorstore.base import VectorStore


@dataclass(frozen=True)
class DenseRetrievalMetrics:
    """Instrumentation from a single dense retrieval run."""

    query: str
    query_embedding_time_ms: float
    vector_search_time_ms: float
    total_time_ms: float
    candidates_found: int
    candidates_above_threshold: int
    embedding_model: str
    embedding_version: str
    index_metadata: dict
    retrieval_method: str = "dense_search"


@dataclass(frozen=True)
class DenseChunk:
    """Result from dense retrieval with score and metadata."""

    rank: int
    chunk_id: str
    document_id: str
    document_name: str | None
    score: float
    page_number: int
    section: str | None
    heading: str | None
    text: str
    category: str | None


@dataclass(frozen=True)
class DenseRetrievalResult:
    """Complete dense retrieval result with chunks and metrics."""

    chunks: list[DenseChunk]
    metrics: DenseRetrievalMetrics


class DenseRetriever:
    """Pure dense retrieval baseline: embed, search, score, measure.

    This retriever implements only the core dense search pipeline without
    reranking or filtering, to establish a clean baseline for experimentation.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        similarity_threshold: float = 0.30,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.similarity_threshold = similarity_threshold

    def retrieve_dense(self, query: str, top_k: int = 5) -> DenseRetrievalResult:
        """Execute dense retrieval pipeline with full instrumentation.

        Args:
            query: User query string
            top_k: Number of results to return

        Returns:
            DenseRetrievalResult with chunks and metrics

        Raises:
            EmptyQueryError: If query is blank
            NoRelevantResultsError: If no results meet threshold
        """
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be blank.")

        start_time = time.time()

        # Stage 1: Embedding
        embed_start = time.time()
        query_vector = self.embedding_provider.embed_query(query)
        embedding_time_ms = (time.time() - embed_start) * 1000

        # Stage 2: Vector Search
        search_start = time.time()
        raw_results = self.vector_store.search(query_vector, top_k=top_k)
        search_time_ms = (time.time() - search_start) * 1000

        # Capture index metadata
        embedding_model = (
            raw_results[0].record.embedding_model if raw_results else "unknown"
        )
        embedding_version = (
            raw_results[0].record.embedding_version if raw_results else "unknown"
        )
        candidates_found = len(raw_results)

        # Stage 3: Threshold Filter
        above_threshold = [
            result for result in raw_results
            if result.score >= self.similarity_threshold
        ]
        candidates_above_threshold = len(above_threshold)

        if not above_threshold:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found.")

        # Stage 4: Convert to DenseChunk objects
        chunks = [
            DenseChunk(
                rank=index + 1,
                chunk_id=result.record.chunk_id,
                document_id=result.record.document_id,
                document_name=result.record.document_name,
                score=result.score,
                page_number=result.record.page_number,
                section=result.record.section,
                heading=result.record.heading,
                text=result.record.text,
                category=result.record.category,
            )
            for index, result in enumerate(above_threshold[:top_k])
        ]

        total_time_ms = (time.time() - start_time) * 1000

        # Build metrics
        metrics = DenseRetrievalMetrics(
            query=query,
            query_embedding_time_ms=embedding_time_ms,
            vector_search_time_ms=search_time_ms,
            total_time_ms=total_time_ms,
            candidates_found=candidates_found,
            candidates_above_threshold=candidates_above_threshold,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
            index_metadata={
                "embedding_model": embedding_model,
                "embedding_version": embedding_version,
                "retrieval_method": "dense_search",
                "similarity_threshold": self.similarity_threshold,
            },
        )

        return DenseRetrievalResult(chunks=chunks, metrics=metrics)

    def batch_retrieve_dense(
        self, queries: list[str], top_k: int = 5
    ) -> list[DenseRetrievalResult]:
        """Run dense retrieval on multiple queries.

        Useful for experimentation and evaluation.

        Args:
            queries: List of query strings
            top_k: Number of results per query

        Returns:
            List of DenseRetrievalResult objects
        """
        results = []
        for query in queries:
            try:
                result = self.retrieve_dense(query, top_k=top_k)
                results.append(result)
            except (EmptyQueryError, NoRelevantResultsError):
                # Continue on individual query failures
                pass
        return results
