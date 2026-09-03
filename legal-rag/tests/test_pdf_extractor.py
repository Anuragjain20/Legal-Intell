from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from src.ingestion.exceptions import UploadValidationError
from src.ingestion.pdf_extractor import PDFExtractor


def build_pdf(page_texts: list[str]) -> bytes:
    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=200, height=200)
        if text:
            stream = DecodedStreamObject()
            stream.set_data(
                f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("utf-8")
            )
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


def test_normal_pdf_produces_three_page_records():
    extractor = PDFExtractor()
    content = build_pdf(["First page", "Second page", "Third page"])

    result = extractor.extract(
        document_id="doc-1",
        filename="contract.pdf",
        storage_path="/tmp/contract.pdf",
        content=content,
    )

    assert len(result.pages) == 3


def test_page_numbering_starts_at_one():
    extractor = PDFExtractor()
    content = build_pdf(["A", "B", "C"])

    result = extractor.extract(
        document_id="doc-1",
        filename="contract.pdf",
        storage_path="/tmp/contract.pdf",
        content=content,
    )

    assert [page.page_number for page in result.pages] == [1, 2, 3]


def test_empty_page_is_preserved():
    extractor = PDFExtractor()
    content = build_pdf(["First page", "", "Third page"])

    result = extractor.extract(
        document_id="doc-1",
        filename="contract.pdf",
        storage_path="/tmp/contract.pdf",
        content=content,
    )

    assert len(result.pages) == 3
    middle_page = result.pages[1]
    assert middle_page.page_number == 2
    assert middle_page.text == ""
    assert middle_page.extraction_status == "no_text"


def test_invalid_pdf_fails_gracefully():
    extractor = PDFExtractor()

    with pytest.raises(UploadValidationError):
        extractor.extract(
            document_id="doc-1",
            filename="contract.pdf",
            storage_path="/tmp/contract.pdf",
            content=b"not-a-pdf",
        )


def test_document_identity_is_preserved():
    extractor = PDFExtractor()
    content = build_pdf(["First page", "Second page", "Third page"])

    result = extractor.extract(
        document_id="doc-123",
        filename="contract.pdf",
        storage_path="/tmp/contract.pdf",
        content=content,
    )

    assert all(page.document_id == "doc-123" for page in result.pages)
