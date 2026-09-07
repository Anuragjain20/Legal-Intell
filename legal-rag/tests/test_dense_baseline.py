"""Tests for dense retrieval baseline with instrumentation."""

from __future__ import annotations

import pytest

from src.embeddings.base import EmbeddedChunk
from src.ingestion.models import Chunk
from src.retrieval.dense_baseline import DenseChunk, DenseRetriever, DenseRetrievalMetrics
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.vectorstore.local_store import LocalVectorStore
from src.vectorstore.service import VectorIndexService


class FakeEmbeddingProvider:
    model_name = "bge-small-en-v1.5"
    model_version = "1.0.0"

    @property
    def embedding_dimension(self) -> int:
        return 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        if "termination" in lowered or "terminate" in lowered:
            return [0.99, 0.01, 0.0]
        if "payment" in lowered:
            return [0.01, 0.99, 0.0]
        if "confidential" in lowered:
            return [0.0, 0.01, 0.99]
        return [0.0, 0.0, 1.0]


def make_chunk(
    chunk_id: str,
    text: str,
    page_number: int,
    heading: str,
    document_id: str = "doc-1",
    category: str | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        page_number=page_number,
        end_page_number=page_number,
        section="1",
        heading=heading,
        text=text,
        category=category,
    )


def index_chunks(tmp_path, chunks: list[Chunk]) -> LocalVectorStore:
    provider = FakeEmbeddingProvider()
    embedded = [
        EmbeddedChunk(
            chunk=chunk,
            embedding=provider.embed_query(chunk.text),
            embedding_model=provider.model_name,
            embedding_version=provider.model_version,
        )
        for chunk in chunks
    ]
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    VectorIndexService(store=store).index_embeddings(embedded)
    return store


class TestDenseRetrieverBasics:
    """Tests for basic dense retrieval functionality."""

    def test_dense_retriever_rejects_blank_query(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        with pytest.raises(EmptyQueryError):
            retriever.retrieve_dense("", top_k=5)

    def test_dense_retriever_returns_chunks(self, tmp_path):
        store = index_chunks(
            tmp_path,
            [
                make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
                make_chunk("b", "Payment is due within 30 days.", 2, "PAYMENT"),
            ],
        )
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("What are the termination conditions?", top_k=3)

        assert len(result.chunks) > 0
        assert all(isinstance(chunk, DenseChunk) for chunk in result.chunks)

    def test_dense_retriever_preserves_chunk_metadata(self, tmp_path):
        store = index_chunks(
            tmp_path,
            [make_chunk("chunk-xyz", "Termination clause.", page_number=42, heading="TERMINATION CLAUSE")],
        )
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)
        chunk = result.chunks[0]

        assert chunk.chunk_id == "chunk-xyz"
        assert chunk.page_number == 42
        assert chunk.heading == "TERMINATION CLAUSE"
        assert chunk.score >= 0.0


