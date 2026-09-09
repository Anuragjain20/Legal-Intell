# Retrieval

`Retriever.retrieve()` ([retriever.py:21-37](../src/retrieval/retriever.py#L21-L37)) is short — the whole query-time retrieval funnel is ~15 lines. Understanding it exactly, including the parts that are easy to get subtly wrong when explaining it, matters more than the line count suggests.

## The funnel, with real numbers from this codebase

```
question string
  → raise EmptyQueryError if blank                          retriever.py:22-23
  → raise NotImplementedError if filters passed              retriever.py:24-25  (metadata filters: not built)
  → embed_query(question)         → 384-dim vector           retriever.py:27
  → vector_store.search(vector, top_k)                       retriever.py:28
       the /query API handler calls this with top_k=8        src/api/main.py
  → keep only results with score >= similarity_threshold     retriever.py:30-34
       default threshold = 0.35 (SIMILARITY_THRESHOLD env)   settings.py:18
  → raise NoRelevantResultsError if nothing survives          retriever.py:35-36
  → _rank_by_relevance() re-ranks the survivors               retriever.py:37, 39-64
  → returned to the /query handler as list[RetrievalResult]
       ContextBuilder then takes only the first 6             context_builder.py:15, 19
```

**Three things about this funnel that are easy to misstate:**

1. **`top_k=8` is not "the number of chunks the LLM sees."** It's the candidate pool *before* threshold filtering and re-ranking. The threshold filter can reduce it below 8 (in the limit, to zero, which raises rather than returning an empty list — callers must handle `NoRelevantResultsError` explicitly, not just check `if results:`). Then `ContextBuilder` caps the *context* at 6 sources regardless of how many `Retriever` returned. So the real numbers are: search 8 → filter to ≤8 → re-rank → context-build takes ≤6.
2. **The threshold is compared against similarity, not distance** (see [03-embeddings-vectorstore.md](03-embeddings-vectorstore.md)) — `score >= self.similarity_threshold` ([retriever.py:33](../src/retrieval/retriever.py#L33)) keeps the *most* similar results, which is correct only because `score` is already `1 - distance`.
3. **Zero results is an exception, not an empty list.** `NoRelevantResultsError` ([retriever.py:36](../src/retrieval/retriever.py#L36)) forces every caller to have an explicit "nothing relevant found" path. The `/query` handler catches it and returns **HTTP 200 with `refused: true`** rather than an error status — a refusal is a correct product outcome, not a failure, and it's exactly what [06-evaluation.md](06-evaluation.md)'s confidence-gate metric measures the rate of. `RetrievalError` subclasses other than this one map to a 400; `GenerationError` maps to a 502.

## The re-ranker: what it actually is

`_rank_by_relevance()` ([retriever.py:39-64](../src/retrieval/retriever.py#L39-L64)) is **not a cross-encoder, not a learned reranker, not an LLM call.** It's a Python tuple sort with four keys, ascending (so lower tuples rank first):

```python
def relevance_score(result) -> tuple[int, float, int, int]:
    frontmatter_priority  # 0 if (query looks like a "purpose/intent" question AND this chunk is FRONTMATTER), else 1
    -sim_score             # negative similarity, so higher similarity sorts first
    -query_term_count      # negative count of query words (len>3) literally present in chunk text, so more overlap sorts first
    section_bonus          # 0 for frontmatter, 1 otherwise (a tiebreak nudge, mostly redundant with the first key)
```

Two concrete behaviors this produces:

- A query containing "purpose", "intent", "object", "aim", "goal", or "why" ([retriever.py:43-45](../src/retrieval/retriever.py#L43-L45)) will have any `FRONTMATTER:*`-sectioned chunk (preambles, recitals, "object of the act" clauses — see [02-ingestion.md](02-ingestion.md)) pulled to the very top, ahead of cosine similarity. This directly encodes the domain knowledge that a statute's stated purpose usually lives in its preamble, which a pure similarity search might not rank first if the preamble's phrasing doesn't lexically match the question.
- Among non-frontmatter (or non-purpose-question) results, it's cosine similarity first, then a crude keyword-overlap tiebreak (`word in text.lower()`, substring match, no stemming/lemmatization, words >3 chars only).

**Why not a cross-encoder reranker (e.g. a `bge-reranker` or Cohere rerank call)?** Two honest reasons to give: (1) scope — this is an MVP wired for a fixed, small, known corpus, and a hand-rolled heuristic that encodes one specific domain insight (purpose questions → look at frontmatter) was cheaper to build and easier to unit test than adding another model dependency; (2) it works entirely offline/deterministically, no extra latency or API cost per query. The honest trade-off to name back: this heuristic doesn't generalize past the patterns it was written for, and a cross-encoder would likely out-rank it on anything outside "purpose questions" and "keyword overlap." If asked "what would you add first," this is the answer — see [07](07-interview-narrative.md) and [08](08-question-bank.md).

## `RetrievalResult` and rank semantics

`RetrievalResult` ([retrieval/models.py:10-16](../src/retrieval/models.py#L10-L16)) carries `rank`, `score`, and the full `VectorRecord`. Note `rank` is **assigned twice** — once by position after threshold filtering ([retriever.py:31](../src/retrieval/retriever.py#L31)), then **reassigned** by position after re-ranking ([retriever.py:61-63](../src/retrieval/retriever.py#L61-L63)). The `rank` a caller sees is always the final, re-ranked position — the pre-rerank rank is discarded, not preserved anywhere. This matters because `ContextBuilder` labels sources `[SOURCE_1]`, `[SOURCE_2]`... by this final `rank`, and the citation system (see [05-generation.md](05-generation.md)) resolves `[SOURCE_N]` references against it — so the LLM's citations reflect re-ranked order, not raw similarity order.

## What's not implemented (stated once, cross-referenced from 01)

Metadata filters (category, document, date range) are a `NotImplementedError` stub ([retriever.py:24-25](../src/retrieval/retriever.py#L24-L25)) despite `Chunk`/`VectorRecord` already carrying `category`, `document_id`, `section` fields that a real filter implementation could use directly against Chroma's `where=` clause (already used internally for `delete_document`, [chroma_store.py:48](../src/vectorstore/chroma_store.py#L48)). This is a "next thing to build," not a "thing that doesn't exist as a concept" — the metadata is already there.
