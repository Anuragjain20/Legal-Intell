"""Ingest every PDF under a source directory into the vector store.

Walks <source>/<category>/[<subcategory>/]<filename>.pdf, runs each one
through the same DocumentUploadService the app uses (so document_id is
derived from content, storage is populated, and chunking matches
production exactly), then embeds and indexes every chunk. The category is
the immediate parent directory name; a directory nested one level deeper
(e.g. judgments/supreme_court) contributes its leaf name as the category
instead of the grouping directory.

The Chroma collection is dropped first so stale chunks from a previous
chunker version never coexist with newly produced ones.

Usage:
    python scripts/ingest.py --source /path/to/raw/pdfs
    python scripts/ingest.py    # defaults to data/documents_source/ if present
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from src.config.settings import Settings  # noqa: E402
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider  # noqa: E402
from src.embeddings.service import EmbeddingService  # noqa: E402
from src.ingestion.service import DocumentUploadService  # noqa: E402
from src.vectorstore.chroma_store import ChromaVectorStore  # noqa: E402
from src.vectorstore.service import VectorIndexService  # noqa: E402

DATA_DIR = APP_DIR / "data"
DEFAULT_SOURCE_DIR = DATA_DIR / "documents_source"
DOCUMENTS_DIR = DATA_DIR / "documents"
CHROMA_DIR = DATA_DIR / "chroma"


def _category_for(pdf_path: Path, source_dir: Path) -> str:
    """Category is the PDF's immediate parent, relative to source_dir.

    A PDF sitting directly under one category folder (source/acts/x.pdf)
    gets category "acts". A PDF nested one level deeper under a grouping
    folder (source/judgments/supreme_court/x.pdf) gets the leaf folder
    name "supreme_court" instead of the grouping folder "judgments".
    """
    return pdf_path.parent.name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing <category>/[<subcategory>/]*.pdf (default: data/documents_source)",
    )
    args = parser.parse_args()
    source_dir: Path = args.source

    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        print("Pass --source /path/to/raw/pdfs pointing at the category-organized PDF corpus.")
        return

    pdf_paths = sorted(source_dir.rglob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under {source_dir}")
        return

    categories = {_category_for(p, source_dir) for p in pdf_paths}
    print(f"Found {len(pdf_paths)} PDFs across {len(categories)} categories: {sorted(categories)}")

    if CHROMA_DIR.exists():
        print(f"Dropping existing vector store at {CHROMA_DIR}")
        shutil.rmtree(CHROMA_DIR)

    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=CHROMA_DIR, dimension=embedding_service.embedding_dimension())
    index_service = VectorIndexService(store=vector_store)
    upload_service = DocumentUploadService(storage_dir=DOCUMENTS_DIR)

    total_chunks = 0
    start = time.monotonic()

    for pdf_path in pdf_paths:
        category = _category_for(pdf_path, source_dir)
        content = pdf_path.read_bytes()

        metadata, extraction, chunks = upload_service.upload(
            filename=pdf_path.name,
            content=content,
            category=category,
            source_path=str(pdf_path),
        )
        embedded = embedding_service.embed_chunks(chunks)
        index_service.index_embeddings(embedded)

        total_chunks += len(chunks)
        print(f"  {category:16s} {pdf_path.name:70s} {len(chunks):4d} chunks  ({metadata.document_id[:12]}...)")

    elapsed = time.monotonic() - start
    print(f"\nIndexed {total_chunks} chunks from {len(pdf_paths)} documents in {elapsed:.1f}s")
    print(f"Vector store: {CHROMA_DIR}")


if __name__ == "__main__":
    main()
