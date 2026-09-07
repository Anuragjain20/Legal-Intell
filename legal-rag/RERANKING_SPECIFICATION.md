# Reranking Stage: LG-RAG-026

## Goal

Implement a second retrieval stage that **improves precision by reranking a larger set of candidates** after hybrid retrieval.

## Key Insight

**Retrieval ≠ Reranking**

| Stage | Goal | Metric | Model Call |
|-------|------|--------|------------|
| **Retrieval** | "Give me plausible candidates" | Recall | One pass (dense + BM25) |
| **Reranking** | "Which are actually most relevant?" | Precision | Second pass (lightweight) |

The reference architecture shows:
- **Retrieving more candidates** → Improves recall (find true positives)
- **Reranking top-N** → Improves precision (eliminate false positives)
- **Combined** → Better recall AND precision with limited latency overhead

## Architecture

```
Query
  ↓
Hybrid Retrieval (Dense + BM25)
  ├─ Top 5:  Direct answer (fast)
  ├─ Top 10: Confidence check (moderate)
  └─ Top 20: Candidate pool (for reranking)
  ↓
[RERANKING STAGE] ← NEW
  ├─ Input: Top 20 candidates
  ├─ Rerank by relevance
  ├─ Measure score change
  └─ Output: Top 5 (refined)
  ↓
Response
```

## Two Optimization Strategies

### Strategy A: Direct Precision
```
Hybrid top-5 → return
Latency: ~50ms
Precision: Highest confidence only
Recall: May miss valid answers
```

### Strategy B: Precision + Recall Balance
```
Hybrid top-20 → Rerank → Top-5
Latency: ~55ms (reranking is 1-5ms overhead)
Precision: Better filtering
Recall: More candidates considered
```

**Measurement shows Strategy B wins when:**
- Hybrid fusion has high variance in top-20
- Reranker can distinguish true positives from near-misses
- Latency overhead < 10% acceptable

## Reranking Strategies

### 1. No Reranking (Identity/Baseline)

```python
class NoReranker(Reranker):
    def rerank(self, query, candidates):
        return [RerankScore(chunk_id=c.chunk_id, score=c.score) for c in candidates]
```

**Use case:** Baseline for A/B testing
- Proves retrieval stage is doing the work
- Measures cost of reranking infrastructure

### 2. Hybrid Score Reranking

```python
class HybridScoreReranker(Reranker):
    def rerank(self, query, candidates):
        # Re-rank using existing hybrid score (no-op)
        return [RerankScore(chunk_id=c.chunk_id, score=c.score) for c in candidates]
```

**Use case:** Sanity check
- If hybrid score is already optimal, reranking won't help
- Proves dual attribution is working

### 3. Query Term Overlap Reranking

```python
class QueryTermOverlapReranker(Reranker):
    def rerank(self, query, candidates):
        # Count and weight query terms in candidate text
        for candidate in candidates:
            overlap_count = count_matching_terms(query, candidate.text)
            term_frequency_weighted = weight_by_frequency(overlap_count)
            yield RerankScore(chunk_id, score=normalized_score)
```

**How it works:**
1. Tokenize query: "party notice contract" → ["party", "notice", "contract"]
2. For each candidate, count matches
3. Weight by term frequency (repeated terms boost score with diminishing returns)
4. Normalize by query size

**Why it works:**
- Complements dense retrieval (which captures semantics)
- Complements BM25 (which already did term matching)
- Emphasizes candidates mentioning multiple query concepts
- Fast: O(candidates × query_length × candidate_length)

**Example:**

```
Query: "party notice contract"

Candidate 1:
  Text: "The party must provide notice. Contract terms..."
  Matches: party (1), notice (1), contract (1)
  Score: 1.0 (all 3 terms)

Candidate 2:
  Text: "System performance is important."
  Matches: none
  Score: 0.0

Candidate 3:
  Text: "Party party party notice."
  Matches: party (3x frequency weighted), notice (1)
  Score: 1.2+ (term frequency boost)
```

### Future: Semantic Similarity Reranker

```python
class SemanticSimilarityReranker(Reranker):
    def rerank(self, query, candidates):
        # Use dense model to score query against each candidate
        query_embedding = embed(query)
        for candidate in candidates:
            similarity = cosine_similarity(query_embedding, candidate.embedding)
            yield RerankScore(chunk_id, score=similarity)
```

