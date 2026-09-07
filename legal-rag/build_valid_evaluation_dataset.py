"""Build a valid evaluation dataset grounded in actual corpus chunks."""

from pathlib import Path
import json
from typing import Optional
from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.vectorstore.chroma_store import ChromaVectorStore
from src.retrieval.retriever import Retriever

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma"

def get_corpus_inventory() -> dict:
    """Get inventory of all indexed chunks by document."""
    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=CHROMA_DIR, dimension=embedding_service.embedding_dimension())

    collection = vector_store._collection
    total = collection.count()
    print(f"[INFO] Total chunks indexed: {total}\n")

    # Get all chunks
    results = collection.get(limit=100000, include=["documents", "metadatas"])

    # Group by document
    by_document = {}
    for chunk_id, metadata, text in zip(results["ids"], results["metadatas"], results["documents"]):
        doc_name = metadata.get("document_name", "UNKNOWN")
        section = metadata.get("section", "UNKNOWN")
        heading = metadata.get("heading", "N/A")
        page = metadata.get("page_number", 0)
        doc_id = metadata.get("document_id", "UNKNOWN")

        if doc_name not in by_document:
            by_document[doc_name] = []

        by_document[doc_name].append({
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "section": section,
            "heading": heading,
            "page": page,
            "text": text[:200],
        })

    # Print inventory
    print("[CORPUS INVENTORY]\n")
    for doc_name in sorted(by_document.keys()):
        chunks = by_document[doc_name]
        sections = sorted(set(c["section"] for c in chunks if c["section"]))
        print(f"\n{doc_name}")
        print(f"  Total Chunks: {len(chunks)}")
        print(f"  Sections: {sections}")
        print(f"  Sample Chunks:")
        for chunk in chunks[:2]:
            print(f"    ID: {chunk['chunk_id'][:16]}...")
            print(f"    Sec: {chunk['section']}, Page: {chunk['page']}")
            print(f"    Text: {chunk['text']}...")

    return by_document

def create_evaluation_questions(inventory: dict, retriever: Retriever) -> list[dict]:
    """Create evaluation questions grounded in actual corpus chunks."""
    questions = []
    q_id = 1

    # 1. INDIAN CONTRACT ACT QUESTIONS (5-7)
    ica_chunks = inventory.get("indian_contract_act_1872.pdf", [])
    if ica_chunks:
        print("[INFO] Creating Indian Contract Act questions...")
        # Pick specific chunks and create questions about them
        for chunk in ica_chunks[:7]:
            if chunk["section"] and chunk["text"]:
                questions.append({
                    "id": f"Q{q_id:03d}",
                    "question": f"What does the {chunk['section']} section state about {chunk['heading']}?",
                    "expected_document": "indian_contract_act_1872.pdf",
                    "expected_section": chunk["section"],
                    "expected_chunk_id": chunk["chunk_id"],
                    "question_type": "direct_definition",
                    "context": f"Direct question about {chunk['section']}"
                })
                q_id += 1

    # 2. BHARATIYA NYAYA SANHITA QUESTIONS (5-7)
    bns_chunks = inventory.get("bharatiya_nyaya_sanhita_2023.pdf", [])
    if bns_chunks:
        print("[INFO] Creating Bharatiya Nyaya Sanhita questions...")
        for chunk in bns_chunks[:7]:
            if chunk["section"] and chunk["text"]:
                questions.append({
                    "id": f"Q{q_id:03d}",
                    "question": f"Describe the provisions in {chunk['section']} regarding {chunk['heading']}.",
                    "expected_document": "bharatiya_nyaya_sanhita_2023.pdf",
                    "expected_section": chunk["section"],
                    "expected_chunk_id": chunk["chunk_id"],
                    "question_type": "section_specific",
                    "context": f"Question about {chunk['section']}"
                })
                q_id += 1

    # 3. IT INTERMEDIARY GUIDELINES QUESTIONS (5-7)
    it_chunks = inventory.get("it_intermediary_guidelines_2021_updated_2023.pdf", [])
    if it_chunks:
        print("[INFO] Creating IT Intermediary Guidelines questions...")
        for chunk in it_chunks[:7]:
            if chunk["section"] and chunk["text"]:
                questions.append({
                    "id": f"Q{q_id:03d}",
                    "question": f"What are the requirements under {chunk['section']} for {chunk['heading']}?",
                    "expected_document": "it_intermediary_guidelines_2021_updated_2023.pdf",
                    "expected_section": chunk["section"],
                    "expected_chunk_id": chunk["chunk_id"],
                    "question_type": "section_specific",
                    "context": f"Regulatory requirement question"
                })
                q_id += 1

    # 4. CUAD CONTRACT QUESTIONS (5-7)
    contract_docs = [k for k in inventory.keys() if k.startswith(("Creditcards", "Cybergy", "Digital", "LinkPlus", "SouthernStar"))]
    if contract_docs:
        print("[INFO] Creating CUAD Contract questions...")
        for doc in contract_docs[:3]:
            chunks = inventory[doc]
            for chunk in chunks[:2]:
                if chunk["section"] and chunk["text"]:
                    questions.append({
                        "id": f"Q{q_id:03d}",
                        "question": f"According to this agreement, what are the details in {chunk['section']}?",
                        "expected_document": doc,
                        "expected_section": chunk["section"],
                        "expected_chunk_id": chunk["chunk_id"],
                        "question_type": "direct_definition",
                        "context": f"Contract clause question"
                    })
                    q_id += 1

    # 5. HIGH COURT DELHI JUDGMENT QUESTIONS (5)
    hc_docs = [k for k in inventory.keys() if "DLHC" in k]
    if hc_docs:
        print("[INFO] Creating Delhi High Court judgment questions...")
        for doc in hc_docs[:3]:
            chunks = inventory[doc]
            for chunk in chunks[:2]:
                if chunk["section"] and chunk["text"]:
                    questions.append({
                        "id": f"Q{q_id:03d}",
                        "question": f"In this judgment, what is stated in {chunk['section']} regarding {chunk['heading']}?",
                        "expected_document": doc,
                        "expected_section": chunk["section"],
                        "expected_chunk_id": chunk["chunk_id"],
                        "question_type": "consequence_effect",
                        "context": f"Judgment question"
                    })
                    q_id += 1

    # 6. PARAPHRASED QUESTIONS (5)
    print("[INFO] Creating paraphrased questions...")
    sample_chunks = []
    for chunks in inventory.values():
        sample_chunks.extend(chunks[:2])

    for chunk in sample_chunks[:5]:
        if chunk["section"] and chunk["text"]:
            questions.append({
                "id": f"Q{q_id:03d}",
                "question": f"In simpler terms, what does {chunk['section']} cover?",
                "expected_document": chunk["document_id"],
                "expected_section": chunk["section"],
                "expected_chunk_id": chunk["chunk_id"],
                "question_type": "paraphrased",
                "context": f"Simplified question"
            })
            q_id += 1

    # 7. OUT-OF-CORPUS QUESTIONS (5) - Run through retriever and record results
    print("[INFO] Creating out-of-corpus questions...")
    ooc_questions = [
        "What is the exchange rate for cryptocurrency payments?",
        "How do we handle arbitration disputes in Singapore?",
        "What are the environmental compliance requirements?",
        "Who are the approved subcontractors for this agreement?",
        "What are the tax implications for international parties?",
    ]

    for ooc_q in ooc_questions:
        try:
            results = retriever.retrieve(ooc_q, top_k=5)
            retrieved_sections = [
                {
                    "document_name": r.record.document_name,
                    "section": r.record.section,
                    "score": float(r.score)
                }
                for r in results
            ]
        except Exception as e:
            retrieved_sections = []
            print(f"  [WARNING] Error retrieving OOC question: {e}")

        questions.append({
            "id": f"Q{q_id:03d}",
            "question": ooc_q,
            "expected_document": None,
            "expected_section": None,
            "expected_chunk_id": None,
            "question_type": "out_of_corpus",
            "is_out_of_corpus": True,
            "retrieved_sections": retrieved_sections,
            "context": "Out-of-corpus question"
        })
        q_id += 1

    return questions

