from __future__ import annotations

from src.ingestion.models import DocumentPage
from src.ingestion.recursive_chunker import RecursiveCharacterChunker, RecursiveChunkerConfig


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


def test_short_document_produces_single_chunk():
    text = "A short paragraph that fits well within the default chunk size."
    chunks = RecursiveCharacterChunker().chunk(document_id="doc-1", pages=make_pages([text]))
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_long_document_splits_into_multiple_size_bounded_chunks():
    text = ". ".join(f"Sentence number {i} contains some obligations text" for i in range(60))
    config = RecursiveChunkerConfig(chunk_size=200, chunk_overlap=0)
    chunks = RecursiveCharacterChunker(config).chunk(document_id="doc-1", pages=make_pages([text]))
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= config.chunk_size + 50  # small slack for overlap-free boundary text


def test_no_structure_metadata_is_populated():
    text = "SECTION 1\n\nSome content that looks structured but this chunker ignores it."
    chunks = RecursiveCharacterChunker().chunk(document_id="doc-1", pages=make_pages([text]))
    assert chunks
    for c in chunks:
        assert c.section is None
        assert c.heading is None
        assert c.section_number is None
        assert c.subsection is None
        assert c.clause is None
        assert c.structure_path is None


def test_overlap_exists_between_adjacent_chunks():
    para_a = "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike."
    para_b = "November oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee."
    text = f"{para_a}\n\n{para_b}"
    config = RecursiveChunkerConfig(chunk_size=len(para_a) + 5, chunk_overlap=20, separators=("\n\n", " "))
    chunks = RecursiveCharacterChunker(config).chunk(document_id="doc-1", pages=make_pages([text]))
    assert len(chunks) >= 2
    tail_of_first_words = para_a.split()[-3:]
    assert any(word in chunks[1].text for word in tail_of_first_words)


def test_page_attribution_for_text_spanning_pages():
    pages = make_pages(
        [
            "First page content that is reasonably long to fill some space here.",
            "Second page content continues the document further along nicely.",
        ]
    )
    config = RecursiveChunkerConfig(chunk_size=50, chunk_overlap=0)
    chunks = RecursiveCharacterChunker(config).chunk(document_id="doc-1", pages=pages)
    assert chunks
    page_numbers = {c.page_number for c in chunks} | {c.end_page_number for c in chunks}
    assert page_numbers <= {1, 2}
    assert any(c.page_number == 1 for c in chunks)
    assert any(c.end_page_number == 2 for c in chunks)


def test_blank_pages_produce_no_chunks():
    chunks = RecursiveCharacterChunker().chunk(document_id="doc-1", pages=make_pages(["", "   "]))
    assert chunks == []
