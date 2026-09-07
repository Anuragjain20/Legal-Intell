# Contextual Retrieval Analysis & Validation: LG-RAG-025

## Goal

Validate and measure whether adding contextual information to chunks improves retrieval quality. Do NOT blindly rebuild—measure before optimizing.

## Current State Analysis

### What Context Is Already Preserved

✅ **In Chunk (ingestion/models.py):**
- document_id
- document_name
- page_number, end_page_number
- section
- heading
- category
- section_number, subsection, clause, structure_path (hierarchical)

✅ **Carried to VectorRecord (vectorstore/base.py):**
- chunk_id
- document_id
- text (the chunk itself)
- page_number
- section
- heading
- document_name
- category
- embedding_model
- embedding_version

### What Context Is LOST

❌ **Not stored in VectorRecord (hierarchical structure):**
- section_number (e.g., "2")
- subsection (e.g., "d")
- clause (e.g., "i")
- structure_path (e.g., ["2", "d", "i"])

❌ **Not embedded as text (only as metadata):**
- These fields exist but are not prepended to the text before embedding
- Embedding only includes the chunk text itself, not its hierarchical context

## Context-Loss Cases Identified

### Case 1: Hierarchical Structure Not in Embedding

**Example:**
```
Chunk text: "The party must provide written notice."
Chunk metadata: section_number="2", subsection="d", clause="i"

Current embedding input: "The party must provide written notice."
Missing context: "Section 2(d)(i): ..."
```

**Impact:** Query for "Section 2(d)(i) notice requirements" might miss this chunk because "2(d)(i)" is not in the embedding space, only in metadata.

### Case 2: Document Context Not in Embedding

**Example:**
```
Chunk text: "Interest rate shall be 5% per annum."
Chunk metadata: document_name="Loan Agreement", section="Payment Terms"

Current embedding input: "Interest rate shall be 5% per annum."
Missing context: "Loan Agreement - Payment Terms: Interest rate shall be 5% per annum."
```

**Impact:** Query distinguishing between different document types might not work well.

### Case 3: Page Context Not in Embedding

**Example:**
```
Chunk text: "Signature of authorized representative."
Chunk metadata: page_number=42, document_name="Employment Contract"

Current embedding input: "Signature of authorized representative."
Missing context: "Page 42: Signature of authorized representative."
```

**Impact:** Queries about "where do I sign" might struggle without knowing this is a signature section.

## Contextual Retrieval Strategy

### What the Reference Describes

Prepend 50-100 tokens of context before embedding:

```
Input to embedding model:
"
[Document: Employment Agreement]
[Section: 2(d)]
[Page: 5]

The party must provide written notice within 30 days of termination.
"
```

### Benefits (From Reference)

1. **Dense retrieval** sees structured context in embedding space
2. **BM25 retrieval** gets more term variety (document name, section, etc.)
3. **Combined** with hybrid search and reranking → substantial failure reduction

### Our Current Gap

- Context exists in metadata ✅
- Context is preserved through retrieval ✅
- But context is NOT in the embeddings used for dense search ❌
- And context is NOT boosting BM25 term frequency ❌

## Proposal: Measured Contextual Improvement

### Phase 1: Measurement (This Story)

Before touching indexing, measure the problem:

1. **Baseline metrics** on current system
   - Run evaluation set on current dense + BM25 + hybrid
   - Measure: recall@5, recall@10, recall@20, MRR, latency

2. **Identify gaps** in current retrieval
   - Which queries fail?
   - Are failures related to hierarchical sections? (Case 1)
   - Are failures related to document type? (Case 2)
   - Are failures related to exact identifiers? (Case 3)

3. **Hypothesize improvements**
   - If hierarchical sections are problem → Add section context to embeddings
   - If document type is problem → Add document name to embeddings
   - If identifiers are problem → BM25 already handles, check if more context helps

### Phase 2: Targeted Improvements (Future Story)

Once measurement shows what helps:

1. **Option A: Minimal context addition**
   - Prepend only what measurement shows is broken
   - E.g., if only hierarchical sections matter: "Section 2(d)(i):\n{text}"
   - Avoids unnecessary duplication and index bloat

2. **Option B: Full contextual embeddings** (if justified by measurement)
   - Prepend all available context (50-100 tokens)
   - Requires index version increment
   - Requires re-indexing entire corpus

3. **Option C: Hybrid approach**
   - Keep current embeddings (for backward compatibility)
   - Add contextual variants for high-value chunks only
   - Parallel indices, weighted combination

