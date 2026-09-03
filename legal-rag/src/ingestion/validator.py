"""Validation helpers for uploaded documents."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from src.ingestion.exceptions import UploadValidationError


class DocumentValidator:
    """Validate basic upload constraints before storage."""

    def __init__(self, max_file_size_bytes: int = 50 * 1024 * 1024) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    def validate(self, filename: str, content: bytes) -> None:
        if not filename or not filename.strip():
            raise UploadValidationError("Please provide a valid filename.")

        if Path(filename).suffix.lower() != ".pdf":
            raise UploadValidationError("Only PDF files are supported.")

        if not content:
            raise UploadValidationError("Uploaded file is empty.")

        if len(content) > self.max_file_size_bytes:
            raise UploadValidationError("File size exceeds the 50 MB limit.")

        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:  # noqa: BLE001
            raise UploadValidationError("Uploaded file is not a valid PDF.") from exc

        if reader.is_encrypted:
            raise UploadValidationError("Encrypted PDFs are not supported.")

        if len(reader.pages) == 0:
            raise UploadValidationError("PDF does not contain any pages.")
