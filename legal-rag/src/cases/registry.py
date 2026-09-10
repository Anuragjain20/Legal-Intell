"""Small JSON-backed case catalog, mirroring DocumentRegistry's pattern.

A case is a named collection of already-ingested document_ids - it never
holds document content or chunk data itself, only the association. This
keeps case membership fully decoupled from ingestion: the same document_id
can belong to any number of cases without being re-uploaded or duplicated.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from src.cases.models import Case


class CaseNotFoundError(KeyError):
    """Raised when a case_id does not exist in the registry."""


class CaseRegistry:
    """Small JSON-backed case catalog for the local MVP."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def create(self, name: str, description: str | None = None) -> Case:
        case = Case(
            case_id=uuid.uuid4().hex,
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc),
            document_ids=[],
        )
        self._save(case)
        return case

    def get(self, case_id: str) -> Case | None:
        return self._load().get(case_id)

    def list_all(self) -> list[Case]:
        return list(self._load().values())

    def add_document(self, case_id: str, document_id: str) -> Case:
        case = self._require(case_id)
        if document_id in case.document_ids:
            return case
        updated = Case(
            case_id=case.case_id,
            name=case.name,
            description=case.description,
            created_at=case.created_at,
            document_ids=[*case.document_ids, document_id],
        )
        self._save(updated)
        return updated

    def remove_document(self, case_id: str, document_id: str) -> Case:
        case = self._require(case_id)
        updated = Case(
            case_id=case.case_id,
            name=case.name,
            description=case.description,
            created_at=case.created_at,
            document_ids=[d for d in case.document_ids if d != document_id],
        )
        self._save(updated)
        return updated

    def _require(self, case_id: str) -> Case:
        case = self.get(case_id)
        if case is None:
            raise CaseNotFoundError(case_id)
        return case

    def _save(self, case: Case) -> None:
        cases = self._load()
        cases[case.case_id] = case
        entries = []
        for c in cases.values():
            entry = asdict(c)
            entry["created_at"] = c.created_at.isoformat()
            entries.append(entry)
        self.registry_path.write_text(json.dumps({"cases": entries}, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Case]:
        if not self.registry_path.exists():
            return {}
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        cases = {}
        for entry in payload.get("cases", []):
            case = Case(
                case_id=entry["case_id"],
                name=entry["name"],
                description=entry.get("description"),
                created_at=datetime.fromisoformat(entry["created_at"]),
                document_ids=list(entry.get("document_ids", [])),
            )
            cases[case.case_id] = case
        return cases
