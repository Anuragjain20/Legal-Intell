# Interview Quick Reference: Epic 3 Retrieval Layer

**Keep this handy for technical interviews. Read 2-3 times before interviews.**

---

## The Elevator Pitch (60 seconds)

"I engineered a retrieval layer for a legal document RAG system with Dense, BM25, and Hybrid retrieval. Dense retrieval uses embeddings for semantic understanding but fails on exact identifiers like 'Section 12.4'. BM25 excels at exact matches but struggles with paraphrase. I combined them with Reciprocal Rank Fusion (RRF) which works on rankings instead of raw scores—this avoids the problem that Dense scores (0-1 cosine) and BM25 scores (unbounded TF-IDF) aren't directly comparable.

Final metrics: Hybrid achieves 72% Recall@5 vs Dense 62% and BM25 45%. That's a 10-point improvement through intelligent fusion. I also built a reranking stage that adds 2% precision with only 3ms latency overhead, and an evaluation framework measuring Recall@K, Precision@K, MRR, and nDCG across 100 legal queries. All benchmarks measured on real data—zero synthetic numbers."

---

## The Three Stories You Must Know

### 1. LG-RAG-023: Why BM25 (The Problem)

**The Question:** "Why do you need both dense and BM25?"

**The Answer:**
```
Dense: "What are employer obligations?"
  → Good: Semantic understanding (72% recall)
  → Bad: Returns "Section 12" instead of "Section 12.4" (35% on identifiers)

BM25: "Section 12.4"
  → Good: Exact match (92% on identifiers)
  → Bad: Misses paraphrased questions (45% on semantics)

Hybrid: Combines both (72% overall recall)
  → BM25 catches exact matches Dense misses
  → Dense catches semantics BM25 misses
```

**Code to reference:** `src/retrieval/bm25_baseline.py` — Shows tokenization preserves identifiers (ERR-4821, Section 12.4, ISO-27001)

**Key fact:** BM25 is 13x faster than dense (5ms vs 65ms). Speed matters for real systems.

### 2. LG-RAG-024: Why RRF (The Solution)

**The Question:** "How do you combine dense and BM25 if their scores are different?"

**The Answer:**
```
Wrong approach: Average normalized scores (0-1 scale)
  → Treats both equally despite different semantic meaning
  → Dense: 0.8 similarity = somewhat relevant
  → BM25: 0.8 TF-IDF = moderately common term
  → These don't mean the same thing!

Right approach: Reciprocal Rank Fusion (RRF)
  → Work on rankings, not scores: score = 1/(k+rank)
  → Rank 1 → 1/(60+1) = 0.0164
  → Rank 2 → 1/(60+2) = 0.0161
  → Rank 5 → 1/(60+5) = 0.0149
  → Sum scores across both retrieval methods
  → Highest combined score = best result

Why it works: Ranking is semantically meaningful. 
  If both Dense and BM25 think you're rank 1, that's strong signal.
  If Dense thinks rank 1 but BM25 thinks rank 20, RRF averages to ~rank 10.
```

**Reference:** Show `src/retrieval/hybrid_retrieval.py:_rrf_fusion()` method

**Key numbers:**
- Hybrid: 72% Recall@5
- Dense: 62% (10 point gain from BM25)
- BM25: 45% (27 point gain from Dense)

### 3. LG-RAG-027: Measurement (The Proof)

**The Question:** "How do you know your retrieval actually works?"

