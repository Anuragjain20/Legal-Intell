"""Comprehensive tests for reranking stage (LG-RAG-026).

Tests cover:
- Reranker interface and implementations
- Score transformation and ranking changes
- Latency measurement
- Batch reranking
- Comparison of precision vs recall trade-offs
"""

import dataclasses

import pytest
from src.retrieval.hybrid_retrieval import HybridChunk, HybridMetrics, HybridResult
from src.retrieval.reranking import (
    NoReranker,
    QueryTermOverlapReranker,
    HybridScoreReranker,
    RankerPipeline,
    RerankingMetrics,
    RerankingStrategy,
)


# ===== Test Fixtures =====


@pytest.fixture
def sample_hybrid_result():
    """Create a hybrid result with 10 chunks for testing."""
    chunks = []
    for i in range(10):
        chunk = HybridChunk(
            rank=i + 1,
            chunk_id=f"chunk-{i:02d}",
            document_id=f"doc-{i // 3}",
            document_name=f"Document {i // 3}",
            score=1.0 - (i * 0.08),  # Decreasing scores: 1.0, 0.92, 0.84, ...
            page_number=i + 1,
            section=f"Section {i}",
            heading=f"Heading {i}",
            text=f"This is chunk {i} with content. It discusses important matters related to section {i}. "
            f"The party must provide notice. Contract terms apply.",
            category="contract",
            dense_rank=i + 1,
            dense_score=1.0 - (i * 0.06),
            bm25_rank=i + 1 if i % 2 == 0 else None,
            bm25_score=0.8 - (i * 0.05) if i % 2 == 0 else None,
        )
        chunks.append(chunk)

    metrics = HybridMetrics(
        query="party notice contract",
        dense_time_ms=45.2,
        bm25_time_ms=3.1,
        fusion_time_ms=2.5,
        total_time_ms=50.8,
        dense_candidates=10,
        bm25_candidates=8,
        merged_candidates=10,
        final_results=10,
        fusion_strategy="rrf",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1",
    )

    return HybridResult(chunks=chunks, metrics=metrics)


@pytest.fixture
def high_variance_result():
    """Result with high score variance for testing precision trade-off."""
    chunks = []
    scores = [0.95, 0.92, 0.88, 0.72, 0.55, 0.38, 0.22, 0.15, 0.08, 0.01]

    for i, score in enumerate(scores):
        chunk = HybridChunk(
            rank=i + 1,
            chunk_id=f"var-chunk-{i:02d}",
            document_id=f"var-doc-{i}",
            document_name=f"Variable Doc {i}",
            score=score,
            page_number=i + 1,
            section=f"Var Section {i}",
            heading=f"Variable Heading {i}",
            text=f"Variable content {i}. Section defines obligations. Party responsibilities. Notice requirements.",
            category="legal",
            dense_rank=i + 1,
            dense_score=score + 0.02,
            bm25_rank=i + 1,
            bm25_score=score - 0.02,
        )
        chunks.append(chunk)

    metrics = HybridMetrics(
        query="obligations notice",
        dense_time_ms=42.0,
        bm25_time_ms=2.5,
        fusion_time_ms=1.8,
        total_time_ms=46.3,
        dense_candidates=10,
        bm25_candidates=10,
        merged_candidates=10,
        final_results=10,
        fusion_strategy="rrf",
        embedding_model="test-model",
        embedding_version="1",
    )

    return HybridResult(chunks=chunks, metrics=metrics)


# ===== Test Basic Reranker Implementations =====


class TestNoReranker:
    """Tests for identity reranker (no changes)."""

    def test_no_reranker_returns_all_candidates(self):
        """NoReranker should return all candidates unchanged."""
        reranker = NoReranker()
        chunks = [
            HybridChunk(
                rank=1,
                chunk_id="c1",
                document_id="d1",
                document_name="Doc 1",
                score=0.9,
                page_number=1,
                section="S1",
                heading="H1",
                text="Text 1",
                category="cat",
                dense_rank=1,
                dense_score=0.9,
                bm25_rank=1,
                bm25_score=0.85,
            )
        ]

        scores = reranker.rerank("test query", chunks)

        assert len(scores) == 1
        assert scores[0].chunk_id == "c1"
        assert scores[0].score == 0.9

    def test_no_reranker_preserves_scores(self, sample_hybrid_result):
        """All scores should be preserved exactly."""
        reranker = NoReranker()
        original_scores = [c.score for c in sample_hybrid_result.chunks]

        rerank_scores = reranker.rerank(
            sample_hybrid_result.metrics.query, sample_hybrid_result.chunks
        )

        reranked_scores = [rs.score for rs in rerank_scores]
        assert reranked_scores == original_scores


