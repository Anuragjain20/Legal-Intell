# Section 2(d) Retrieval Issue - Complete Diagnostic Summary

**Status:** ✓ RETRIEVAL WORKING | ❓ GENERATION NEEDS INSPECTION

---

## Quick Answer

### What We Found

For query **"What is consideration?"**:

| Component | Status | Details |
|-----------|--------|---------|
| **Chunking** | ✓ OK | Section 2(d) exists in chunks (chunk_id: ...0034) |
| **Embedding** | ✓ OK | Has 384-dim embedding, stored in Chroma |
| **Vector Search** | ✓ OK | Ranks #2 with score 0.7012 (high relevance) |
| **Retrieval** | ✓ OK | Successfully retrieved in top-5 |
| **Context Building** | ✓ OK | Present in context passed to LLM |
| **LLM Response** | ❓ TBD | **Need to run audit tool to verify** |

---

## Part 1: Retrieval Diagnostics (Complete)

### Section 2(d) Chunk Details

```
Chunk ID:    d756d45a58c4cd8440e70a0189ea1fda9d7c5dfcdd6ef31a5f2ecd9cb209c59d:0034
Page:        11
Section:     2(a)(b)(c)(d)
Text:        (d) When, at the desire of the promisor, the promisee or any other person has done 
             or abstained from doing, or does or abstains from doing, or promises to do or to 
             abstain from doing, something, such act or abstinence or promise is called a 
             consideration for the promise;
```

### Similarity Search Results

For "What is consideration?":

```
Rank  Score   Section              Document              Similarity
────────────────────────────────────────────────────────────────────
  1   0.7165  127 (Guarantee)      Indian Contract Act   ✓ High
  2   0.7012  2(d) ⭐ DEFINITION   Indian Contract Act   ✓ High
  3   0.6446  IT Guidelines (b)    IT Intermediary Rules  ✓ Medium
  4   0.6392  23                   Indian Contract Act   ✓ Medium
  5   0.6378  IT Guidelines (a)    IT Intermediary Rules  ✓ Medium
  6   0.6365  4(a)(b)(c)           Indian Contract Act   ✓ Medium
  7   0.6282  8                    Indian Contract Act   ✓ Medium
```

**Threshold:** 0.30 (all above threshold ✓)

### Context Building

- **Sources included:** 6 (max_sources = 6)
- **Context length:** ~3,600 chars (max = 8,000, plenty of room)
- **Section 2(d) position:** SOURCE_2 (second out of six)
- **All sources included:** ✓ YES (no truncation)

---

## Part 2: Generation Pipeline (Needs Inspection)

### Key Question

**Why might the LLM prefer Section 4 examples over Section 2(d) direct definition?**

### LLM Configuration

```
Model:              deepseek-chat
Temperature:        0.0 (deterministic)
Top P:              default (LangChain ChatOpenAI)
Max Tokens:         default (LangChain ChatOpenAI)
Base URL:           https://api.deepseek.com
```

### Prompt Structure

The LLM receives:

1. **System Instruction** (lines 14-36 of `src/generation/prompt.py`):
   - "Answer ONLY using facts found in sources"
   - "Every claim MUST be cited with [SOURCE_N]"
   - "Start with the most specific, on-point source"
   - "Quote relevant sections directly when possible"

2. **User Question**:
   ```
   What is consideration?
   ```

3. **Retrieved Context** (6 sources):
   - SOURCE_1: Section 127 (Consideration for guarantee)
   - SOURCE_2: Section 2(d) (Direct definition) ⭐
   - SOURCE_3-6: Other sections on consideration
   
   All marked with `[SOURCE_N]` for citation

### Theories Why Section 2(d) Might Be Overlooked

#### Theory A: System Prompt Ambiguity
> "Start with the most specific, on-point source"

- Section 127 is **specific to guarantees** (a use case)
- Section 2(d) is **general definition** (the root concept)

The LLM might interpret "specific" as "narrower context" rather than "most directly relevant to the question."

#### Theory B: Custom Re-ranking in Retriever
`src/retrieval/retriever.py` lines 39-64 re-sort results by:
1. Frontmatter priority
2. Similarity score
3. Query term count
4. Section specificity bonus

The re-ranking might demote Section 2(d) if it thinks another source is "more specific."

#### Theory C: Context Order Bias
LLMs have recency bias:
- SOURCE_1 is seen first (Section 127)
- LLM might latch onto first answer found, even if not best

#### Theory D: Examples Are Clearer
Section 4 contains concrete examples ("A promises, for a certain sum paid...").
- More detailed explanation
- Easier to elaborate on
- More "confident-sounding" to generate

Section 2(d) is terse legal definition—harder to expand without paraphrasing.

---

## How to Debug This Now

### Use the Audit Tool

```bash
cd legal-rag
python audit_generation.py
```

**This will show you:**

1. ✓ The exact prompt sent to the LLM (copy-paste it)
2. ✓ The exact LLM response
3. ✓ Whether Section 2(d) appears in the response
4. ✓ Which sources are cited

### What to Look For

#### Scenario A: Section 2(d) IS in Response
- Issue: **Ranking/prioritization**, not retrieval
- Fix: Adjust system prompt or retriever logic

#### Scenario B: Section 2(d) NOT in Response
- Check: Is it in the 6-source context? (audit tool shows this)
- If YES: LLM chose to ignore it
- If NO: Retriever re-ranking dropped it

---

## File Locations

### Diagnostic Tools (Run These)
- **`audit_generation.py`** ← Run this first! Shows full pipeline
- **`audit_retrieval.py`** ← Already provided, shows retrieval stage
- **`GENERATION_LAYER_DIAGNOSTIC.md`** ← Detailed explanations

### Source Code (For Understanding)
```
src/retrieval/retriever.py          (Re-ranking logic - lines 39-64)
src/generation/context_builder.py   (Context assembly - lines 15-47)
src/generation/prompt.py            (System instructions - lines 14-36)
src/generation/providers.py         (LLM parameters - lines 10-28)
src/generation/llm_service.py       (Generation orchestration)
```

---

## Summary of Findings

### ✓ What's Working

1. ✓ PDF extraction → chunks are created
2. ✓ Chunking → Section 2(d) is chunked correctly
3. ✓ Embedding → Section 2(d) gets proper embedding
4. ✓ Vector search → Retrieves at rank #2 (0.7012 score)
5. ✓ Context building → Included in context (SOURCE_2)
6. ✓ Prompt assembly → Section 2(d) passed to LLM

### ❓ What Needs Inspection

1. ❓ LLM response → Does it cite Section 2(d)?
2. ❓ Source prioritization → Why #1 (127) over #2 (2(d))?
3. ❓ Re-ranking logic → Is it reordering optimally?
4. ❓ System prompt clarity → Is "most specific" clear to LLM?

---

## Next Action: Run the Audit

```bash
python audit_generation.py > audit_output.txt 2>&1
```

Then:
1. Check if `[LLM RESPONSE]` contains "2(d)" or "desire of the promisor"
2. Share the output for deeper analysis
3. Check `audit_generation_output.json` for structured data

---

## Don't Change Anything Yet

As requested:
- ✗ No code modifications
- ✗ No embedding re-runs
- ✗ No re-ingestion
- ✓ Just inspection and diagnostics

Run the audit tool and we'll know exactly what to fix.

