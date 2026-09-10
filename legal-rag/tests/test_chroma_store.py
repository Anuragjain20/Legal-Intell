from __future__ import annotations

from src.vectorstore.base import VectorRecord
from src.vectorstore.chroma_store import ChromaVectorStore


def make_record() -> VectorRecord:
    return VectorRecord(
        chunk_id="chunk-1",
        document_id="doc-1",
        vector=[1.0, 0.0, 0.0],
        text="Termination requires written notice.",
        page_number=3,
        section="7",
        heading="TERMINATION",
        embedding_model="test-model",
        embedding_version="1",
        document_name="contract.pdf",
        category="contracts",
    )


def test_chroma_persists_and_searches_records(tmp_path):
    store = ChromaVectorStore(storage_dir=tmp_path / "chroma", dimension=3, collection_name="test_records")
    store.add([make_record()])

    reloaded = ChromaVectorStore(storage_dir=tmp_path / "chroma", dimension=3, collection_name="test_records")
    record = reloaded.get_by_chunk_id("chunk-1")
    results = reloaded.search([1.0, 0.0, 0.0], top_k=1)

    assert record is not None
    assert record.document_name == "contract.pdf"
    assert record.category == "contracts"
    assert reloaded.list_document_ids() == ["doc-1"]
    assert results[0].record.chunk_id == "chunk-1"
    assert results[0].score == 1.0


def test_get_all_returns_every_record_without_embeddings(tmp_path):
    store = ChromaVectorStore(storage_dir=tmp_path / "chroma", dimension=3, collection_name="test_records")
    store.add([make_record(), VectorRecord(**{**make_record().__dict__, "chunk_id": "chunk-2"})])

    records = store.get_all()

    assert {r.chunk_id for r in records} == {"chunk-1", "chunk-2"}
    assert all(r.vector == [] for r in records)
    assert next(r for r in records if r.chunk_id == "chunk-1").text == "Termination requires written notice."


def test_search_with_document_ids_restricts_to_matching_documents(tmp_path):
    store = ChromaVectorStore(storage_dir=tmp_path / "chroma", dimension=3, collection_name="test_records")
    other = VectorRecord(**{**make_record().__dict__, "chunk_id": "chunk-2", "document_id": "doc-2"})
    store.add([make_record(), other])

    results = store.search([1.0, 0.0, 0.0], top_k=5, document_ids=["doc-1"])

    assert {r.record.chunk_id for r in results} == {"chunk-1"}


def test_search_without_document_ids_is_unfiltered(tmp_path):
    store = ChromaVectorStore(storage_dir=tmp_path / "chroma", dimension=3, collection_name="test_records")
    other = VectorRecord(**{**make_record().__dict__, "chunk_id": "chunk-2", "document_id": "doc-2"})
    store.add([make_record(), other])

    results = store.search([1.0, 0.0, 0.0], top_k=5, document_ids=None)

    assert {r.record.chunk_id for r in results} == {"chunk-1", "chunk-2"}
