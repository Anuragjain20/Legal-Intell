"""Tests for retrieval evaluation metrics.

Covers:
- Recall@K
- Precision@K
- MRR (Mean Reciprocal Rank)
- nDCG (Normalized Discounted Cumulative Gain)
"""

import pytest
from src.evaluation.metrics import (
    calculate_all_metrics,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_k,
    find_first_relevant_rank,
)


class TestRecallAtK:
    """Tests for Recall@K metric."""

    def test_recall_all_relevant_found(self):
        """If all relevant chunks in top-k, recall is 1.0."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3", "chunk-4", "chunk-5"]

        recall = calculate_recall_at_k(relevant, retrieved, k=5)

        assert recall == 1.0

    def test_recall_some_relevant_found(self):
        """If some relevant chunks in top-k, recall is partial."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-4", "chunk-5", "chunk-6", "chunk-7"]

        recall = calculate_recall_at_k(relevant, retrieved, k=5)

        # 1 out of 3 relevant chunks found
        assert recall == pytest.approx(1.0 / 3.0)

    def test_recall_none_found(self):
        """If no relevant chunks in top-k, recall is 0.0."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-4", "chunk-5", "chunk-6"]

        recall = calculate_recall_at_k(relevant, retrieved, k=5)

        assert recall == 0.0

    def test_recall_empty_relevant(self):
        """If no relevant chunks expected, recall is 1.0."""
        relevant = []
        retrieved = ["chunk-1", "chunk-2"]

        recall = calculate_recall_at_k(relevant, retrieved, k=5)

        assert recall == 1.0

    def test_recall_truncates_at_k(self):
        """Recall should only consider top-k results."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-3", "chunk-4", "chunk-1", "chunk-2"]  # Relevant at 3,4

        recall_at_2 = calculate_recall_at_k(relevant, retrieved, k=2)
        recall_at_4 = calculate_recall_at_k(relevant, retrieved, k=4)

        assert recall_at_2 == 0.0  # Not in top-2
        assert recall_at_4 == 1.0  # Found in top-4

    def test_recall_handles_duplicates(self):
        """Duplicates in retrieved should be handled correctly."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-1", "chunk-1", "chunk-2"]  # Duplicate chunk-1

        recall = calculate_recall_at_k(relevant, retrieved, k=3)

        assert recall == 1.0  # Both relevant chunks present

    def test_recall_at_different_k_values(self):
        """Recall should increase (or stay same) as k increases."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-4", "chunk-5", "chunk-1", "chunk-2", "chunk-3"]

        recall_5 = calculate_recall_at_k(relevant, retrieved, k=5)
        recall_3 = calculate_recall_at_k(relevant, retrieved, k=3)
        recall_2 = calculate_recall_at_k(relevant, retrieved, k=2)

        assert recall_5 >= recall_3 >= recall_2