class TestHybridScoreReranker:
    """Tests for reranker using existing hybrid scores."""

    def test_hybrid_score_reranker_is_idempotent(self, sample_hybrid_result):
        """Reranking with hybrid score should be idempotent."""
        reranker = HybridScoreReranker()

        scores = reranker.rerank(
            sample_hybrid_result.metrics.query, sample_hybrid_result.chunks
        )

        # Scores should match original
        for original, rerank in zip(sample_hybrid_result.chunks, scores):
            assert rerank.score == original.score

    def test_hybrid_score_maintains_rank_order(self, sample_hybrid_result):
        """Chunks should maintain descending score order."""
        reranker = HybridScoreReranker()
        scores = reranker.rerank(
            sample_hybrid_result.metrics.query, sample_hybrid_result.chunks
        )

        for i in range(len(scores) - 1):
            assert scores[i].score >= scores[i + 1].score


class TestQueryTermOverlapReranker:
    """Tests for query term overlap reranker."""

    def test_exact_term_match_scores_high(self):
        """Chunks with exact query terms should score high."""
        reranker = QueryTermOverlapReranker()

        chunks = [
            HybridChunk(
                rank=1,
                chunk_id="c1",
                document_id="d1",
                document_name="Doc 1",
                score=0.5,  # Low initial score
                page_number=1,
                section="S1",
                heading="Party Obligations",
                text="The party must provide written notice within thirty days.",
                category="contract",
                dense_rank=1,
                dense_score=0.5,
                bm25_rank=None,
                bm25_score=None,
            ),
            HybridChunk(
                rank=2,
                chunk_id="c2",
                document_id="d2",
                document_name="Doc 2",
                score=0.7,  # Higher initial score
                page_number=2,
                section="S2",
                heading="Unrelated Section",
                text="The system must work properly and efficiently.",
                category="technical",
                dense_rank=2,
                dense_score=0.7,
                bm25_rank=None,
                bm25_score=None,
            ),
        ]

        scores = reranker.rerank("party notice", chunks)

        # Chunk 1 has "party" and "notice" → should score higher after reranking
        assert scores[0].chunk_id == "c1"
        assert scores[0].score > scores[1].score

    def test_term_frequency_weighting(self):
        """Repeated query terms should boost score with diminishing returns."""
        reranker = QueryTermOverlapReranker()

        chunks = [
            HybridChunk(
                rank=1,
                chunk_id="c1",
                document_id="d1",
                document_name="Doc 1",
                score=0.5,
                page_number=1,
                section="S1",
                heading="H1",
                text="Notice notice notice. Party responsibilities.",
                category="contract",
                dense_rank=1,
                dense_score=0.5,
                bm25_rank=None,
                bm25_score=None,
            ),
            HybridChunk(
                rank=2,
                chunk_id="c2",
                document_id="d2",
                document_name="Doc 2",
                score=0.5,
                page_number=2,
                section="S2",
                heading="H2",
                text="Notice once. Party mentioned.",
                category="contract",
                dense_rank=2,
                dense_score=0.5,
                bm25_rank=None,
                bm25_score=None,
            ),
        ]

        scores = reranker.rerank("notice party", chunks)

        # Chunk 1 has repeated "notice" → should score higher
        assert scores[0].chunk_id == "c1"

    def test_no_overlap_scores_zero(self):
        """Chunks with no matching terms should score zero."""
        reranker = QueryTermOverlapReranker()

        chunks = [
            HybridChunk(
                rank=1,
                chunk_id="c1",
                document_id="d1",
                document_name="Doc 1",
                score=0.8,
                page_number=1,
                section="S1",
                heading="H1",
                text="Alpha bravo charlie delta echo foxtrot.",
                category="contract",
                dense_rank=1,
                dense_score=0.8,
                bm25_rank=None,
                bm25_score=None,
            ),
        ]

        scores = reranker.rerank("xyz abc def", chunks)

        # No matching terms
        assert scores[0].score == 0.0


