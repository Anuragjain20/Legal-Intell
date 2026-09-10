"""Tests for DocumentRegistry.list_all() - the Cases tab's document picker source."""

from __future__ import annotations

from datetime import datetime, timezone

from src.ingestion.models import DocumentMetadata
from src.ingestion.storage import DocumentRegistry


def make_metadata(document_id: str, filename: str) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=document_id,
        filename=filename,
        file_type="application/pdf",
        file_size=1024,
        upload_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        storage_path=f"/documents/{document_id}-{filename}",
        category="contracts",
    )


def test_list_all_returns_empty_when_no_registry_exists(tmp_path):
    registry = DocumentRegistry(tmp_path / "documents.json")

    assert registry.list_all() == []


def test_list_all_round_trips_upserted_documents(tmp_path):
    registry = DocumentRegistry(tmp_path / "documents.json")
    registry.upsert(make_metadata("doc-1", "contract.pdf"))
    registry.upsert(make_metadata("doc-2", "statute.pdf"))

    documents = registry.list_all()

    assert {d.document_id for d in documents} == {"doc-1", "doc-2"}
    doc1 = next(d for d in documents if d.document_id == "doc-1")
    assert doc1.filename == "contract.pdf"
    assert doc1.category == "contracts"
    assert doc1.upload_timestamp == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_list_all_reflects_upsert_overwrite(tmp_path):
    registry = DocumentRegistry(tmp_path / "documents.json")
    registry.upsert(make_metadata("doc-1", "contract.pdf"))
    registry.upsert(DocumentMetadata(**{**make_metadata("doc-1", "contract.pdf").__dict__, "category": "acts"}))

    documents = registry.list_all()

    assert len(documents) == 1
    assert documents[0].category == "acts"
