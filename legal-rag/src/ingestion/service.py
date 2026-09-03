"""Document upload orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.ingestion.chunker import LegalChunker
from src.ingestion.exceptions import UploadValidationError
from src.ingestion.models import Chunk, DocumentMetadata
from src.ingestion.pdf_extractor import PDFExtractionResult, PDFExtractor
from src.ingestion.storage import DocumentStorage
from src.ingestion.validator import DocumentValidator


class DocumentUploadService:
    """Validate, store, extract, and chunk uploaded documents."""

    def __init__(
        self,
        storage_dir: Path,
        max_file_size_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.validator = DocumentValidator(max_file_size_bytes=max_file_size_bytes)
        self.storage = DocumentStorage(storage_dir)
        self.extractor = PDFExtractor()
        self.chunker = LegalChunker()

    def upload(self, filename: str, content: bytes) -> tuple[DocumentMetadata, PDFExtractionResult, list[Chunk]]:
        self.validator.validate(filename, content)
        document_id = str(uuid4())
        storage_path = self.storage.save(filename, content)
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=filename,
            file_type="pdf",
            file_size=len(content),
            upload_timestamp=datetime.now(timezone.utc),
            storage_path=str(storage_path),
        )
        extraction = self.extractor.extract(
            document_id=document_id,
            filename=filename,
            storage_path=str(storage_path),
            content=content,
        )
        chunks = self.chunker.chunk(document_id=document_id, pages=extraction.pages)
        return metadata, extraction, chunks
