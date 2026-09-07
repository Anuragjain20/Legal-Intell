# Documentation Index: LG-RAG-019 & LG-RAG-020

Quick navigation guide for retrieval layer implementation.

## 🎯 Start Here

**New to this work?** Read in this order:

1. **DELIVERABLES.md** — What was built (summary + file list)
2. **IMPLEMENTATION_STATUS.md** — Full status and architecture
3. **MODULES_OVERVIEW.md** — API reference for actual usage

---

## 📋 Story Documentation

### LG-RAG-019: Retrieval Contract & Query Representation

**Purpose:** Define what enters/leaves retrieval subsystem with guaranteed metadata preservation.

| Document | Purpose | Length |
|----------|---------|--------|
| [RETRIEVAL_CONTRACT.md](RETRIEVAL_CONTRACT.md) | Complete specification | 195 lines |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md#lg-rag-019) | Story details | See section |
| [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#retrieval_modelsspy) | API reference | See section |

**Key Files:**
- `src/retrieval/models.py` — RetrievalRequest, RetrievalResponse, RetrievedChunk
- `src/retrieval/retriever.py` — Structured + legacy APIs
- `tests/test_retrieval_contract.py` — 19 comprehensive tests

**Quick Start:**
```python
from src.retrieval.models import RetrievalRequest
request = RetrievalRequest(query="What are the terms?", top_k=5)
response = retriever.retrieve_structured(request)
```

---

### LG-RAG-020: Query Analysis & Normalization

**Purpose:** Convert raw queries into retrieval-ready representations deterministically.

| Document | Purpose | Length |
|----------|---------|--------|
| [QUERY_NORMALIZATION.md](QUERY_NORMALIZATION.md) | Complete specification | 280 lines |
| [QUERY_NORMALIZATION_EXAMPLES.md](QUERY_NORMALIZATION_EXAMPLES.md) | 10 concrete examples | 420 lines |
| [LG-RAG-020-SUMMARY.md](LG-RAG-020-SUMMARY.md) | Feature summary | 320 lines |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md#lg-rag-020) | Story details | See section |
| [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#query_modelsspy) | API reference | See section |

**Key Files:**
- `src/query/models.py` — QueryIntent, LegalTermSignal, QuerySignal, NormalizedQuery
- `src/query/analyzer.py` — 8-stage analysis pipeline
- `tests/test_query_analyzer.py` — 36 comprehensive tests

**Quick Start:**
```python
from src.query.analyzer import QueryAnalyzer
analyzer = QueryAnalyzer()
normalized = analyzer.analyze("What must the party do?")
print(normalized.intent)  # QueryIntent.OBLIGATION
```

---

## 🔍 By Use Case

### "I want to understand the architecture"
1. Read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) — Full overview
2. Check "Architecture: How LG-RAG-019 & LG-RAG-020 Fit Together" section
3. See flow diagram in the document

### "I want to use query analysis"
1. Read [QUERY_NORMALIZATION.md](QUERY_NORMALIZATION.md) — Design & components
2. Study [QUERY_NORMALIZATION_EXAMPLES.md](QUERY_NORMALIZATION_EXAMPLES.md) — Real examples
3. Reference [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#queryanalyzer-class) — API details

### "I want to use structured retrieval"
1. Read [RETRIEVAL_CONTRACT.md](RETRIEVAL_CONTRACT.md) — Full contract
2. Check [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#retriever-class) — API reference
3. Look for integration patterns in [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#integration-patterns)

### "I want to integrate both together"
1. Start with [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md#architecture-how-lg-rag-019--lg-rag-020-fit-together) — Architecture
2. Follow "Pattern 2: Analysis-Informed Retrieval" in [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#pattern-2-analysis-informed-retrieval)
3. See full example in [QUERY_NORMALIZATION_EXAMPLES.md](QUERY_NORMALIZATION_EXAMPLES.md#using-analyzed-queries-in-retrieval)

### "I want to debug retrieval issues"
1. See [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#common-questions) — Common questions
2. Check performance table in [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#performance-characteristics)
3. Debug tracing pattern in [QUERY_NORMALIZATION_EXAMPLES.md](QUERY_NORMALIZATION_EXAMPLES.md#pattern-3-end-to-end-with-tracing)

### "I want to run tests"
1. Go to [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md#testing-summary) — Test summary
2. Check [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md#testing) — How to run

### "I want to know what's next"
1. Read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md#future-stories) — Planned stories
2. See "Next Steps" in [DELIVERABLES.md](DELIVERABLES.md#next-steps-options) — Options

---

## 📚 Document Reference

| Document | Audience | Length | Purpose |
|----------|----------|--------|---------|
| **DELIVERABLES.md** | Project manager | 450 lines | Complete manifest of all deliverables |
| **IMPLEMENTATION_STATUS.md** | Tech lead | 600 lines | Full status, architecture, testing |
| **RETRIEVAL_CONTRACT.md** | Backend engineer | 195 lines | LG-RAG-019 specification |
| **QUERY_NORMALIZATION.md** | Backend engineer | 280 lines | LG-RAG-020 specification |
| **QUERY_NORMALIZATION_EXAMPLES.md** | Engineer, QA | 420 lines | 10 concrete examples with output |
| **LG-RAG-020-SUMMARY.md** | Tech lead | 320 lines | LG-RAG-020 summary |
| **MODULES_OVERVIEW.md** | API user | 450 lines | Complete API reference |
| **INDEX.md** | Everyone | This file | Navigation guide |

---

## 🎓 Learning Path

### Beginner (30 minutes)
1. [DELIVERABLES.md](DELIVERABLES.md) — What was built?
2. [MODULES_OVERVIEW.md](MODULES_OVERVIEW.md) — How do I use it?
3. Try the quick start examples

### Intermediate (1-2 hours)
1. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) — Full architecture
2. [QUERY_NORMALIZATION_EXAMPLES.md](QUERY_NORMALIZATION_EXAMPLES.md) — See real examples
3. Read source code: `src/retrieval/models.py`, `src/query/analyzer.py`

### Advanced (2-4 hours)
1. [RETRIEVAL_CONTRACT.md](RETRIEVAL_CONTRACT.md) — Deep dive into LG-RAG-019
2. [QUERY_NORMALIZATION.md](QUERY_NORMALIZATION.md) — Deep dive into LG-RAG-020
3. Study tests: `tests/test_retrieval_contract.py`, `tests/test_query_analyzer.py`
4. Read source code completely

### Full Mastery (4-8 hours)
1. Read all documentation
2. Study all source code
3. Run all tests with variations
4. Extend analyzer with new legal terms
5. Implement new retrieval filters

---

## 🔧 Common Tasks

### Task: Add a new legal term to query analyzer
See [QUERY_NORMALIZATION.md](QUERY_NORMALIZATION.md#legal-term-extraction) for term dictionary structure, then edit `src/query/analyzer.py` line ~13.

### Task: Understand how reranking preserves scores
See [RETRIEVAL_CONTRACT.md](RETRIEVAL_CONTRACT.md#score-preservation-across-reranking) for explanation.

### Task: Implement a new filter for retrieval
See [RETRIEVAL_CONTRACT.md](RETRIEVAL_CONTRACT.md#filtering-strategy) and `src/retrieval/retriever.py` `_apply_filters()` method.

### Task: Add a new QueryIntent type
Edit `src/query/models.py` to add new enum value, then update `src/query/analyzer.py` to detect it.

### Task: Measure retrieval quality improvements
See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md#future-stories) for guidance on A/B testing.

---

## ✅ Verification Checklist

- [ ] Read DELIVERABLES.md
- [ ] Read IMPLEMENTATION_STATUS.md
- [ ] Understand module structure in MODULES_OVERVIEW.md
- [ ] Run: `pytest tests/test_retrieval_contract.py -v` (19 tests pass)
- [ ] Run: `pytest tests/test_query_analyzer.py -v` (36 tests pass)
- [ ] Try query analyzer: `python -c "from src.query.analyzer import QueryAnalyzer; print(QueryAnalyzer().analyze('test query'))"`
- [ ] Review [QUERY_NORMALIZATION_EXAMPLES.md](QUERY_NORMALIZATION_EXAMPLES.md) for realistic examples
- [ ] Check backward compatibility in [RETRIEVAL_CONTRACT.md](RETRIEVAL_CONTRACT.md#backward-compatibility)

---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Source code files | 6 |
| Total lines of code | 465 |
| Test files | 2 (+ updates to 1) |
| Total tests | 73 |
| Test pass rate | 100% |
| Documentation files | 8 |
| Total documentation lines | 2,500+ |
| Legal terms indexed | 40+ |
| QueryIntent types | 9 |
| Processing latency | <2ms per query |

---

## 🎯 Key Takeaways

1. **LG-RAG-019** — Retrieval has a formal contract
   - Every request is structured
   - Every response includes metadata
   - Scores and metadata preserved end-to-end

2. **LG-RAG-020** — Queries are analyzed deterministically
   - Intent detection (9 types)
   - Legal term extraction (40+ terms)
   - Negation and temporal awareness
   - Exact term preservation
   - Performance: <2ms per query

3. **Together** — They enable
   - Intent-informed retrieval tuning
   - Measurement-first query improvements
   - Auditable and traceable results
   - Foundation for future features

---

## ❓ FAQ

**Q: Are these changes backward compatible?**
A: Yes. Legacy code continues to work unchanged. New APIs are opt-in.

**Q: Do I have to use both stories together?**
A: No. Use either independently. Together they're more powerful.

**Q: When should I use query analysis?**
A: Always. It's deterministic, fast, and provides useful signals.

**Q: When should I use structured retrieval?**
A: When you need metadata (embedding model, retrieval method) or filtering.

**Q: Will query analysis slow down retrieval?**
A: No. Query analysis takes <2ms; retrieval takes 100-300ms (dominated by embedding + search).

**Q: What if I need query rewriting?**
A: That's a future story (LG-RAG-022). First measure baseline with LG-RAG-020.

**Q: How do I add more legal terms?**
A: Edit `LEGAL_TERMS` dict in `src/query/analyzer.py`.

**Q: How do I add a new intent?**
A: Add to `QueryIntent` enum, then update detection logic.

---

## 📞 Support

- **Architecture questions:** See IMPLEMENTATION_STATUS.md
- **API questions:** See MODULES_OVERVIEW.md
- **Examples:** See QUERY_NORMALIZATION_EXAMPLES.md
- **Specifications:** See RETRIEVAL_CONTRACT.md or QUERY_NORMALIZATION.md
- **Test failures:** Check IMPLEMENTATION_STATUS.md#testing-summary

---

## Related Documentation (External)

- Legal documents ingestion pipeline: See `src/ingestion/`
- Vector embeddings: See `src/embeddings/`
- Generation/LLM integration: See `src/generation/`
- Evaluation framework: See `src/evaluation/`

---

**Last Updated:** 2026-09-07
**Status:** Complete and tested ✅
**Version:** 1.0 (LG-RAG-019 & LG-RAG-020)