def main():
    """Main workflow."""
    print("=" * 70)
    print("BUILDING VALID EVALUATION DATASET FROM ACTUAL CORPUS")
    print("=" * 70)

    # Step 1: Get corpus inventory
    print("\n[STEP 1] Inspecting corpus...")
    inventory = get_corpus_inventory()

    # Step 2: Initialize retriever for OOC testing
    print("\n[STEP 2] Initializing retriever...")
    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=CHROMA_DIR, dimension=embedding_service.embedding_dimension())
    retriever = Retriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        similarity_threshold=settings.similarity_threshold,
    )

    # Step 3: Create questions
    print("\n[STEP 3] Creating evaluation questions...")
    questions = create_evaluation_questions(inventory, retriever)

    # Step 4: Build dataset
    dataset = {
        "metadata": {
            "version": "2.0",
            "created_at": "2026-09-06",
            "corpus": "MVP Legal Documents (Real)",
            "total_questions": len(questions),
            "in_corpus_questions": len([q for q in questions if not q.get("is_out_of_corpus")]),
            "out_of_corpus_questions": len([q for q in questions if q.get("is_out_of_corpus")]),
            "notes": "All in-corpus questions grounded in actual indexed chunks",
        },
        "questions": questions
    }

    # Step 5: Save dataset
    dataset_path = DATA_DIR / "evaluation_dataset.json"
    with open(dataset_path, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"\n[SUCCESS] Dataset saved to {dataset_path}")
    print(f"\n[SUMMARY] Statistics:")
    print(f"  Total Questions: {len(questions)}")
    print(f"  In-Corpus: {len([q for q in questions if not q.get('is_out_of_corpus')])}")
    print(f"  Out-of-Corpus: {len([q for q in questions if q.get('is_out_of_corpus')])}")
    print(f"\n  By Type:")
    by_type = {}
    for q in questions:
        t = q.get("question_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    for t, count in sorted(by_type.items()):
        print(f"    {t}: {count}")

if __name__ == "__main__":
    main()