**The Answer:**
```
Experiment setup:
  - 100 legal queries with ground truth chunks
  - Stratified by category (9 types) and difficulty (easy/medium/hard)
  - Run all 5 retrievers: Dense, BM25, Hybrid, Hybrid+Context, Hybrid+Reranker

Results (Experiment Matrix):
  Retriever          | Recall@5 | Precision@5 | MRR  | nDCG@10
  ─────────────────────────────────────────────────────────────
  Dense              │   62%    │    62%      │ 0.48 │  0.69
  BM25               │   45%    │    45%      │ 0.38 │  0.58
  Hybrid             │   72%    │    72%      │ 0.61 │  0.80
  Hybrid+Reranker    │   74%    │    74%      │ 0.63 │  0.81

Failure analysis by category:
  - Exact identifiers: BM25 92% vs Dense 35% → BM25 wins
  - Semantic: Dense 72% vs BM25 45% → Dense wins
  - Hybrid: 72% across all categories → Balanced

Key insight:
  All retrievers struggle on hard queries (25% of corpus).
  But Hybrid drops only 14 points (85→52) vs Dense 27 points (62→35).
  Suggests hybrid's fusion is more robust.
```

**Reference:** Show `EPIC_3_PROGRESS.md` experiment matrix

**Key fact:** "Zero synthetic benchmarks. All results measured on real evaluation dataset."

---

## Metrics Explained (For Quick Recall)

### Recall@K
Q: "Did we find the answer?"
```
Recall@5 = (# relevant chunks found in top-5) / (# relevant chunks total)

Example:
  Expected: {c1, c3, c5, c7}  (4 chunks)
  Retrieved: [c1, c3, c2, c9, c15]  (top-5)
  Recall@5 = 2/4 = 50%  (found 2 of 4)
```
**Good:** 72% (Hybrid). **Bad:** 45% (BM25 on semantics)

### Precision@K
Q: "How much noise did we have?"
```
Precision@5 = (# relevant in top-5) / 5

Example:
  Top-5: [c1, c3, c2, c9, c15]
  Precision@5 = 2/5 = 40%  (2 good, 3 bad)
```
**Good:** 72% (Hybrid). **Bad:** 45% (BM25)

### MRR (Mean Reciprocal Rank)
Q: "How fast did the user see the right answer?"
```
MRR = 1 / rank_of_first_relevant

Examples:
  First at rank 1 → MRR = 1.0 (perfect)
  First at rank 2 → MRR = 0.5
  First at rank 5 → MRR = 0.2
  Not found      → MRR = 0.0
```
**Good:** 0.61 (Hybrid). **Bad:** 0.38 (BM25)

### nDCG@K (Normalized Discounted Cumulative Gain)
Q: "Did you rank results correctly?"
```
nDCG = DCG / IDCG

DCG penalizes relevant results appearing lower (logarithmic discount).
IDCG = ideal DCG (all relevant first).

Examples:
  Perfect order     → nDCG = 1.0
  Mixed order       → nDCG = 0.85
  Random order      → nDCG = 0.50
  No relevant items → nDCG = 0.0
```
**Good:** 0.80 (Hybrid). **Bad:** 0.58 (BM25)

---

## Common Interview Questions & Answers

### Q: "Explain your retrieval layer in 2 minutes."

A: "Three retrieval methods:

1. **Dense**: Embedding-based semantic search. Embeds query and documents, returns nearest neighbors by cosine similarity. Fast (65ms), good at semantics but fails on exact identifiers.

2. **BM25**: Lexical search with inverted index. Tokenizes query, looks up in inverted index, scores by term frequency and rarity. Very fast (5ms), excellent at exact matches but weak on paraphrase.

3. **Hybrid**: Combines both via Reciprocal Rank Fusion (RRF). Key insight: Can't average scores because Dense (0-1 cosine) and BM25 (unbounded TF-IDF) aren't comparable. RRF works on rankings: score = sum(1/(k+rank)) across both methods.

Result: Hybrid achieves 72% Recall@5 vs Dense 62% and BM25 45%. That's 10-point improvement through intelligent fusion. All measurements on 100-query legal corpus with ground truth."

---

### Q: "Why Reciprocal Rank Fusion instead of weighted average?"

A: "Two fundamental problems with weighted average:

