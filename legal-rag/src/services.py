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
from src.retrieval.retriever import Retriever
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
    retriever: Retriever
    generation_service: GenerationService


def build_services(app_dir: Path) -> Services:
    """Construct the pipeline once, from environment configuration at app_dir/.env.

    app_dir is the directory containing .env and data/ - the FastAPI app and
    CLI scripts each resolve this from their own location and pass it in, so
    this function has no dependency on where it is imported from.
    """
    data_dir = app_dir / "data"
    documents_dir = data_dir / "documents"
    chroma_dir = data_dir / "chroma"

    settings = Settings.from_env(app_dir / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=chroma_dir, dimension=embedding_service.embedding_dimension())

    return Services(
        settings=settings,
        upload_service=DocumentUploadService(storage_dir=documents_dir, max_file_size_bytes=MAX_UPLOAD_SIZE_BYTES),
        embedding_service=embedding_service,
        index_service=VectorIndexService(store=vector_store),
        retriever=Retriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
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
