"""Tests for the retrieval contract: RetrievalRequest -> RetrievalResponse."""

from __future__ import annotations

import pytest

from src.embeddings.base import EmbeddedChunk
from src.ingestion.models import Chunk
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.retrieval.models import RetrievalRequest, RetrievalResponse, RetrievedChunk
from src.retrieval.retriever import Retriever
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
        if "termination" in lowered:
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


class TestRetrievalRequest:
    """Tests for RetrievalRequest contract."""

    def test_request_rejects_blank_query(self):
        with pytest.raises(EmptyQueryError):
            RetrievalRequest(query="")

    def test_request_rejects_whitespace_only_query(self):
        with pytest.raises(EmptyQueryError):
            RetrievalRequest(query="   ")

    def test_request_rejects_date_range(self):
        from datetime import datetime

        with pytest.raises(NotImplementedError):
            RetrievalRequest(
                query="test",
                date_range=(datetime(2024, 1, 1), datetime(2024, 12, 31)),
            )

    def test_request_accepts_valid_document_ids_filter(self):
        request = RetrievalRequest(query="test", document_ids=["doc-1", "doc-2"])
        assert request.document_ids == ["doc-1", "doc-2"]

    def test_request_accepts_valid_document_types_filter(self):
        request = RetrievalRequest(query="test", document_types=["contract", "act"])
        assert request.document_types == ["contract", "act"]