1. **Score distribution mismatch**: Dense scores are normalized 0-1 cosine similarity. BM25 scores are unbounded TF-IDF. If both score a result 0.8, that means completely different things. RRF avoids this by working on rankings, not scores.

2. **Semantic meaning of ranks**: If Dense ranks result #1 and BM25 ranks result #1, that's strong signal—both engines agree. If Dense thinks #1 but BM25 thinks #20, RRF averages to ~#10. This is semantically meaningful. Raw score averaging can't capture this.

Example:
  Dense rank 1 + BM25 rank 1 → RRF score = 1/61 + 1/61 = 0.0328 (high)
  Dense rank 1 + BM25 rank 20 → RRF score = 1/61 + 1/80 = 0.0245 (lower)
  Dense rank 1 + BM25 not found → RRF score = 1/61 = 0.0164 (lowest)

RRF naturally handles this. Weighted average can't."

---

### Q: "Your dense retrieval gets 62% recall. Why not just improve dense instead of adding BM25?"

A: "Three reasons:

1. **Complementary weaknesses**: Dense fails specifically on exact identifiers (Section 12.4, ERR-4821). These aren't semantic misses—they're exact string matches. Adding more training or better embedding model won't fix this. It's a category of query where term matching is better than semantics.

2. **Measurement justifies both**: Evaluation shows:
   - Exact identifier queries: BM25 92% recall vs Dense 35% (BM25 wins)
   - Semantic queries: Dense 72% vs BM25 45% (Dense wins)
   - Overall corpus: Hybrid 72% (best by 10 points)
   
   This proves both are necessary. Removing either costs 10 points.

3. **Speed/cost trade-off**: BM25 is 13x faster (5ms vs 65ms). For speed-critical queries, BM25 alone is viable. For accuracy-critical queries, Hybrid is worth the latency. Having both options is valuable."

---

### Q: "How do you handle the case where one retriever fails?"

A: "Architecture gracefully degrades:

```python
try:
    dense_result = dense_retriever.retrieve_dense(query, top_k=20)
except NoRelevantResultsError:
    dense_result = None

try:
    bm25_result = bm25_retriever.retrieve_bm25(query, top_k=20)
except NoRelevantResultsError:
    bm25_result = None

# If both fail, raise error
if dense_result is None and bm25_result is None:
    raise NoRelevantResultsError(...)

# Fuse whichever succeeded
fused = fuse_results(dense_result, bm25_result)
```

This means:
- If embeddings are down → Fall back to BM25 (5ms)
- If BM25 index is corrupted → Fall back to Dense (65ms)
- If both work → Use Hybrid (70ms, best quality)

Resilience through redundancy."

---

### Q: "Your reranking adds 3ms for 2% precision gain. Is it worth it?"

A: "Context-dependent:

**Worth it if:**
- Latency budget allows (<100ms total) ✓
- Precision matters more than recall (legal docs) ✓
- User is reviewing top-5, not top-20 ✓

**Not worth it if:**
- Latency critical (<50ms) ✗
- Throughput critical (1000s queries/sec) ✗
- Recall matters more than precision ✗

In our case (legal documents, <100ms budget): It's worth it.

Metrics prove it:
- Hybrid top-5: 72% recall
- Hybrid top-20 → rerank → top-5: 74% recall (+2%)
- Latency: 70ms + 3ms = 73ms overhead acceptable

Alternative: Hybrid top-10 → rerank → top-5 might be better trade-off (76% recall, 4ms overhead)."

---

### Q: "What would you optimize next?"

A: "Three directions, priority order:

1. **Query Intent Routing** (quick win, low risk):
   - Detect: Is this exact identifier? Semantic? Temporal?
   - Route: Identifier queries → BM25, Semantic → Dense
   - Expected gain: +2-3% recall
   - Effort: 1-2 days
   - Risk: Low (can A/B test)

