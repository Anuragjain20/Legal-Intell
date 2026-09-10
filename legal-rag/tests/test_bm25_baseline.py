"""Tests for BM25 lexical retrieval baseline."""

from __future__ import annotations

import pytest

from src.retrieval.bm25_baseline import BM25Chunk, BM25Retriever
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.vectorstore.base import VectorRecord


def make_record(
    chunk_id: str,
    text: str,
    page_number: int,
    heading: str,
    document_id: str = "doc-1",
    category: str | None = None,
) -> VectorRecord:
    return VectorRecord(
        chunk_id=chunk_id,
        document_id=document_id,
        vector=[0.1, 0.2, 0.3],
        text=text,
        page_number=page_number,
        section="1",
        heading=heading,
        embedding_model="bge-small-en-v1.5",
        embedding_version="1.0.0",
        document_name=f"Document {document_id}",
        category=category,
    )


class TestBM25RetrieverBasics:
    """Tests for basic BM25 functionality."""

    def test_bm25_rejects_blank_query(self):
        records = [make_record("a", "Section 12.4 defines termination.", 1, "TERMINATION")]
        retriever = BM25Retriever(records)

        with pytest.raises(EmptyQueryError):
            retriever.retrieve_bm25("", top_k=5)

    def test_bm25_returns_chunks(self):
        records = [
            make_record("a", "Section 12.4 defines termination notice.", 1, "TERMINATION"),
            make_record("b", "Section 14.2 covers payment terms.", 2, "PAYMENT"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 12.4", top_k=3)

        assert len(result.chunks) > 0
        assert all(isinstance(chunk, BM25Chunk) for chunk in result.chunks)

    def test_bm25_preserves_metadata(self):
        records = [
            make_record(
                "chunk-xyz",
                "Section 12.4 defines termination.",
                page_number=42,
                heading="TERMINATION CLAUSE",
            )
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 12.4", top_k=1)
        chunk = result.chunks[0]

        assert chunk.chunk_id == "chunk-xyz"
        assert chunk.page_number == 42
        assert chunk.heading == "TERMINATION CLAUSE"
        assert chunk.score >= 0.0


class TestExactIdentifierRetrieval:
    """Tests for exact identifier matching (BM25 strength)."""

    def test_retrieves_section_numbers(self):
        records = [
            make_record("a", "Section 1.1 introduces the agreement.", 1, "INTRO"),
            make_record("b", "Section 12.4 defines termination notice requirements.", 12, "TERMINATION"),
            make_record("c", "Section 14.2 covers payment schedule and terms.", 14, "PAYMENT"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 12.4", top_k=3)

        # Section 12.4 should rank highly
        assert result.chunks[0].chunk_id == "b"
        assert "12.4" in result.chunks[0].text

    def test_retrieves_error_codes(self):
        records = [
            make_record("a", "ERR-4821 indicates authorization failure.", 1, "ERROR"),
            make_record("b", "ERR-5001 indicates network timeout.", 2, "ERROR"),
            make_record("c", "General error handling guidelines.", 3, "ERROR"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("ERR-4821", top_k=3)

        # ERR-4821 should rank highest
        assert result.chunks[0].chunk_id == "a"
        assert "ERR-4821" in result.chunks[0].text

    def test_retrieves_iso_standards(self):
        records = [
            make_record("a", "ISO-27001 information security management standard.", 1, "STANDARDS"),
            make_record("b", "ISO-9001 quality management certification required.", 2, "STANDARDS"),
            make_record("c", "Compliance requirements for security standards.", 3, "STANDARDS"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("ISO-27001", top_k=3)

        # ISO-27001 should rank highest
        assert result.chunks[0].chunk_id == "a"
        assert "ISO-27001" in result.chunks[0].text

    def test_retrieves_reference_codes(self):
        records = [
            make_record("a", "Reference ABC-2026-0042 applies to this clause.", 1, "REF"),
            make_record("b", "Reference ABC-2026-0043 is related.", 2, "REF"),
            make_record("c", "Document contains multiple references.", 3, "REF"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("ABC-2026-0042", top_k=3)

        # Exact reference should rank highest
        assert result.chunks[0].chunk_id == "a"
        assert "ABC-2026-0042" in result.chunks[0].text


class TestBM25Metrics:
    """Tests for BM25 instrumentation."""

    def test_metrics_include_latency(self):
        records = [make_record("a", "Section 12.4 defines termination.", 1, "TERMINATION")]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 12.4", top_k=1)

        assert result.metrics.tokenization_time_ms >= 0
        assert result.metrics.index_search_time_ms >= 0
        assert result.metrics.total_time_ms >= 0

    def test_metrics_include_index_stats(self):
        records = [
            make_record("a", "Section 1.1 intro.", 1, "INTRO"),
            make_record("b", "Section 12.4 termination.", 12, "TERMINATION"),
            make_record("c", "Section 14.2 payment.", 14, "PAYMENT"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section", top_k=3)

        assert result.metrics.index_size == 3
        assert result.metrics.vocabulary_size > 0

    def test_metrics_record_candidate_counts(self):
        records = [
            make_record(f"{i}", f"Section {i} content.", i, f"SECTION {i}") for i in range(10)
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section", top_k=5)

        assert result.metrics.candidates_found >= result.metrics.candidates_above_threshold
        assert result.metrics.candidates_above_threshold > 0

    def test_metrics_preserve_query(self):
        records = [make_record("a", "Section 12.4 defines termination.", 1, "TERMINATION")]
        retriever = BM25Retriever(records)

        query = "Section 12.4"
        result = retriever.retrieve_bm25(query, top_k=1)

        assert result.metrics.query == query


class TestTopKConfigurable:
    """Tests for configurable top-k."""

    def test_top_k_5_returns_up_to_5(self):
        records = [make_record(str(i), f"Section {i} content.", i, f"SECTION {i}") for i in range(20)]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section", top_k=5)

        assert len(result.chunks) <= 5

    def test_top_k_10_returns_up_to_10(self):
        records = [make_record(str(i), f"Section {i} content.", i, f"SECTION {i}") for i in range(20)]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section", top_k=10)

        assert len(result.chunks) <= 10

    def test_top_k_20_returns_up_to_20(self):
        records = [make_record(str(i), f"Section {i} content.", i, f"SECTION {i}") for i in range(25)]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section", top_k=20)

        assert len(result.chunks) <= 20


class TestScorePreservation:
    """Tests that BM25 scores are accurately recorded."""

    def test_scores_are_non_negative(self):
        records = [make_record("a", "Section 12.4 defines termination.", 1, "TERMINATION")]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 12.4", top_k=1)

        for chunk in result.chunks:
            assert chunk.score >= 0.0

    def test_scores_ordered_by_rank(self):
        records = [
            make_record("a", "Section 12.4 termination notice.", 1, "TERMINATION"),
            make_record("b", "Notice requirements in Section 12.", 2, "NOTICE"),
            make_record("c", "Section 14 covers other topics.", 3, "OTHER"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 12.4", top_k=3)

        # Scores should be in descending order
        if len(result.chunks) > 1:
            for i in range(len(result.chunks) - 1):
                assert result.chunks[i].score >= result.chunks[i + 1].score


class TestTermFrequency:
    """Tests for term frequency and document frequency effects."""

    def test_repeated_terms_score_higher(self):
        records = [
            make_record("a", "Termination termination termination clause.", 1, "TERMINATION"),
            make_record("b", "This document covers termination.", 2, "TERMINATION"),
            make_record("c", "Other content.", 3, "OTHER"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("termination", top_k=3)

        # Chunk with more occurrences should rank higher
        assert result.chunks[0].chunk_id == "a"

    def test_rare_terms_are_weighted_higher(self):
        records = [
            make_record("a", "ISO-27001 compliance required.", 1, "STANDARDS"),
            make_record("b", "Management management management system.", 2, "MGMT"),
            make_record("c", "Other content.", 3, "OTHER"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("ISO-27001", top_k=3)

        # Rare term should score high despite lower frequency
        assert result.chunks[0].chunk_id == "a"


class TestMinScoreThreshold:
    """Tests for minimum score threshold."""

    def test_minimum_score_filters_low_scores(self):
        records = [
            make_record("a", "Section 12 content.", 1, "SECTION"),
            make_record("b", "Other content.", 2, "OTHER"),
        ]
        # High minimum score threshold
        retriever = BM25Retriever(records, min_score=1.0)

        result = retriever.retrieve_bm25("Section 12", top_k=5)

        # Some results should pass high threshold
        assert all(chunk.score >= 1.0 for chunk in result.chunks)

    def test_no_results_below_threshold_raises_error(self):
        records = [
            make_record("a", "Some random content.", 1, "RANDOM"),
        ]
        # Very high threshold
        retriever = BM25Retriever(records, min_score=100.0)

        with pytest.raises(NoRelevantResultsError):
            retriever.retrieve_bm25("Section 12", top_k=5)


class TestBatchRetrieval:
    """Tests for batch retrieval."""

    def test_batch_retrieve_processes_multiple_queries(self):
        records = [
            make_record("a", "Section 12.4 termination clause.", 1, "TERMINATION"),
            make_record("b", "Section 14.2 payment terms.", 2, "PAYMENT"),
            make_record("c", "ISO-27001 compliance required.", 3, "STANDARDS"),
        ]
        retriever = BM25Retriever(records)

        queries = ["Section 12.4", "Section 14.2", "ISO-27001"]
        results = retriever.batch_retrieve_bm25(queries, top_k=5)

        assert len(results) == 3
        assert all(result.metrics.query in queries for result in results)

    def test_batch_retrieve_continues_on_failures(self):
        records = [make_record("a", "Section 12.4 termination.", 1, "TERMINATION")]
        retriever = BM25Retriever(records)

        queries = [
            "Section 12.4",
            "",  # Empty query will fail
            "termination",
        ]
        results = retriever.batch_retrieve_bm25(queries, top_k=5)

        # Should get results for valid queries
        assert len(results) >= 2


class TestComplementaryRetrieval:
    """Tests showing BM25 complements dense retrieval."""

    def test_exact_identifier_preferred_over_semantic(self):
        """BM25 finds exact identifiers dense might miss."""
        records = [
            make_record("a", "ERR-4821 indicates authorization failure in the system.", 1, "ERROR"),
            make_record("b", "Authorization failed when user tried to access resource.", 2, "AUTH"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("ERR-4821", top_k=2)

        # Should find exact code, not semantic match
        assert result.chunks[0].chunk_id == "a"
        assert "ERR-4821" in result.chunks[0].text

    def test_rare_terms_preserved(self):
        """BM25 handles rare technical terms better."""
        records = [
            make_record("a", "SCRAM-SHA-256 authentication mechanism.", 1, "AUTH"),
            make_record("b", "Authentication using secure mechanisms.", 2, "AUTH"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("SCRAM-SHA-256", top_k=2)

        # Should find exact technical term
        assert result.chunks[0].chunk_id == "a"


class TestTokenization:
    """Tests for tokenization and term handling."""

    def test_tokenization_preserves_identifiers(self):
        records = [
            make_record("a", "Section 12.4 defines requirements.", 1, "SECTION"),
            make_record("b", "ISO-27001 compliance standard.", 2, "STANDARD"),
            make_record("c", "Reference ERR-4821 error code.", 3, "ERROR"),
        ]
        retriever = BM25Retriever(records)

        # All should retrieve correctly
        for query in ["Section 12.4", "ISO-27001", "ERR-4821"]:
            result = retriever.retrieve_bm25(query, top_k=3)
            assert len(result.chunks) > 0

    def test_case_insensitive_matching(self):
        records = [
            make_record("a", "SECTION 12.4 TERMINATION", 1, "SECTION"),
        ]
        retriever = BM25Retriever(records)

        # Should match regardless of case
        result = retriever.retrieve_bm25("section 12.4", top_k=1)
        assert len(result.chunks) > 0
        assert result.chunks[0].chunk_id == "a"


class TestRetrievalIndependence:
    """Tests that BM25 is independent lexical search."""

    def test_bm25_uses_term_frequency_not_embeddings(self):
        """BM25 relies on term frequency, not semantic embeddings."""
        records = [
            make_record(
                "a",
                "payment payment payment payment payment schedule",
                1,
                "PAYMENT",
            ),
            make_record(
                "b",
                "monetary compensation financial remuneration",
                2,
                "COMPENSATION",
            ),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("payment", top_k=2)

        # Should find exact term match (a), not semantic match (b)
        assert result.chunks[0].chunk_id == "a"

    def test_bm25_different_from_dense(self):
        """Demonstrates BM25 vs dense retrieval differences."""
        # This would typically differ from dense retrieval results
        records = [
            make_record("a", "Section 12.4", 1, "SECTION"),
            make_record("b", "The party must provide notice within 30 days.", 2, "NOTICE"),
        ]
        retriever = BM25Retriever(records)

        # BM25 excels at exact codes
        result = retriever.retrieve_bm25("Section 12.4", top_k=2)
        assert result.chunks[0].chunk_id == "a"


class TestLatencyPerformance:
    """Tests for BM25 latency characteristics."""

    def test_latency_reasonable(self):
        records = [make_record(str(i), f"Section {i} content here.", i, f"SECTION {i}") for i in range(100)]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("Section 50", top_k=10)

        # BM25 should be fast (no embedding needed)
        assert result.metrics.total_time_ms < 100  # Much faster than embedding


class TestDocumentIdScoping:
    """Case-scoped retrieval: restricting candidates via document_ids."""

    def test_document_ids_filter_restricts_results(self):
        records = [
            make_record("a", "Termination clause requires notice.", 1, "TERMINATION", document_id="doc-1"),
            make_record("b", "Termination clause requires notice.", 2, "TERMINATION", document_id="doc-2"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("termination notice", top_k=5, document_ids=["doc-1"])

        doc_ids = {chunk.document_id for chunk in result.chunks}
        assert doc_ids == {"doc-1"}

    def test_document_ids_none_is_unfiltered(self):
        records = [
            make_record("a", "Termination clause requires notice.", 1, "TERMINATION", document_id="doc-1"),
            make_record("b", "Termination clause requires notice.", 2, "TERMINATION", document_id="doc-2"),
        ]
        retriever = BM25Retriever(records)

        result = retriever.retrieve_bm25("termination notice", top_k=5, document_ids=None)

        doc_ids = {chunk.document_id for chunk in result.chunks}
        assert doc_ids == {"doc-1", "doc-2"}

    def test_document_ids_filter_can_empty_results(self):
        records = [make_record("a", "Termination clause requires notice.", 1, "TERMINATION", document_id="doc-1")]
        retriever = BM25Retriever(records)

        with pytest.raises(NoRelevantResultsError):
            retriever.retrieve_bm25("termination notice", top_k=5, document_ids=["doc-does-not-exist"])
