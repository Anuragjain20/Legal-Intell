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
from src.ingestion.chunker import Chunker
from src.ingestion.chunker_factory import CHUNKING_METHODS, build_chunker
from src.ingestion.service import DocumentUploadService
from src.retrieval.bm25_baseline import BM25Retriever
from src.retrieval.dense_baseline import DenseRetriever
from src.retrieval.hybrid_query_retriever import HybridQueryRetriever
from src.retrieval.hybrid_retrieval import HybridRetriever
from src.vectorstore.chroma_store import ChromaVectorStore
from src.vectorstore.service import VectorIndexService

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024


def chroma_dir_for_method(data_dir: Path, method: str) -> Path:
    """Each chunking method gets its own Chroma directory - chunking is baked
    into the index, so strategies must never share a collection."""
    return data_dir / "chroma" if method == "legal" else data_dir / f"chroma_{method}"


@dataclass
class Services:
    """The fully wired RAG pipeline.

    The active/default pipeline (settings.chunking_method, normally "legal")
    is what upload_service/vector_store/retriever point at - this is the
    path POST /query and the CLI's default ingest use, unchanged from
    before per-method chunking existed. chunkers/upload_services_by_method
    hold all CHUNKING_METHODS built once at startup, each with its own
    Chroma directory (see chroma_dir_for_method), so POST /ingest can
    route a request to any method without a second concurrent writer on
    the same Chroma path.
    """

    settings: Settings
    upload_service: DocumentUploadService
    embedding_service: EmbeddingService
    index_service: VectorIndexService
    vector_store: ChromaVectorStore
    retriever: HybridQueryRetriever
    generation_service: GenerationService
    chunkers: dict[str, Chunker]
    upload_services_by_method: dict[str, DocumentUploadService]
    vector_stores_by_method: dict[str, ChromaVectorStore]

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
    chroma_dir = chroma_dir_for_method(data_dir, "legal")

    settings = Settings.from_env(app_dir / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())

    dense_retriever = DenseRetriever(embedding_provider=embedding_provider, vector_store=vector_store)
    bm25_retriever = BM25Retriever(chunks=vector_store.get_all())
    hybrid_retriever = HybridRetriever(dense_retriever=dense_retriever, bm25_retriever=bm25_retriever)

    llm_client = DeepSeekLLMClient(
        api_key=settings.deepseek_api_key,
        model_name=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )

    # All three chunking methods are built once at startup, each pointed at its
    # own Chroma directory, so POST /ingest can route to any of them (Phase 8a)
    # without ever opening the same Chroma path from two writers.
    chunkers: dict[str, Chunker] = {}
    upload_services_by_method: dict[str, DocumentUploadService] = {}
    vector_stores_by_method: dict[str, ChromaVectorStore] = {}
    for method in CHUNKING_METHODS:
        chunker = build_chunker(
            settings,
            llm_client=llm_client,
            llm_cache_dir=data_dir / "llm_chunk_cache",
            method=method,
        )
        chunkers[method] = chunker
        if method == "legal":
            upload_services_by_method[method] = DocumentUploadService(
                storage_dir=documents_dir, max_file_size_bytes=MAX_UPLOAD_SIZE_BYTES, chunker=chunker
            )
            vector_stores_by_method[method] = vector_store
        else:
            method_chroma_dir = chroma_dir_for_method(data_dir, method)
            method_store = ChromaVectorStore(
                storage_dir=method_chroma_dir, dimension=embedding_service.embedding_dimension()
            )
            vector_stores_by_method[method] = method_store
            upload_services_by_method[method] = DocumentUploadService(
                storage_dir=documents_dir, max_file_size_bytes=MAX_UPLOAD_SIZE_BYTES, chunker=chunker
            )

    return Services(
        settings=settings,
        upload_service=upload_services_by_method["legal"],
        embedding_service=embedding_service,
        index_service=VectorIndexService(store=vector_store),
        vector_store=vector_store,
        retriever=HybridQueryRetriever(
            hybrid_retriever=hybrid_retriever,
            similarity_threshold=settings.similarity_threshold,
        ),
        generation_service=GenerationService(
            llm_service=LLMService(client=llm_client),
            context_builder=ContextBuilder(),
            prompt_builder=PromptBuilder(),
            citation_mapper=CitationMapper(),
        ),
        chunkers=chunkers,
        upload_services_by_method=upload_services_by_method,
        vector_stores_by_method=vector_stores_by_method,
    )
