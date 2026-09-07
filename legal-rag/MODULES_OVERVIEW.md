# Retrieval Layer Modules Overview

This document provides a quick reference for the retrieval layer components created in LG-RAG-019 and LG-RAG-020.

## Module Structure

```
src/
├── retrieval/           [LG-RAG-019: Retrieval Contract]
│   ├── __init__.py
│   ├── models.py        ← RetrievalRequest, RetrievalResponse, RetrievedChunk
│   ├── retriever.py     ← Retriever class (structured + legacy APIs)
│   └── exceptions.py
│
└── query/               [LG-RAG-020: Query Analysis]
    ├── __init__.py
    ├── models.py        ← QueryIntent, LegalTermSignal, QuerySignal, NormalizedQuery
    └── analyzer.py      ← QueryAnalyzer (8-stage pipeline)
```

## Public API Reference

### retrieval/models.py

#### RetrievalRequest
Structured query request with filters.

```python
from src.retrieval.models import RetrievalRequest
from datetime import datetime

request = RetrievalRequest(
    query="What are the termination conditions?",
    top_k=5,
    document_ids=["doc-1", "doc-2"],          # Optional
    document_types=["contract", "act"],       # Optional
    date_range=(datetime(2024, 1, 1), datetime(2024, 12, 31))  # Raises NotImplementedError
)
```

**Fields:**
- `query: str` — Search query (must be non-blank)
- `top_k: int = 5` — Number of results
- `document_ids: list[str] | None = None` — Filter to specific documents
- `document_types: list[str] | None = None` — Filter to document categories
- `date_range: tuple[datetime, datetime] | None = None` — Reserved (raises NotImplementedError if set)

**Exceptions:**
- `EmptyQueryError` — If query is blank or whitespace-only
- `NotImplementedError` — If date_range is provided

---

#### RetrievalResponse
Complete retrieval response with metadata envelope.

```python
from src.retrieval.models import RetrievalResponse

# Example response structure:
response = RetrievalResponse(
    chunks=[RetrievedChunk(...), RetrievedChunk(...)],
    embedding_model="bge-small-en-v1.5",
    embedding_version="1.0.0",
    retrieval_method="dense_with_reranking",
    total_searched=42
)
```

**Fields:**
- `chunks: list[RetrievedChunk]` — Retrieved chunks in ranked order
- `embedding_model: str` — Model used to embed query and chunks
- `embedding_version: str` — Version of embedding model
- `retrieval_method: str` — How retrieval was performed
- `total_searched: int` — Number of candidates searched before filtering

---

#### RetrievedChunk
Individual retrieved result with preserved metadata and score.

```python
from src.retrieval.models import RetrievedChunk

# Each chunk in RetrievalResponse.chunks is a RetrievedChunk
chunk = response.chunks[0]
print(chunk.rank)                 # int: position in results
print(chunk.score)                # float: similarity score (0.0-1.0)
print(chunk.retrieval_method)     # str: "dense_with_reranking"
print(chunk.record)               # VectorRecord: complete metadata
print(chunk.record.chunk_id)      # str: unique chunk ID
print(chunk.record.document_id)   # str: source document ID
print(chunk.record.text)          # str: full chunk text
print(chunk.record.page_number)   # int: page (if applicable)
print(chunk.record.section)       # str: detected section (if applicable)
print(chunk.record.heading)       # str: section heading (if applicable)
print(chunk.record.category)      # str: document type
print(chunk.record.embedding_model)    # str: model used
print(chunk.record.embedding_version)  # str: model version
```

**Frozen (immutable):** Cannot modify after creation.

---

### retrieval/retriever.py

#### Retriever class

```python
from src.retrieval.retriever import Retriever
from src.retrieval.models import RetrievalRequest

retriever = Retriever(
    embedding_provider=embedding_provider,
    vector_store=vector_store,
    similarity_threshold=0.30  # Optional, default 0.30
)
```

**Methods:**

##### retrieve() — Legacy API (backward compatible)
```python
results: list[RetrievedChunk] = retriever.retrieve(
    query="What are the termination conditions?",
    top_k=5,
    filters=None  # Dict-based filters not supported; use RetrievalRequest instead
)

# Access results
for result in results:
    print(f"[{result.rank}] {result.record.heading}: {result.score:.3f}")
```

Returns: `list[RetrievedChunk]` (for backward compatibility)

**Exceptions:**
- `EmptyQueryError` — If query is blank
- `NoRelevantResultsError` — If no chunks meet similarity threshold
- `NotImplementedError` — If filters dict is passed

---

