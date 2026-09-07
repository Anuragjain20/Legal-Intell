#!/usr/bin/env python3
"""Re-ingest the Contract Act with updated hierarchical metadata."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.ingestion.service import DocumentUploadService
from src.vectorstore.chroma_store import ChromaVectorStore
from src.vectorstore.service import VectorIndexService

def reingest():
    print("=" * 80)
    print("RE-INGESTING CONTRACT ACT WITH HIERARCHICAL METADATA")
    print("=" * 80)

    settings = Settings.from_env(Path(".env"))
    app_dir = Path(__file__).parent
    data_dir = app_dir / "data"
    documents_dir = data_dir / "documents"
    chroma_dir = data_dir / "chroma"

    # Find the Contract Act PDF
    contract_act_path = None
    for doc_dir in [documents_dir / "acts", documents_dir]:
        for pdf_file in doc_dir.glob("*indian_contract_act*"):
            contract_act_path = pdf_file
            break
        if contract_act_path:
            break

    if not contract_act_path or not contract_act_path.exists():
        print("❌ Contract Act PDF not found")
        return

    print(f"\n✓ Found: {contract_act_path.name}")

    # Setup services
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())
    index_service = VectorIndexService(store=vector_store)
    upload_service = DocumentUploadService(storage_dir=documents_dir)

    # Re-ingest the document
    print(f"\n📖 Processing {contract_act_path.name}...")

    with open(contract_act_path, "rb") as f:
        content = f.read()

    metadata, extraction, chunks = upload_service.upload(
        filename=contract_act_path.name,
        content=content,
        category="acts",
    )

    print(f"\n✓ Extracted: {len(extraction.pages)} pages")
    print(f"✓ Created: {len(chunks)} chunks")

    # Embed and index
    print("\n🔄 Embedding chunks...")
    embedded = embedding_service.embed_chunks(chunks)
    print(f"✓ Embedded: {len(embedded)} chunks")

    print("\n💾 Indexing in Chroma...")
    index_service.index_embeddings(embedded)
    print(f"✓ Indexed: {len(embedded)} chunks")

    # Sample output
    print("\n" + "=" * 80)
    print("SAMPLE CHUNK METADATA")
    print("=" * 80)

    target_sections = ["2(d)", "15", "19", "73"]
    for chunk in chunks[:100]:  # Check first 100 chunks
        if chunk.section in target_sections:
            print(f"\n✓ Found Section {chunk.section}:")
            print(f"  - Chunk ID: {chunk.chunk_id}")
            print(f"  - Page: {chunk.page_number}")
            print(f"  - Heading: {chunk.heading}")
            print(f"  - Section Number: {chunk.section_number}")
            print(f"  - Subsection: {chunk.subsection}")
            print(f"  - Clause: {chunk.clause}")
            print(f"  - Structure Path: {chunk.structure_path}")
            print(f"  - Text (first 100 chars): {chunk.text[:100]}...")

    print("\n" + "=" * 80)
    print("✓ RE-INGESTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    reingest()
