"""Ingest every PDF under a source directory into the vector store.

Walks <source>/<category>/[<subcategory>/]<filename>.pdf, runs each one
through the same DocumentUploadService the app uses (so document_id is
derived from content, storage is populated, and chunking matches
production exactly), then embeds and indexes every chunk. The category is
the immediate parent directory name; a directory nested one level deeper
(e.g. judgments/supreme_court) contributes its leaf name as the category
instead of the grouping directory.

The Chroma collection is dropped first so stale chunks from a previous
chunker version never coexist with newly produced ones. Each chunking
method has its own Chroma directory (data/chroma for "legal", the
default; data/chroma_<method> otherwise) so re-ingesting under one
strategy never clobbers another's index.

Usage:
    python scripts/ingest.py --source /path/to/raw/pdfs
    python scripts/ingest.py    # defaults to data/documents_source/ if present
    python scripts/ingest.py --chunking-method recursive
    python scripts/ingest.py --chunking-method llm_semantic
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
from src.generation.providers import DeepSeekLLMClient  # noqa: E402
from src.ingestion.chunker_factory import CHUNKING_METHODS, build_chunker  # noqa: E402
from src.ingestion.service import DocumentUploadService  # noqa: E402
from src.vectorstore.chroma_store import ChromaVectorStore  # noqa: E402
from src.vectorstore.service import VectorIndexService  # noqa: E402

DATA_DIR = APP_DIR / "data"
DEFAULT_SOURCE_DIR = DATA_DIR / "documents_source"
DOCUMENTS_DIR = DATA_DIR / "documents"


def _chroma_dir_for(method: str) -> Path:
    """The "legal" (default) method keeps today's data/chroma path, since
    that's what build_services()/the running API already point at by
    default; the two new methods get their own directory so re-ingesting
    under one strategy never clobbers another's index."""
    return DATA_DIR / "chroma" if method == "legal" else DATA_DIR / f"chroma_{method}"


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
    parser.add_argument(
        "--chunking-method",
        choices=CHUNKING_METHODS,
        default="legal",
        help="Chunking strategy to ingest with (default: legal). Each method is indexed "
        "into its own Chroma directory so strategies never collide.",
    )
    args = parser.parse_args()
    source_dir: Path = args.source
    chroma_dir = _chroma_dir_for(args.chunking_method)

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
    print(f"Chunking method: {args.chunking_method}")

    if chroma_dir.exists():
        print(f"Dropping existing vector store at {chroma_dir}")
        shutil.rmtree(chroma_dir)

    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())
    index_service = VectorIndexService(store=vector_store)

    llm_client = None
    if args.chunking_method == "llm_semantic":
        llm_client = DeepSeekLLMClient(
            api_key=settings.deepseek_api_key,
            model_name=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
        )
    chunker = build_chunker(
        settings,
        llm_client=llm_client,
        llm_cache_dir=DATA_DIR / "llm_chunk_cache",
        method=args.chunking_method,
    )
    upload_service = DocumentUploadService(storage_dir=DOCUMENTS_DIR, chunker=chunker)

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
    print(f"Vector store: {chroma_dir}")


if __name__ == "__main__":
    main()
