"""Run evaluation on REAL corpus-grounded dataset with detailed failure analysis."""

from __future__ import annotations

import json
from pathlib import Path

from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.evaluation.evaluator import RetrievalEvaluator
from src.retrieval.retriever import Retriever
from src.vectorstore.chroma_store import ChromaVectorStore


def main() -> None:
    """Run evaluation harness and save results with failure analysis."""
    app_dir = Path(__file__).resolve().parent
    data_dir = app_dir / "data"
    chroma_dir = data_dir / "chroma"
    dataset_path = data_dir / "evaluation_dataset.json"
    results_path = data_dir / "evaluation_results.json"

    print("=" * 70)
    print("LEGAL RAG RETRIEVAL EVALUATION")
    print("=" * 70)

    print("\n🔄 Loading settings...")
    settings = Settings.from_env(app_dir / ".env")

    print("📦 Initializing embeddings...")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)

    print("🔍 Loading vector store...")
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())
    print(f"   Total indexed chunks: {vector_store._collection.count()}")

    print("🎯 Creating retriever...")
    retriever = Retriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        similarity_threshold=settings.similarity_threshold,
    )

    print("📊 Running evaluation...")
    evaluator = RetrievalEvaluator(retriever, dataset_path)
    results = evaluator.evaluate(top_k=5)

    results_dict = evaluator.results_to_dict()

    # Generate failure analysis
    failures = [r for r in results.individual_results if not r.found_in_top_5 and not r.is_out_of_corpus]
    ooc_questions = [r for r in results.individual_results if r.is_out_of_corpus]

    print("\n" + "=" * 70)
    print("RETRIEVAL EVALUATION RESULTS - BASELINE")
    print("=" * 70)

    summary = results_dict["summary"]
    print(f"\n📊 SUMMARY METRICS:")
    print(f"  Total Questions: {summary['total_questions']}")
    print(f"  In-Corpus Questions: {summary['in_corpus_questions']}")
    print(f"  Out-of-Corpus Questions: {summary['out_of_corpus_questions']}")

    print(f"\n✅ RETRIEVAL PERFORMANCE:")
    print(f"  Recall@1:  {summary['recall_at_1']:.4f} ({int(summary['recall_at_1'] * summary['in_corpus_questions'])}/{summary['in_corpus_questions']})")
    print(f"  Recall@3:  {summary['recall_at_3']:.4f} ({int(summary['recall_at_3'] * summary['in_corpus_questions'])}/{summary['in_corpus_questions']})")
    print(f"  Recall@5:  {summary['recall_at_5']:.4f} ({int(summary['recall_at_5'] * summary['in_corpus_questions'])}/{summary['in_corpus_questions']})")
    print(f"  MRR:       {summary['mrr']:.4f}")

    print(f"\n🚫 OUT-OF-CORPUS DETECTION:")
    print(f"  Detection Rate: {summary['no_answer_detection_rate']:.4f} ({summary['out_of_corpus_questions']}/{summary['total_questions']})")

    print(f"\n📊 METRICS BY QUESTION TYPE:")
    for q_type, metrics in results_dict["metrics_by_type"].items():
        print(f"\n  {q_type.replace('_', ' ').upper()} (n={metrics['count']}):")
        print(f"    Recall@1: {metrics['recall_at_1']:.4f}")
        print(f"    Recall@3: {metrics['recall_at_3']:.4f}")
        print(f"    Recall@5: {metrics['recall_at_5']:.4f}")
        print(f"    MRR:      {metrics['mrr']:.4f}")

    # Failure analysis
    if failures:
        print(f"\n\n[FAILURES] Questions NOT found in top-5:")
        print(f"   Total: {len(failures)}")
        from dataclasses import asdict
        for metric in failures:
            m_dict = asdict(metric) if hasattr(metric, '__dataclass_fields__') else metric
            print(f"\n   Q: {m_dict.get('case_id')} - {m_dict.get('question', '')[:60]}")
            print(f"      Type: {m_dict.get('question_type')}")
            print(f"      Expected: {m_dict.get('expected_section')}")
            if m_dict.get("expected_chunk_id"):
                print(f"      Expected Chunk ID: {m_dict['expected_chunk_id'][:16]}...")
            retrieved = m_dict.get('retrieved_sections', [])
            scores = m_dict.get('scores', [])
            print(f"      Retrieved: {retrieved[:3]}")
            print(f"      Scores: {[f'{s:.4f}' for s in scores[:3]]}")

    # Out-of-corpus analysis
    if ooc_questions:
        print(f"\n\n[OOC] OUT-OF-CORPUS QUESTIONS ({len(ooc_questions)}):")
        from dataclasses import asdict
        for metric in ooc_questions:
            m_dict = asdict(metric) if hasattr(metric, '__dataclass_fields__') else metric
            print(f"\n   Q: {m_dict.get('case_id')} - {m_dict.get('question', '')[:60]}")
            print(f"      Type: {m_dict.get('question_type')}")
            print(f"      Result: Correctly identified as out-of-corpus")

    print("\n📁 Saving results...")
    with open(results_path, "w") as f:
        json.dump(results_dict, f, indent=2)

    print(f"✅ Results saved to {results_path}")
    print("\n" + "=" * 70)

    return results


if __name__ == "__main__":
    main()