##### retrieve_structured() — Structured API (recommended)
```python
from src.retrieval.models import RetrievalRequest, RetrievalResponse

request = RetrievalRequest(
    query="What are the termination conditions?",
    top_k=5,
    document_types=["contract"]
)

response: RetrievalResponse = retriever.retrieve_structured(request)

# Access response metadata
print(f"Model: {response.embedding_model}")
print(f"Method: {response.retrieval_method}")
print(f"Searched: {response.total_searched} candidates")

# Access chunks
for chunk in response.chunks:
    print(f"[{chunk.rank}] {chunk.record.heading}: {chunk.score:.3f}")
```

Returns: `RetrievalResponse` (with metadata envelope)

**Exceptions:**
- `EmptyQueryError` — If query is blank (raised by RetrievalRequest validation)
- `NoRelevantResultsError` — If no chunks meet threshold after filtering

---

### query/models.py

#### QueryIntent Enum

```python
from src.query.models import QueryIntent

# 9 possible intents:
QueryIntent.DEFINITION          # "What does X mean?"
QueryIntent.OBLIGATION          # "What must be done?"
QueryIntent.RIGHT               # "What can be done?"
QueryIntent.CONDITION           # "When/if does X apply?"
QueryIntent.PROCEDURE           # "How is X done?"
QueryIntent.SCOPE               # "To whom/what applies?"
QueryIntent.TEMPORAL            # "When does X happen?"
QueryIntent.CROSS_REFERENCE     # References sections
QueryIntent.GENERAL_INQUIRY     # Catch-all default
```

---

#### LegalTermSignal

```python
from src.query.models import LegalTermSignal

signal = LegalTermSignal(
    term="must",                  # str: the detected term
    confidence=0.9,               # float: 0.0-1.0
    is_quoted=False,              # bool: was it quoted?
    potential_section="2(a)"      # str | None: section reference nearby
)
```

**Frozen (immutable):** Cannot modify after creation.

---

#### QuerySignal

```python
from src.query.models import QuerySignal

signal = QuerySignal(
    signal="must",                # str: the signal text
    weight=0.9,                   # float: 0.0-1.0, importance
    category="legal_term"         # str: "legal_term" or "noun_phrase"
)
```

**Frozen (immutable):** Cannot modify after creation.

---

#### NormalizedQuery

```python
from src.query.models import NormalizedQuery
from src.query.analyzer import QueryAnalyzer

analyzer = QueryAnalyzer()
normalized = analyzer.analyze("What must the party do?")

# Access analysis results
print(normalized.original)              # str: unchanged raw query
print(normalized.normalized)            # str: whitespace-normalized
print(normalized.intent)                # QueryIntent: detected intent
print(normalized.legal_terms)           # list[LegalTermSignal]
print(normalized.retrieval_signals)     # list[QuerySignal]
print(normalized.exact_matches)         # list[str]: quoted terms
print(normalized.has_negation)          # bool: contains negation?
print(normalized.has_temporal_constraint)  # bool: contains temporal word?
print(normalized.query_length)          # int: word count
print(normalized.processing_time_ms)    # float: analysis time in ms
```

**Frozen (immutable):** Cannot modify after creation.

---

### query/analyzer.py

#### QueryAnalyzer class

```python
from src.query.analyzer import QueryAnalyzer

analyzer = QueryAnalyzer()
```

**Methods:**

##### analyze(query: str) -> NormalizedQuery
```python
result = analyzer.analyze("What must the party do?")
```

Performs 8-stage analysis pipeline:
1. Whitespace normalization
2. Intent detection
3. Legal term extraction
4. Quoted term preservation
5. Negation detection
6. Temporal constraint detection
7. Retrieval signal extraction
8. Performance measurement

Returns: `NormalizedQuery` with complete analysis

**Exceptions:**
- `ValueError` — If query is blank or whitespace-only

**Performance:**
- Target: <100ms for typical queries
- Typical: <2ms per query
- No external dependencies or LLM calls

---

## Integration Patterns

### Pattern 1: Query Analysis Only
```python
from src.query.analyzer import QueryAnalyzer

analyzer = QueryAnalyzer()
normalized = analyzer.analyze(user_query)

print(f"Intent: {normalized.intent}")
print(f"Processing time: {normalized.processing_time_ms:.2f}ms")
```

---

### Pattern 2: Analysis-Informed Retrieval
```python
from src.query.analyzer import QueryAnalyzer
from src.retrieval.models import RetrievalRequest
from src.retrieval.retriever import Retriever

analyzer = QueryAnalyzer()
normalized = analyzer.analyze(user_query)

# Use analysis to inform retrieval
top_k = 3 if normalized.intent == QueryIntent.DEFINITION else 8
document_types = infer_types(normalized.intent)

request = RetrievalRequest(
    query=normalized.normalized,
    top_k=top_k,
    document_types=document_types,
)

response = retriever.retrieve_structured(request)
```

