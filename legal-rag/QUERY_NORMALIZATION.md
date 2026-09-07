# Query Analysis & Normalization: LG-RAG-020

## Overview

Query Analysis & Normalization converts raw user queries into retrieval-ready representations with preserved semantics and measured latency. This module establishes a deterministic baseline for query understanding before considering more complex techniques like LLM-based query rewriting.

## Design Principles

1. **Deterministic**: All transformations are rule-based, reproducible, and explainable.
2. **Preserving**: Original query is always preserved; normalization adds metadata, never destroys information.
3. **Measurement-first**: No query rewriting without data showing it improves retrieval.
4. **Lean**: No LLM calls inside this module; if query rewriting is needed, it's a separate story.

## Architecture

```
Raw Query (str)
    ↓
QueryAnalyzer.analyze()
    ├─→ Whitespace normalization
    ├─→ Intent detection
    ├─→ Legal term extraction
    ├─→ Quoted term preservation
    ├─→ Negation detection
    ├─→ Temporal constraint detection
    ├─→ Retrieval signal extraction
    └─→ Latency measurement
    ↓
NormalizedQuery (dataclass)
    ├─→ original: str (unchanged)
    ├─→ normalized: str (whitespace normalized)
    ├─→ intent: QueryIntent (enum)
    ├─→ legal_terms: list[LegalTermSignal]
    ├─→ retrieval_signals: list[QuerySignal]
    ├─→ exact_matches: list[str] (quoted terms)
    ├─→ has_negation: bool
    ├─→ has_temporal_constraint: bool
    ├─→ query_length: int (word count)
    └─→ processing_time_ms: float
```

## Components

### QueryIntent Enum

Identifies the primary semantic intent of a query:

| Intent | When to use | Example |
|--------|-----------|---------|
| `DEFINITION` | Query asks for meaning or definition | "What does 'material breach' mean?" |
| `OBLIGATION` | Query asks what someone must do | "What must the party do?" |
| `RIGHT` | Query asks what someone can do | "What rights does the licensor have?" |
| `CONDITION` | Query asks under what circumstances | "What conditions must be met?" |
| `PROCEDURE` | Query asks how to do something | "How should notice be delivered?" |
| `SCOPE` | Query asks what something applies to | "To which parties does this apply?" |
| `TEMPORAL` | Query asks about timing | "When does the agreement end?" |
| `CROSS_REFERENCE` | Query references other sections | "What does Section 5 say?" |
| `GENERAL_INQUIRY` | Fallback when no specific intent detected | "Tell me about the contract." |

### LegalTermSignal

Represents a detected legal term in the query:

```python
@dataclass(frozen=True)
class LegalTermSignal:
    term: str                          # The detected term (e.g., "shall")
    confidence: float                  # 0.0-1.0; how sure are we
    is_quoted: bool                    # Whether it appeared in quotes
    potential_section: str | None      # Section reference if found nearby
```

### QuerySignal

Semantic signal extracted for retrieval optimization:

```python
@dataclass(frozen=True)
class QuerySignal:
    signal: str                        # The signal text (e.g., "must", "shall")
    weight: float                      # 0.0-1.0; importance for retrieval
    category: str                      # Type: "legal_term", "noun_phrase", etc.
```

### NormalizedQuery

Complete analysis result:

```python
@dataclass
class NormalizedQuery:
    original: str                      # Unchanged original query
    normalized: str                    # Whitespace-normalized version
    intent: QueryIntent                # Detected primary intent
    legal_terms: list[LegalTermSignal] # All detected legal terms
    retrieval_signals: list[QuerySignal]
    exact_matches: list[str]           # Terms from quotes, preserved exactly
    has_negation: bool                 # Does query contain "not", "no", etc.?
    has_temporal_constraint: bool      # Does query mention time?
    query_length: int                  # Word count
    processing_time_ms: float          # Time to analyze (ms)
```

## Analysis Pipeline

### 1. Whitespace Normalization

Collapses multiple spaces, strips leading/trailing whitespace. Does not change case or remove punctuation.

```python
"What   are   the   termination    conditions?"
    ↓
"What are the termination conditions?"
```

### 2. Intent Detection

Identifies the primary intent by:
1. Counting occurrences of known legal terms
2. Returning the intent associated with the most frequent term
3. Falling back to heuristics ("how" → PROCEDURE, "when" → TEMPORAL)
4. Defaulting to GENERAL_INQUIRY if no signal

```python
analyzer.analyze("The party must perform its obligations.")
    ↓ (finds "must" and "obligation")
    ↓
QueryIntent.OBLIGATION
```

### 3. Legal Term Extraction

Finds known legal terms using word boundary matching. Avoids partial matches.