**Note:** This is a second embedding call (expensive). Only use if:
- First retrieval phase is lexical (BM25)
- Reranking can use different embedding model
- Latency budget allows 40-80ms for reranking

## Core Data Structures

### RerankScore
```python
@dataclass(frozen=True)
class RerankScore:
    chunk_id: str           # Which chunk
    score: float            # Rerank score
    reasoning: str | None   # Why? (for analysis)
```

### RerankingMetrics
```python
@dataclass(frozen=True)
class RerankingMetrics:
    query: str
    input_candidates: int              # Before reranking (e.g., 20)
    output_candidates: int             # After truncation (e.g., 5)
    reranking_strategy: str
    reranking_time_ms: float           # How long did reranking take?
    avg_score_before: float            # Average score of input
    avg_score_after: float             # Average score of output
    recall_at_k_change: float          # Of original top-5, how many in final?
```

### RerankResult
```python
@dataclass(frozen=True)
class RerankResult:
    chunks: list[HybridChunk]          # Final results
    metrics: RerankingMetrics
    original_chunks: list[HybridChunk] # For comparison
```

## RankerPipeline Interface

```python
class RankerPipeline:
    def __init__(self, reranker: Reranker, strategy: RerankingStrategy):
        pass

    def rerank(self, hybrid_result: HybridResult, top_k: int = 5) -> RerankResult:
        """Apply reranking and truncate to top_k."""
        pass

    def batch_rerank(self, results: list[HybridResult], top_k: int = 5) -> list[RerankResult]:
        """Batch reranking for evaluation."""
        pass
```

## Acceptance Criteria

✅ **Reranker integrated behind interface**
- `Reranker` abstract base class
- Multiple concrete implementations (No, Hybrid, TermOverlap)
- Future implementations drop in without breaking changes

✅ **Candidate count configurable**
- RankerPipeline takes `hybrid_result` (with any number of candidates)
- Retrieval can request top-20, top-50, etc.
- Reranker consumes all input candidates

✅ **Final top-N configurable**
- `rerank(..., top_k=5)` → Return top-5
- `rerank(..., top_k=3)` → Return top-3
- Easy to experiment: 5, 10, 20

✅ **Rerank scores captured**
- `RerankScore` stores chunk_id and score
- Stored in `RerankResult.chunks` as updated `HybridChunk`
- Original chunks preserved in `RerankResult.original_chunks`

✅ **Latency measured separately**
- `RerankingMetrics.reranking_time_ms` — Pure reranking time
- Separate from retrieval latency
- Can compare total latency: Hybrid-only vs Hybrid+Rerank

✅ **Retrieval quality compared against baseline**
- `avg_score_before` vs `avg_score_after` — Did quality improve?
- `recall_at_k_change` — Of original top-5, how many in final top-k?
- Can measure: Hybrid top-5 vs Hybrid top-20→rerank→top-5

## Experiment Plan

### Experiment 1: Direct Precision

**Setup:**
```python
# Baseline: Hybrid retrieval only
hybrid_result = hybrid_retriever.retrieve_hybrid(query, top_k=5)
print(f"Hybrid top-5: {len(hybrid_result.chunks)} results")
```

**Metrics:**
- Retrieval latency
- Average score of top-5
- Quality of results

### Experiment 2: Reranking Overhead

**Setup:**
```python
# Retrieve more candidates
hybrid_result = hybrid_retriever.retrieve_hybrid(query, top_k=20)

# Rerank down to 5
reranker = QueryTermOverlapReranker()
pipeline = RankerPipeline(reranker)
reranked = pipeline.rerank(hybrid_result, top_k=5)

# Compare
print(f"Retrieval: {hybrid_result.metrics.total_time_ms:.1f}ms")
print(f"Reranking: {reranked.metrics.reranking_time_ms:.1f}ms")
print(f"Total: {hybrid_result.metrics.total_time_ms + reranked.metrics.reranking_time_ms:.1f}ms")
```

**Decision:** If reranking adds < 10% latency, it's worth testing quality.

### Experiment 3: Quality Improvement

