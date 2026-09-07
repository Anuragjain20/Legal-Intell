"""Inspect the actual indexed corpus in Chroma."""

from pathlib import Path
from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.vectorstore.chroma_store import ChromaVectorStore
import json

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma"

def main():
    """Inspect indexed chunks."""
    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=CHROMA_DIR, dimension=embedding_service.embedding_dimension())

    # Get collection stats
    collection = vector_store.collection
    print(f"📊 Total chunks indexed: {collection.count()}\n")

    # Get all documents with limit
    results = collection.get(limit=10000)

    # Group by document
    by_document = {}
    for i, (chunk_id, metadata, _) in enumerate(zip(
        results["ids"],
        results["metadatas"],
        results["documents"]
    )):
        doc_name = metadata.get("document_name", "UNKNOWN")
        section = metadata.get("section", "UNKNOWN")
        heading = metadata.get("heading", "N/A")
        page = metadata.get("page_number", "?")

        if doc_name not in by_document:
            by_document[doc_name] = []

        by_document[doc_name].append({
            "chunk_id": chunk_id,
            "section": section,
            "heading": heading,
            "page": page,
            "text_preview": results["documents"][i][:100] + "..." if results["documents"][i] else "EMPTY"
        })

    # Print summary
    print("📚 Documents in Corpus:\n")
    for doc_name in sorted(by_document.keys()):
        chunks = by_document[doc_name]
        print(f"\n{doc_name}")
        print(f"  Chunks: {len(chunks)}")

        # Show unique sections
        sections = sorted(set(c["section"] for c in chunks))
        print(f"  Sections: {', '.join(sections[:5])}")
        if len(sections) > 5:
            print(f"           ... and {len(sections) - 5} more")

        # Show sample chunks
        print(f"  Samples:")
        for chunk in chunks[:3]:
            print(f"    • [{chunk['chunk_id'][:8]}...] Sec {chunk['section']}, Page {chunk['page']}")
            print(f"      {chunk['text_preview']}")

    # Export detailed inventory
    inventory = {
        "total_chunks": collection.count(),
        "documents": {}
    }

    for doc_name, chunks in by_document.items():
        inventory["documents"][doc_name] = {
            "chunk_count": len(chunks),
            "sections": sorted(set(c["section"] for c in chunks)),
            "page_range": [min(c["page"] for c in chunks), max(c["page"] for c in chunks)],
            "sample_chunks": chunks[:5]
        }

    with open(DATA_DIR / "corpus_inventory.json", "w") as f:
        json.dump(inventory, f, indent=2)

    print(f"\n\n✅ Detailed inventory saved to corpus_inventory.json")

if __name__ == "__main__":
    main()
