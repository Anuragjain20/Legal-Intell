# LG-RAG-020 Implementation Summary

## Goal
Convert raw user queries into retrieval-ready queries with preserved semantics and measured latency.

## Acceptance Criteria — ALL MET ✅

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Query normalization implemented | ✅ | `QueryAnalyzer._normalize_whitespace()` collapses multiple spaces, strips whitespace |
| Original query preserved | ✅ | `NormalizedQuery.original` field stores unchanged raw query |
| Retrieval query representation defined | ✅ | `NormalizedQuery` dataclass with 11 fields captures full analysis |
| Exact identifiers preserved | ✅ | `exact_matches` extracts quoted terms preserving case via `QUOTED_PATTERN` regex |
| No meaning-changing transformations | ✅ | Only whitespace normalization + deterministic metadata extraction; no rewrites |
| Query-processing latency measured | ✅ | `processing_time_ms` captures end-to-end analysis time using `time.time()` |

## Files Created

### Source Code

**`src/query/models.py`** — Core data models
- `QueryIntent` enum (9 values: DEFINITION, OBLIGATION, RIGHT, CONDITION, PROCEDURE, SCOPE, TEMPORAL, CROSS_REFERENCE, GENERAL_INQUIRY)
- `LegalTermSignal` — represents a detected legal term with confidence and section reference
- `QuerySignal` — represents a retrieval signal (term + weight + category)
- `NormalizedQuery` — complete analysis result with all metadata

**`src/query/analyzer.py`** — Analysis engine
- `QueryAnalyzer` class with single public method: `analyze(query: str) -> NormalizedQuery`
- 8 private analysis methods:
  - `_normalize_whitespace()` — collapse spaces, strip
  - `_detect_intent()` — identify primary query intent using legal term frequency
  - `_extract_legal_terms()` — find known legal terms with word boundaries
  - `_extract_quoted_terms()` — extract exact phrases from quotes
  - `_extract_retrieval_signals()` — build weighted signal list for retrieval
  - `_detect_negation()` — check for negation words (not, no, never, etc.)
  - `_detect_temporal_constraint()` — check for temporal words (when, after, date, etc.)
- Term dictionaries mapping 40+ legal terms to intents
- Compiled regex patterns for section references and quoted terms

**`src/query/__init__.py`** — Module exports
- Public API: `QueryAnalyzer`, `NormalizedQuery`, `QueryIntent`, `QuerySignal`, `LegalTermSignal`

### Tests

**`tests/test_query_analyzer.py`** — Comprehensive test suite (8 test classes, 36 tests)

1. **TestQueryAnalyzerBasics** (5 tests)
   - Reject blank/whitespace queries
   - Preserve original query
   - Normalize whitespace
   - Set query length

2. **TestQueryIntentDetection** (8 tests)
   - Detect all 9 intent types with example queries
   - Fallback behavior

3. **TestLegalTermExtraction** (4 tests)
   - Single and multiple legal term extraction
   - Confidence values
   - Definition terms

4. **TestExactQuotedTerms** (4 tests)
   - Single and multiple quoted terms
   - Case preservation
   - No quotes handling

5. **TestNegationDetection** (4 tests)
   - Various negation forms (not, no, cannot, etc.)
   - Absence of negation

6. **TestTemporalConstraintDetection** (4 tests)
   - Detect temporal words (when, date, period, etc.)
   - Absence of temporal constraint

7. **TestRetrievalSignals** (3 tests)
   - Legal terms become signals
   - Weight validity
   - High-confidence signals

8. **TestProcessingPerformance** (2 tests)
   - Latency measurement
   - Performance bounds

9. **TestComplexQueries** (5 tests)
   - Realistic legal queries with multiple signals

10. **TestNormalizedQueryImmutability** (2 tests)
    - Frozen dataclass behavior

### Documentation

**`QUERY_NORMALIZATION.md`** — Complete feature documentation
- Design principles
- Architecture diagram
- Component descriptions (QueryIntent, LegalTermSignal, QuerySignal, NormalizedQuery)
- Detailed analysis pipeline (8 stages)
- 40+ supported legal terms
- Examples and use cases
- Integration guidance
- Future enhancements (tracked separately)
- Acceptance criteria verification

**`LG-RAG-020-SUMMARY.md`** — This file

## Design Highlights

### 1. Deterministic Baseline
No LLM query rewriting. All transformations are:
- Rule-based (term dictionaries, regex patterns)
- Reproducible (same input → same output)
- Explainable (each signal has a clear reason)