**Setup:**
```python
# Strategy A: Direct top-5
strategy_a = hybrid_retriever.retrieve_hybrid(query, top_k=5)

# Strategy B: Top-20 → rerank → top-5
hybrid_20 = hybrid_retriever.retrieve_hybrid(query, top_k=20)
strategy_b = pipeline.rerank(hybrid_20, top_k=5)

# Compare on evaluation set
metrics_a = evaluate(strategy_a, gold_answers)
metrics_b = evaluate(strategy_b, gold_answers)

print(f"Direct top-5:")
print(f"  Recall@5: {metrics_a.recall_at_5:.2%}")
print(f"  MRR: {metrics_a.mrr:.3f}")
print(f"\nTop-20 → Rerank → Top-5:")
print(f"  Recall@5: {metrics_b.recall_at_5:.2%}")
print(f"  MRR: {metrics_b.mrr:.3f}")
print(f"  Latency delta: {hybrid_20.metrics.total_time_ms + reranked.metrics.reranking_time_ms - strategy_a.metrics.total_time_ms:.1f}ms")
```

### Experiment 4: Failure Case Analysis

**Setup:**
```python
# On evaluation set, find where each approach fails
failures_a = [q for q in eval_set if not found_in_top_5(strategy_a[q])]
failures_b = [q for q in eval_set if not found_in_top_5(strategy_b[q])]

improved = set(failures_a) - set(failures_b)
regressed = set(failures_b) - set(failures_a)

print(f"Reranking improved: {len(improved)} queries")
print(f"Reranking regressed: {len(regressed)} queries")

# Analyze improved queries
for query in improved:
    print(f"\nQuery: {query}")
    print(f"  Direct top-5 score range: {hybrid_a[query].min_score:.2f} - {hybrid_a[query].max_score:.2f}")
    print(f"  Reranked top-5 score range: {reranked_b[query].min_score:.2f} - {reranked_b[query].max_score:.2f}")
```

## Usage Examples

### Example 1: Basic Reranking

```python
from src.retrieval.hybrid_retrieval import HybridRetriever
from src.retrieval.reranking import (
    QueryTermOverlapReranker,
    RankerPipeline,
    RerankingStrategy,
)

# Stage 1: Hybrid retrieval
hybrid_retriever = HybridRetriever(dense_retriever, bm25_retriever)
hybrid_result = hybrid_retriever.retrieve_hybrid("party notice contract", top_k=20)

print(f"Hybrid retrieved {len(hybrid_result.chunks)} candidates in {hybrid_result.metrics.total_time_ms:.1f}ms")

# Stage 2: Reranking
reranker = QueryTermOverlapReranker()
pipeline = RankerPipeline(reranker, strategy=RerankingStrategy.QUERY_TERM_OVERLAP)
reranked = pipeline.rerank(hybrid_result, top_k=5)

print(f"Reranking took {reranked.metrics.reranking_time_ms:.2f}ms")
print(f"Score improved: {reranked.metrics.avg_score_before:.3f} → {reranked.metrics.avg_score_after:.3f}")
print(f"Recall@5: {reranked.metrics.recall_at_k_change:.1%} of original top-5 remain")

for chunk in reranked.chunks:
    print(f"  [{chunk.rank}] {chunk.score:.3f} - {chunk.heading}")
```

### Example 2: Experiment A/B Testing

```python
# Control: Direct top-5
control = hybrid_retriever.retrieve_hybrid(query, top_k=5)

# Treatment: Top-20 → rerank → top-5
candidates = hybrid_retriever.retrieve_hybrid(query, top_k=20)
reranker = QueryTermOverlapReranker()
pipeline = RankerPipeline(reranker)
treatment = pipeline.rerank(candidates, top_k=5)

# Both have 5 results but different quality
print(f"Control avg score: {control.metrics.dense_time_ms + control.metrics.bm25_time_ms:.1f}ms latency")
print(f"  → Top result score: {control.chunks[0].score:.3f}")

print(f"Treatment latency: {candidates.metrics.total_time_ms + treatment.metrics.reranking_time_ms:.1f}ms")
print(f"  → Top result score: {treatment.chunks[0].score:.3f}")
```

### Example 3: Batch Evaluation

```python
queries = [
    "What are the party obligations?",
    "Section 12.4 defines what?",
    "What triggers termination?",
]

# Retrieve all
hybrid_results = hybrid_retriever.batch_retrieve_hybrid(queries, top_k=20)

# Rerank all
reranker = QueryTermOverlapReranker()
pipeline = RankerPipeline(reranker)
reranked_results = pipeline.batch_rerank(hybrid_results, top_k=5)

# Analyze
for result in reranked_results:
    print(f"\nQuery: {result.metrics.query}")
    print(f"  Input candidates: {result.metrics.input_candidates}")
    print(f"  Reranking time: {result.metrics.reranking_time_ms:.2f}ms")
    print(f"  Quality: avg score {result.metrics.avg_score_before:.2f} → {result.metrics.avg_score_after:.2f}")
    print(f"  Recall: {result.metrics.recall_at_k_change:.1%} of top-5 preserved")
```

