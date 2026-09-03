"""Semantic retrieval over indexed vectors."""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.base import EmbeddingProvider
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.retrieval.models import RetrievalResult
from src.vectorstore.base import VectorStore


@dataclass
class Retriever:
    """Embed a query, search the vector store, and return ranked results."""

    embedding_provider: EmbeddingProvider
    vector_store: VectorStore
    similarity_threshold: float = 0.35

    def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[RetrievalResult]:
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be blank.")
        if filters:
            # Basic filter hook for future stories; intentionally unused for now.
            raise NotImplementedError("Metadata filters are not implemented yet.")

        query_vector = self.embedding_provider.embed_query(query)
        candidates = self.vector_store.search(query_vector, top_k=top_k)

        accepted = [
            RetrievalResult(rank=index + 1, score=result.score, record=result.record)
            for index, result in enumerate(candidates)
            if result.score >= self.similarity_threshold
        ]
        if not accepted:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found.")
        return accepted

