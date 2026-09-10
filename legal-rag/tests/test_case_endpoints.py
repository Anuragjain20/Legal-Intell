"""Tests for the /cases* and /documents endpoint functions in src/api/main.py.

These wrap CaseRegistry/DocumentRegistry directly (already covered in
tests/test_case_registry.py and tests/test_document_registry.py) so this
only checks the HTTP-facing wiring: request/response shapes and 404s.
Same direct-call isolation strategy as tests/test_evaluate_endpoint.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import main as api_main
from src.cases.registry import CaseRegistry
from src.ingestion.models import DocumentMetadata
from src.ingestion.storage import DocumentRegistry
from datetime import datetime, timezone


def _build_app_state(tmp_path):
    cases = CaseRegistry(tmp_path / "cases.json")
    registry = DocumentRegistry(tmp_path / "documents.json")
    registry.upsert(
        DocumentMetadata(
            document_id="doc-1",
            filename="contract.pdf",
            file_type="application/pdf",
            file_size=100,
            upload_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            storage_path="/documents/doc-1-contract.pdf",
            category="contracts",
        )
    )
    services = SimpleNamespace(upload_service=SimpleNamespace(registry=registry))
    return SimpleNamespace(services=services, cases=cases)


def test_list_documents_returns_registered_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path))

    result = api_main.list_documents()

    assert len(result) == 1
    assert result[0].document_id == "doc-1"
    assert result[0].filename == "contract.pdf"


def test_create_and_list_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path))

    created = api_main.create_case(api_main.CreateCaseRequest(name="Smith v. Jones", description="A dispute"))
    assert created.name == "Smith v. Jones"
    assert created.document_ids == []

    listed = api_main.list_cases()
    assert len(listed) == 1
    assert listed[0].case_id == created.case_id


def test_get_case_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        api_main.get_case("does-not-exist")
    assert exc_info.value.status_code == 404


def test_add_and_remove_document_from_case(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path))
    case = api_main.create_case(api_main.CreateCaseRequest(name="Smith v. Jones"))

    added = api_main.add_document_to_case(case.case_id, api_main.AddDocumentToCaseRequest(document_id="doc-1"))
    assert added.document_ids == ["doc-1"]

    removed = api_main.remove_document_from_case(case.case_id, "doc-1")
    assert removed.document_ids == []


def test_add_document_to_unknown_case_404s(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        api_main.add_document_to_case("does-not-exist", api_main.AddDocumentToCaseRequest(document_id="doc-1"))
    assert exc_info.value.status_code == 404
