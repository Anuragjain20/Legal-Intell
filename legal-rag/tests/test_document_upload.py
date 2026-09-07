from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from src.ingestion.exceptions import UploadValidationError
from src.ingestion.service import DocumentUploadService


def build_pdf_bytes() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return buffer.getvalue()


def build_pdf_with_text(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 250 Td ({text}) Tj ET".encode("utf-8"))
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


def build_service(tmp_path):
    return DocumentUploadService(storage_dir=tmp_path / "documents")


def test_valid_pdf_is_accepted(tmp_path):
    service = build_service(tmp_path)

    metadata, extraction, chunks = service.upload("contract.pdf", build_pdf_bytes())

    assert metadata.filename == "contract.pdf"
    assert metadata.file_type == "pdf"
    assert metadata.file_size > 0
    stored_path = tmp_path / "documents" / "uncategorized" / Path(metadata.storage_path).name
    assert stored_path.exists()
    assert stored_path.name.endswith("-contract.pdf")
    assert extraction.document_id == metadata.document_id
    # The blank test page has no text, so chunking legitimately produces nothing.
    assert chunks == []


@pytest.mark.parametrize("filename", ["notes.txt", "agreement.docx"])
def test_unsupported_file_types_are_rejected(tmp_path, filename):
    service = build_service(tmp_path)

    with pytest.raises(UploadValidationError):
        service.upload(filename, b"not a pdf")


def test_empty_file_is_rejected(tmp_path):
    service = build_service(tmp_path)

    with pytest.raises(UploadValidationError):
        service.upload("contract.pdf", b"")


def test_oversized_file_is_rejected(tmp_path):
    service = DocumentUploadService(
        storage_dir=tmp_path / "documents",
        max_file_size_bytes=10,
    )

    with pytest.raises(UploadValidationError):
        service.upload("contract.pdf", build_pdf_bytes())


def test_corrupt_pdf_is_rejected(tmp_path):
    service = build_service(tmp_path)

    with pytest.raises(UploadValidationError):
        service.upload("contract.pdf", b"%PDF-1.4\ncorrupt content")


def test_upload_produces_chunks_for_text_bearing_pdf(tmp_path):
    service = build_service(tmp_path)

    text = "This notice terminates the agreement effective immediately."
    metadata, _extraction, chunks = service.upload("notice.pdf", build_pdf_with_text(text))

    assert chunks
    assert all(c.document_id == metadata.document_id for c in chunks)


def test_reuploading_identical_content_reuses_the_document_id(tmp_path):
    service = build_service(tmp_path)

    first, _, _ = service.upload("first.pdf", build_pdf_bytes())
    second, _, _ = service.upload("second.pdf", build_pdf_bytes())

    assert first.document_id == second.document_id


def test_upload_preserves_category_on_chunks(tmp_path):
    service = build_service(tmp_path)

    metadata, _, chunks = service.upload(
        "notice.pdf", build_pdf_with_text("Termination requires notice."), category="contracts"
    )

    assert metadata.category == "contracts"
    assert chunks[0].category == "contracts"
    assert Path(metadata.storage_path).parent.name == "contracts"


def test_upload_records_document_metadata_in_json_catalog(tmp_path):
    service = build_service(tmp_path)

    metadata, _, _ = service.upload("contract.pdf", build_pdf_bytes(), category="master agreements")

    catalog = json.loads((tmp_path / "documents.json").read_text(encoding="utf-8"))
    assert catalog["documents"][0]["document_id"] == metadata.document_id
    assert catalog["documents"][0]["category"] == "master agreements"


def test_upload_storage_uses_only_the_filename_component(tmp_path):
    service = build_service(tmp_path)

    metadata, _, _ = service.upload("../contract.pdf", build_pdf_bytes())

    stored_path = Path(metadata.storage_path)
    assert stored_path.parent == tmp_path / "documents" / "uncategorized"
    assert stored_path.name.endswith("-contract.pdf")
