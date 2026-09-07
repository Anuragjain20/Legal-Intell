"""Metrics calculation for retrieval evaluation.

Implements:
- Recall@K: Was the relevant chunk found in top-K?
- Precision@K: How much of top-K was relevant?
- MRR: Reciprocal Rank Fusion score
- nDCG: Normalized Discounted Cumulative Gain
"""

from __future__ import annotations

import math
from typing import Optional


def calculate_recall_at_k(
    relevant_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
    k: int = 5,
) -> float:
    """Calculate Recall@K.

    Recall@K = (# relevant chunks in top-k) / (# relevant chunks total)

    Answers: "Did we find all the relevant results?"

    Args:
        relevant_chunk_ids: Ground truth relevant chunks
        retrieved_chunk_ids: Chunks retrieved by retriever (in rank order)
        k: Evaluate at top-k

    Returns:
        Recall@K in [0, 1]
    """
    if not relevant_chunk_ids:
        return 1.0  # No relevant chunks expected

    top_k_chunks = set(retrieved_chunk_ids[:k])
    relevant_set = set(relevant_chunk_ids)

    found = len(top_k_chunks & relevant_set)
    return found / len(relevant_set)


def calculate_precision_at_k(
    relevant_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
    k: int = 5,
) -> float:
    """Calculate Precision@K.

    Precision@K = (# relevant chunks in top-k) / k

    Answers: "How much of what we returned was actually relevant?"

    Args:
        relevant_chunk_ids: Ground truth relevant chunks
        retrieved_chunk_ids: Chunks retrieved by retriever (in rank order)
        k: Evaluate at top-k

    Returns:
        Precision@K in [0, 1]
    """
    if k == 0:
        return 0.0

    top_k_chunks = set(retrieved_chunk_ids[:k])
    relevant_set = set(relevant_chunk_ids)

    found = len(top_k_chunks & relevant_set)
    return found / k


def calculate_mrr(
    relevant_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
) -> float:
    """Calculate Mean Reciprocal Rank.

    MRR = 1 / rank_of_first_relevant_result

    Answers: "How early did the first correct result appear?"

    Args:
        relevant_chunk_ids: Ground truth relevant chunks
        retrieved_chunk_ids: Chunks retrieved by retriever (in rank order)

    Returns:
        MRR in [0, 1]
        - 1.0 if first result is relevant
        - 0.5 if second result is first relevant
        - 0.333 if third result is first relevant
        - 0.0 if no relevant result found
    """
    relevant_set = set(relevant_chunk_ids)

    for rank, chunk_id in enumerate(retrieved_chunk_ids, 1):
        if chunk_id in relevant_set:
            return 1.0 / rank

    return 0.0  # No relevant result found


def calculate_ndcg_at_k(
    relevant_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
    k: int = 5,
) -> float:
    """Calculate Normalized Discounted Cumulative Gain.

    nDCG@K = DCG@K / IDCG@K

    DCG = sum(relevance_i / log2(i+1)) for i in top-k
    IDCG = ideal DCG (all relevant chunks first, then not relevant)

    Answers: "How well did we order results by relevance?"

    Relevance scoring:
    - 1.0 if chunk is in relevant set
    - 0.0 if chunk is not relevant

    Args:
        relevant_chunk_ids: Ground truth relevant chunks (ordered by relevance)
        retrieved_chunk_ids: Chunks retrieved by retriever (in rank order)
        k: Evaluate at top-k

    Returns:
        nDCG@K in [0, 1]
        - 1.0 if perfect ordering
        - 0.5 if half correct ordering
        - 0.0 if no relevant results
    """
    if not relevant_chunk_ids:
        return 1.0  # No relevant chunks expected

    # Calculate DCG (actual ranking)
    relevant_set = set(relevant_chunk_ids)
    dcg = 0.0

    for rank, chunk_id in enumerate(retrieved_chunk_ids[:k], 1):
        if chunk_id in relevant_set:
            # Relevance 1.0 if relevant, 0.0 otherwise
            dcg += 1.0 / math.log2(rank + 1)

    # Calculate IDCG (ideal ranking: all relevant first, then not relevant)
    idcg = 0.0
    num_relevant = len(relevant_chunk_ids)

    for rank in range(1, min(k + 1, num_relevant + 1)):
        idcg += 1.0 / math.log2(rank + 1)

    if idcg == 0.0:
        return 0.0

    return dcg / idcg


def find_first_relevant_rank(
    relevant_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
) -> Optional[int]:
    """Find rank (1-indexed) of first relevant chunk.

    Args:
        relevant_chunk_ids: Ground truth relevant chunks
        retrieved_chunk_ids: Chunks retrieved by retriever

    Returns:
        Rank (1-indexed) or None if no relevant chunk found
    """
    relevant_set = set(relevant_chunk_ids)

    for rank, chunk_id in enumerate(retrieved_chunk_ids, 1):
        if chunk_id in relevant_set:
            return rank

    return None


def calculate_all_metrics(
    relevant_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
) -> dict[str, dict[str, float]]:
    """Calculate all metrics for all K values.

    Args:
        relevant_chunk_ids: Ground truth relevant chunks
        retrieved_chunk_ids: Chunks retrieved (in rank order)

    Returns:
        Dict with metrics at different K values
    """
    k_values = [5, 10, 20]

    metrics = {}

    for k in k_values:
        metrics[f"recall_at_{k}"] = calculate_recall_at_k(
            relevant_chunk_ids, retrieved_chunk_ids, k
        )
        metrics[f"precision_at_{k}"] = calculate_precision_at_k(
            relevant_chunk_ids, retrieved_chunk_ids, k
        )
        metrics[f"ndcg_at_{k}"] = calculate_ndcg_at_k(
            relevant_chunk_ids, retrieved_chunk_ids, k
        )

    metrics["mrr"] = calculate_mrr(relevant_chunk_ids, retrieved_chunk_ids)
    metrics["first_relevant_rank"] = find_first_relevant_rank(
        relevant_chunk_ids, retrieved_chunk_ids
    )

    return metrics