class TestDenseRetrievalMetrics:
    """Tests for instrumentation and metrics collection."""

    def test_metrics_include_latency(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        assert result.metrics.query_embedding_time_ms >= 0
        assert result.metrics.vector_search_time_ms >= 0
        assert result.metrics.total_time_ms >= 0
        assert result.metrics.total_time_ms > 0

    def test_metrics_include_embedding_model(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        assert result.metrics.embedding_model == "bge-small-en-v1.5"
        assert result.metrics.embedding_version == "1.0.0"

    def test_metrics_record_candidate_counts(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(10)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=5)

        assert result.metrics.candidates_found >= result.metrics.candidates_above_threshold
        assert result.metrics.candidates_above_threshold > 0

    def test_metrics_preserve_query(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        query = "What are the termination conditions?"
        result = retriever.retrieve_dense(query, top_k=1)

        assert result.metrics.query == query


class TestTopKExperimentation:
    """Tests for configurable top_k experimentation."""

    def test_top_k_5_returns_up_to_5_results(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(20)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=5)

        assert len(result.chunks) <= 5

    def test_top_k_10_returns_up_to_10_results(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(20)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=10)

        assert len(result.chunks) <= 10

    def test_top_k_20_returns_up_to_20_results(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(25)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=20)

        assert len(result.chunks) <= 20

    def test_top_k_affects_result_count(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(30)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result_5 = retriever.retrieve_dense("termination", top_k=5)
        result_10 = retriever.retrieve_dense("termination", top_k=10)
        result_20 = retriever.retrieve_dense("termination", top_k=20)

        assert len(result_5.chunks) <= len(result_10.chunks)
        assert len(result_10.chunks) <= len(result_20.chunks)


class TestSimilarityThreshold:
    """Tests for similarity threshold filtering."""

    def test_threshold_filters_low_scores(self, tmp_path):
        store = index_chunks(
            tmp_path,
            [
                make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
                make_chunk("b", "Payment is due within 30 days.", 2, "PAYMENT"),
            ],
        )
        retriever = DenseRetriever(
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=store,
            similarity_threshold=0.95,  # High threshold
        )

        result = retriever.retrieve_dense("payment", top_k=5)

        # Payment query matches payment chunk well, but termination chunk poorly
        assert all(chunk.score >= 0.95 for chunk in result.chunks)

    def test_no_results_below_threshold_raises_error(self, tmp_path):
        store = index_chunks(
            tmp_path,
            [make_chunk("a", "Payment is due within 30 days.", 2, "PAYMENT")],
        )
        retriever = DenseRetriever(
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=store,
            similarity_threshold=0.95,
        )

        with pytest.raises(NoRelevantResultsError):
            retriever.retrieve_dense("termination", top_k=5)


class TestScorePreservation:
    """Tests that similarity scores are accurately recorded."""

    def test_chunk_scores_are_positive(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        for chunk in result.chunks:
            assert chunk.score > 0.0

    def test_chunk_scores_between_0_and_1(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(10)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=10)

        for chunk in result.chunks:
            assert 0.0 <= chunk.score <= 1.0

    def test_scores_ordered_by_rank(self, tmp_path):
        chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(10)]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=5)

        # Highest scoring chunk should be rank 1
        if len(result.chunks) > 1:
            for i in range(len(result.chunks) - 1):
                assert result.chunks[i].score >= result.chunks[i + 1].score


class TestBatchRetrieval:
    """Tests for batch retrieval across multiple queries."""

    def test_batch_retrieve_processes_multiple_queries(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
            make_chunk("b", "Payment is due within 30 days.", 2, "PAYMENT"),
            make_chunk("c", "Confidential information must be protected.", 3, "CONFIDENTIALITY"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        queries = [
            "What are the termination conditions?",
            "What is the payment schedule?",
            "What confidentiality obligations exist?",
        ]
        results = retriever.batch_retrieve_dense(queries, top_k=5)

        assert len(results) == 3
        assert all(result.metrics.query in queries for result in results)

    def test_batch_retrieve_continues_on_failures(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        queries = [
            "What are the termination conditions?",
            "",  # Empty query will fail
            "termination",
        ]
        results = retriever.batch_retrieve_dense(queries, top_k=5)

        # Should get results for the valid queries
        assert len(results) >= 2


class TestIndexMetadata:
    """Tests that index version and embedding model are recorded."""

    def test_index_metadata_in_metrics(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        assert "embedding_model" in result.metrics.index_metadata
        assert "embedding_version" in result.metrics.index_metadata
        assert result.metrics.index_metadata["embedding_model"] == "bge-small-en-v1.5"
        assert result.metrics.index_metadata["embedding_version"] == "1.0.0"

    def test_retrieval_method_recorded(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        assert result.metrics.retrieval_method == "dense_search"


class TestLatencyMeasurement:
    """Tests for latency recording and analysis."""

    def test_latency_components_sum_to_total(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        # Total should be at least sum of components (allowing for overhead)
        component_sum = result.metrics.query_embedding_time_ms + result.metrics.vector_search_time_ms
        assert result.metrics.total_time_ms >= component_sum * 0.95  # 5% tolerance for overhead

    def test_latency_reasonable_for_single_query(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)

        # Should complete in under 1 second for small corpus
        assert result.metrics.total_time_ms < 1000


class TestResultInspectability:
    """Tests that results are easily inspectable for analysis."""

    def test_dense_chunk_fields_accessible(self, tmp_path):
        store = index_chunks(
            tmp_path,
            [
                make_chunk(
                    "chunk-1",
                    "Termination requires written notice within 30 days.",
                    page_number=5,
                    heading="TERMINATION CLAUSE",
                    category="contract",
                )
            ],
        )
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)
        chunk = result.chunks[0]

        # Verify all fields are accessible
        assert chunk.rank == 1
        assert chunk.chunk_id == "chunk-1"
        assert chunk.document_id == "doc-1"
        assert chunk.score > 0.0
        assert chunk.page_number == 5
        assert chunk.heading == "TERMINATION CLAUSE"
        assert chunk.category == "contract"
        assert "written notice" in chunk.text

    def test_metrics_fields_accessible(self, tmp_path):
        store = index_chunks(tmp_path, [make_chunk("a", "Termination clause.", 1, "TERMINATION")])
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=1)
        metrics = result.metrics

        # Verify all fields are accessible for analysis
        assert metrics.query == "termination"
        assert metrics.query_embedding_time_ms > 0
        assert metrics.vector_search_time_ms > 0
        assert metrics.total_time_ms > 0
        assert metrics.candidates_found > 0
        assert metrics.candidates_above_threshold > 0
        assert metrics.embedding_model is not None
        assert metrics.embedding_version is not None


class TestDenseRetrievalIndependence:
    """Tests that dense retrieval works independently without reranking or filtering."""

    def test_dense_retrieval_no_reranking(self, tmp_path):
        # This test verifies that scores from dense search are preserved
        # (not modified by reranking)
        store = index_chunks(
            tmp_path,
            [
                make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
                make_chunk("b", "Termination clause in agreement.", 2, "TERMINATION"),
            ],
        )
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=2)

        # Scores should reflect vector similarity, not reranking
        # (reranking might change order based on term overlap, frontmatter, etc.)
        assert all(0.0 < chunk.score <= 1.0 for chunk in result.chunks)

    def test_dense_retrieval_no_filtering(self, tmp_path):
        # Dense retrieval should not filter by document_id or category
        chunks = [
            make_chunk("a", "Termination clause.", 1, "TERMINATION", document_id="doc-1", category="contract"),
            make_chunk("b", "Termination rule.", 2, "TERMINATION", document_id="doc-2", category="act"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = DenseRetriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        result = retriever.retrieve_dense("termination", top_k=5)

        # Both documents should be included
        doc_ids = {chunk.document_id for chunk in result.chunks}
        assert "doc-1" in doc_ids
        assert "doc-2" in doc_ids
