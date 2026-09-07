"""Semantic retrieval over indexed vectors."""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.base import EmbeddingProvider
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.retrieval.models import RetrievalRequest, RetrievalResponse, RetrievedChunk
from src.vectorstore.base import VectorStore


@dataclass
class Retriever:
    """Embed a query, search the vector store, and return ranked results."""

    embedding_provider: EmbeddingProvider
    vector_store: VectorStore
    similarity_threshold: float = 0.30

    def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[RetrievedChunk]:
        """Legacy interface: embed, search, threshold, and re-rank. Returns list for backward compatibility."""
        request = self._build_request_from_legacy(query, top_k, filters)
        response = self.retrieve_structured(request)
        return response.chunks

    def retrieve_structured(self, request: RetrievalRequest) -> RetrievalResponse:
        """Structured retrieval: accept RetrievalRequest, return RetrievalResponse with metadata."""
        query_vector = self.embedding_provider.embed_query(request.query)

        # Over-fetch to account for post-filtering.
        search_top_k = request.top_k * 4 if (request.document_ids or request.document_types) else request.top_k
        candidates = self.vector_store.search(query_vector, top_k=search_top_k)

        # Apply filters.
        filtered = self._apply_filters(candidates, request)

        # Threshold filter.
        accepted = [
            result for result in filtered
            if result.score >= self.similarity_threshold
        ]
        if not accepted:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found.")

        # Re-rank but preserve original scores.
        ranked = self._rank_by_relevance(accepted, request.query)

        # Truncate to requested top_k.
        final = ranked[: request.top_k]

        chunks = [
            RetrievedChunk(
                rank=index + 1,
                score=result.score,
                retrieval_method="dense_with_reranking",
                record=result.record,
            )
            for index, result in enumerate(final)
        ]

        return RetrievalResponse(
            chunks=chunks,
            embedding_model=candidates[0].record.embedding_model if candidates else "unknown",
            embedding_version=candidates[0].record.embedding_version if candidates else "unknown",
            retrieval_method="dense_with_reranking",
            total_searched=len(candidates),
        )

    def _build_request_from_legacy(self, query: str, top_k: int, filters: dict | None) -> RetrievalRequest:
        """Convert legacy (query, top_k, filters) to structured RetrievalRequest."""
        if filters and any(filters.values()):
            raise NotImplementedError("Metadata filters via dict are not supported. Use RetrievalRequest directly.")
        return RetrievalRequest(query=query, top_k=top_k)

    def _apply_filters(self, candidates: list, request: RetrievalRequest) -> list:
        """Apply document_ids and document_types filters to candidates."""
        result = candidates

        if request.document_ids:
            result = [
                c for c in result
                if c.record.document_id in request.document_ids
            ]

        if request.document_types:
            result = [
                c for c in result
                if c.record.category in request.document_types
            ]

        return result

    def _rank_by_relevance(self, results: list, query: str) -> list:
        """Re-rank results by: frontmatter > similarity > term matching > specificity. Preserves score."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        is_purpose_question = any(
            word in query_lower for word in ["purpose", "intent", "object", "aim", "goal", "why"]
        )

        def relevance_key(result) -> tuple[int, float, int, int]:
            is_frontmatter = result.record.section and result.record.section.startswith("FRONTMATTER:")
            frontmatter_priority = 0 if (is_purpose_question and is_frontmatter) else 1

            sim_score = result.score
            query_term_count = sum(
                1 for word in query_words
                if word in result.record.text.lower() and len(word) > 3
            )
            section_bonus = 0 if is_frontmatter else 1

            return (frontmatter_priority, -sim_score, -query_term_count, section_bonus)

        return sorted(results, key=relevance_key)