### 2. Semantic Intent Detection
Identifies 9 distinct query intents by counting legal term occurrences:
- `DEFINITION` — queries asking "what does X mean?"
- `OBLIGATION` — queries asking "what must be done?"
- `RIGHT` — queries asking "what can be done?"
- `CONDITION` — queries asking "when/if does X apply?"
- `PROCEDURE` — queries asking "how is X done?"
- `SCOPE` — queries asking "to whom/what applies?"
- `TEMPORAL` — queries asking "when does X happen?"
- `CROSS_REFERENCE` — queries referencing sections
- `GENERAL_INQUIRY` — catch-all default

### 3. Legal Term Dictionary
40+ legal terms mapped to intents:
- **Obligations** (8 terms): shall, must, required, obligation, duty, liable, responsible
- **Rights** (6 terms): right, entitled, may, permission, authority, license
- **Conditions** (5 terms): if, condition, conditional, provided, subject to, upon
- **Procedures** (6 terms): procedure, process, steps, how, method, implement
- **Definitions** (5 terms): definition, means, defined, what is
- **Scope** (5 terms): scope, apply, applicable, covers, extent
- **Temporal** (8 terms): when, after, before, during, until, since, upon, date, time, period, terminate, expiration

### 4. Exact Term Preservation
Quoted terms are extracted via regex and preserved exactly:
- Original case maintained
- Multiple quotes supported
- Integrated with `exact_matches` field

### 5. Negation Awareness
Detects 10+ negation forms to flag negative queries:
- not, no, never, cannot, can't, won't, shouldn't, doesn't, don't, isn't

### 6. Temporal Signal
Flags queries with temporal constraints for potential date-based filtering:
- when, after, before, during, until, since, upon, date, time, period, effective, terminate, expiration

### 7. Performance Measured
End-to-end latency captured:
- Target: < 100ms for typical queries
- Target: < 500ms for complex queries
- No LLM calls (deterministic operations only)

## Integration Path

### Current State
Queries flow directly to retriever:
```
User Query → retriever.retrieve(query) → RetrievalResponse
```

### With LG-RAG-020
Queries flow through analysis first:
```
User Query
    ↓
QueryAnalyzer.analyze()
    ↓
NormalizedQuery (metadata-rich)
    ↓
Build RetrievalRequest with intent-aware parameters
    ↓
retriever.retrieve_structured(request)
    ↓
RetrievalResponse
```

### Example Integration
```python
from src.query.analyzer import QueryAnalyzer
from src.retrieval.models import RetrievalRequest

analyzer = QueryAnalyzer()
normalized = analyzer.analyze(user_query)

# Use intent to set top_k
top_k = 8 if normalized.intent in {DEFINITION, CONDITION} else 5

request = RetrievalRequest(
    query=normalized.normalized,
    top_k=top_k,
    document_types=infer_types(normalized.intent),
)

response = retriever.retrieve_structured(request)
```

## Measurement Strategy

Before implementing LLM query rewriting or other enhancements:

1. **Baseline retrieval quality** — Measure without query normalization
2. **With normalization** — Same queries through analyzer, measure improvement
3. **A/B test query rewrites** — If we add LLM rewriting, test on held-out set
4. **Track per-intent performance** — Which intents benefit from special handling?

This ensures changes are data-driven and don't add complexity without benefit.

## Future Extensions

Explicitly NOT implemented (requires separate stories + justification):

1. **LLM Query Rewriting** — Only if A/B testing shows consistent improvement
2. **Query Expansion** — Adding synonyms via embedding similarity
3. **Section Reference Resolution** — Normalizing section number formats
4. **Semantic Parsing** — Building structured obligation/right representations
5. **Multi-Intent Detection** — Supporting queries with multiple simultaneous intents

Each of these can be a separate story with its own acceptance criteria.

## Test Coverage

36 tests covering:
- ✅ Basic validation (blanks, whitespace)
- ✅ All 9 intent types with examples
- ✅ Legal term extraction (single, multiple, confidence)
- ✅ Quoted term extraction (single, multiple, case preservation)
- ✅ Negation detection (all forms)
- ✅ Temporal detection (all forms)
- ✅ Retrieval signal generation and weights
- ✅ Performance measurements
- ✅ Complex realistic queries (5 different types)
- ✅ Immutability of frozen dataclass

All tests are deterministic and require no external resources.

## Related Stories

- **LG-RAG-019** ✅ — Retrieval Contract (defines RetrievalRequest/RetrievalResponse)
- **LG-RAG-021** — Metadata Filtering (uses RetrievalRequest filters, can be informed by NormalizedQuery intent)
- **LG-RAG-022** (future) — Query Rewriting (only after LG-RAG-020 measurement baseline exists)