---

### Pattern 3: End-to-End with Tracing
```python
from src.query.analyzer import QueryAnalyzer
from src.retrieval.models import RetrievalRequest
from src.retrieval.retriever import Retriever

analyzer = QueryAnalyzer()
normalized = analyzer.analyze(user_query)

request = RetrievalRequest(query=normalized.normalized, top_k=5)
response = retriever.retrieve_structured(request)

# Full tracing for debugging
trace = {
    "query_analysis": {
        "original": normalized.original,
        "intent": str(normalized.intent),
        "processing_time_ms": normalized.processing_time_ms,
        "legal_terms": [t.term for t in normalized.legal_terms],
    },
    "retrieval": {
        "embedding_model": response.embedding_model,
        "retrieval_method": response.retrieval_method,
        "total_searched": response.total_searched,
        "results_returned": len(response.chunks),
    },
}

for chunk in response.chunks:
    print(f"[{chunk.rank}] {chunk.record.heading}: {chunk.score:.3f}")
```

---

## Common Questions

**Q: How do I filter by document type?**
```python
request = RetrievalRequest(
    query="What are the termination conditions?",
    document_types=["contract", "agreement"]
)
response = retriever.retrieve_structured(request)
```

**Q: How do I get the original query back?**
```python
normalized = analyzer.analyze(user_query)
print(normalized.original)  # Unchanged raw query
print(normalized.normalized)  # Whitespace-normalized version
```

**Q: What if I need to filter by date?**
```python
# Not yet supported. Use try/except:
try:
    request = RetrievalRequest(
        query="...",
        date_range=(start_date, end_date)
    )
except NotImplementedError:
    # Date filtering not yet available
    request = RetrievalRequest(query="...")
```

**Q: How do I know if query analysis found anything?**
```python
normalized = analyzer.analyze(query)
if normalized.legal_terms:
    print(f"Found {len(normalized.legal_terms)} legal terms")
if normalized.exact_matches:
    print(f"Found exact matches: {normalized.exact_matches}")
```

**Q: How can I debug retrieval issues?**
```python
response = retriever.retrieve_structured(request)
print(f"Searched: {response.total_searched}")  # How many candidates?
print(f"Returned: {len(response.chunks)}")     # How many passed threshold?
print(f"Method: {response.retrieval_method}")  # How was it retrieved?
print(f"Model: {response.embedding_model}")    # Which model?
```

---

## Performance Characteristics

| Operation | Latency | Bottleneck |
|-----------|---------|-----------|
| Query normalization | <0.1ms | Whitespace processing |
| Intent detection | <0.3ms | Legal term counting |
| Term extraction | <0.5ms | Regex matching |
| Complete analysis | <2ms | All stages combined |
| Vector embedding | 50-200ms | LLM-based embedding |
| Vector search | 10-50ms | Approximate nearest neighbor |
| Filtering (post-search) | <1ms | Python list filtering |
| Reranking | <5ms | Tuple sorting |
| Complete retrieval | 100-300ms | Embedding + search |

**Query analysis does NOT add significant latency to retrieval pipeline.**

---

## Testing

### Run All Tests
```bash
pytest legal-rag/tests/test_retrieval.py -v
pytest legal-rag/tests/test_retrieval_contract.py -v
pytest legal-rag/tests/test_query_analyzer.py -v
```

### Run Specific Test Class
```bash
pytest legal-rag/tests/test_query_analyzer.py::TestQueryIntentDetection -v
```

### Run With Performance Timing
```bash
pytest legal-rag/tests/test_query_analyzer.py::TestProcessingPerformance -v --durations=0
```

---

## Backward Compatibility

### Legacy Code Still Works
```python
# Old API
results = retriever.retrieve("What are the terms?", top_k=5)
```

### Migration Path (Optional)
```python
# New API provides more information
from src.retrieval.models import RetrievalRequest
request = RetrievalRequest(query="What are the terms?", top_k=5)
response = retriever.retrieve_structured(request)
# Access response.embedding_model, response.retrieval_method, etc.
```

### No Breaking Changes
All existing code continues to work unchanged.

---

## Related Documentation

- `RETRIEVAL_CONTRACT.md` — Full specification for LG-RAG-019
- `QUERY_NORMALIZATION.md` — Full specification for LG-RAG-020
- `QUERY_NORMALIZATION_EXAMPLES.md` — 10 concrete examples with output
- `LG-RAG-020-SUMMARY.md` — Feature summary
- `IMPLEMENTATION_STATUS.md` — Overall status and testing
