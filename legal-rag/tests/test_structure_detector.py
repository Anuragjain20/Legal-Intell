from __future__ import annotations

from src.ingestion.chunker import LegalChunker
from src.ingestion.models import DocumentPage
from src.ingestion.structure_detector import StructureDetector
from src.ingestion.structure_patterns import match_line


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


def test_legal_definition_clauses_are_detected():
    """Test that definition clauses like 2(a), 2(d), 3(b) are recognized as sections."""
    text = (
        "2. Definitions.\n\n"
        '2(a) "Acceptance" means a manifestation of assent to the terms of an offer.\n\n'
        '2(b) "Breach" means failure to perform obligations under this contract.\n\n'
        '2(d) "Consideration" means an act, forbearance, or return promise given by one party to another as a price for the promise or act of the other party.\n\n'
        "3. General Provisions.\n\n"
        '3(a) The parties agree to this arrangement.\n\n'
        "Some general text here."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))

    by_section = {p.section: p for p in paragraphs}

    # Verify Section 2(a) is detected
    assert "2(a)" in by_section, "Section 2(a) should be detected"
    assert "Acceptance" in by_section["2(a)"].text
    assert by_section["2(a)"].heading == '2(a). "Acceptance" means a manifestation of assent to the terms of an offer.'

    # Verify Section 2(d) is detected
    assert "2(d)" in by_section, "Section 2(d) should be detected"
    assert "Consideration" in by_section["2(d)"].text
    assert "act, forbearance, or return promise" in by_section["2(d)"].text

    # Verify Section 2(b) is detected
    assert "2(b)" in by_section, "Section 2(b) should be detected"
    assert "Breach" in by_section["2(b)"].text

    # Verify Section 3(a) is detected
    assert "3(a)" in by_section, "Section 3(a) should be detected"
    assert "parties agree" in by_section["3(a)"].text

    two_d = next(p for p in paragraphs if p.section == "2(d)" and "Consideration" in p.text)
    assert "act, forbearance, or return promise" in two_d.text
    assert two_d.structure is not None
    assert two_d.structure.type == "section"
    assert two_d.structure.identifier == "2(d)"
    assert two_d.structure.level == 2
    assert two_d.structure.confidence == 1.0

    two_b = next(p for p in paragraphs if p.section == "2(b)")
    assert "Breach" in two_b.text

    three_a = next(p for p in paragraphs if p.section == "3(a)" and "parties agree" in p.text)
    assert three_a.structure is not None
    assert three_a.structure.identifier == "3(a)"


def test_numbered_section_short_title_is_detected():
    text = "CHAPTER I\n10. Short title\nThis Act may be called the Example Act."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "10")
    assert found.heading == "Short title"
    assert found.structure is not None
    assert found.structure.type == "section"
    assert found.structure.identifier == "10"


def test_lettered_subsection_is_detected():
    text = "(a) When one person signifies to another his willingness to do an act."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "(a)")
    assert "willingness" in found.text
    assert found.structure is not None
    assert found.structure.identifier == "(a)"
    assert found.structure.type == "section"


def test_nested_roman_clause_is_detected():
    text = "(ii) the promisee has done or abstained from doing something."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "(ii)")
    assert "promisee" in found.text
    assert found.structure is not None
    assert found.structure.type == "nested_clause"
    assert found.structure.identifier == "(ii)"
    assert found.structure.level == 4


def test_chapter_heading_is_detected():
    text = "CHAPTER VI\nOF THE CONSEQUENCES OF BREACH OF CONTRACT\n\nThe following provisions apply."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if "following provisions" in p.text)
    assert found.heading == "CHAPTER VI OF THE CONSEQUENCES OF BREACH OF CONTRACT"
    assert found.section == "VI"
    assert found.structure is not None
    assert found.structure.type == "chapter"


def test_article_heading_is_detected():
    text = "Article 21\nNo person shall be deprived of his life or personal liberty."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "21")
    assert found.heading == "Article 21"
    assert found.structure is not None
    assert found.structure.type == "article"
    assert "personal liberty" in found.text


def test_rule_heading_is_detected():
    text = "Rule 3\nThe intermediary shall publish the rules and regulations."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "3")
    assert found.heading == "Rule 3"
    assert found.structure is not None
    assert found.structure.type == "rule"


def test_regulation_heading_is_detected():
    text = "Regulation 5\nDue diligence shall be observed by the intermediary."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "5")
    assert found.heading == "Regulation 5"
    assert found.structure is not None
    assert found.structure.type == "regulation"


def test_schedule_heading_is_detected():
    text = "SCHEDULE I\nList of applicable forms."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "I")
    assert found.heading == "SCHEDULE I"
    assert found.structure is not None
    assert found.structure.type == "schedule"
    assert "applicable forms" in found.text


def test_the_first_schedule_is_detected():
    text = "THE FIRST SCHEDULE\nRepealed."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.heading == "THE FIRST SCHEDULE")
    assert found.structure is not None
    assert found.structure.type == "schedule"
    assert found.structure.identifier == "FIRST"