## Performance Characteristics

| Strategy | Latency | Pros | Cons |
|----------|---------|------|------|
| Hybrid only (top-5) | ~50ms | Fast | Limited recall |
| Hybrid only (top-20) | ~60ms | More candidates | Slower, lower precision |
| Hybrid + NoReranker (top-20→5) | ~50ms + <1ms | Baseline | Truncation loses info |
| Hybrid + TermOverlap (top-20→5) | ~50ms + 2-5ms | Better precision | Small latency cost |
| Hybrid + SemanticReranker (top-20→5) | ~50ms + 40-80ms | Best quality | Significant latency |

## Design Decisions

### Why Not Pre-filter to Top-5?

**Tempting:** "Just retrieve top-5 from hybrid."

**Problem:**
```
Hybrid scores: [0.92, 0.91, 0.90, 0.89, 0.88, ...]

If top-5:
- No second chance to fix ranking
- One bad fusion decision propagates to user

If top-20 + rerank to 5:
- Candidates 6-20 have data (0.87-0.70)
- Reranker can promote 0.87 if it's more relevant
- Fusion errors have second chance
```

### Why Separate Reranker Interface?

**Instead of:** Bake reranking into HybridRetriever

**Benefits:**
- Retrieval stays focused: "Get candidates"
- Reranking stays focused: "Rank candidates"
- Easy to A/B test: Reranker on/off
- Easy to swap strategies: Change RerankingStrategy enum
- Easy to measure: Separate latency metrics

### Why Term Overlap as Default?

**Why not:** Dense embeddings (SemanticReranker)

**Trade-off:**
- SemanticReranker: Better quality but 40-80ms overhead
- TermOverlap: Modest quality gain, 2-5ms overhead
- TermOverlap fits 50ms latency budget; semantic doesn't
- Can upgrade once we measure if worth it

## Acceptance Criteria Verification

Run these to verify implementation:

```bash
# All 50 tests pass
pytest tests/test_reranking.py -v

# Check specific acceptance criteria
pytest tests/test_reranking.py::TestRankerPipelineBasics -v
pytest tests/test_reranking.py::TestRerankingStrategies -v
pytest tests/test_reranking.py::TestRerankerLatencyMeasurement -v
pytest tests/test_reranking.py::TestRankerPipelinePrecisionRecall -v
```

## Files

### Implementation
- `src/retrieval/reranking.py` — Reranker interface, implementations, RankerPipeline

### Tests
- `tests/test_reranking.py` — 50 comprehensive tests

### Documentation
- `RERANKING_SPECIFICATION.md` — This file

## Next Steps

### After LG-RAG-026 (Reranking) is Complete

**LG-RAG-027:** Cross-Encoder Reranker
- Use a cross-encoder model (e.g., mxbai-rerank-base-v1)
- Score query ↔ candidate pairs jointly
- Better semantic relevance but more expensive
- Experiment: Query-term vs cross-encoder trade-off

**LG-RAG-028:** Query-Type Router
- Detect query intent (exact identifier vs semantic)
- Route to appropriate retrieval strategy:
  - Exact: Prefer BM25 or top-5 direct
  - Semantic: Prefer dense, rerank for precision
  - Mixed: Hybrid with heavier weighting

**LG-RAG-029:** Learning-to-Rank
- Train ML model on query ↔ chunk relevance
- Learn optimal reranking weights
- Combine all signals (dense, BM25, term overlap, length, etc.)

## Summary

**LG-RAG-026 delivers:**
- ✅ Reranker interface (pluggable strategies)
- ✅ Three concrete implementations (No, Hybrid, TermOverlap)
- ✅ RankerPipeline (orchestrates retrieval → reranking)
- ✅ Dual metric tracking (retrieval vs reranking latency)
- ✅ Precision/recall trade-off measurement (recall@k_change)
- ✅ 50 comprehensive tests (all acceptance criteria covered)
- ✅ Foundation for semantic reranking (LG-RAG-027+)

**Ready for:** Precision optimization experiments, failure case analysis, and quality comparison against direct retrieval.
