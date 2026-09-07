# Generation Layer Diagnostic Guide

## How to Capture the Generation Pipeline

### Step 1: Run the Audit Tool

From the project root (`legal-rag/`), run:

```bash
python audit_generation.py
```

This will:
1. ✓ Execute the exact query "What is consideration?"
2. ✓ Show all 5 retrieved chunks with similarity scores
3. ✓ Display the full prompt sent to the LLM
4. ✓ Show the LLM response
5. ✓ Export JSON with complete audit data to `audit_generation_output.json`

### Step 2: Copy the Output

The tool prints:
- **[CONFIG]** - Embedding model, LLM model, settings
- **[RETRIEVAL STAGE]** - Top-5 chunks retrieved, with Section 2(d) marked if present
- **[CONTEXT BUILDING STAGE]** - How chunks are assembled into context
- **[FULL PROMPT SENT TO LLM]** - The exact prompt (copy this!)
- **[LLM CALL PARAMETERS]** - Temperature, model, etc.
- **[LLM RESPONSE]** - The answer returned
- **[ANALYSIS]** - Whether Section 2(d) is in context and response

---

## Prompt Structure

### What Gets Sent to the LLM

The PromptBuilder combines three parts:

#### 1. **System Instruction** (CRITICAL RULES)

From `src/generation/prompt.py`:

```
You are a legal information assistant. Your role is to provide accurate, 
well-sourced answers based solely on provided documents.

CRITICAL RULES:
1. Answer ONLY using facts, clauses, provisions, and definitions found in the sources.
2. Do NOT invent, infer, or assume legal provisions not explicitly stated.
3. Every factual claim MUST be cited with [SOURCE_N] immediately after the claim.
4. If a source contains key terms or definitions, quote them accurately.
5. If sources do NOT contain sufficient information to answer, say: 
   'I could not find this information in the provided documents.'

WHEN ANSWERING:
- Quote relevant sections or clauses directly when possible.
- Start with the most specific, on-point source.
- If multiple sources apply, cite all relevant ones.
- Use the source's own language—avoid paraphrasing critical legal terms.
- If a question asks about purpose, aim, or intent: look for preambles, recitals, 
  long titles, or 'object' clauses as primary evidence.

EXAMPLES:
❌ BAD: 'The Act applies to all commercial transactions.' (no citation)
✓ GOOD: 'The Act applies to all commercial transactions [SOURCE_1].'
✓ BETTER: 'The Act applies to "all commercial transactions [SOURCE_1], including 
          contracts for goods, services, and intellectual property [SOURCE_2]."'
```

#### 2. **User Question**

```
USER QUESTION:
What is consideration?
```

#### 3. **Retrieved Sources (Context)**

From `src/generation/context_builder.py`:

```
SOURCES:

[SOURCE_1]
Document: indian_contract_act_1872.pdf
Section/Heading: Consideration for guarantee
Category: 127
Page: 34

127. Consideration for guarantee .—Anything done, or any promise made, for the benefit of the
principal debtor, may be a sufficient consideration to the surety for giving the guarantee.
Illustrations
  (a) A gives a guarantee to B to be answerable for C, a merchant. B accepts the guarantee. The 
  acceptance by B of the guarantee from A is a good consideration for A's promise...

[SOURCE_2]
Document: indian_contract_act_1872.pdf
Section/Heading: 2(a)(b)(c)(d). When, at the desire of the promisor, the promisee or any other person has done or abstained
Category: 2(a)(b)(c)(d)
Page: 11

(d) When, at the desire of the promisor, the promisee or any other person has done or abstained
from doing, or does or abstains from doing, or promises to do or to absta in from doing, something,
such act or abstinence or promise is called a consideration for the promise;

[SOURCE_3]
...
```

---

## LLM Call Parameters

### From DeepSeekLLMClient (src/generation/providers.py):

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Model** | `deepseek-chat` | Default from `.env` |
| **API Key** | from `DEEPSEEK_API_KEY` env var | Loaded from `.env` |
| **Base URL** | `https://api.deepseek.com` | DeepSeek API endpoint |
| **Temperature** | `0.0` | **DETERMINISTIC** - no randomness |
| **Top P** | (default) | LangChain ChatOpenAI default (not overridden) |
| **Max Tokens** | (default) | LangChain ChatOpenAI default (not overridden) |

### Why Temperature = 0.0?

With temperature at 0.0, the model should:
- ✓ Always pick the highest-probability token
- ✓ Never sample lower-probability outputs
- ✓ Be completely deterministic for the same input
- ✗ NOT prefer examples over direct definitions

