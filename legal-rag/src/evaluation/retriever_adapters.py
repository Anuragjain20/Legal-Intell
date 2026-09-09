"""Adapters that let harness.py score dense, BM25, hybrid, and reranked
retrieval through the same evaluate_case()/run_evaluation() code path.

harness.py's scoring reads chunk.record.chunk_id / .document_name / .text -
the shape Retriever.retrieve() already returns. BM25Retriever, HybridRetriever,
and RankerPipeline each return their own flat-field chunk dataclasses instead
(no nested .record), so each adapter here wraps one method's result chunks
into that same nested shape and exposes retrieve(question, top_k) -> list,
raising NoRelevantResultsError exactly like Retriever.retrieve() does. This
keeps exactly one implementation of the scoring logic for every method being
compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.retrieval.bm25_baseline import BM25Retriever
from src.retrieval.exceptions import NoRelevantResultsError
from src.retrieval.hybrid_retrieval import HybridRetriever
from src.retrieval.reranking import RankerPipeline


@dataclass(frozen=True)
class _RecordView:
    """Minimal stand-in for VectorRecord: only the fields harness.py reads."""

    chunk_id: str
    document_name: str | None
    text: str


@dataclass(frozen=True)
class _ScoredChunk:
    """Minimal stand-in for RetrievedChunk: score + a nested .record."""

    score: float
    record: _RecordView


def _wrap(chunks: list) -> list[_ScoredChunk]:
    return [
        _ScoredChunk(score=c.score, record=_RecordView(chunk_id=c.chunk_id, document_name=c.document_name, text=c.text))
        for c in chunks
    ]


class EvaluatableRetriever(Protocol):
    """The interface harness.evaluate_case() actually needs from a retriever."""

    def retrieve(self, question: str, top_k: int) -> list[_ScoredChunk]:
        ...


@dataclass
class BM25RetrieverAdapter:
    """Adapts BM25Retriever.retrieve_bm25() to the Retriever.retrieve() shape."""

    bm25_retriever: BM25Retriever

    def retrieve(self, question: str, top_k: int) -> list[_ScoredChunk]:
        result = self.bm25_retriever.retrieve_bm25(question, top_k=top_k)
        return _wrap(result.chunks)


@dataclass
class HybridRetrieverAdapter:
    """Adapts HybridRetriever.retrieve_hybrid() to the Retriever.retrieve() shape."""

    hybrid_retriever: HybridRetriever

    def retrieve(self, question: str, top_k: int) -> list[_ScoredChunk]:
        result = self.hybrid_retriever.retrieve_hybrid(question, top_k=top_k)
        return _wrap(result.chunks)


@dataclass
class RerankedHybridRetrieverAdapter:
    """Adapts HybridRetriever + RankerPipeline to the Retriever.retrieve() shape.

    Over-fetches from the hybrid retriever before reranking, since a reranker
    can only reorder candidates it was given - top_k alone would starve it.
    """

    hybrid_retriever: HybridRetriever
    ranker_pipeline: RankerPipeline
    overfetch_factor: int = 3

    def retrieve(self, question: str, top_k: int) -> list[_ScoredChunk]:
        hybrid_result = self.hybrid_retriever.retrieve_hybrid(question, top_k=top_k * self.overfetch_factor)
        reranked = self.ranker_pipeline.rerank(hybrid_result, top_k=top_k)
        if not reranked.chunks:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found after reranking.")
        return _wrap(reranked.chunks)
