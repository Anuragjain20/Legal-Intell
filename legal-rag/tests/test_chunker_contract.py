"""Shared-behavior contract tests across all Chunker implementations.

Any chunking strategy registered here must satisfy these invariants
regardless of its internal algorithm — mirrors the retrieval-contract
pattern in test_retrieval_contract.py.
"""

from __future__ import annotations

import json

import pytest

from src.ingestion.chunker import LegalChunker
from src.ingestion.llm_semantic_chunker import LLMSemanticChunker
from src.ingestion.models import DocumentPage
from src.ingestion.recursive_chunker import RecursiveCharacterChunker

TEXT = (
    "SECTION ONE\n\n"
    "This section establishes the general obligations of both parties under "
    "this agreement, including timely performance and good-faith cooperation.\n\n"
    "SECTION TWO\n\n"
    "This section addresses payment terms, including invoicing schedules, "
    "late-payment penalties, and currency of settlement.\n\n"
    "SECTION THREE\n\n"
    "This section covers termination rights, notice periods, and the "
    "survival of confidentiality obligations after termination."
)


def make_pages(texts: list[str], document_id: str = "doc-1") -> list[DocumentPage]:
    return [
        DocumentPage(
            page_number=index + 1,
            text=text,
            extraction_status="extracted" if text.strip() else "no_text",
            document_id=document_id,
            filename="doc.pdf",
            storage_path="/tmp/doc.pdf",
        )
        for index, text in enumerate(texts)
    ]


class _ScriptedLLM:
    model_name = "scripted-llm"

    def __init__(self, anchors: list[str]) -> None:
        self._anchors = anchors

    def generate(self, prompt: str) -> str:
        return json.dumps(self._anchors)


def _llm_semantic_chunker() -> LLMSemanticChunker:
    anchors = ["SECTION ONE", "SECTION TWO", "SECTION THREE"]
    return LLMSemanticChunker(_ScriptedLLM(anchors))


CHUNKER_FACTORIES = {
    "legal": lambda: LegalChunker(),
    "recursive": lambda: RecursiveCharacterChunker(),
    "llm_semantic": _llm_semantic_chunker,
}


@pytest.fixture(params=list(CHUNKER_FACTORIES))
def chunker(request):
    return CHUNKER_FACTORIES[request.param]()


def test_chunk_ids_are_unique_and_sequential(chunker):
    chunks = chunker.chunk(document_id="doc-1", pages=make_pages([TEXT]))
    assert chunks
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert ids == [f"doc-1:{i:04d}" for i in range(len(chunks))]


def test_page_numbers_stay_within_input_range(chunker):
    pages = make_pages([TEXT, "MORE TEXT here for a second page of content."])
    chunks = chunker.chunk(document_id="doc-1", pages=pages)
    assert chunks
    min_page = min(p.page_number for p in pages)
    max_page = max(p.page_number for p in pages)
    for c in chunks:
        assert c.page_number <= c.end_page_number
        assert min_page <= c.page_number <= max_page
        assert min_page <= c.end_page_number <= max_page


def test_every_chunk_has_non_empty_alphanumeric_text(chunker):
    chunks = chunker.chunk(document_id="doc-1", pages=make_pages([TEXT]))
    assert chunks
    for c in chunks:
        assert c.text.strip()
        assert any(ch.isalnum() for ch in c.text)


def test_document_metadata_propagated_consistently(chunker):
    chunks = chunker.chunk(document_id="doc-xyz", pages=make_pages([TEXT], document_id="doc-xyz"), category="acts")
    assert chunks
    for c in chunks:
        assert c.document_id == "doc-xyz"
        assert c.document_name == "doc.pdf"
        assert c.category == "acts"


def test_empty_pages_produce_no_chunks(chunker):
    chunks = chunker.chunk(document_id="doc-1", pages=make_pages(["", "   "]))
    assert chunks == []


def test_no_fabrication_chunks_are_substrings_of_source(chunker):
    """Every chunk's text must be verbatim from the source — no chunker may
    paraphrase, normalize, or otherwise alter what it indexes."""
    pages = make_pages([TEXT])
    full_text = "\n\n".join(p.text for p in pages)
    chunks = chunker.chunk(document_id="doc-1", pages=pages)
    assert chunks
    for c in chunks:
        assert c.text in full_text, f"chunk text not found verbatim in source: {c.text[:60]!r}"
