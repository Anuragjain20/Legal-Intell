"""Document upload orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from src.ingestion.chunker import Chunker, LegalChunker
from src.ingestion.exceptions import UploadValidationError
from src.ingestion.models import Chunk, DocumentMetadata
from src.ingestion.pdf_extractor import PDFExtractionResult, PDFExtractor
from src.ingestion.storage import DocumentRegistry, DocumentStorage, normalize_category
from src.ingestion.validator import DocumentValidator


class DocumentUploadService:
    """Validate, store, extract, and chunk uploaded documents."""

    def __init__(
        self,
        storage_dir: Path,
        max_file_size_bytes: int = 50 * 1024 * 1024,
        chunker: Chunker | None = None,
    ) -> None:
        self.validator = DocumentValidator(max_file_size_bytes=max_file_size_bytes)
        self.storage = DocumentStorage(storage_dir)
        self.registry = DocumentRegistry(storage_dir.parent / "documents.json")
        self.extractor = PDFExtractor()
        self.chunker = chunker or LegalChunker()

    def upload(
        self, filename: str, content: bytes, category: str | None = None, source_path: str | None = None
    ) -> tuple[DocumentMetadata, PDFExtractionResult, list[Chunk]]:
        self.validator.validate(filename, content)
        safe_filename = Path(filename).name
        document_id = sha256(content).hexdigest()
        normalized_category = normalize_category(category)
        storage_path = self.storage.save(safe_filename, content, document_id, normalized_category)
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=safe_filename,
            file_type="pdf",
            file_size=len(content),
            upload_timestamp=datetime.now(timezone.utc),
            storage_path=str(storage_path),
            category=normalized_category,
            source_path=source_path,
        )
        extraction = self.extractor.extract(
            document_id=document_id,
            filename=safe_filename,
            storage_path=str(storage_path),
            content=content,
        )
        chunks = self.chunker.chunk(document_id=document_id, pages=extraction.pages, category=normalized_category)
        self.registry.upsert(metadata)
        return metadata, extraction, chunks
