from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from src.ingestion.chunker import ChunkerConfig, LegalChunker
from src.ingestion.models import DocumentPage
from src.ingestion.pdf_extractor import PDFExtractor


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


SMALL_CONFIG = ChunkerConfig(target_chunk_size=200, max_chunk_size=280, overlap_size=40, min_chunk_size=10)


def build_pdf_lines(lines: list[str]) -> bytes:
    """A single page with each line drawn separately, no blank lines between them —
    matching how pypdf's extract_text() actually renders real, non-synthetic PDFs
    (see test_title_line_does_not_merge_into_first_numbered_heading)."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    ops = []
    y = 380
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        ops.append(f"BT /F1 12 Tf 20 {y} Td ({escaped}) Tj ET")
        y -= 14
    stream = DecodedStreamObject()
    stream.set_data("\n".join(ops).encode("utf-8"))
    stream[NameObject("/Length")] = NumberObject(len(stream.get_data()))
    page[NameObject("/Contents")] = stream
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_basic_document_retains_section_context():
    text = "Section 1\nParagraph A\n\nParagraph B\n\nSection 2\nParagraph C"
    chunks = LegalChunker().chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) > 0
    section_1_chunks = [c for c in chunks if c.heading == "Section 1"]
    section_2_chunks = [c for c in chunks if c.heading == "Section 2"]
    assert section_1_chunks and section_2_chunks
    assert all(c.section == "1" for c in section_1_chunks)
    assert all(c.section == "2" for c in section_2_chunks)
    assert any("Paragraph A" in c.text for c in section_1_chunks)
    assert any("Paragraph B" in c.text for c in section_1_chunks)
    assert any("Paragraph C" in c.text for c in section_2_chunks)


def test_long_section_produces_multiple_chunks_with_same_metadata():
    paragraphs = [f"Paragraph {i} contains obligations relevant to payment terms and schedules." for i in range(8)]
    text = "PAYMENT TERMS\n\n" + "\n\n".join(paragraphs)
    chunks = LegalChunker(SMALL_CONFIG).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) > 1
    assert all(c.heading == "PAYMENT TERMS" for c in chunks)
    assert all(c.section is None for c in chunks)


def test_boundary_preservation_does_not_split_paragraphs_mid_sentence():
    para_a = "A" * 150
    para_b = "B" * 100
    text = f"OBLIGATIONS\n\n{para_a}\n\n{para_b}"
    chunks = LegalChunker(SMALL_CONFIG).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 2
    assert para_a in chunks[0].text
    assert para_b in chunks[1].text
    # Chunk 1 is not truncated mid-paragraph: the full "AAAA...A" run is present.
    assert chunks[0].text.count("A") == len(para_a)


def test_page_metadata_is_preserved_including_spanning_paragraphs():
    pages = make_pages(
        [
            "TERMINATION\n\nThis clause begins here",
            "and concludes on the following page.",
            "NOTICES\n\nAll notices must be in writing.",
        ]
    )
    chunks = LegalChunker().chunk(document_id="doc-1", pages=pages)

    termination_chunk = next(c for c in chunks if c.heading == "TERMINATION")
    assert termination_chunk.page_number == 1
    assert termination_chunk.end_page_number == 2

    notices_chunk = next(c for c in chunks if c.heading == "NOTICES")
    assert notices_chunk.page_number == 3
    assert notices_chunk.end_page_number == 3


def test_document_id_is_preserved_on_every_chunk():
    text = "Section 1\nParagraph A\n\nSection 2\nParagraph B"
    chunks = LegalChunker().chunk(document_id="doc-xyz", pages=make_pages([text], document_id="doc-xyz"))

    assert chunks
    assert all(c.document_id == "doc-xyz" for c in chunks)


def test_configured_overlap_exists_between_split_chunks():
    para_a = "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima."
    para_b = "Mike november oscar papa quebec romeo sierra tango uniform victor whiskey."
    text = f"OBLIGATIONS\n\n{para_a}\n\n{para_b}"
    config = ChunkerConfig(target_chunk_size=len(para_a) + 5, max_chunk_size=200, overlap_size=20, min_chunk_size=10)
    chunks = LegalChunker(config).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 2
    tail_of_first = para_a[-20:].split(" ", 1)[-1]
    assert tail_of_first in chunks[1].text
    assert chunks[1].text.strip().endswith(para_b)


def test_chunk_ids_are_unique():
    text = "Section 1\nParagraph A\n\nSection 2\nParagraph B\n\nSection 3\nParagraph C"
    chunks = LegalChunker().chunk(document_id="doc-1", pages=make_pages([text]))

    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(cid.startswith("doc-1:") for cid in ids)


def test_blank_pages_produce_no_chunks():
    chunks = LegalChunker().chunk(document_id="doc-1", pages=make_pages(["", "   "]))
    assert chunks == []


def test_symbol_only_text_produces_no_chunks():
    chunks = LegalChunker().chunk(document_id="doc-1", pages=make_pages(["----\n\n****"]))
    assert chunks == []


def test_short_real_section_is_not_dropped():
    # A one-line notices clause is genuine, citable content even though it's well
    # under the target chunk size — it must not be treated as "meaningless".
    text = "NOTICES\n\nAll notices must be in writing."
    config = ChunkerConfig(min_chunk_size=50)
    chunks = LegalChunker(config).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 1
    assert chunks[0].heading == "NOTICES"
    assert "All notices must be in writing." in chunks[0].text


def test_title_line_does_not_merge_into_first_numbered_heading():
    # A caps document title directly followed by the first numbered section (no
    # blank line survives real pypdf extraction) must not be fused into one
    # heading — "SERVICES AGREEMENT DEFINITIONS" appears nowhere in the source text.
    lines = [
        "SERVICES AGREEMENT",
        "1. DEFINITIONS",
        '1.1 "Services" means the services described in Schedule A.',
    ]
    content = build_pdf_lines(lines)
    extraction = PDFExtractor().extract(
        document_id="doc-1", filename="agreement.pdf", storage_path="/tmp/agreement.pdf", content=content
    )
    chunks = LegalChunker().chunk(document_id="doc-1", pages=extraction.pages)

    assert len(chunks) == 1
    assert chunks[0].heading == "DEFINITIONS"
    assert chunks[0].section == "1.1"


def test_unstructured_document_chunks_without_inventing_structure():
    text = (
        "This agreement is entered into by the parties.\n\n"
        "The parties agree that all disputes shall be resolved by arbitration.\n\n"
        "The obligations shall survive termination of this agreement."
    )
    chunks = LegalChunker().chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) > 0
    assert all(c.heading is None for c in chunks)
    assert all(c.section is None for c in chunks)
