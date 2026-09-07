"""Evaluation runner script - generates baseline retrieval metrics."""

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
    """Run evaluation harness and save results."""
    app_dir = Path(__file__).resolve().parent
    data_dir = app_dir / "data"
    chroma_dir = data_dir / "chroma"
    dataset_path = data_dir / "evaluation_dataset.json"
    results_path = data_dir / "evaluation_results.json"

    print("🔄 Loading settings...")
    settings = Settings.from_env(app_dir / ".env")

    print("📦 Initializing embeddings...")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)

    print("🔍 Loading vector store...")
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())

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

    print("\n" + "=" * 60)
    print("RETRIEVAL EVALUATION RESULTS")
    print("=" * 60)
    print(f"\n📈 Summary Metrics:")
    print(f"  Total Questions: {results.total_questions}")
    print(f"  In-Corpus Questions: {results.in_corpus_questions}")
    print(f"  Out-of-Corpus Questions: {results.out_of_corpus_questions}")
    print(f"\n✅ Retrieval Performance:")
    print(f"  Recall@1: {results.recall_at_1:.4f}")
    print(f"  Recall@3: {results.recall_at_3:.4f}")
    print(f"  Recall@5: {results.recall_at_5:.4f}")
    print(f"  MRR: {results.mrr:.4f}")
    print(f"\n🚫 Out-of-Corpus Detection Rate: {results.no_answer_detection_rate:.4f}")

    print(f"\n📊 Metrics by Question Type:")
    for q_type, metrics in results.metrics_by_type.items():
        print(f"\n  {q_type.replace('_', ' ').title()} (n={metrics['count']}):")
        print(f"    Recall@1: {metrics['recall_at_1']:.4f}")
        print(f"    Recall@3: {metrics['recall_at_3']:.4f}")
        print(f"    Recall@5: {metrics['recall_at_5']:.4f}")
        print(f"    MRR: {metrics['mrr']:.4f}")

    print("\n📁 Saving results...")
    with open(results_path, "w") as f:
        json.dump(results_dict, f, indent=2)

    print(f"✅ Results saved to {results_path}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
