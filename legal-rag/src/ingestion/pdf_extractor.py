"""PDF page extraction with page boundary preservation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

from src.ingestion.exceptions import UploadValidationError
from src.ingestion.models import DocumentPage


@dataclass(frozen=True)
class PDFExtractionResult:
    document_id: str
    filename: str
    storage_path: str
    pages: list[DocumentPage]


class PDFExtractor:
    """Extract page-level text while preserving citation metadata."""

    def extract(self, *, document_id: str, filename: str, storage_path: str, content: bytes) -> PDFExtractionResult:
        if not content:
            raise UploadValidationError("Uploaded file is empty.")

        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:  # noqa: BLE001
            raise UploadValidationError("Uploaded file is not a valid PDF.") from exc

        if reader.is_encrypted:
            raise UploadValidationError("Encrypted PDFs are not supported.")

        pages: list[DocumentPage] = []
        for page_index, page in enumerate(reader.pages, start=1):
            extracted_text = page.extract_text() or ""
            extraction_status = "extracted" if extracted_text.strip() else "no_text"
            pages.append(
                DocumentPage(
                    page_number=page_index,
                    text=extracted_text,
                    extraction_status=extraction_status,
                    document_id=document_id,
                    filename=filename,
                    storage_path=storage_path,
                )
            )

        return PDFExtractionResult(
            document_id=document_id,
            filename=filename,
            storage_path=storage_path,
            pages=pages,
        )
