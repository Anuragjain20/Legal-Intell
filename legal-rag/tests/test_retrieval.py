from __future__ import annotations

import pytest

from src.embeddings.base import EmbeddedChunk
from src.ingestion.models import Chunk
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.retrieval.retriever import Retriever
from src.vectorstore.local_store import LocalVectorStore
from src.vectorstore.service import VectorIndexService


class FakeEmbeddingProvider:
    model_name = "fake-model"
    model_version = "1"

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


def make_chunk(chunk_id: str, text: str, page_number: int, heading: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        page_number=page_number,
        end_page_number=page_number,
        section="1",
        heading=heading,
        text=text,
    )


def index_chunks(tmp_path, chunks: list[Chunk]) -> LocalVectorStore:
    provider = FakeEmbeddingProvider()
    embedded = [
        EmbeddedChunk(chunk=chunk, embedding=provider.embed_query(chunk.text), embedding_model=provider.model_name, embedding_version=provider.model_version)
        for chunk in chunks
    ]
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    VectorIndexService(store=store).index_embeddings(embedded)
    return store


def test_relevant_query_ranks_termination_highest(tmp_path):
    store = index_chunks(
        tmp_path,
        [
            make_chunk("a", "Termination requires written notice.", 1, "TERMINATION"),
            make_chunk("b", "Payment is due within 30 days.", 2, "PAYMENT"),
            make_chunk("c", "Confidential information must be protected.", 3, "CONFIDENTIALITY"),
        ],
    )
    retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

    results = retriever.retrieve("What are the termination conditions?", top_k=3)

    assert results[0].record.chunk_id == "a"
    assert results[0].record.heading == "TERMINATION"
    assert results[0].record.page_number == 1


def test_top_k_limits_result_count(tmp_path):
    chunks = [make_chunk(str(i), f"Termination clause {i}.", i + 1, "TERMINATION") for i in range(10)]
    store = index_chunks(tmp_path, chunks)
    retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

    results = retriever.retrieve("termination", top_k=3)

    assert len(results) == 3


def test_metadata_is_preserved_in_results(tmp_path):
    store = index_chunks(
        tmp_path,
        [make_chunk("a", "Termination requires written notice.", 12, "TERMINATION")],
    )
    retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

    result = retriever.retrieve("termination", top_k=1)[0]

    assert result.record.document_id == "doc-1"
    assert result.record.chunk_id == "a"
    assert result.record.page_number == 12
    assert result.record.section == "1"
    assert result.record.heading == "TERMINATION"


def test_threshold_filters_irrelevant_results(tmp_path):
    store = index_chunks(
        tmp_path,
        [make_chunk("a", "Payment is due within 30 days.", 2, "PAYMENT")],
    )
    retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store, similarity_threshold=0.9)

    with pytest.raises(NoRelevantResultsError):
        retriever.retrieve("What are the termination conditions?", top_k=5)


def test_empty_query_is_rejected(tmp_path):
    store = index_chunks(
        tmp_path,
        [make_chunk("a", "Termination requires written notice.", 1, "TERMINATION")],
    )
    retriever = Retriever(embedding_provider=FakeEmbeddingProvider(), vector_store=store)

    with pytest.raises(EmptyQueryError):
        retriever.retrieve("", top_k=5)

