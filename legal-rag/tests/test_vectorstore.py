from __future__ import annotations

import pytest

from src.embeddings.base import EmbeddedChunk
from src.ingestion.models import Chunk
from src.vectorstore.exceptions import VectorDimensionMismatchError
from src.vectorstore.local_store import LocalVectorStore
from src.vectorstore.service import VectorIndexService


def make_chunk(chunk_id: str, document_id: str, text: str, page_number: int = 1) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        page_number=page_number,
        end_page_number=page_number,
        section="1",
        heading="TERMS",
        text=text,
    )


def make_embedded_chunk(chunk: Chunk, vector: list[float]) -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=chunk,
        embedding=vector,
        embedding_model="fake-local-model",
        embedding_version="2026.09",
    )


def test_insert_indexes_all_records(tmp_path):
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    service = VectorIndexService(store=store)
    chunks = [
        make_embedded_chunk(make_chunk("chunk-1", "doc-1", "Alpha"), [0.1, 0.2, 0.3]),
        make_embedded_chunk(make_chunk("chunk-2", "doc-1", "Beta"), [0.4, 0.5, 0.6]),
    ]

    service.index_embeddings(chunks)

    assert store.get_by_chunk_id("chunk-1") is not None
    assert store.get_by_chunk_id("chunk-2") is not None
    assert store.list_document_ids() == ["doc-1"]


def test_persistence_survives_reload(tmp_path):
    storage_dir = tmp_path / "vectorstore"
    store = LocalVectorStore(storage_dir=storage_dir, dimension=3)
    service = VectorIndexService(store=store)
    service.index_embeddings([make_embedded_chunk(make_chunk("chunk-1", "doc-1", "Alpha"), [1.0, 2.0, 3.0])])

    reloaded = LocalVectorStore(storage_dir=storage_dir, dimension=3)

    assert reloaded.get_by_chunk_id("chunk-1") is not None
    assert reloaded.get_by_chunk_id("chunk-1").text == "Alpha"


def test_metadata_is_preserved(tmp_path):
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    service = VectorIndexService(store=store)
    embedded = make_embedded_chunk(make_chunk("chunk-1", "doc-1", "This is the clause.", page_number=7), [0.1, 0.2, 0.3])

    service.index_embeddings([embedded])
    record = store.get_by_chunk_id("chunk-1")

    assert record is not None
    assert record.document_id == "doc-1"
    assert record.chunk_id == "chunk-1"
    assert record.page_number == 7
    assert record.section == "1"
    assert record.text == "This is the clause."


def test_delete_document_removes_only_target_document(tmp_path):
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    service = VectorIndexService(store=store)
    service.index_embeddings(
        [
            make_embedded_chunk(make_chunk("chunk-a1", "doc-a", "Alpha"), [0.1, 0.2, 0.3]),
            make_embedded_chunk(make_chunk("chunk-b1", "doc-b", "Beta"), [0.4, 0.5, 0.6]),
        ]
    )

    removed = service.delete_document("doc-a")

    assert removed == 1
    assert store.get_by_chunk_id("chunk-a1") is None
    assert store.get_by_chunk_id("chunk-b1") is not None


def test_dimension_mismatch_is_rejected(tmp_path):
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    service = VectorIndexService(store=store)
    embedded = make_embedded_chunk(make_chunk("chunk-1", "doc-1", "Alpha"), [0.1, 0.2, 0.3, 0.4])

    with pytest.raises(VectorDimensionMismatchError):
        service.index_embeddings([embedded])


def test_duplicate_indexing_upserts_by_chunk_id(tmp_path):
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=3)
    service = VectorIndexService(store=store)
    first = make_embedded_chunk(make_chunk("chunk-1", "doc-1", "Alpha"), [0.1, 0.2, 0.3])
    second = make_embedded_chunk(make_chunk("chunk-1", "doc-1", "Alpha updated"), [0.9, 0.8, 0.7])

    service.index_embeddings([first])
    service.index_embeddings([second])

    record = store.get_by_chunk_id("chunk-1")
    assert record is not None
    assert record.text == "Alpha updated"
    assert record.vector == [0.9, 0.8, 0.7]
    assert len(store.list_document_ids()) == 1

