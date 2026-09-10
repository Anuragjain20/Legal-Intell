"""Validate every ground-truth span in data/evaluation_dataset.json against
the live vector store, and refresh anchor_chunk_id (a debug-only field) to
point at whatever chunk currently contains the span.

Chunk boundaries and chunk_ids are not stable across chunker changes, so
this must be re-run (and the dataset patched) after any re-ingest.

Usage:
    python scripts/validate_dataset.py [--fix]
    python scripts/validate_dataset.py --chroma-dir data/chroma_recursive
    python scripts/validate_dataset.py --collection legal_rag

--chroma-dir/--collection let this be pointed at any per-chunking-method
index (see scripts/ingest.py --chunking-method) to check span-findability
under a different chunker, not just the default data/chroma.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from src.evaluation.matching import (  # noqa: E402
    DOCUMENT_SEPARATOR,
    span_matches,
    split_multi_span,
)

DATASET_PATH = APP_DIR / "data" / "evaluation_dataset.json"
DEFAULT_CHROMA_DIR = APP_DIR / "data" / "chroma"
DEFAULT_COLLECTION = "legal_rag"


def _load_chunks_by_document(chroma_dir: Path, collection_name: str) -> dict[str, list[tuple[str, str]]]:
    """Return {document_name: [(chunk_id, text), ...]} for every indexed chunk."""
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_collection(collection_name)
    result = collection.get(limit=100_000, include=["documents", "metadatas"])

    by_document: dict[str, list[tuple[str, str]]] = {}
    for chunk_id, metadata, text in zip(result["ids"], result["metadatas"], result["documents"]):
        doc_name = metadata.get("document_name", "UNKNOWN")
        by_document.setdefault(doc_name, []).append((chunk_id, text))
    return by_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="Rewrite stale anchor_chunk_id values in place")
    parser.add_argument("--chroma-dir", type=Path, default=DEFAULT_CHROMA_DIR, help="Chroma directory to validate against")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Chroma collection name")
    args = parser.parse_args()
    fix = args.fix

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    chunks_by_document = _load_chunks_by_document(args.chroma_dir, args.collection)

    total = 0
    passed = 0
    failures: list[str] = []
    refreshed = 0

    for case in dataset["questions"]:
        if case.get("is_out_of_corpus") or not case.get("expected_answer_span"):
            continue

        total += 1
        documents = case["expected_document"].split(DOCUMENT_SEPARATOR)
        spans = split_multi_span(case["expected_answer_span"])
        old_chunk_ids = (case.get("anchor_chunk_id") or "").split(DOCUMENT_SEPARATOR)

        # A multi_section/comparison case can either span multiple documents
        # (one span per document) or hold multiple spans within a single
        # document (one document, several spans). Only the former needs
        # document/span counts to line up; the latter checks every span
        # against that one document's chunks.
        if len(documents) == 1 and len(spans) > 1:
            documents = documents * len(spans)
        elif len(documents) != len(spans):
            failures.append(f"{case['id']}: document count ({len(documents)}) != span count ({len(spans)})")
            continue

        new_chunk_ids: list[str] = []
        case_ok = True
        for doc_name, span in zip(documents, spans):
            candidates = chunks_by_document.get(doc_name, [])
            match = next((cid for cid, text in candidates if span_matches(span, text)), None)
            if match is None:
                case_ok = False
                failures.append(f"{case['id']}: span not found in any '{doc_name}' chunk: {span[:80]!r}")
            else:
                new_chunk_ids.append(match)

        if case_ok:
            passed += 1
            new_anchor = DOCUMENT_SEPARATOR.join(new_chunk_ids)
            if new_anchor != DOCUMENT_SEPARATOR.join(old_chunk_ids):
                refreshed += 1
                if fix:
                    case["anchor_chunk_id"] = new_anchor

    print(f"Validated {total} in-corpus cases: {passed} passed, {total - passed} failed")
    if refreshed:
        action = "refreshed" if fix else "would refresh (pass --fix to apply)"
        print(f"{refreshed} case(s) had a stale anchor_chunk_id and were {action}")

    for line in failures:
        print(f"  FAIL {line}")

    if fix and refreshed:
        DATASET_PATH.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote updated anchor_chunk_id values to {DATASET_PATH}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
