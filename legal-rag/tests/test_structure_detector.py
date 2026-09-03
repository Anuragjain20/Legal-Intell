from __future__ import annotations

from src.ingestion.models import DocumentPage
from src.ingestion.structure_detector import StructureDetector


def make_pages(texts: list[str]) -> list[DocumentPage]:
    return [
        DocumentPage(
            page_number=index + 1,
            text=text,
            extraction_status="extracted" if text.strip() else "no_text",
            document_id="doc-1",
            filename="doc.pdf",
            storage_path="/tmp/doc.pdf",
        )
        for index, text in enumerate(texts)
    ]


def test_numbered_contract_sections_are_detected():
    text = (
        "AGREEMENT\n\n"
        "1. DEFINITIONS\n\n"
        '1.1 "Services" means the services described in Schedule A.\n\n'
        '1.2 "Confidential Information" means any non-public information.\n\n'
        "2. PAYMENT\n\n"
        "The Client shall pay all invoices within thirty days.\n\n"
        "3. TERMINATION\n\n"
        "Either party may terminate this Agreement on notice.\n\n"
        "7.1 Termination for Cause\n\n"
        "A party may terminate immediately for material breach."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))

    by_section = {p.section: p for p in paragraphs}

    assert by_section["1.1"].heading == "DEFINITIONS"
    assert by_section["1.2"].heading == "DEFINITIONS"
    assert by_section["2"].heading == "PAYMENT"
    assert by_section["3"].heading == "TERMINATION"
    # "7.1 Termination for Cause" reads as its own (title-case) sub-heading.
    termination_for_cause = next(p for p in paragraphs if p.heading == "Termination for Cause")
    assert termination_for_cause.section == "7.1"
    assert "material breach" in termination_for_cause.text


def test_chapter_style_statute_is_detected():
    text = (
        "CHAPTER I\n"
        "PRELIMINARY\n\n"
        "1. Short title and commencement.\n\n"
        "2. Definitions.\n\n"
        "CHAPTER II\n"
        "GENERAL PROVISIONS\n\n"
        "3. Application of the Act."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))

    first = next(p for p in paragraphs if p.section == "1")
    assert first.heading == "CHAPTER I PRELIMINARY"

    third = next(p for p in paragraphs if p.section == "3")
    assert third.heading == "CHAPTER II GENERAL PROVISIONS"


def test_unnumbered_judgment_headings_have_no_section():
    text = (
        "FACTS\n\n"
        "The petitioner filed a complaint before the tribunal.\n\n"
        "ISSUES\n\n"
        "The following issues arise for consideration.\n\n"
        "ORDER\n\n"
        "The petition is dismissed."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))

    headings = {p.heading for p in paragraphs}
    assert headings == {"FACTS", "ISSUES", "ORDER"}
    assert all(p.section is None for p in paragraphs)


def test_unstructured_document_never_invents_headings():
    text = (
        "This agreement is entered into by the parties.\n\n"
        "The parties agree that all disputes shall be resolved by arbitration.\n\n"
        "The obligations shall survive termination of this agreement."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))

    assert len(paragraphs) == 3
    assert all(p.heading is None for p in paragraphs)
    assert all(p.section is None for p in paragraphs)


def test_paragraph_spanning_pages_keeps_both_page_numbers():
    pages = make_pages(["TERMINATION\n\nThis clause continues", "onto the next page without a break."])
    paragraphs = StructureDetector().detect(pages)

    spanning = next(p for p in paragraphs if "continues" in p.text)
    assert spanning.page_number == 1
    assert spanning.end_page_number == 2


def test_blank_pages_produce_no_paragraphs():
    paragraphs = StructureDetector().detect(make_pages(["", "   ", ""]))
    assert paragraphs == []