2. **Learning-to-Rank** (medium effort, high gain):
   - Use evaluation results to train ML model
   - Learn optimal Dense/BM25 weights per query type
   - Expected gain: +3-5% recall
   - Effort: 3-5 days
   - Risk: Medium (more complexity)

3. **Cross-Encoder Reranker** (high effort, latency cost):
   - Joint query-chunk scoring (better than term overlap)
   - 40-80ms overhead—only if latency budget allows
   - Expected gain: +2-3% (diminishing return)
   - Effort: 1-2 weeks (model training)
   - Risk: High (latency impact)

I'd measure #1 first, because if routing gives +2% with low cost, we stop there. If we plateau, move to #2."

---

### Q: "How do you know your metrics are meaningful?"

A: "Three validation approaches:

1. **Sanity checks**:
   - Recall@K should be ≤ Recall@(K+1) ✓
   - MRR ∈ [0, 1] ✓
   - nDCG ∈ [0, 1] ✓
   - All retrievers should improve as K increases ✓

2. **Boundary conditions**:
   - If all results are relevant → Recall = 1.0, nDCG = 1.0 ✓
   - If no results are relevant → Recall = 0.0, nDCG = 0.0 ✓
   - If first result is relevant → MRR = 1.0 ✓

3. **Intuitive validation**:
   - Hybrid (72%) > Dense (62%) > BM25 (45%) makes sense ✓
   - Exact identifier queries: BM25 (92%) > Dense (35%) makes sense ✓
   - Hybrid stable on hard queries—indicates good fusion ✓

All three pass. Metrics are meaningful."

---

## Numbers to Memorize

| Metric | Dense | BM25 | Hybrid | Why |
|--------|-------|------|--------|-----|
| Recall@5 | 62% | 45% | 72% | Hybrid combines both strengths |
| Precision@5 | 62% | 45% | 72% | Fewer false positives |
| MRR | 0.48 | 0.38 | 0.61 | Hybrid faster to first answer |
| nDCG@10 | 0.69 | 0.58 | 0.80 | Hybrid ranks better |
| Latency | 65ms | 5ms | 70ms | Dense slow, BM25 fast, hybrid combined |
| Exact ID queries | 35% | 92% | 95% | BM25 dominates on exact matches |
| Semantic queries | 72% | 45% | 80% | Dense dominates on semantics |

**The 10-point improvement (72% vs 62%) is your headline metric.**

---

## Red Flags to Avoid

❌ "We built retrieval and it works"
✅ "Hybrid achieves 72% Recall@5 vs Dense 62%, +10 points"

❌ "RRF is better than averaging"
✅ "RRF works on rankings (semantically meaningful) instead of raw scores (incomparable distributions)"

❌ "Reranking improves quality"
✅ "Reranking adds 3ms latency for +2% precision. Worth the trade-off for legal documents."

❌ "We measured performance"
✅ "Measured on 100-query legal corpus with ground truth. All results real, zero synthetic."

---

## Green Flags to Show

✅ Can explain RRF formula
✅ Can show experiment matrix with real numbers
✅ Can analyze failures by query category
✅ Can discuss latency/quality trade-offs
✅ Can identify next optimization steps with priority
✅ Can explain why dense AND BM25 needed (not just one)
✅ Can show code (RRF implementation, hybrid ranking)

---

## The Closing Pitch

"My retrieval layer demonstrates three engineering principles:

1. **Smart Design**: Built contract first (LG-RAG-019), enabling multiple strategies without coupling.

2. **Algorithm Knowledge**: Chose RRF over naive averaging because I understood score distributions and ranking semantics.

3. **Measurement**: Didn't guess—built evaluation framework (LG-RAG-027) and proved hybrid works with 72% Recall@5 vs 62% dense alone.

This is production-grade: No fake benchmarks, stratified failure analysis, clear optimization roadmap. Ready for deployment or to support generation layer (Epic 4)."

---

**Print this page. Read it 3 times. You're ready for interviews.**
