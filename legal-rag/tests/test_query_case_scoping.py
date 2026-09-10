"""Tests for POST /query's case_id resolution in src/api/main.py.

Full end-to-end coverage would need the real embedding model and Chroma
index (see tests/test_evaluate_endpoint.py's docstring for why that's too
heavy for a unit test). Instead this calls query() directly against a
stubbed services/retriever/generation_service and a real CaseRegistry
pointed at a temp file - the same isolation strategy test_evaluate_endpoint.py
uses for _run_evaluation_job.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api import main as api_main
from src.cases.registry import CaseRegistry
from src.retrieval.exceptions import NoRelevantResultsError


class _FakeRecord:
    document_name = "doc.pdf"
    document_id = "doc-1"
    page_number = 1
    section = "1"
    heading = "HEADING"
    text = "Some retrieved text."


class _FakeRetrievedChunk:
    rank = 1
    score = 0.9
    record = _FakeRecord()


class _FakeRetriever:
    def __init__(self):
        self.last_filters = "not-called"

    def retrieve(self, question, top_k=8, filters=None):
        self.last_filters = filters
        if filters and not filters.get("document_ids"):
            raise NoRelevantResultsError("empty filter")
        return [_FakeRetrievedChunk()]


class _FakeGenerationResult:
    answer = "The answer."
    model = "fake-model"
    citations = []
    used_context = SimpleNamespace(sources=[], rendered_context="")


class _FakeGenerationService:
    def answer(self, question, results):
        return _FakeGenerationResult()


def _build_app_state(tmp_path, retriever=None):
    settings = SimpleNamespace(deepseek_api_key="fake-key")
    services = SimpleNamespace(
        settings=settings,
        retriever=retriever or _FakeRetriever(),
        generation_service=_FakeGenerationService(),
    )
    cases = CaseRegistry(tmp_path / "cases.json")
    return SimpleNamespace(services=services, cases=cases)


def test_query_without_case_id_searches_unscoped(tmp_path, monkeypatch):
    retriever = _FakeRetriever()
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path, retriever))

    response = api_main.query(api_main.QueryRequest(question="test", case_id=None))

    assert response.refused is False
    assert response.case_id is None
    assert retriever.last_filters is None


def test_query_with_unknown_case_id_is_refused_not_fallback(tmp_path, monkeypatch):
    retriever = _FakeRetriever()
    monkeypatch.setattr(api_main.app, "state", _build_app_state(tmp_path, retriever))

    response = api_main.query(api_main.QueryRequest(question="test", case_id="does-not-exist"))

    assert response.refused is True
    assert response.case_id == "does-not-exist"
    # Retriever must never be called for an unresolved case - no silent global fallback.
    assert retriever.last_filters == "not-called"


def test_query_with_case_that_has_no_documents_is_refused(tmp_path, monkeypatch):
    state = _build_app_state(tmp_path)
    case = state.cases.create("Empty Case")
    monkeypatch.setattr(api_main.app, "state", state)

    response = api_main.query(api_main.QueryRequest(question="test", case_id=case.case_id))

    assert response.refused is True
    assert response.case_id == case.case_id
    assert state.services.retriever.last_filters == "not-called"


def test_query_with_populated_case_id_passes_document_ids_filter(tmp_path, monkeypatch):
    retriever = _FakeRetriever()
    state = _build_app_state(tmp_path, retriever)
    case = state.cases.create("Smith v. Jones")
    state.cases.add_document(case.case_id, "doc-1")
    state.cases.add_document(case.case_id, "doc-2")
    monkeypatch.setattr(api_main.app, "state", state)

    response = api_main.query(api_main.QueryRequest(question="test", case_id=case.case_id))

    assert response.refused is False
    assert response.case_id == case.case_id
    assert retriever.last_filters == {"document_ids": ["doc-1", "doc-2"]}
