#!/usr/bin/env python3
"""Audit script for Legal RAG retrieval pipeline."""

import sys
import io
from pathlib import Path
from src.ingestion.pdf_extractor import PDFExtractor
from src.ingestion.chunker import LegalChunker
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
import numpy as np

# Fix Unicode output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Target sections to audit
TARGET_SECTIONS = {"2(d)", "10", "15", "19", "73"}
QUERIES = [
    "What is consideration?",
    "What happens when a contract is breached?",
    "What is the legal effect of coercion?"
]

def cosine_similarity(vec1, vec2):
    """Compute cosine similarity between two vectors."""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

def main():
    pdf_path = Path("data/documents/acts/d756d45a58c4cd8440e70a0189ea1fda9d7c5dfcdd6ef31a5f2ecd9cb209c59d-indian_contract_act_1872.pdf")

    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return

    print("=" * 100)
    print("LEGAL RAG PIPELINE AUDIT: Indian Contract Act 1872")
    print("=" * 100)

    # Step 1: Extract PDF
    print("\n📄 STEP 1: PDF EXTRACTION")
    print("-" * 100)
    extractor = PDFExtractor()
    content = pdf_path.read_bytes()
    extraction = extractor.extract(
        document_id="audit_test",
        filename="indian_contract_act_1872.pdf",
        storage_path=str(pdf_path),
        content=content
    )
    print(f"✅ Extracted {len(extraction.pages)} pages")

    # Show first few pages to verify extraction
    for i, page in enumerate(extraction.pages[:3]):
        status = "✅ Text" if page.extraction_status == "extracted" else "⚠️ Scanned"
        preview = page.text[:80].replace("\n", " ")
        print(f"   Page {page.page_number}: {status} | {preview}...")

    # Step 2: Chunk document
    print("\n✂️ STEP 2: CHUNKING")
    print("-" * 100)
    chunker = LegalChunker()
    chunks = chunker.chunk(document_id="audit_test", pages=extraction.pages, category="acts")
    print(f"✅ Created {len(chunks)} chunks")

    # Step 3: Find target sections
    print("\n🔍 STEP 3: LOCATE TARGET SECTIONS IN CHUNKS")
    print("-" * 100)

    target_chunks = {}
    for section_num in sorted(TARGET_SECTIONS):
        matching = [c for c in chunks if c.section and section_num in c.section]
        target_chunks[section_num] = matching

        print(f"\nSection {section_num}:")
        if matching:
            for i, chunk in enumerate(matching, 1):
                text_preview = chunk.text[:250].replace("\n", " ")
                print(f"\n  Result {i}:")
                print(f"    • Chunk ID: {chunk.chunk_id}")
                print(f"    • Page: {chunk.page_number}")
                print(f"    • Section: {chunk.section}")
                print(f"    • Heading: {chunk.heading}")
                print(f"    • Preview: {text_preview}...")
        else:
            print(f"  ❌ NOT FOUND in chunks with matching section metadata")

    # Step 4: Test retrieval
    print("\n" + "=" * 100)
    print("🔎 STEP 4: RETRIEVAL SCORING & RANKING")
    print("=" * 100)

    print("\n⏳ Loading embedding model...")
    embedding_provider = LocalHuggingFaceEmbeddingProvider()
    print("✅ Embedding model loaded")

    for query in QUERIES:
        print(f"\n{'=' * 100}")
        print(f"📝 Query: \"{query}\"")
        print(f"{'=' * 100}")

        query_vector = embedding_provider.embed_query(query)

        # Score all chunks
        chunk_scores = []
        chunk_vectors = embedding_provider.embed_documents([c.text for c in chunks])
        for chunk, chunk_vector in zip(chunks, chunk_vectors):
            score = cosine_similarity(query_vector, chunk_vector)
            chunk_scores.append((chunk, score))

        # Sort by score
        chunk_scores.sort(key=lambda x: x[1], reverse=True)

        # Show top 10
        print("\nTop 10 Retrieved Results:")
        print("-" * 100)
        for i, (chunk, score) in enumerate(chunk_scores[:10], 1):
            is_target = "⭐ TARGET" if any(s in (chunk.section or "") for s in TARGET_SECTIONS) else ""
            doc_name = chunk.document_name or "Indian_Contract_Act_1872"
            print(f"\n  [{i}] Score: {score:.4f} {is_target}")
            print(f"      Section: {chunk.section or 'N/A'}")
            print(f"      Heading: {chunk.heading or 'N/A'}")
            print(f"      Page: {chunk.page_number}")
            print(f"      Chunk ID: {chunk.chunk_id}")
            preview = chunk.text[:120].replace("\n", " ")
            print(f"      Text: {preview}...")

        # Find target sections in results
        print("\n" + "-" * 100)
        print("Target Sections in Results:")
        found_count = 0
        for section_num in sorted(TARGET_SECTIONS):
            section_chunks = [(c, s) for c, s in chunk_scores if c.section and section_num in c.section]
            if section_chunks:
                chunk, score = section_chunks[0]
                rank = next(i for i, (c, s) in enumerate(chunk_scores, 1) if c.chunk_id == chunk.chunk_id)
                print(f"  ✅ Section {section_num}: Rank #{rank:2d} | Score: {score:.4f}")
                found_count += 1
            else:
                print(f"  ❌ Section {section_num}: NOT RETRIEVED")

        if found_count == 0:
            print("  ⚠️  WARNING: None of the target sections were retrieved in top results")

    print("\n" + "=" * 100)
    print("AUDIT COMPLETE")
    print("=" * 100)

if __name__ == "__main__":
    main()
