# Retrieval Contract: LG-RAG-019

## Overview

This document defines the formal contract for the retrieval subsystem: what data enters (`RetrievalRequest`) and what leaves (`RetrievalResponse`), with guaranteed metadata preservation and traceability.

The contract ensures:
- No ad-hoc structures or implicit contracts
- Dense search, BM25, hybrid search, and reranking all return the same structured output
- Every retrieved chunk is traceable to its source and retrieval method
- Metadata and scores are preserved end-to-end, never invented or dropped

## Request Contract: RetrievalRequest

```python
@dataclass
class RetrievalRequest:
    query: str
    top_k: int = 5
    document_ids: list[str] | None = None
    document_types: list[str] | None = None
    date_range: tuple[datetime, datetime] | None = None
```

### Field Definitions

| Field | Type | Required | Enforceable | Notes |
|-------|------|----------|-----------|-------|
| `query` | `str` | Yes | Yes | Query text; must be non-blank. Raises `EmptyQueryError` if blank. |
| `top_k` | `int` | No (default 5) | Yes | Number of results to return after all filtering and ranking. |
| `document_ids` | `list[str]` | No | Yes | Filter to documents in this set. Post-search filtering. |
| `document_types` | `list[str]` | No | Yes | Filter to categories in this set (e.g., `["contract", "act"]`). Post-search filtering. |
| `date_range` | `tuple[datetime, datetime]` | No | No | Reserved for future use. Raises `NotImplementedError` if provided. |

### Validation

The `RetrievalRequest` constructor validates:
1. **Non-blank query**: Raises `EmptyQueryError` immediately.
2. **No date_range**: Raises `NotImplementedError` if `date_range` is provided.

### Filtering Strategy

**Filters are applied post-search:**
- The vector store has no filter parameters; filtering happens in the retriever after vector search.
- To maintain `top_k` results even with filtering, the retriever over-fetches: `search(top_k * 4)` if filtering, then applies filters, then truncates to `top_k`.
- If all candidates are filtered out, raises `NoRelevantResultsError`.

## Response Contract: RetrievalResponse

```python
@dataclass(frozen=True)
class RetrievalResponse:
    chunks: list[RetrievedChunk]
    embedding_model: str
    embedding_version: str
    retrieval_method: str
    total_searched: int
```

### Field Definitions

| Field | Type | Invariant | Source |
|-------|------|-----------|--------|
| `chunks` | `list[RetrievedChunk]` | `len(chunks) <= request.top_k` | Retriever ranking & truncation |
| `embedding_model` | `str` | Non-empty; matches all chunk records | From `VectorRecord.embedding_model` |
| `embedding_version` | `str` | Non-empty; matches all chunk records | From `VectorRecord.embedding_version` |
| `retrieval_method` | `str` | Currently `"dense_with_reranking"` | Metadata about how retrieval was done |
| `total_searched` | `int` | `>= 0` | Count of candidates returned by vector store before filtering |

### Invariants

1. All chunks share the same `embedding_model` and `embedding_version`.
2. `retrieval_method` identifies the retrieval pipeline (currently single value; expandable for hybrid/BM25/rerankers).
3. `total_searched` enables tracking of filter effectiveness.

## Result Contract: RetrievedChunk

```python
@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    score: float
    retrieval_method: str
    record: VectorRecord
```

### Field Definitions

| Field | Type | Invariant | Notes |
|-------|------|-----------|-------|
| `rank` | `int` | `1 <= rank <= top_k` | Position in final ranked list (after reranking). |
| `score` | `float` | `0.0 <= score <= 1.0` | **Similarity score preserved from vector search**, NOT reranked. |
| `retrieval_method` | `str` | `"dense_with_reranking"` | Identifies how this chunk was retrieved. |
| `record` | `VectorRecord` | Frozen, complete | Complete metadata from indexing time. |

### VectorRecord (Complete Metadata)

Every `RetrievedChunk` carries a complete `VectorRecord` with:
- `chunk_id`: Unique chunk identifier
- `document_id`: Source document identifier
- `text`: Full chunk text
- `page_number`: Page (for paginated documents)
- `section`: Structural section (if detected)
- `heading`: Section heading (if detected)
- `category`: Document category (contract/act/regulation/etc.)
- `embedding_model`: Model used to embed this chunk
- `embedding_version`: Version of embedding model
- `document_name`: Human-readable document name (if available)

### Score Preservation Across Reranking

**Critical invariant: The `score` field is the similarity score from vector search, NOT the reranked position.**

The retriever applies a second-stage re-ranking (frontmatter priority, term overlap, specificity) to reorder results, but the original similarity score is preserved on each chunk. This allows downstream code to:
- Trust the neural relevance signal
- Debug ranking choices
- Audit retrieval behavior

## Backward Compatibility

The legacy `retrieve()` interface remains unchanged:

```python
def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[RetrievedChunk]
```

This maps to the new structured API internally:
- Raises `NotImplementedError` if `filters` dict is passed (dict-based filters are not supported; use `RetrievalRequest` instead).
- Returns only the `chunks` list (not the full `RetrievalResponse`).

## Acceptance Criteria Verification

✅ **Retrieval request schema defined** — `RetrievalRequest` with all fields  
✅ **Retrieval response schema defined** — `RetrievalResponse` with metadata envelope  
✅ **Metadata preserved** — All `VectorRecord` fields carried through in `RetrievedChunk.record`  
✅ **Scores preserved** — `RetrievedChunk.score` is the unmodified similarity score  
✅ **Retrieval method identifiable** — `RetrievalResponse.retrieval_method` and `RetrievedChunk.retrieval_method`  
✅ **Index/embedding version available** — `RetrievalResponse.embedding_model` and `.embedding_version`  
✅ **No LLM generation inside retrieval** — Verified by grep: no imports from `src.generation` or LLM providers  

## Example Usage

### Structured API (recommended)

```python
from src.retrieval.models import RetrievalRequest
from src.retrieval.retriever import Retriever

retriever = Retriever(embedding_provider=..., vector_store=...)

request = RetrievalRequest(
    query="What are the termination conditions?",
    top_k=5,
    document_ids=["contract-001", "contract-002"],
    document_types=["contract"]
)

response = retriever.retrieve_structured(request)

# Response metadata
print(f"Model: {response.embedding_model}")
print(f"Version: {response.embedding_version}")
print(f"Method: {response.retrieval_method}")
print(f"Searched: {response.total_searched} candidates")

# Per-chunk
for chunk in response.chunks:
    print(f"[{chunk.rank}] Score: {chunk.score:.2f}")
    print(f"  Document: {chunk.record.document_id}")
    print(f"  Chunk: {chunk.record.chunk_id}")
    print(f"  Page: {chunk.record.page_number}")
    print(f"  Heading: {chunk.record.heading}")
    print(f"  Text: {chunk.record.text[:100]}...")
```

### Legacy API (backward compatible)

```python
results = retriever.retrieve("What are the termination conditions?", top_k=5)

for result in results:
    print(f"Score: {result.score:.2f}")
    print(f"Document: {result.record.document_id}")
```

## Future Extensibility

The contract is designed for future enhancements without breaking changes:

- **New retrieval methods**: Add new values to `retrieval_method` enum/constant.
- **Hybrid search**: Return `RetrievalResponse` with `retrieval_method="hybrid_bm25_dense"`.
- **Date filtering**: Implement date range indexing and post-filter in `_apply_filters()`.
- **Cross-encoder reranking**: Preserve similarity score, add reranker score field.

All of these are implementation details; the request/response contract remains stable.
