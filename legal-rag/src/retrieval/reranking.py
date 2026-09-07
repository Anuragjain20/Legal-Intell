"""Reranking stage for improving precision after initial retrieval.

Reranking ≠ Retrieval

Retriever: "Give me plausible candidates" (recall focus)
Reranker: "Which are actually most relevant?" (precision focus)

This module provides an extensible reranking interface and reference implementations.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from src.retrieval.hybrid_retrieval import HybridChunk, HybridResult


class RerankingStrategy(Enum):
    """Reranking strategies."""

    NONE = "none"  # No reranking
    HYBRID_SCORE = "hybrid_score"  # Re-rank using existing hybrid score
    SEMANTIC_SIMILARITY = "semantic_similarity"  # Rerank using dense model
    QUERY_TERM_OVERLAP = "query_term_overlap"  # Rerank by term matching


@dataclass(frozen=True)
class RerankScore:
    """Score from reranker for a single chunk."""

    chunk_id: str
    score: float
    reasoning: str | None = None  # Why did reranker score this way?


@dataclass(frozen=True)
class RerankingMetrics:
    """Instrumentation from reranking stage."""

    query: str
    input_candidates: int  # Candidates before reranking
    output_candidates: int  # Candidates after reranking
    reranking_strategy: str
    reranking_time_ms: float
    avg_score_before: float  # Average score before reranking
    avg_score_after: float  # Average score after reranking (should be higher)
    recall_at_k_change: float  # How many from top-5 stayed in top-5?


@dataclass(frozen=True)
class RerankResult:
    """Result from reranking stage."""

    chunks: list[HybridChunk]  # Re-ranked chunks
    metrics: RerankingMetrics
    original_chunks: list[HybridChunk]  # Original order for comparison


class Reranker(ABC):
    """Abstract base class for reranking strategies."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[HybridChunk],
    ) -> list[RerankScore]:
        """Score candidates for relevance to query.

        Args:
            query: User query
            candidates: Chunks to rerank

        Returns:
            List of RerankScore objects (may be shorter than candidates if filtered)
        """
        pass


class NoReranker(Reranker):
    """Identity reranker—returns candidates unchanged."""

    def rerank(
        self,
        query: str,
        candidates: list[HybridChunk],
    ) -> list[RerankScore]:
        """Return candidates with their existing scores."""
        return [
            RerankScore(chunk_id=c.chunk_id, score=c.score)
            for c in candidates
        ]


class HybridScoreReranker(Reranker):
    """Uses existing hybrid score for reranking.

    This is a baseline: if hybrid score is already good,
    reranking by the same score changes nothing.
    """

    def rerank(
        self,
        query: str,
        candidates: list[HybridChunk],
    ) -> list[RerankScore]:
        """Return candidates ranked by their existing hybrid score."""
        return [
            RerankScore(chunk_id=c.chunk_id, score=c.score)
            for c in candidates
        ]


class QueryTermOverlapReranker(Reranker):
    """Rerank by query term overlap with chunk text.

    Simple but effective baseline:
    - Count how many query terms appear in chunk text
    - Weight by term frequency
    - Use as rerank score

    Complements hybrid retrieval:
    - Dense captures semantics
    - BM25 captures exact terms
    - This reranker emphasizes term overlap
    """

    def rerank(
        self,
        query: str,
        candidates: list[HybridChunk],
    ) -> list[RerankScore]:
        """Score candidates by query term overlap."""
        query_terms = set(query.lower().split())
        query_terms = {t for t in query_terms if len(t) > 2}  # Filter short terms

        scores = []
        for candidate in candidates:
            chunk_text = candidate.text.lower()
            chunk_words = set(chunk_text.split())

            # Count overlapping terms
            overlap_count = len(query_terms & chunk_words)

            # Weight by term frequency in chunk
            overlap_score = 0.0
            for term in query_terms & chunk_words:
                term_freq = chunk_text.count(term)
                # Logarithmic weighting: repeated terms matter, but with diminishing returns
                overlap_score += 1.0 + (0.5 * (term_freq - 1)) / (term_freq + 1)

            # Normalize by number of query terms (higher = more terms matched)
            normalized_score = overlap_score / max(len(query_terms), 1)

            scores.append(
                RerankScore(
                    chunk_id=candidate.chunk_id,
                    score=normalized_score,
                    reasoning=f"Matched {overlap_count}/{len(query_terms)} query terms",
                )
            )

        return scores