def test_annexure_heading_is_detected():
    text = "ANNEXURE A\nForm of notice."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.section == "A")
    assert found.heading == "ANNEXURE A"
    assert found.structure is not None
    assert found.structure.type == "annexure"


def test_part_heading_is_detected():
    text = "PART I\nPRELIMINARY\n\nThis Part applies to the whole of India."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if "whole of India" in p.text)
    assert found.heading == "PART I PRELIMINARY"
    assert found.section == "I"
    assert found.structure is not None
    assert found.structure.type == "part"


def test_contract_allcaps_heading_is_detected():
    text = "TERMINATION\nEither party may terminate this Agreement on notice."
    paragraphs = StructureDetector().detect(make_pages([text]))
    found = next(p for p in paragraphs if p.heading == "TERMINATION")
    assert found.section is None
    assert found.structure is not None
    assert found.structure.type == "heading"
    assert found.structure.title == "TERMINATION"
    assert "terminate this Agreement" in found.text


def test_ordinary_numbered_paragraphs_are_not_sections():
    text = (
        "1. The plaintiff filed a complaint before the tribunal seeking damages for breach.\n\n"
        "2. The defendant denied the allegations in a written statement thereafter."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))
    assert paragraphs
    assert all(p.section is None for p in paragraphs)
    assert all(p.heading is None for p in paragraphs)
    assert "plaintiff filed" in paragraphs[0].text


def test_page_numbers_dates_and_citations_are_not_sections():
    assert match_line("12") is None
    assert match_line("12/03/2023") is None
    assert match_line("AIR 2023 SC 1") is None


def test_indian_contract_act_core_sections_are_detected():
    dash = "\u2014"
    text = (
        "PRELIMINARY\n"
        f"2. Interpretation-clause.{dash}In this Act the following words and expressions are used "
        "in the following senses, unless a contrary intention appears from the context:-\n"
        "(a) When one person signifies to another his willingness to do or to abstain from doing anything, "
        "he is said to make a proposal;\n"
        "(d) When, at the desire of the promisor, the promisee or any other person has done or abstained "
        "from doing something, such act or abstinence or promise is called a consideration for the promise;\n\n"
        "CHAPTER II\n"
        "OF CONTRACTS, VOIDABLE CONTRACTS AND VOID AGREEMENTS\n"
        f'15. "Coercion" defined.{dash}"Coercion" is the committing, or threatening to commit, any act forbidden '
        "by the Indian Penal Code (45 of 1860).\n\n"
        f"19. Voidability of agreements without free consent.{dash}When consent to an agreement is caused by "
        "coercion, fraud or misrepresentation, the agreement is a contract voidable at the option of the party "
        "whose consent was so caused.\n\n"
        "CHAPTER VI\n"
        "OF THE CONSEQUENCES OF BREACH OF CONTRACT\n"
        f"73. Compensation for loss or damage caused by breach of contract.{dash}When a contract has been broken, "
        "the party who suffers by such breach is entitled to receive compensation."
    )
    paragraphs = StructureDetector().detect(make_pages([text]))
    by_section = {p.section: p for p in paragraphs}

    assert "2(d)" in by_section
    assert "consideration for the promise" in by_section["2(d)"].text
    assert by_section["2(d)"].text.startswith("(d) When, at the desire of the promisor")
    assert by_section["2(d)"].structure is not None
    assert by_section["2(d)"].structure.identifier == "2(d)"

    assert "15" in by_section
    assert "Coercion" in by_section["15"].text
    assert "15. \"Coercion\" defined" in by_section["15"].text

    assert "19" in by_section
    assert "voidable" in by_section["19"].text
    assert by_section["19"].text.startswith("19. Voidability")

    assert "73" in by_section
    assert "compensation" in by_section["73"].text.lower()
    assert by_section["73"].text.startswith("73. Compensation for loss")


def test_indian_contract_act_core_sections_become_chunks():
    dash = "\u2014"
    text = (
        f"2. Interpretation-clause.{dash}In this Act the following words and expressions are used "
        "in the following senses, unless a contrary intention appears from the context:-\n"
        "(d) When, at the desire of the promisor, the promisee or any other person has done or abstained "
        "from doing something, such act or abstinence or promise is called a consideration for the promise;\n\n"
        f'15. "Coercion" defined.{dash}"Coercion" is the committing, or threatening to commit, any act forbidden '
        "by the Indian Penal Code (45 of 1860).\n\n"
        f"19. Voidability of agreements without free consent.{dash}When consent to an agreement is caused by "
        "coercion, the agreement is a contract voidable at the option of the party whose consent was so caused.\n\n"
        f"73. Compensation for loss or damage caused by breach of contract.{dash}When a contract has been broken, "
        "the party who suffers by such breach is entitled to receive compensation."
    )
    chunks = LegalChunker().chunk(document_id="doc-1", pages=make_pages([text]))
    by_section = {c.section: c for c in chunks}

    assert "2(d)" in by_section
    assert "consideration for the promise" in by_section["2(d)"].text
    assert "15" in by_section
    assert "19" in by_section
    assert "73" in by_section
