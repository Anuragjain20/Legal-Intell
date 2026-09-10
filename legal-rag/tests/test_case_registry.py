"""Tests for CaseRegistry - the JSON-backed case-to-document association catalog."""

from __future__ import annotations

import pytest

from src.cases.registry import CaseNotFoundError, CaseRegistry


def test_create_returns_case_with_generated_id(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")

    case = registry.create("Smith v. Jones", description="Contract dispute")

    assert case.case_id
    assert case.name == "Smith v. Jones"
    assert case.description == "Contract dispute"
    assert case.document_ids == []


def test_get_returns_none_for_unknown_case(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")

    assert registry.get("does-not-exist") is None


def test_get_round_trips_through_disk(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")
    created = registry.create("Smith v. Jones")

    reloaded = CaseRegistry(tmp_path / "cases.json")
    fetched = reloaded.get(created.case_id)

    assert fetched == created


def test_list_all_returns_every_created_case(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")
    registry.create("Case A")
    registry.create("Case B")

    cases = registry.list_all()

    assert {c.name for c in cases} == {"Case A", "Case B"}


def test_add_document_appends_to_case(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")
    case = registry.create("Smith v. Jones")

    updated = registry.add_document(case.case_id, "doc-1")

    assert updated.document_ids == ["doc-1"]
    assert registry.get(case.case_id).document_ids == ["doc-1"]


def test_add_document_is_idempotent(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")
    case = registry.create("Smith v. Jones")
    registry.add_document(case.case_id, "doc-1")

    updated = registry.add_document(case.case_id, "doc-1")

    assert updated.document_ids == ["doc-1"]


def test_add_document_allows_same_document_in_multiple_cases(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")
    case_a = registry.create("Case A")
    case_b = registry.create("Case B")

    registry.add_document(case_a.case_id, "shared-doc")
    registry.add_document(case_b.case_id, "shared-doc")

    assert registry.get(case_a.case_id).document_ids == ["shared-doc"]
    assert registry.get(case_b.case_id).document_ids == ["shared-doc"]


def test_remove_document_drops_it_from_the_case(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")
    case = registry.create("Smith v. Jones")
    registry.add_document(case.case_id, "doc-1")
    registry.add_document(case.case_id, "doc-2")

    updated = registry.remove_document(case.case_id, "doc-1")

    assert updated.document_ids == ["doc-2"]


def test_add_document_raises_for_unknown_case(tmp_path):
    registry = CaseRegistry(tmp_path / "cases.json")

    with pytest.raises(CaseNotFoundError):
        registry.add_document("does-not-exist", "doc-1")