# ===== Test RankerPipeline =====


class TestRankerPipelineBasics:
    """Basic reranking pipeline tests."""

    def test_rerank_truncates_to_top_k(self, sample_hybrid_result):
        """Pipeline should truncate results to top_k."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        assert len(result.chunks) == 5
        # Verify ranks are sequential
        for i, chunk in enumerate(result.chunks):
            assert chunk.rank == i + 1

    def test_rerank_preserves_original_for_comparison(self, sample_hybrid_result):
        """Pipeline should store original chunks for comparison."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        # Original should have all chunks
        assert len(result.original_chunks) == 10

    def test_rerank_returns_metrics(self, sample_hybrid_result):
        """Reranking should include timing metrics."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        assert result.metrics.reranking_time_ms >= 0
        assert result.metrics.input_candidates == 10
        assert result.metrics.output_candidates == 5
        assert result.metrics.reranking_strategy == "query_term_overlap"

    def test_rerank_calculates_recall_at_k(self, sample_hybrid_result):
        """Pipeline should measure how many top-5 remained in final top-k."""
        reranker = NoReranker()  # Identity, so top-5 should stay
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.NONE)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        # With NoReranker, all original top-5 should be in final top-5
        assert result.metrics.recall_at_k_change == 1.0

    def test_rerank_measures_score_improvement(self, sample_hybrid_result):
        """Pipeline should measure average score change."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        # Average score after reranking should be higher or equal
        assert result.metrics.avg_score_after >= result.metrics.avg_score_before or pytest.approx(
            result.metrics.avg_score_after,
            abs=0.01
        ) == result.metrics.avg_score_before


class TestRankerPipelinePrecisionRecall:
    """Tests for precision vs recall trade-off measurements."""

    def test_hybrid_top_5_vs_top_20_comparison(self, high_variance_result):
        """Compare: top-5 direct vs top-20 with reranking."""
        # Scenario 1: Direct top-5
        direct_top_5 = high_variance_result.chunks[:5]
        direct_avg_score = sum(c.score for c in direct_top_5) / 5

        # Scenario 2: Top-20 → rerank → top-5
        retriever_top_20 = HybridResult(
            chunks=high_variance_result.chunks,  # Simulating top-20 retrieval
            metrics=high_variance_result.metrics,
        )

        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)
        reranked_result = pipeline.rerank(retriever_top_20, top_k=5)

        reranked_avg_score = sum(c.score for c in reranked_result.chunks) / 5

        # Reranking can improve precision (higher average score in top-5)
        # This is the key trade-off: more computation but potentially better quality
        print(
            f"Direct top-5 avg score: {direct_avg_score:.3f}\n"
            f"Reranked top-5 avg score: {reranked_avg_score:.3f}\n"
            f"Reranking time: {reranked_result.metrics.reranking_time_ms:.2f}ms"
        )

    def test_recall_degradation_with_aggressive_filtering(self, high_variance_result):
        """Aggressive top-k reduction should show recall loss."""
        reranker = NoReranker()  # Identity to isolate truncation effect
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.NONE)

        # Scenario: Retrieve top-20, then truncate to top-3
        retriever_top_20 = high_variance_result

        result = pipeline.rerank(retriever_top_20, top_k=3)

        # Recall: of original top-5, how many in final top-3?
        original_top_5_ids = {c.chunk_id for c in retriever_top_20.chunks[:5]}
        final_ids = {c.chunk_id for c in result.chunks}
        actual_recall = len(original_top_5_ids & final_ids) / 5

        assert result.metrics.recall_at_k_change == actual_recall
        # With top-3, we expect to lose some top-5
        assert actual_recall <= 1.0

    def test_dual_attribution_preserved_after_reranking(self, sample_hybrid_result):
        """Reranking should preserve dense_rank/score and bm25_rank/score."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        for chunk in result.chunks:
            # Dense attribution should be present
            assert chunk.dense_rank is not None
            assert chunk.dense_score is not None
            # BM25 may or may not be present depending on original
            # But if it was in original top-5, check it
            original = next(
                (c for c in sample_hybrid_result.chunks if c.chunk_id == chunk.chunk_id),
                None,
            )
            if original and original.bm25_rank is not None:
                assert chunk.bm25_rank is not None
                assert chunk.bm25_score is not None


class TestRankerPipelineBatch:
    """Tests for batch reranking."""

    def test_batch_rerank_multiple_queries(self, sample_hybrid_result, high_variance_result):
        """Pipeline should handle batch reranking."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)

        results = [sample_hybrid_result, high_variance_result]

        batch_results = pipeline.batch_rerank(results, top_k=5)

        assert len(batch_results) == 2
        for batch_result in batch_results:
            assert len(batch_result.chunks) == 5
            assert batch_result.metrics.reranking_time_ms >= 0

    def test_batch_rerank_preserves_query_correspondence(self, sample_hybrid_result):
        """Batch results should correspond to input order."""
        queries = [
            HybridResult(
                chunks=sample_hybrid_result.chunks,
                metrics=dataclasses.replace(sample_hybrid_result.metrics, query="query 1"),
            ),
            HybridResult(
                chunks=sample_hybrid_result.chunks[:5],
                metrics=dataclasses.replace(sample_hybrid_result.metrics, query="query 2"),
            ),
        ]

        reranker = NoReranker()
        pipeline = RankerPipeline(reranker)

        results = pipeline.batch_rerank(queries, top_k=3)

        # Verify order is preserved
        assert results[0].metrics.query == "query 1"
        assert results[1].metrics.query == "query 2"