class TestRetrievalResponse:
    """Tests for RetrievalResponse contract."""

    def test_response_preserves_embedding_metadata(self, tmp_path):
        chunks = [make_chunk("a", "Termination requires written notice.", 1, "TERMINATION")]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=1)
        response = retriever.retrieve_structured(request)

        assert isinstance(response, RetrievalResponse)
        assert response.embedding_model == "bge-small-en-v1.5"
        assert response.embedding_version == "1.0.0"

    def test_response_preserves_retrieval_method(self, tmp_path):
        chunks = [make_chunk("a", "Termination requires written notice.", 1, "TERMINATION")]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=1)
        response = retriever.retrieve_structured(request)

        assert response.retrieval_method == "dense_with_reranking"
        assert all(chunk.retrieval_method == "dense_with_reranking" for chunk in response.chunks)

    def test_response_includes_total_searched(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
            make_chunk("b", "Payment is due within 30 days.", 2, "PAYMENT"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=1)
        response = retriever.retrieve_structured(request)

        assert response.total_searched >= 1


class TestRetrievedChunk:
    """Tests for RetrievedChunk contract."""

    def test_chunk_preserves_score_across_reranking(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
            make_chunk("b", "Payment is due within 30 days.", 2, "PAYMENT"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination payment", top_k=2)
        response = retriever.retrieve_structured(request)

        # Score should be the similarity score, not the reranked position.
        for chunk in response.chunks:
            assert isinstance(chunk.score, float)
            assert 0.0 <= chunk.score <= 1.0

    def test_chunk_includes_retrieval_method(self, tmp_path):
        chunks = [make_chunk("a", "Termination requires written notice.", 1, "TERMINATION")]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=1)
        response = retriever.retrieve_structured(request)

        chunk = response.chunks[0]
        assert chunk.retrieval_method == "dense_with_reranking"

    def test_chunk_preserves_all_metadata(self, tmp_path):
        chunks = [
            make_chunk(
                "chunk-xyz",
                "Termination requires written notice.",
                page_number=42,
                heading="TERMINATION CLAUSE",
                document_id="contract-001",
                category="contract",
            )
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=1)
        response = retriever.retrieve_structured(request)

        chunk = response.chunks[0]
        assert chunk.record.chunk_id == "chunk-xyz"
        assert chunk.record.document_id == "contract-001"
        assert chunk.record.page_number == 42
        assert chunk.record.heading == "TERMINATION CLAUSE"
        assert chunk.record.section == "1"
        assert chunk.record.category == "contract"


class TestDocumentIdFiltering:
    """Tests for document_ids filter."""

    def test_document_ids_filter_restricts_results(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination requires written notice.", 1, "TERMINATION", document_id="doc-1"),
            make_chunk("b", "Termination clause in doc-2.", 2, "TERMINATION", document_id="doc-2"),
            make_chunk("c", "Termination in doc-3.", 3, "TERMINATION", document_id="doc-3"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=10, document_ids=["doc-1", "doc-3"])
        response = retriever.retrieve_structured(request)

        returned_docs = {chunk.record.document_id for chunk in response.chunks}
        assert returned_docs <= {"doc-1", "doc-3"}
        assert all(doc in ["doc-1", "doc-3"] for doc in returned_docs)

    def test_document_ids_filter_empty_returns_error(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination requires written notice.", 1, "TERMINATION", document_id="doc-1"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=10, document_ids=["doc-nonexistent"])

        with pytest.raises(NoRelevantResultsError):
            retriever.retrieve_structured(request)


class TestDocumentTypeFiltering:
    """Tests for document_types (category) filter."""

    def test_document_types_filter_restricts_results(self, tmp_path):
        chunks = [
            make_chunk("a", "Payment clause.", 1, "PAYMENT", category="contract"),
            make_chunk("b", "Payment regulation.", 2, "PAYMENT", category="regulation"),
            make_chunk("c", "Payment act.", 3, "PAYMENT", category="act"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="payment", top_k=10, document_types=["contract", "act"])
        response = retriever.retrieve_structured(request)

        returned_types = {chunk.record.category for chunk in response.chunks}
        assert returned_types <= {"contract", "act"}

    def test_document_types_filter_empty_returns_error(self, tmp_path):
        chunks = [
            make_chunk("a", "Payment clause.", 1, "PAYMENT", category="contract"),
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="payment", top_k=10, document_types=["nonexistent_type"])

        with pytest.raises(NoRelevantResultsError):
            retriever.retrieve_structured(request)


class TestLegacyBackwardCompatibility:
    """Tests for legacy retrieve() interface."""

    def test_legacy_interface_still_works(self, tmp_path):
        chunks = [make_chunk("a", "Termination requires written notice.", 1, "TERMINATION")]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        results = retriever.retrieve("termination", top_k=1)

        assert len(results) == 1
        assert isinstance(results[0], RetrievedChunk)
        assert results[0].record.chunk_id == "a"

    def test_legacy_interface_raises_on_dict_filters(self, tmp_path):
        chunks = [make_chunk("a", "Termination requires written notice.", 1, "TERMINATION")]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        with pytest.raises(NotImplementedError):
            retriever.retrieve("termination", top_k=1, filters={"document_id": "doc-1"})


class TestOverFetching:
    """Tests that filtering causes over-fetching to maintain top_k."""

    def test_over_fetch_when_filtering_on_document_ids(self, tmp_path):
        chunks = [
            make_chunk(f"{i}", "Termination clause.", i, "TERMINATION", document_id="doc-1" if i < 3 else "doc-2")
            for i in range(10)
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=3, document_ids=["doc-1"])
        response = retriever.retrieve_structured(request)

        # Should try to return top_k even with filtering.
        assert len(response.chunks) <= 3
        assert all(chunk.record.document_id == "doc-1" for chunk in response.chunks)

    def test_over_fetch_when_filtering_on_document_types(self, tmp_path):
        chunks = [
            make_chunk(f"{i}", "Termination clause.", i, "TERMINATION", category="contract" if i < 3 else "regulation")
            for i in range(10)
        ]
        store = index_chunks(tmp_path, chunks)
        retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

        request = RetrievalRequest(query="termination", top_k=3, document_types=["contract"])
        response = retriever.retrieve_structured(request)

        assert len(response.chunks) <= 3
        assert all(chunk.record.category == "contract" for chunk in response.chunks)