class TestPrecisionAtK:
    """Tests for Precision@K metric."""

    def test_precision_all_relevant(self):
        """If all top-k are relevant, precision is 1.0."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3", "chunk-4"]

        precision = calculate_precision_at_k(relevant, retrieved, k=3)

        assert precision == 1.0

    def test_precision_half_relevant(self):
        """If half of top-k are relevant, precision is 0.5."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-1", "chunk-3", "chunk-2", "chunk-4"]

        precision = calculate_precision_at_k(relevant, retrieved, k=4)

        # 2 out of 4 are relevant
        assert precision == 0.5

    def test_precision_none_relevant(self):
        """If none of top-k are relevant, precision is 0.0."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-2", "chunk-3", "chunk-4"]

        precision = calculate_precision_at_k(relevant, retrieved, k=3)

        assert precision == 0.0

    def test_precision_empty_k(self):
        """Precision at k=0 should be 0.0."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-1"]

        precision = calculate_precision_at_k(relevant, retrieved, k=0)

        assert precision == 0.0

    def test_precision_differs_from_recall(self):
        """Precision and recall measure different things."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-4", "chunk-5", "chunk-2", "chunk-6"]

        precision = calculate_precision_at_k(relevant, retrieved, k=5)
        recall = calculate_recall_at_k(relevant, retrieved, k=5)

        # Precision: 2/5 = 0.4
        # Recall: 2/3 ≈ 0.667
        assert precision == 0.4
        assert recall == pytest.approx(2.0 / 3.0)
        assert precision != recall


class TestMRR:
    """Tests for Mean Reciprocal Rank."""

    def test_mrr_first_result_relevant(self):
        """If first result is relevant, MRR is 1.0."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        mrr = calculate_mrr(relevant, retrieved)

        assert mrr == 1.0

    def test_mrr_second_result_relevant(self):
        """If second result is first relevant, MRR is 0.5."""
        relevant = ["chunk-2"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        mrr = calculate_mrr(relevant, retrieved)

        assert mrr == 0.5

    def test_mrr_third_result_relevant(self):
        """If third result is first relevant, MRR is 0.333."""
        relevant = ["chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        mrr = calculate_mrr(relevant, retrieved)

        assert mrr == pytest.approx(1.0 / 3.0)

    def test_mrr_no_relevant(self):
        """If no relevant result, MRR is 0.0."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-2", "chunk-3", "chunk-4"]

        mrr = calculate_mrr(relevant, retrieved)

        assert mrr == 0.0

    def test_mrr_multiple_relevant_uses_first(self):
        """MRR uses only the first relevant result."""
        relevant = ["chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        mrr = calculate_mrr(relevant, retrieved)

        # First relevant is chunk-2 at rank 2
        assert mrr == 0.5

    def test_mrr_ignores_position_after_first(self):
        """Position of other relevant results doesn't matter."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved_a = ["chunk-1", "chunk-4", "chunk-2", "chunk-3"]
        retrieved_b = ["chunk-1", "chunk-2", "chunk-3", "chunk-4"]

        mrr_a = calculate_mrr(relevant, retrieved_a)
        mrr_b = calculate_mrr(relevant, retrieved_b)

        # Both have first relevant at rank 1
        assert mrr_a == 1.0
        assert mrr_b == 1.0


class TestNDCG:
    """Tests for Normalized Discounted Cumulative Gain."""

    def test_ndcg_perfect_ranking(self):
        """If all relevant results first, nDCG is 1.0."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3", "chunk-4", "chunk-5"]

        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=5)

        assert ndcg == 1.0

    def test_ndcg_reversed_ranking(self):
        """If relevant results last, nDCG is low."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-2", "chunk-3", "chunk-1", "chunk-4", "chunk-5"]

        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=5)

        # Relevant at rank 3: relevance / log2(4) = 1 / 2 = 0.5
        # IDCG = 1 / log2(2) = 1 / 1 = 1
        # nDCG = 0.5 / 1 = 0.5
        assert ndcg == pytest.approx(0.5)

    def test_ndcg_no_relevant(self):
        """If no relevant results, nDCG is 0.0."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-2", "chunk-3", "chunk-4"]

        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=5)

        assert ndcg == 0.0

    def test_ndcg_empty_relevant(self):
        """If no relevant chunks expected, nDCG is 1.0."""
        relevant = []
        retrieved = ["chunk-1", "chunk-2"]

        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=5)

        assert ndcg == 1.0

    def test_ndcg_multiple_relevant(self):
        """nDCG considers all relevant results in ranking order."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=3)

        # Perfect ordering
        assert ndcg == 1.0

    def test_ndcg_partial_relevant(self):
        """nDCG with partial relevant chunks."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-1", "chunk-3", "chunk-2"]

        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=3)

        # DCG = 1/log2(2) + 1/log2(4) = 1 + 0.5 = 1.5
        # IDCG = 1/log2(2) + 1/log2(3) = 1 + 0.631 = 1.631
        # nDCG = 1.5 / 1.631 ≈ 0.92
        assert ndcg == pytest.approx(1.5 / 1.631, rel=0.01)

    def test_ndcg_truncates_at_k(self):
        """nDCG should only consider top-k results."""
        relevant = ["chunk-10"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3", "chunk-10"]

        ndcg_at_3 = calculate_ndcg_at_k(relevant, retrieved, k=3)
        ndcg_at_4 = calculate_ndcg_at_k(relevant, retrieved, k=4)

        # At k=3, chunk-10 not in top-3, so DCG=0
        assert ndcg_at_3 == 0.0
        # At k=4, chunk-10 at rank 4
        assert ndcg_at_4 > 0.0

    def test_ndcg_different_k_values(self):
        """nDCG with different k values."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        ndcg_5 = calculate_ndcg_at_k(relevant, retrieved, k=5)
        ndcg_2 = calculate_ndcg_at_k(relevant, retrieved, k=2)

        # Both should have perfect ordering up to k=2
        assert ndcg_2 == 1.0
        assert ndcg_5 == 1.0


class TestFirstRelevantRank:
    """Tests for finding first relevant rank."""

    def test_first_rank_is_relevant(self):
        """If first result is relevant, return rank 1."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-1", "chunk-2"]

        rank = find_first_relevant_rank(relevant, retrieved)

        assert rank == 1

    def test_third_rank_is_relevant(self):
        """If third result is first relevant, return rank 3."""
        relevant = ["chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        rank = find_first_relevant_rank(relevant, retrieved)

        assert rank == 3

    def test_no_relevant_found(self):
        """If no relevant result, return None."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-2", "chunk-3"]

        rank = find_first_relevant_rank(relevant, retrieved)

        assert rank is None

    def test_uses_first_relevant_only(self):
        """Only uses first relevant, ignores others."""
        relevant = ["chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-2", "chunk-3"]

        rank = find_first_relevant_rank(relevant, retrieved)

        # First relevant is chunk-2 at rank 2
        assert rank == 2


