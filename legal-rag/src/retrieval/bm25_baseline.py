"""BM25 lexical retrieval baseline for exact identifiers and rare terms.

BM25 is excellent for:
- Exact identifiers (Section 12.4, ERR-4821, ISO-27001)
- Rare proper nouns and technical terms
- Document-specific vocabularies
- Complement to dense retrieval

This module provides BM25 retrieval with the same instrumentation as dense_baseline.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass
from math import log

from src.ingestion.models import Chunk
from src.retrieval.exceptions import EmptyQueryError, NoRelevantResultsError
from src.vectorstore.base import VectorRecord


@dataclass(frozen=True)
class BM25Metrics:
    """Instrumentation from a single BM25 retrieval run."""

    query: str
    tokenization_time_ms: float
    index_search_time_ms: float
    total_time_ms: float
    candidates_found: int
    candidates_above_threshold: int
    index_size: int  # Number of documents in index
    vocabulary_size: int  # Number of unique terms
    retrieval_method: str = "bm25"


@dataclass(frozen=True)
class BM25Chunk:
    """Result from BM25 retrieval with score and metadata."""

    rank: int
    chunk_id: str
    document_id: str
    document_name: str | None
    score: float
    page_number: int
    section: str | None
    heading: str | None
    text: str
    category: str | None


@dataclass(frozen=True)
class BM25Result:
    """Complete BM25 retrieval result with chunks and metrics."""

    chunks: list[BM25Chunk]
    metrics: BM25Metrics


class BM25Index:
    """Inverted index for BM25 retrieval.

    Builds term frequency and document frequency statistics.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 parameters.

        Args:
            k1: Term frequency saturation parameter (default 1.5)
            b: Length normalization parameter (default 0.75)
        """
        self.k1 = k1
        self.b = b

        # Index structures
        self.documents: dict[str, VectorRecord] = {}  # chunk_id -> VectorRecord
        self.inverted_index: dict[str, set[str]] = defaultdict(set)  # term -> set of chunk_ids
        self.term_frequencies: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # chunk_id -> term -> count
        self.document_lengths: dict[str, int] = {}  # chunk_id -> token count
        self.document_frequency: dict[str, int] = defaultdict(int)  # term -> document count

        self.avg_doc_length = 0.0
        self.num_docs = 0

    def add_chunk(self, record: VectorRecord) -> None:
        """Add a chunk to the BM25 index.

        Args:
            record: VectorRecord to index
        """
        chunk_id = record.chunk_id
        self.documents[chunk_id] = record

        # Tokenize and build term statistics
        tokens = self._tokenize(record.text)
        self.document_lengths[chunk_id] = len(tokens)

        # Build inverted index and term frequencies
        seen_terms = set()
        for token in tokens:
            self.term_frequencies[chunk_id][token] += 1
            if token not in seen_terms:
                self.inverted_index[token].add(chunk_id)
                self.document_frequency[token] += 1
                seen_terms.add(token)

        self.num_docs += 1

    def _build_statistics(self) -> None:
        """Compute document frequency statistics (call after all documents added)."""
        if self.num_docs == 0:
            return

        total_length = sum(self.document_lengths.values())
        self.avg_doc_length = total_length / self.num_docs

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Search the index using BM25 scoring.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            List of (chunk_id, score) tuples, sorted by score descending
        """
        # Ensure statistics are built
        self._build_statistics()

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Calculate BM25 scores for each document
        scores: dict[str, float] = {}

        for token in query_tokens:
            if token not in self.inverted_index:
                continue

            # IDF calculation
            df = self.document_frequency[token]
            idf = log((self.num_docs - df + 0.5) / (df + 0.5) + 1)

            # Score documents containing this term
            for chunk_id in self.inverted_index[token]:
                tf = self.term_frequencies[chunk_id][token]
                doc_len = self.document_lengths[chunk_id]

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_length))
                score = idf * (numerator / denominator)

                scores[chunk_id] = scores.get(chunk_id, 0) + score

        # Sort by score and return top-k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for BM25 indexing.

        Preserves identifiers, handles common variations.
        """
        # Convert to lowercase
        text = text.lower()

        # Preserve identifiers: Section X.X, ERR-XXXX, ISO-XXXXX, etc.
        # Split on whitespace and punctuation but keep identifier-like tokens
        tokens = re.findall(r"\b[\w\-\.]+\b", text)

        # Filter: keep tokens >= 2 chars (avoids single letters)
        tokens = [t for t in tokens if len(t) >= 2]

        return tokens


class BM25Retriever:
    """BM25 retrieval with full instrumentation."""

    def __init__(self, chunks: list[VectorRecord], k1: float = 1.5, b: float = 0.75, min_score: float = 0.0):
        """Initialize BM25 retriever.

        Args:
            chunks: List of VectorRecord to index
            k1: BM25 k1 parameter (default 1.5)
            b: BM25 b parameter (default 0.75)
            min_score: Minimum score threshold (default 0.0)
        """
        self.min_score = min_score
        self.index = BM25Index(k1=k1, b=b)

        # Build index
        for chunk in chunks:
            self.index.add_chunk(chunk)

        self.index._build_statistics()

    def retrieve_bm25(self, query: str, top_k: int = 5) -> BM25Result:
        """Execute BM25 retrieval pipeline with instrumentation.

        Args:
            query: User query string
            top_k: Number of results to return

        Returns:
            BM25Result with chunks and metrics

        Raises:
            EmptyQueryError: If query is blank
            NoRelevantResultsError: If no results meet min_score threshold
        """
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be blank.")

        start_time = time.time()

        # Stage 1: Tokenization
        tokenize_start = time.time()
        query_tokens = self.index._tokenize(query)
        tokenization_time_ms = (time.time() - tokenize_start) * 1000

        # Stage 2: Index Search
        search_start = time.time()
        raw_results = self.index.search(query_tokens if query_tokens else query, top_k=top_k)
        search_time_ms = (time.time() - search_start) * 1000

        candidates_found = len(raw_results)

        # Stage 3: Threshold Filter
        above_threshold = [
            (chunk_id, score) for chunk_id, score in raw_results
            if score >= self.min_score
        ]
        candidates_above_threshold = len(above_threshold)

        if not above_threshold:
            raise NoRelevantResultsError("No sufficiently relevant chunks were found.")

        # Stage 4: Convert to BM25Chunk objects
        chunks = [
            BM25Chunk(
                rank=index + 1,
                chunk_id=chunk_id,
                document_id=self.index.documents[chunk_id].document_id,
                document_name=self.index.documents[chunk_id].document_name,
                score=score,
                page_number=self.index.documents[chunk_id].page_number,
                section=self.index.documents[chunk_id].section,
                heading=self.index.documents[chunk_id].heading,
                text=self.index.documents[chunk_id].text,
                category=self.index.documents[chunk_id].category,
            )
            for index, (chunk_id, score) in enumerate(above_threshold[:top_k])
        ]

        total_time_ms = (time.time() - start_time) * 1000

        # Build metrics
        metrics = BM25Metrics(
            query=query,
            tokenization_time_ms=tokenization_time_ms,
            index_search_time_ms=search_time_ms,
            total_time_ms=total_time_ms,
            candidates_found=candidates_found,
            candidates_above_threshold=candidates_above_threshold,
            index_size=self.index.num_docs,
            vocabulary_size=len(self.index.inverted_index),
        )

        return BM25Result(chunks=chunks, metrics=metrics)

    def batch_retrieve_bm25(self, queries: list[str], top_k: int = 5) -> list[BM25Result]:
        """Run BM25 retrieval on multiple queries.

        Args:
            queries: List of query strings
            top_k: Number of results per query

        Returns:
            List of BM25Result objects
        """
        results = []
        for query in queries:
            try:
                result = self.retrieve_bm25(query, top_k=top_k)
                results.append(result)
            except (EmptyQueryError, NoRelevantResultsError):
                # Continue on individual query failures
                pass
        return results