## Acceptance Criteria for LG-RAG-025

✅ **Context carried into retrieval representation**
- Validate that all metadata fields reach HybridChunk
- Document what context is available for each result

✅ **Context-loss cases identified**
- List which metadata fields are NOT in embeddings
- Document impact: "Section numbers not in dense embeddings"
- List which fields ARE in BM25 index

✅ **Before/after retrieval experiment performed**
- Establish baseline metrics (dense, BM25, hybrid on eval set)
- Measure which query types fail most
- Categorize failures by context type

✅ **No unnecessary chunk duplication**
- Do NOT modify chunks or create duplicates
- Do NOT re-index
- Only measure and analyze current state

✅ **Index version incremented when representation changes**
- Current: embedding_version from EmbeddingProvider
- If we change what text is embedded: increment version
- Not needed for this story (only measurement)

## Implementation Plan

### Step 1: Context Audit
Create `ContextAudit` class that examines each chunk:
```python
class ContextAudit:
    def analyze_chunk(self, chunk: Chunk, vector_record: VectorRecord):
        return {
            "chunk_id": chunk.chunk_id,
            "context_in_embedding": [
                # What's in VectorRecord.text that was embedded
            ],
            "context_in_metadata": [
                # What's in VectorRecord but not embedded
                "section_number": chunk.section_number,
                "subsection": chunk.subsection,
                "clause": chunk.clause,
                "structure_path": chunk.structure_path,
            ],
            "context_loss_types": [
                # Categorize what's missing
            ],
        }
```

### Step 2: Retrieval Comparison Framework
Create `RetrievalComparison` to track:
- Query
- Dense results (with context metadata)
- BM25 results (with context metadata)
- Hybrid results (with dual attribution)
- Which context fields appear in top-k
- Which are missing

### Step 3: Evaluation Experiment
Run on evaluation set:
```python
results = {
    "dense_only": [...],      # baseline
    "bm25_only": [...],       # baseline
    "hybrid": [...],          # current best
}

analysis = {
    "failures_by_context_type": {
        "hierarchical_section": 12,  # queries failing on section queries
        "document_type": 5,
        "exact_identifier": 3,
    },
    "context_coverage": {
        "dense_includes_section_number": False,
        "bm25_includes_section_number": False,
        "metadata_preserved": True,
    },
}
```

### Step 4: Report & Recommendations
Document findings and next steps:
- Which context is most impactful?
- What changes would help most?
- Is re-indexing justified?
- What's the ROI of contextual embeddings?

## Key Insight

The reference shows 30-50% failure reduction with full contextual approach. But your architecture is smarter:

1. **You have hierarchical structure detection** (section_number, subsection, clause, structure_path)
2. **You preserve it in metadata** (available to all retrieval methods)
3. **You have hybrid search** (combines dense + BM25)

So measurement might show:
- Hierarchical context → Important for some queries, not others
- Document context → BM25 already handles via document_name
- Full contextual embeddings → Nice-to-have, not essential

Result: You can optimize based on data, not hype.

## Why This Approach Is Better

### Avoid
- ❌ Blind re-indexing (expensive, might not help)
- ❌ Duplicating chunks with context prepended (bloat, confusion)
- ❌ "Contextual" embeddings without knowing what helps

### Instead
- ✅ Measure current state (baseline)
- ✅ Identify specific failures (root cause analysis)
- ✅ Implement only what measurement justifies (efficient)
- ✅ Track impact with before/after metrics (data-driven)

## Success Metrics

**Measurement quality:**
- Evaluation set size: N queries with gold-standard answers
- Baseline metrics: recall@5/10/20, MRR for dense/BM25/hybrid
- Failure categories: hierarchical, document-type, identifier, semantic

**Decision support:**
- Clear answer to: "Does context help?"
- Clear answer to: "Which context helps most?"
- Quantified ROI for any indexing changes

## Future Work Enabled

Once measurement is done, LG-RAG-026+ can decide:
- Increment embedding_version and re-index (if justified)
- Add context-aware variants for specific query types
- Improve BM25 by adding more context terms
- Route queries by type (hierarchical → prefer dense with context, etc.)

All decisions backed by data.

## Files This Story Creates

1. **ContextAudit** class — Analyzes what context reaches each retrieval method
2. **RetrievalComparison** class — Tracks dual-method results with context analysis
3. **Evaluation experiment script** — Runs on eval set, produces metrics
4. **Analysis report** — Findings and recommendations for LG-RAG-026+

No index changes, no chunk duplication, no breaking changes.
Pure measurement.