class TestAllMetrics:
    """Tests for calculate_all_metrics."""

    def test_calculates_all_k_values(self):
        """Should calculate metrics for k=5, 10, 20."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-1"] + ["chunk-x"] * 15 + ["chunk-2"]

        metrics = calculate_all_metrics(relevant, retrieved)

        # Should have metrics for k=5, 10, 20
        assert "recall_at_5" in metrics
        assert "recall_at_10" in metrics
        assert "recall_at_20" in metrics
        assert "precision_at_5" in metrics
        assert "precision_at_10" in metrics
        assert "precision_at_20" in metrics
        assert "mrr" in metrics
        assert "ndcg_at_5" in metrics
        assert "ndcg_at_10" in metrics
        assert "ndcg_at_20" in metrics

    def test_metric_values_reasonable(self):
        """Metrics should be in valid ranges."""
        relevant = ["chunk-1", "chunk-2", "chunk-3"]
        retrieved = ["chunk-1", "chunk-4", "chunk-2", "chunk-5", "chunk-3"]

        metrics = calculate_all_metrics(relevant, retrieved)

        # Recall should be in [0, 1]
        assert 0.0 <= metrics["recall_at_5"] <= 1.0
        # Precision should be in [0, 1]
        assert 0.0 <= metrics["precision_at_5"] <= 1.0
        # MRR should be in [0, 1]
        assert 0.0 <= metrics["mrr"] <= 1.0
        # nDCG should be in [0, 1]
        assert 0.0 <= metrics["ndcg_at_5"] <= 1.0

    def test_first_relevant_rank_calculated(self):
        """first_relevant_rank should be calculated."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-x", "chunk-1"]

        metrics = calculate_all_metrics(relevant, retrieved)

        assert metrics["first_relevant_rank"] == 2


class TestMetricsEdgeCases:
    """Edge cases and special scenarios."""

    def test_single_relevant_single_retrieved(self):
        """Single query and single result."""
        relevant = ["chunk-1"]
        retrieved = ["chunk-1"]

        recall = calculate_recall_at_k(relevant, retrieved, k=1)
        precision = calculate_precision_at_k(relevant, retrieved, k=1)
        mrr = calculate_mrr(relevant, retrieved)
        ndcg = calculate_ndcg_at_k(relevant, retrieved, k=1)

        assert recall == 1.0
        assert precision == 1.0
        assert mrr == 1.0
        assert ndcg == 1.0

    def test_many_relevant(self):
        """Query with many relevant results."""
        relevant = [f"chunk-{i}" for i in range(100)]
        retrieved = [f"chunk-{i}" for i in range(50)]

        recall_5 = calculate_recall_at_k(relevant, retrieved, k=5)
        recall_10 = calculate_recall_at_k(relevant, retrieved, k=10)
        recall_20 = calculate_recall_at_k(relevant, retrieved, k=20)

        # Every retrieved item is relevant, but only a fraction of the 100
        # relevant items are ever retrieved, so recall stays low - this is
        # Recall@K (share of *all* relevant items found), not Precision@K.
        assert recall_5 == 5 / 100
        assert recall_10 == 10 / 100
        assert recall_20 == 20 / 100

    def test_large_k(self):
        """K larger than result set."""
        relevant = ["chunk-1", "chunk-2"]
        retrieved = ["chunk-1", "chunk-2"]

        recall = calculate_recall_at_k(relevant, retrieved, k=1000)
        precision = calculate_precision_at_k(relevant, retrieved, k=1000)

        assert recall == 1.0
        # Precision decreases with larger k
        assert precision == 2.0 / 1000.0

    def test_order_independent_recall_precision(self):
        """Order of chunks in retrieved matters for MRR/nDCG."""
        relevant = ["chunk-1"]
        retrieved_a = ["chunk-1", "chunk-2"]
        retrieved_b = ["chunk-2", "chunk-1"]

        # Recall and precision same regardless of order
        assert calculate_recall_at_k(relevant, retrieved_a) == calculate_recall_at_k(
            relevant, retrieved_b
        )
        assert calculate_precision_at_k(relevant, retrieved_a) == calculate_precision_at_k(
            relevant, retrieved_b
        )

        # But MRR/nDCG different
        assert calculate_mrr(relevant, retrieved_a) == 1.0
        assert calculate_mrr(relevant, retrieved_b) == 0.5
