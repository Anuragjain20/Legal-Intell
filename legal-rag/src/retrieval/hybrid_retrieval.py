"""Hybrid retrieval combining dense and BM25 with rank fusion.

This module combines dense embedding retrieval with BM25 lexical retrieval
using Reciprocal Rank Fusion (RRF) to handle different score distributions.

Key insight: Dense similarity and BM25 scores are not directly comparable.
RRF works on rankings, not raw scores, avoiding unfair biases.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from src.retrieval.bm25_baseline import BM25Retriever
from src.retrieval.dense_baseline import DenseRetriever
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError


class FusionStrategy(Enum):
    """Rank fusion strategy."""

    RRF = "rrf"  # Reciprocal Rank Fusion (default, recommended)
    SIMPLE_AVERAGE = "simple_average"  # Simple average of normalized scores
    WEIGHTED_AVERAGE = "weighted_average"  # Weighted average (configurable)


@dataclass(frozen=True)
class HybridChunk:
    """Hybrid retrieval result combining dense and BM25."""

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
    dense_rank: int | None  # Rank from dense retrieval (or None if not present)
    dense_score: float | None  # Score from dense retrieval
    bm25_rank: int | None  # Rank from BM25 retrieval (or None if not present)
    bm25_score: float | None  # Score from BM25 retrieval


@dataclass(frozen=True)
class HybridMetrics:
    """Instrumentation from hybrid retrieval run."""

    query: str
    dense_time_ms: float
    bm25_time_ms: float
    fusion_time_ms: float
    total_time_ms: float
    dense_candidates: int
    bm25_candidates: int
    merged_candidates: int
    final_results: int
    fusion_strategy: str
    embedding_model: str
    embedding_version: str


@dataclass(frozen=True)
class HybridResult:
    """Complete hybrid retrieval result."""

    chunks: list[HybridChunk]
    metrics: HybridMetrics


class HybridRetriever:
    """Combines dense and BM25 retrieval with rank fusion."""

    def __init__(
        self,
        dense_retriever: DenseRetriever,
        bm25_retriever: BM25Retriever,
        fusion_strategy: FusionStrategy = FusionStrategy.RRF,
        dense_weight: float = 0.5,
        bm25_weight: float = 0.5,
        k: float = 60.0,  # RRF parameter
    ):
        """Initialize hybrid retriever.

        Args:
            dense_retriever: DenseRetriever instance
            bm25_retriever: BM25Retriever instance
            fusion_strategy: How to combine rankings
            dense_weight: Weight for dense results (used in weighted average)
            bm25_weight: Weight for BM25 results (used in weighted average)
            k: RRF parameter (higher k gives more weight to low-ranked results)
        """
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.fusion_strategy = fusion_strategy
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        self.k = k

        # Normalize weights
        total_weight = dense_weight + bm25_weight
        self.dense_weight = dense_weight / total_weight
        self.bm25_weight = bm25_weight / total_weight

    def retrieve_hybrid(
        self, query: str, top_k: int = 5, document_ids: list[str] | None = None
    ) -> HybridResult:
        """Execute hybrid retrieval with rank fusion.

        Args:
            query: User query string
            top_k: Number of results to return
            document_ids: If set, restrict both dense and BM25 candidates to
                these document_ids before scoring/fusion (e.g. case-scoped
                retrieval). None searches the whole corpus, unchanged.

        Returns:
            HybridResult with fused chunks and metrics

        Raises:
            EmptyQueryError: If query is blank
            NoRelevantResultsError: If no results after fusion
        """
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be blank.")

        start_time = time.time()

        # Stage 1: Dense Retrieval
        dense_start = time.time()
        try:
            dense_result = self.dense_retriever.retrieve_dense(query, top_k=top_k * 2, document_ids=document_ids)
            dense_time_ms = (time.time() - dense_start) * 1000
            dense_candidates = len(dense_result.chunks)
        except NoRelevantResultsError:
            dense_result = None
            dense_time_ms = (time.time() - dense_start) * 1000
            dense_candidates = 0

        # Stage 2: BM25 Retrieval
        bm25_start = time.time()
        try:
            bm25_result = self.bm25_retriever.retrieve_bm25(query, top_k=top_k * 2, document_ids=document_ids)
            bm25_time_ms = (time.time() - bm25_start) * 1000
            bm25_candidates = len(bm25_result.chunks)
        except NoRelevantResultsError:
            bm25_result = None
            bm25_time_ms = (time.time() - bm25_start) * 1000
            bm25_candidates = 0

        # If both failed, raise error
        if dense_result is None and bm25_result is None:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found.")

        # Stage 3: Rank Fusion
        fusion_start = time.time()
        fused_chunks = self._fuse_results(dense_result, bm25_result, top_k)
        fusion_time_ms = (time.time() - fusion_start) * 1000

        total_time_ms = (time.time() - start_time) * 1000

        # Get embedding metadata from available result
        if dense_result:
            embedding_model = dense_result.metrics.embedding_model
            embedding_version = dense_result.metrics.embedding_version
        else:
            embedding_model = "unknown"
            embedding_version = "unknown"

        # Build metrics
        metrics = HybridMetrics(
            query=query,
            dense_time_ms=dense_time_ms,
            bm25_time_ms=bm25_time_ms,
            fusion_time_ms=fusion_time_ms,
            total_time_ms=total_time_ms,
            dense_candidates=dense_candidates,
            bm25_candidates=bm25_candidates,
            merged_candidates=len(fused_chunks),
            final_results=len(fused_chunks),
            fusion_strategy=self.fusion_strategy.value,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )

        return HybridResult(chunks=fused_chunks, metrics=metrics)

    def _fuse_results(self, dense_result, bm25_result, top_k: int) -> list[HybridChunk]:
        """Fuse dense and BM25 results using configured strategy.

        Args:
            dense_result: DenseRetrievalResult or None
            bm25_result: BM25Result or None
            top_k: Number of results to return

        Returns:
            List of HybridChunk objects, ranked and truncated to top_k
        """
        if self.fusion_strategy == FusionStrategy.RRF:
            return self._rrf_fusion(dense_result, bm25_result, top_k)
        elif self.fusion_strategy == FusionStrategy.SIMPLE_AVERAGE:
            return self._simple_average_fusion(dense_result, bm25_result, top_k)
        elif self.fusion_strategy == FusionStrategy.WEIGHTED_AVERAGE:
            return self._weighted_average_fusion(dense_result, bm25_result, top_k)
        else:
            raise ValueError(f"Unknown fusion strategy: {self.fusion_strategy}")

    def _rrf_fusion(self, dense_result, bm25_result, top_k: int) -> list[HybridChunk]:
        """Reciprocal Rank Fusion (RRF).

        RRF = (1 / (k + rank)) combined across methods
        Works on rankings, not raw scores, avoiding score distribution issues.
        """
        # Build ranking maps
        dense_rankings = {}
        if dense_result:
            for chunk in dense_result.chunks:
                dense_rankings[chunk.chunk_id] = chunk.rank

        bm25_rankings = {}
        if bm25_result:
            for chunk in bm25_result.chunks:
                bm25_rankings[chunk.chunk_id] = chunk.rank

        # Calculate RRF scores for all chunks
        rrf_scores = {}
        all_chunk_ids = set(dense_rankings.keys()) | set(bm25_rankings.keys())

        for chunk_id in all_chunk_ids:
            score = 0.0
            if chunk_id in dense_rankings:
                score += 1.0 / (self.k + dense_rankings[chunk_id])
            if chunk_id in bm25_rankings:
                score += 1.0 / (self.k + bm25_rankings[chunk_id])
            rrf_scores[chunk_id] = score

        # Build hybrid chunks, sorted by RRF score
        hybrid_chunks = []
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Get metadata from source results
        chunk_metadata = {}
        if dense_result:
            for chunk in dense_result.chunks:
                chunk_metadata[chunk.chunk_id] = ("dense", chunk)
        if bm25_result:
            for chunk in bm25_result.chunks:
                chunk_metadata[chunk.chunk_id] = ("bm25", chunk)

        for rank, (chunk_id, rrf_score) in enumerate(sorted_chunks[:top_k], 1):
            source, source_chunk = chunk_metadata[chunk_id]

            dense_rank = dense_rankings.get(chunk_id)
            dense_score = None
            if dense_result:
                for chunk in dense_result.chunks:
                    if chunk.chunk_id == chunk_id:
                        dense_score = chunk.score
                        break

            bm25_rank = bm25_rankings.get(chunk_id)
            bm25_score = None
            if bm25_result:
                for chunk in bm25_result.chunks:
                    if chunk.chunk_id == chunk_id:
                        bm25_score = chunk.score
                        break

            hybrid_chunk = HybridChunk(
                rank=rank,
                chunk_id=source_chunk.chunk_id,
                document_id=source_chunk.document_id,
                document_name=source_chunk.document_name,
                score=rrf_score,
                page_number=source_chunk.page_number,
                section=source_chunk.section,
                heading=source_chunk.heading,
                text=source_chunk.text,
                category=source_chunk.category,
                dense_rank=dense_rank,
                dense_score=dense_score,
                bm25_rank=bm25_rank,
                bm25_score=bm25_score,
            )
            hybrid_chunks.append(hybrid_chunk)

        return hybrid_chunks

    def _simple_average_fusion(self, dense_result, bm25_result, top_k: int) -> list[HybridChunk]:
        """Simple average of normalized scores.

        Normalize both score ranges to 0-1, then average.
        """
        # Normalize and collect scores
        combined_scores = {}

        if dense_result:
            max_dense_score = max((c.score for c in dense_result.chunks), default=1.0)
            for chunk in dense_result.chunks:
                normalized = chunk.score / max_dense_score if max_dense_score > 0 else 0
                if chunk.chunk_id not in combined_scores:
                    combined_scores[chunk.chunk_id] = {"dense": 0, "bm25": 0, "chunk": chunk}
                combined_scores[chunk.chunk_id]["dense"] = normalized
                combined_scores[chunk.chunk_id]["chunk"] = chunk

        if bm25_result:
            max_bm25_score = max((c.score for c in bm25_result.chunks), default=1.0)
            for chunk in bm25_result.chunks:
                normalized = chunk.score / max_bm25_score if max_bm25_score > 0 else 0
                if chunk.chunk_id not in combined_scores:
                    combined_scores[chunk.chunk_id] = {"dense": 0, "bm25": 0, "chunk": chunk}
                combined_scores[chunk.chunk_id]["bm25"] = normalized
                combined_scores[chunk.chunk_id]["chunk"] = chunk

        # Calculate average scores and build hybrid chunks
        hybrid_chunks = []
        sorted_chunks = sorted(
            combined_scores.items(),
            key=lambda x: (x[1]["dense"] + x[1]["bm25"]) / 2,
            reverse=True,
        )

        for rank, (chunk_id, scores) in enumerate(sorted_chunks[:top_k], 1):
            chunk = scores["chunk"]
            avg_score = (scores["dense"] + scores["bm25"]) / 2

            # Get rankings from original results
            dense_rank = None
            dense_score = None
            if dense_result:
                for c in dense_result.chunks:
                    if c.chunk_id == chunk_id:
                        dense_rank = c.rank
                        dense_score = c.score
                        break

            bm25_rank = None
            bm25_score = None
            if bm25_result:
                for c in bm25_result.chunks:
                    if c.chunk_id == chunk_id:
                        bm25_rank = c.rank
                        bm25_score = c.score
                        break

            hybrid_chunk = HybridChunk(
                rank=rank,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                score=avg_score,
                page_number=chunk.page_number,
                section=chunk.section,
                heading=chunk.heading,
                text=chunk.text,
                category=chunk.category,
                dense_rank=dense_rank,
                dense_score=dense_score,
                bm25_rank=bm25_rank,
                bm25_score=bm25_score,
            )
            hybrid_chunks.append(hybrid_chunk)

        return hybrid_chunks

    def _weighted_average_fusion(self, dense_result, bm25_result, top_k: int) -> list[HybridChunk]:
        """Weighted average of normalized scores."""
        # Similar to simple average but uses configured weights
        combined_scores = {}

        if dense_result:
            max_dense_score = max((c.score for c in dense_result.chunks), default=1.0)
            for chunk in dense_result.chunks:
                normalized = chunk.score / max_dense_score if max_dense_score > 0 else 0
                if chunk.chunk_id not in combined_scores:
                    combined_scores[chunk.chunk_id] = {"dense": 0, "bm25": 0, "chunk": chunk}
                combined_scores[chunk.chunk_id]["dense"] = normalized * self.dense_weight
                combined_scores[chunk.chunk_id]["chunk"] = chunk

        if bm25_result:
            max_bm25_score = max((c.score for c in bm25_result.chunks), default=1.0)
            for chunk in bm25_result.chunks:
                normalized = chunk.score / max_bm25_score if max_bm25_score > 0 else 0
                if chunk.chunk_id not in combined_scores:
                    combined_scores[chunk.chunk_id] = {"dense": 0, "bm25": 0, "chunk": chunk}
                combined_scores[chunk.chunk_id]["bm25"] = normalized * self.bm25_weight
                combined_scores[chunk.chunk_id]["chunk"] = chunk

        # Calculate weighted scores
        hybrid_chunks = []
        sorted_chunks = sorted(
            combined_scores.items(),
            key=lambda x: x[1]["dense"] + x[1]["bm25"],
            reverse=True,
        )

        for rank, (chunk_id, scores) in enumerate(sorted_chunks[:top_k], 1):
            chunk = scores["chunk"]
            weighted_score = scores["dense"] + scores["bm25"]

            dense_rank = None
            dense_score = None
            if dense_result:
                for c in dense_result.chunks:
                    if c.chunk_id == chunk_id:
                        dense_rank = c.rank
                        dense_score = c.score
                        break

            bm25_rank = None
            bm25_score = None
            if bm25_result:
                for c in bm25_result.chunks:
                    if c.chunk_id == chunk_id:
                        bm25_rank = c.rank
                        bm25_score = c.score
                        break

            hybrid_chunk = HybridChunk(
                rank=rank,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                score=weighted_score,
                page_number=chunk.page_number,
                section=chunk.section,
                heading=chunk.heading,
                text=chunk.text,
                category=chunk.category,
                dense_rank=dense_rank,
                dense_score=dense_score,
                bm25_rank=bm25_rank,
                bm25_score=bm25_score,
            )
            hybrid_chunks.append(hybrid_chunk)

        return hybrid_chunks

    def batch_retrieve_hybrid(self, queries: list[str], top_k: int = 5) -> list[HybridResult]:
        """Batch hybrid retrieval for evaluation.

        Args:
            queries: List of queries
            top_k: Number of results per query

        Returns:
            List of HybridResult objects
        """
        results = []
        for query in queries:
            try:
                result = self.retrieve_hybrid(query, top_k=top_k)
                results.append(result)
            except (EmptyQueryError, NoRelevantResultsError):
                pass
        return results
