"""Tests for HybridQueryRetriever's document_ids filtering (case-scoped retrieval)."""

from __future__ import annotations

import pytest

from src.embeddings.base import EmbeddedChunk
from src.ingestion.models import Chunk
from src.retrieval.bm25_baseline import BM25Retriever
from src.retrieval.dense_baseline import DenseRetriever
from src.retrieval.hybrid_query_retriever import HybridQueryRetriever
from src.retrieval.hybrid_retrieval import HybridRetriever
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
        return [0.0, 0.0, 1.0]


def make_chunk(chunk_id: str, text: str, document_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        page_number=1,
        end_page_number=1,
        section="1",
        heading="TERMINATION",
        text=text,
    )


def build_retriever(tmp_path, chunks: list[Chunk]) -> HybridQueryRetriever:
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

    dense_retriever = DenseRetriever(embedding_provider=provider, vector_store=store, similarity_threshold=0.0)
    bm25_retriever = BM25Retriever(chunks=[store.get_by_chunk_id(c.chunk_id) for c in chunks])
    hybrid_retriever = HybridRetriever(dense_retriever=dense_retriever, bm25_retriever=bm25_retriever)
    return HybridQueryRetriever(hybrid_retriever=hybrid_retriever, similarity_threshold=0.0)


class TestDocumentIdsFilter:
    def test_filters_narrows_to_case_documents(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination clause requires notice.", document_id="doc-1"),
            make_chunk("b", "Termination clause requires notice.", document_id="doc-2"),
        ]
        retriever = build_retriever(tmp_path, chunks)

        results = retriever.retrieve("termination", top_k=5, filters={"document_ids": ["doc-1"]})

        assert {r.record.document_id for r in results} == {"doc-1"}

    def test_no_filters_behaves_as_before(self, tmp_path):
        chunks = [
            make_chunk("a", "Termination clause requires notice.", document_id="doc-1"),
            make_chunk("b", "Termination clause requires notice.", document_id="doc-2"),
        ]
        retriever = build_retriever(tmp_path, chunks)

        results = retriever.retrieve("termination", top_k=5, filters=None)

        assert {r.record.document_id for r in results} == {"doc-1", "doc-2"}

    def test_unsupported_filter_key_raises(self, tmp_path):
        chunks = [make_chunk("a", "Termination clause requires notice.", document_id="doc-1")]
        retriever = build_retriever(tmp_path, chunks)

        with pytest.raises(NotImplementedError):
            retriever.retrieve("termination", top_k=5, filters={"category": ["contracts"]})
