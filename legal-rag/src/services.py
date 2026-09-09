"""Composition root: builds the RAG pipeline's services from configuration.

This is the single place that wires embedding, vector store, retrieval, and
generation together. Both the FastAPI backend and CLI scripts should import
`build_services` from here rather than constructing these objects themselves,
so there is exactly one code path that decides how the pipeline is assembled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.generation.citations import CitationMapper
from src.generation.context_builder import ContextBuilder
from src.generation.llm_service import GenerationService, LLMService
from src.generation.prompt import PromptBuilder
from src.generation.providers import DeepSeekLLMClient
from src.ingestion.service import DocumentUploadService
from src.retrieval.bm25_baseline import BM25Retriever
from src.retrieval.dense_baseline import DenseRetriever
from src.retrieval.hybrid_query_retriever import HybridQueryRetriever
from src.retrieval.hybrid_retrieval import HybridRetriever
from src.vectorstore.chroma_store import ChromaVectorStore
from src.vectorstore.service import VectorIndexService

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024


@dataclass
class Services:
    """The fully wired RAG pipeline."""

    settings: Settings
    upload_service: DocumentUploadService
    embedding_service: EmbeddingService
    index_service: VectorIndexService
    vector_store: ChromaVectorStore
    retriever: HybridQueryRetriever
    generation_service: GenerationService

    def rebuild_bm25_index(self) -> None:
        """Rebuild the BM25 half of hybrid retrieval from the current Chroma contents.

        BM25Retriever's inverted index is built once from a snapshot of
        records and has no incremental update path. Call this after
        indexing new chunks (see POST /ingest) so newly uploaded documents
        are lexically searchable too, not just via the dense half.
        """
        records = self.vector_store.get_all()
        self.retriever.hybrid_retriever.bm25_retriever = BM25Retriever(chunks=records)


def build_services(app_dir: Path) -> Services:
    """Construct the pipeline once, from environment configuration at app_dir/.env.

    app_dir is the directory containing .env and data/ - the FastAPI app and
    CLI scripts each resolve this from their own location and pass it in, so
    this function has no dependency on where it is imported from.

    Retrieval is hybrid (dense + BM25, RRF-fused): measured against the
    42-question evaluation dataset, hybrid reached recall@5=0.7838 versus
    dense-only's 0.6486 and BM25-only's 0.6757 (data/eval_runs/, see
    doc/06-evaluation.md). A hand-rolled reranker on top of hybrid was also
    measured and rejected - it dropped recall@5 to 0.6216.
    """
    data_dir = app_dir / "data"
    documents_dir = data_dir / "documents"
    chroma_dir = data_dir / "chroma"

    settings = Settings.from_env(app_dir / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())

    dense_retriever = DenseRetriever(embedding_provider=embedding_provider, vector_store=vector_store)
    bm25_retriever = BM25Retriever(chunks=vector_store.get_all())
    hybrid_retriever = HybridRetriever(dense_retriever=dense_retriever, bm25_retriever=bm25_retriever)

    return Services(
        settings=settings,
        upload_service=DocumentUploadService(storage_dir=documents_dir, max_file_size_bytes=MAX_UPLOAD_SIZE_BYTES),
        embedding_service=embedding_service,
        index_service=VectorIndexService(store=vector_store),
        vector_store=vector_store,
        retriever=HybridQueryRetriever(
            hybrid_retriever=hybrid_retriever,
            similarity_threshold=settings.similarity_threshold,
        ),
        generation_service=GenerationService(
            llm_service=LLMService(
                client=DeepSeekLLMClient(
                    api_key=settings.deepseek_api_key,
                    model_name=settings.deepseek_model,
                    base_url=settings.deepseek_base_url,
                )
            ),
            context_builder=ContextBuilder(),
            prompt_builder=PromptBuilder(),
            citation_mapper=CitationMapper(),
        ),
    )
