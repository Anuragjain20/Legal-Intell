"""Adapts HybridRetriever to the Retriever.retrieve() interface for live queries.

Wraps HybridRetriever.retrieve_hybrid() so the rest of the query pipeline
(ContextBuilder, CitationMapper) can consume its results exactly like
Retriever's - same RetrievedChunk/VectorRecord shape, same
NoRelevantResultsError-on-no-confident-match contract.

Hybrid's own score is a Reciprocal Rank Fusion value (~0.01-0.03 scale,
1/(k+rank) summed across two methods) and is not a cosine similarity - it
cannot be compared against the dense similarity_threshold. Confidence
gating instead uses each result's dense_score, which is the same
cosine-similarity retrieval already produces on its own, so the same
threshold from Settings applies unchanged. Evaluated separately in
data/eval_runs/ (see doc/06-evaluation.md): the measured effect on this
corpus's 5 unanswerable questions is the same as dense-only - none of them
are actually rejected by a 0.35 threshold, because their dense_score is
0.72-0.81 - so wiring hybrid does not silently make refused unreachable,
it inherits dense's existing (documented) gate weakness honestly.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.retrieval.hybrid_retrieval import HybridRetriever
from src.retrieval.models import RetrievedChunk
from src.vectorstore.base import VectorRecord


@dataclass
class HybridQueryRetriever:
    """Hybrid (dense + BM25, RRF-fused) retrieval for the live query path."""

    hybrid_retriever: HybridRetriever
    similarity_threshold: float = 0.30

    def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[RetrievedChunk]:
        if filters:
            raise NotImplementedError("Metadata filters are not supported by HybridQueryRetriever.")
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be blank.")

        result = self.hybrid_retriever.retrieve_hybrid(query, top_k=top_k)

        accepted = [c for c in result.chunks if c.dense_score is not None and c.dense_score >= self.similarity_threshold]
        if not accepted:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found.")

        return [
            RetrievedChunk(
                rank=index + 1,
                score=chunk.score,
                retrieval_method="hybrid_rrf",
                record=VectorRecord(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    vector=[],
                    text=chunk.text,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    heading=chunk.heading,
                    embedding_model="",
                    embedding_version="",
                    document_name=chunk.document_name,
                    category=chunk.category,
                ),
            )
            for index, chunk in enumerate(accepted)
        ]
