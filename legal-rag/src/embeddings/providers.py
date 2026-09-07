"""Concrete embedding providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class EmptyTextError(ValueError):
    """Raised when blank text is sent to an embedding provider."""


def _ensure_non_blank(text: str) -> str:
    if not text or not text.strip():
        raise EmptyTextError("Embedding text must not be blank.")
    return text


@dataclass
class LocalHuggingFaceEmbeddingProvider:
    """Local embedding provider backed by a Hugging Face sentence-transformers model.

    This provider keeps the app free from remote API dependencies while still
    allowing high-quality semantic embeddings for legal text.
    """

    model_name: str = "BAAI/bge-small-en-v1.5"
    model_version: str = "1"
    query_instruction: str = "Represent this sentence for searching relevant passages: "

    def __post_init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only when optional deps are missing
            raise ImportError(
                "LocalHuggingFaceEmbeddingProvider requires 'sentence-transformers'."
            ) from exc

        self._model = SentenceTransformer(self.model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [_ensure_non_blank(text) for text in texts]
        vectors = self._model.encode(cleaned, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        # BGE retrieval models distinguish a search query from a document passage.
        # The instruction improves ranking without requiring the index to be rebuilt.
        return self.embed_documents([f"{self.query_instruction}{_ensure_non_blank(text)}"])[0]

    @property
    def embedding_dimension(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())


@dataclass
class LangChainEmbeddingProvider:
    """Adapter for any LangChain embeddings object.

    The wrapped object only needs ``embed_documents`` and ``embed_query``. This
    lets the rest of the app swap between OpenAI, Hugging Face, Ollama, Azure,
    and other LangChain-supported backends without code changes.
    """

    backend: Any
    model_name: str
    model_version: str = "1"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [_ensure_non_blank(text) for text in texts]
        return [list(vector) for vector in self.backend.embed_documents(cleaned)]

    def embed_query(self, text: str) -> list[float]:
        _ensure_non_blank(text)
        return list(self.backend.embed_query(text))

    @property
    def embedding_dimension(self) -> int:
        dimension = getattr(self.backend, "embedding_dimension", None)
        if dimension is not None:
            return int(dimension)
        probe = self.embed_query("dimension probe")
        return len(probe)


def build_langchain_provider(backend_name: str, **kwargs: Any) -> LangChainEmbeddingProvider:
    """Build a LangChain adapter from a backend name.

    Supported backends depend on the installed LangChain integration packages.
    """

    backend_name = backend_name.lower().strip()
    if backend_name == "huggingface":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "LangChain Hugging Face embeddings require 'langchain-huggingface'."
            ) from exc

        model = HuggingFaceEmbeddings(**kwargs)
        return LangChainEmbeddingProvider(backend=model, model_name=getattr(model, "model_name", backend_name))

    if backend_name == "openai":
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("LangChain OpenAI embeddings require 'langchain-openai'.") from exc

        model = OpenAIEmbeddings(**kwargs)
        return LangChainEmbeddingProvider(backend=model, model_name=getattr(model, "model", backend_name))

    raise ValueError(f"Unsupported LangChain backend: {backend_name}")