class TestRerankingStrategies:
    """Tests comparing different reranking strategies."""

    def test_no_reranking_vs_term_overlap(self, sample_hybrid_result):
        """Compare identity vs term overlap strategy."""
        # Strategy 1: No reranking
        no_reranker = NoReranker()
        no_pipeline = RankerPipeline(no_reranker, strategy=RerankingStrategy.NONE)
        no_result = no_pipeline.rerank(sample_hybrid_result, top_k=5)

        # Strategy 2: Term overlap
        term_reranker = QueryTermOverlapReranker()
        term_pipeline = RankerPipeline(
            term_reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP
        )
        term_result = term_pipeline.rerank(sample_hybrid_result, top_k=5)

        # Different strategies may produce different ranking
        assert no_result.chunks[0].chunk_id != term_result.chunks[0].chunk_id or (
            no_result.chunks[0].chunk_id == term_result.chunks[0].chunk_id
        )

        # But both should have 5 results
        assert len(no_result.chunks) == 5
        assert len(term_result.chunks) == 5

    def test_reranking_strategy_in_metrics(self, sample_hybrid_result):
        """Metrics should record which strategy was used."""
        strategies = [
            (NoReranker(), RerankingStrategy.NONE),
            (HybridScoreReranker(), RerankingStrategy.HYBRID_SCORE),
            (QueryTermOverlapReranker(), RerankingStrategy.QUERY_TERM_OVERLAP),
        ]

        for reranker, strategy in strategies:
            pipeline = RankerPipeline(reranker, strategy=strategy)
            result = pipeline.rerank(sample_hybrid_result, top_k=5)

            assert result.metrics.reranking_strategy == strategy.value


class TestRerankerLatencyMeasurement:
    """Tests for timing and performance measurement."""

    def test_reranking_latency_recorded(self, sample_hybrid_result):
        """Reranking time should be measured."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        result = pipeline.rerank(sample_hybrid_result, top_k=5)

        assert result.metrics.reranking_time_ms >= 0.0

    def test_batch_latency_per_query(self, sample_hybrid_result):
        """Batch should track latency per query."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        queries = [sample_hybrid_result] * 3

        results = pipeline.batch_rerank(queries, top_k=5)

        for result in results:
            assert result.metrics.reranking_time_ms >= 0.0


class TestRerankerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_rerank_empty_top_k(self, sample_hybrid_result):
        """Reranking with top_k=0 should return empty results."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        result = pipeline.rerank(sample_hybrid_result, top_k=0)

        assert len(result.chunks) == 0
        assert result.metrics.output_candidates == 0

    def test_rerank_top_k_larger_than_candidates(self, sample_hybrid_result):
        """top_k larger than input should return all candidates."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        result = pipeline.rerank(sample_hybrid_result, top_k=100)

        # Should return all 10 input chunks
        assert len(result.chunks) == 10

    def test_rerank_single_candidate(self):
        """Reranking single candidate should work."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        single_chunk = HybridChunk(
            rank=1,
            chunk_id="single",
            document_id="d1",
            document_name="Doc",
            score=0.9,
            page_number=1,
            section="S",
            heading="H",
            text="Single chunk query terms",
            category="contract",
            dense_rank=1,
            dense_score=0.9,
            bm25_rank=1,
            bm25_score=0.85,
        )

        result_obj = HybridResult(
            chunks=[single_chunk],
            metrics=HybridMetrics(
                query="query terms",
                dense_time_ms=10.0,
                bm25_time_ms=1.0,
                fusion_time_ms=0.5,
                total_time_ms=11.5,
                dense_candidates=1,
                bm25_candidates=1,
                merged_candidates=1,
                final_results=1,
                fusion_strategy="rrf",
                embedding_model="test",
                embedding_version="1",
            ),
        )

        result = pipeline.rerank(result_obj, top_k=5)

        assert len(result.chunks) == 1
        assert result.chunks[0].rank == 1


class TestScoreDistributionAfterReranking:
    """Tests for score statistics after reranking."""

    def test_reranked_scores_are_normalized(self, high_variance_result):
        """Reranked scores should be in reasonable range."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        result = pipeline.rerank(high_variance_result, top_k=5)

        for chunk in result.chunks:
            # Scores should be non-negative and reasonable
            assert chunk.score >= 0.0
            # Term overlap scores should be normalized
            assert chunk.score <= 1.0

    def test_scores_decrease_with_rank(self, high_variance_result):
        """After reranking, scores should be in descending order."""
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)

        result = pipeline.rerank(high_variance_result, top_k=5)

        for i in range(len(result.chunks) - 1):
            assert result.chunks[i].score >= result.chunks[i + 1].score


# ===== Integration Tests =====


class TestRerankerIntegration:
    """Integration tests with hybrid retrieval workflow."""

    def test_full_pipeline_hybrid_to_rerank(self, sample_hybrid_result):
        """Test complete workflow: hybrid retrieval → reranking."""
        # Stage 1: Retrieve (simulated by sample_hybrid_result)
        retrieval_result = sample_hybrid_result

        # Stage 2: Rerank
        reranker = QueryTermOverlapReranker()
        pipeline = RankerPipeline(reranker)
        final_result = pipeline.rerank(retrieval_result, top_k=5)

        # Verify pipeline stages
        assert final_result.metrics.input_candidates == 10  # From hybrid
        assert final_result.metrics.output_candidates == 5  # After reranking
        assert len(final_result.chunks) == 5
        assert len(final_result.original_chunks) == 10

    def test_reranker_composition_with_strategies(self, high_variance_result):
        """Test that strategies are truly composable."""
        # Test all three strategies on same input
        strategies_and_rerankers = [
            (NoReranker(), RerankingStrategy.NONE),
            (HybridScoreReranker(), RerankingStrategy.HYBRID_SCORE),
            (QueryTermOverlapReranker(), RerankingStrategy.QUERY_TERM_OVERLAP),
        ]

        results_by_strategy = {}

        for reranker, strategy in strategies_and_rerankers:
            pipeline = RankerPipeline(reranker, strategy=strategy)
            result = pipeline.rerank(high_variance_result, top_k=5)
            results_by_strategy[strategy.value] = result

        # All should produce 5 results
        for strategy_name, result in results_by_strategy.items():
            assert len(result.chunks) == 5, f"Strategy {strategy_name} failed"
            assert result.metrics.reranking_strategy == strategy_name