---

## Why Section 2(d) Might Be Ranked Lower Than Section 4

### What We Know:

1. ✓ **Section 2(d) is retrieved** at rank #2 with score 0.7012
2. ✓ **Section 2(d) IS in the context** passed to the LLM
3. ✓ **Section 2(d) has the actual definition** of consideration
4. ✓ **Section 4 examples are ranked #7** with lower scores

### Possible Reasons Why LLM Chooses Section 4:

#### Theory 1: **Context Ordering Matters**
- SOURCE_1 (Section 127: Consideration for guarantee)
- SOURCE_2 (Section 2(d): Direct definition) ← **The actual definition**
- ...
- SOURCE_7 (Section 4: Examples)

If the LLM sees Section 127 first (SOURCE_1) and considers it more specific for "guarantee" context, it might prioritize that. Section 2(d) is SOURCE_2 but not mentioned as prominently by the system prompt.

#### Theory 2: **System Prompt Prioritization**
The system prompt says:
> "Start with the most specific, on-point source."

For a general question like "What is consideration?" the model might see:
- Section 127 (specific to guarantee context) ← Looks more specific?
- Section 2(d) (general definition) ← Looks more general?

The model could interpret Section 127 as "more specific" because it's in a specific context (guarantees).

#### Theory 3: **Examples Are Easier to Explain**
Section 4 examples like "A promises, for a certain sum paid to him by B..." are concrete scenarios. The model might generate a more detailed/confident response using examples rather than the terse definition in Section 2(d).

#### Theory 4: **Source Reranking in Retriever**
From `src/retrieval/retriever.py`, the `_rank_by_relevance` method re-ranks results after initial scoring:

```python
def _rank_by_relevance(self, results: list[RetrievalResult], query: str) -> list[RetrievalResult]:
    # Re-ranks by:
    # 1. Frontmatter priority
    # 2. Similarity score (higher is better)
    # 3. Query term count (how many words from query appear in chunk)
    # 4. Section bonus
    
    return sorted(results, key=relevance_score)
```

This custom re-ranking could reorder Section 2(d) even though it has high similarity.

---

## To Debug Further

### Check 1: Is Section 2(d) in the Actual LLM Response?

Run `audit_generation.py` and look for:
- `"When, at the desire"` in the response
- `"2(d)"` mentioned
- `[SOURCE_2]` cited

If these are present → Section 2(d) **is being used**, just not prioritized  
If these are absent → Section 2(d) **is being ignored by the LLM**

### Check 2: Did Retriever Re-ranking Move Section 2(d) Down?

The audit tool prints:
```
Rank #1: (initial similarity score 0.7165)
Rank #2: (initial similarity score 0.7012) ← Section 2(d)
```

If after retriever re-ranking Section 2(d) drops below rank 6 (max_sources), it won't reach the LLM.

Check `src/retrieval/retriever.py` line 37-64 for the re-ranking logic.

### Check 3: Is Context Truncation Cutting Section 2(d)?

From `src/generation/context_builder.py`:

```python
max_context_chars: int = 8000  # Max chars to include
max_sources: int = 6           # Max number of sources to include
```

If the context exceeds 8000 chars:
- The loop stops and earlier sources are truncated
- Later sources (like Section 4 examples) might be cut entirely

Run `audit_generation.py` and check:
```
[CONTEXT BUILDING STAGE]
Context length: XXXX characters
```

If > 6000 chars, truncation risk is high.

### Check 4: Is the System Prompt Clear Enough?

The current system prompt says "Start with the most specific, on-point source."

- For "What is consideration?" what counts as "most specific"?
- Is Section 127 (specific to guarantees) considered more specific than Section 2(d) (general)?

This ambiguity could cause the LLM to second-guess the ranking.

---

## Next Steps

1. **Run the audit tool** and capture the full output
2. **Check if Section 2(d) appears** in the [LLM RESPONSE]
3. **If it appears:** The issue is prioritization/ranking, not retrieval
4. **If it doesn't appear:** Check context truncation or retriever re-ranking
5. **Share the audit output** for deeper analysis

---

## Files to Review if Debugging

| File | Purpose | Key Lines |
|------|---------|-----------|
| `src/retrieval/retriever.py` | Re-ranking logic | 39-64 |
| `src/generation/context_builder.py` | Context assembly | 15-47 |
| `src/generation/prompt.py` | System instructions | 14-36 |
| `src/generation/providers.py` | LLM parameters | 10-28 |
| `audit_generation.py` | This diagnostic tool | Run it! |