class RankerPipeline:
    """Applies reranking stage after hybrid retrieval."""

    def __init__(
        self,
        reranker: Reranker,
        strategy: RerankingStrategy = RerankingStrategy.QUERY_TERM_OVERLAP,
    ):
        """Initialize reranker pipeline.

        Args:
            reranker: Reranker instance
            strategy: Which reranking strategy to use
        """
        self.reranker = reranker
        self.strategy = strategy

    def rerank(
        self,
        hybrid_result: HybridResult,
        top_k: int = 5,
    ) -> RerankResult:
        """Rerank hybrid retrieval results.

        Args:
            hybrid_result: Result from hybrid retrieval
            top_k: Number of results to return after reranking

        Returns:
            RerankResult with reranked chunks and metrics
        """
        start_time = time.time()

        # Get rerank scores
        rerank_scores = self.reranker.rerank(
            hybrid_result.metrics.query,
            hybrid_result.chunks,
        )

        # Create mapping from chunk_id to rerank score
        score_map = {rs.chunk_id: rs for rs in rerank_scores}

        # Build reranked chunks with new scores
        reranked = []
        for rank, (orig_chunk) in enumerate(hybrid_result.chunks):
            if orig_chunk.chunk_id in score_map:
                rerank_score = score_map[orig_chunk.chunk_id]

                # Create reranked chunk (keep original but update rank and score)
                reranked_chunk = HybridChunk(
                    rank=rank + 1,  # Will be re-ranked next
                    chunk_id=orig_chunk.chunk_id,
                    document_id=orig_chunk.document_id,
                    document_name=orig_chunk.document_name,
                    score=rerank_score.score,  # New rerank score
                    page_number=orig_chunk.page_number,
                    section=orig_chunk.section,
                    heading=orig_chunk.heading,
                    text=orig_chunk.text,
                    category=orig_chunk.category,
                    dense_rank=orig_chunk.dense_rank,
                    dense_score=orig_chunk.dense_score,
                    bm25_rank=orig_chunk.bm25_rank,
                    bm25_score=orig_chunk.bm25_score,
                )
                reranked.append(reranked_chunk)

        # Sort by rerank score (descending)
        reranked.sort(key=lambda c: c.score, reverse=True)

        # Update ranks after sorting
        reranked = [
            HybridChunk(
                rank=i + 1,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_name=c.document_name,
                score=c.score,
                page_number=c.page_number,
                section=c.section,
                heading=c.heading,
                text=c.text,
                category=c.category,
                dense_rank=c.dense_rank,
                dense_score=c.dense_score,
                bm25_rank=c.bm25_rank,
                bm25_score=c.bm25_score,
            )
            for i, c in enumerate(reranked)
        ]

        # Truncate to top-k
        final = reranked[:top_k]

        # Calculate metrics
        original_avg = sum(c.score for c in hybrid_result.chunks) / len(hybrid_result.chunks) if hybrid_result.chunks else 0.0
        reranked_avg = sum(c.score for c in final) / len(final) if final else 0.0

        # Measure recall: how many from original top-5 remained in final top-k?
        original_top_5_ids = {c.chunk_id for c in hybrid_result.chunks[:5]}
        final_ids = {c.chunk_id for c in final}
        recall_at_k = len(original_top_5_ids & final_ids) / max(len(original_top_5_ids), 1)

        reranking_time_ms = (time.time() - start_time) * 1000

        metrics = RerankingMetrics(
            query=hybrid_result.metrics.query,
            input_candidates=len(hybrid_result.chunks),
            output_candidates=len(final),
            reranking_strategy=self.strategy.value,
            reranking_time_ms=reranking_time_ms,
            avg_score_before=original_avg,
            avg_score_after=reranked_avg,
            recall_at_k_change=recall_at_k,
        )

        return RerankResult(
            chunks=final,
            metrics=metrics,
            original_chunks=hybrid_result.chunks,
        )

    def batch_rerank(
        self,
        hybrid_results: list[HybridResult],
        top_k: int = 5,
    ) -> list[RerankResult]:
        """Batch reranking of multiple hybrid results.

        Args:
            hybrid_results: List of HybridResult objects
            top_k: Number of results per query

        Returns:
            List of RerankResult objects
        """
        return [
            self.rerank(result, top_k=top_k)
            for result in hybrid_results
        ]