Supported legal terms include:
- **Obligations**: shall, must, required, obligation, duty, liable, responsible
- **Rights**: right, entitled, may, permission, authority, license
- **Conditions**: if, condition, conditional, provided, subject to, upon
- **Procedures**: procedure, process, steps, how, method, implement
- **Definitions**: definition, means, defined, what is
- **Scope**: scope, apply, applicable, covers, extent
- **Temporal**: when, time, period, duration, effective, date, terminate, expiration

### 4. Quoted Term Preservation

Extracts exact phrases in quotes and preserves them exactly as written:

```python
analyzer.analyze('Define "Material Breach".')
    ↓
exact_matches = ["Material Breach"]  # Case preserved
```

### 5. Negation Detection

Detects negation words: not, no, never, cannot, can't, won't, shouldn't, doesn't, don't

```python
analyzer.analyze("The party must NOT disclose.")
    ↓
has_negation = True
```

This is useful for:
- Alerting downstream systems that the query is negative
- Potentially adjusting retrieval to find negative examples
- Debugging retrieved results that don't account for negation

### 6. Temporal Constraint Detection

Detects temporal signal words: when, after, before, during, until, since, upon, date, time, period

```python
analyzer.analyze("When does the agreement terminate?")
    ↓
has_temporal_constraint = True
```

Signals to retrieval that temporal metadata might be relevant.

### 7. Retrieval Signal Extraction

Builds a weighted list of signals for downstream retrieval:
- Legal terms become high-weight signals (0.9)
- Noun phrases become medium-weight signals (0.6)

```python
analyzer.analyze("What must the party do?")
    ↓
retrieval_signals = [
    QuerySignal(signal="must", weight=0.9, category="legal_term"),
    QuerySignal(signal="party do", weight=0.6, category="noun_phrase"),
]
```

### 8. Performance Measurement

Processing time is measured and included in the response:

```python
result.processing_time_ms  # Milliseconds to analyze
```

Expected: < 100ms for typical queries, < 500ms for very long queries.

## Example: Complex Query Analysis

```python
from src.query.analyzer import QueryAnalyzer

analyzer = QueryAnalyzer()
query = "What happens if either party terminates the agreement because of a material breach?"

result = analyzer.analyze(query)

print(f"Original:  {result.original}")
# Original: What happens if either party terminates the agreement because of a material breach?

print(f"Intent:    {result.intent}")
# Intent:    QueryIntent.CONDITION

print(f"Legal terms: {[t.term for t in result.legal_terms]}")
# Legal terms: ['if', 'terminate']

print(f"Negation?  {result.has_negation}")
# Negation?  False

print(f"Temporal?  {result.has_temporal_constraint}")
# Temporal?  True

print(f"Time:      {result.processing_time_ms:.2f}ms")
# Time:      2.34ms
```

## Integration with Retrieval

The `NormalizedQuery` can be used to enhance `RetrievalRequest`:

```python
from src.query.analyzer import QueryAnalyzer
from src.retrieval.models import RetrievalRequest

analyzer = QueryAnalyzer()
normalized = analyzer.analyze(user_query)

# Use the analysis to inform retrieval parameters
request = RetrievalRequest(
    query=normalized.normalized,  # Use normalized version
    top_k=5 if normalized.intent == QueryIntent.DEFINITION else 8,
    document_types=infer_document_types(normalized.intent),
)

response = retriever.retrieve_structured(request)
```

## Future Enhancements (Not Implemented)

These are tracked separately and require measurement to justify:

1. **LLM Query Rewriting** — Only if A/B testing shows improvement
2. **Query Expansion** — Adding synonyms (needs embedding-based similarity)
3. **Section Reference Resolution** — Normalizing section numbers
4. **Semantic Parsing** — Building structured representations of obligations/rights
5. **Multi-Intent Detection** — Supporting queries with multiple intents

## Acceptance Criteria Verification

✅ **Query normalization implemented** — `QueryAnalyzer.analyze()` applies whitespace normalization  
✅ **Original query preserved** — `NormalizedQuery.original` is unchanged  
✅ **Retrieval query representation defined** — `NormalizedQuery` and `QuerySignal` model the analysis  
✅ **Exact identifiers preserved** — Quoted terms captured in `exact_matches`, case preserved  
✅ **No meaning-changing transformations** — Only whitespace normalization + metadata extraction  
✅ **Query-processing latency measured** — `NormalizedQuery.processing_time_ms` recorded  

## Testing

Comprehensive test suite in `tests/test_query_analyzer.py` covers:
- Basic functionality (blank queries, whitespace normalization)
- Intent detection (all 9 intents tested)
- Legal term extraction (single, multiple, confidence)
- Quoted term extraction (single, multiple, case preservation)
- Negation detection (various negation forms)
- Temporal constraint detection
- Retrieval signal generation
- Performance benchmarks
- Complex realistic queries
- Immutability of frozen dataclass

All tests are deterministic and require no external dependencies.
