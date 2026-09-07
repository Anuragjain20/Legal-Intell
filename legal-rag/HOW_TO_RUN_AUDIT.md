# How to Run the Generation Layer Audit

## TL;DR: Quick Start

### In PowerShell / Terminal

```bash
cd c:\Users\anura\Desktop\legal-rag-intelligence\legal-rag
python audit_generation.py
```

The tool will output everything you need to see.

---

## What You'll See

The output is organized into sections that you can easily copy:

### 1. Configuration Section
```
[CONFIG]
  Embedding Model: BAAI/bge-small-en-v1.5
  LLM Model: deepseek-chat
  LLM Base URL: https://api.deepseek.com
  Similarity Threshold: 0.35
```

**What to look for:** Are these your intended settings?

---

### 2. Retrieval Section
```
[RETRIEVAL STAGE]
  Retrieved 5 chunks
  
  Rank #1:
    - Chunk ID: d756d45a58c4cd84...0250
    - Page: 34
    - Section: 127
    - Score: 0.7165
    - Text (first 80 chars): 127. Consideration for guarantee .—Anything done...
    
  Rank #2:
    - Chunk ID: d756d45a58c4cd84...0034
    - Page: 11
    - Section: 2(a)(b)(c)(d)
    - Score: 0.7012
    - Text (first 80 chars): (d) When, at the desire of the promisor, the promisee...
    ⭐ THIS IS SECTION 2(d)
```

**What to look for:** Section 2(d) should show "⭐ THIS IS SECTION 2(d)" at rank #2

---

### 3. Context Building Section
```
[CONTEXT BUILDING STAGE]
  Built context from 6 sources
  Context length: 3615 characters
  
  SOURCE_1:
    - Chunk ID: d756d45a58c4cd84...0250
    - Page: 34
    - Section: 127
    - Score: 0.7165
    
  SOURCE_2:
    - Chunk ID: d756d45a58c4cd84...0034
    - Page: 11
    - Section: 2(a)(b)(c)(d)
    - Score: 0.7012
    ⭐ THIS IS SECTION 2(d)
```

**What to look for:** Section 2(d) should appear as SOURCE_2 with "⭐ THIS IS SECTION 2(d)"

---

### 4. Full Prompt Section (MOST IMPORTANT!)
```
[FULL PROMPT SENT TO LLM]
====================================================

You are a legal information assistant. Your role is to provide accurate, 
well-sourced answers based solely on provided documents.

CRITICAL RULES:
1. Answer ONLY using facts, clauses, provisions, and definitions found in the sources.
2. Do NOT invent, infer, or assume legal provisions not explicitly stated.
3. Every factual claim MUST be cited with [SOURCE_N] immediately after the claim.
...

USER QUESTION:
What is consideration?

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

[SOURCE_4]
...

[SOURCE_5]
...

[SOURCE_6]
...

Provide a direct, well-cited answer using only the sources above.
====================================================
```

**Copy this entire section!** This is the exact prompt the LLM sees.

---

### 5. LLM Parameters Section
```
[LLM CALL PARAMETERS]
  Model: deepseek-chat
  Base URL: https://api.deepseek.com
  Temperature: 0.0 (deterministic)
  Top P: (LangChain ChatOpenAI defaults)
  Max Tokens: (LangChain ChatOpenAI defaults - no override)
```

**What to look for:** Temperature should be 0.0 (deterministic, not random)

---

### 6. LLM Response Section (CRITICAL!)
```
[CALLING LLM]
====================================================

Based on the provided sources, consideration is defined as follows:

According to Section 2(d) of the Indian Contract Act [SOURCE_2], "When, at the desire of the 
promisor, the promisee or any other person has done or abstained from doing, or does or abstains 
from doing, or promises to do or to abstain from doing, something, such act or abstinence or 
promise is called a consideration for the promise."

This definition is further exemplified in Section 4, where specific illustrations of consideration 
are provided [SOURCE_4]:

Example: "A promises, for a certain sum paid to him by B, to make good to B the value of his ship..."

Additionally, Section 127 specifies that in the context of guarantees, "Anything done, or any 
promise made, for the benefit of the principal debtor, may be a sufficient consideration to the 
surety for giving the guarantee" [SOURCE_1].

====================================================
```

**What to look for:** 
- Does it mention "2(d)"? ✓ Good
- Does it quote "desire of the promisor"? ✓ Good
- Does it cite [SOURCE_2]? ✓ Good
- If it only mentions Section 4 examples: ✗ Problem

---

### 7. Analysis Section
```
[ANALYSIS]
====================================================
  Section 2(d) in context: ✓ YES
  Section 2(d) referenced in response: ✓ YES
  - Section 1 mentioned
  - Section 2 mentioned
  - Section 4 mentioned
  ⚠ Response includes examples/illustrations
    (This suggests model preferred examples over direct definition)
====================================================
```

---

### 8. JSON Export
A file called `audit_generation_output.json` is created with structured data.

---

## What to Do With the Output

### Best Case ✓
If you see:
- "Section 2(d) in context: ✓ YES"
- "Section 2(d) referenced in response: ✓ YES"
- Section 2(d) is quoted in [LLM RESPONSE]

→ **Everything is working!** The issue was either:
  - User asked different query
  - User's cache wasn't cleared
  - Temporary API issue

### Problem Case ✗
If you see:
- "Section 2(d) in context: ✓ YES"
- "Section 2(d) referenced in response: ✗ NO"

→ **LLM is ignoring Section 2(d)** despite receiving it. Check:
  1. Is SOURCE_1 (Section 127) being prioritized instead?
  2. Does the prompt need to prioritize definitions over examples?
  3. Is the re-ranking logic in `src/retrieval/retriever.py` demoting Section 2(d)?

---

## Copy-Paste Checklist

After running `python audit_generation.py`, copy these sections:

- [ ] **[CONFIG]** - Configuration settings
- [ ] **[FULL PROMPT SENT TO LLM]** - The exact prompt (huge, but important!)
- [ ] **[LLM CALL PARAMETERS]** - Model settings
- [ ] **[LLM RESPONSE]** - The answer
- [ ] **[ANALYSIS]** - Summary
- [ ] **audit_generation_output.json** - Structured data (entire file)

---

## If Audit Tool Fails

### Error: "Cannot import..."
→ Run from the `legal-rag/` directory

### Error: "DEEPSEEK_API_KEY not set"
→ Make sure `.env` file exists in `legal-rag/` with `DEEPSEEK_API_KEY=...`

### Error: "No chunks found"
→ Chroma database might be empty. Re-ingest documents first.

### Error: "LLM call failed"
→ DeepSeek API issue. Check `.env` and API status.

---

## Questions This Answers

After running the audit:

1. **"Does Section 2(d) exist in the database?"**
   → See [RETRIEVAL STAGE] and [CONTEXT BUILDING STAGE]

2. **"Is Section 2(d) passed to the LLM?"**
   → See [FULL PROMPT SENT TO LLM] - search for "SOURCE_2"

3. **"Does the LLM use Section 2(d) in its response?"**
   → See [LLM RESPONSE] - search for "2(d)" or "desire of the promisor"

4. **"What are the exact LLM parameters?"**
   → See [LLM CALL PARAMETERS]

5. **"Why might it mention Section 4 instead?"**
   → See [ANALYSIS] section for clues

---

## Run It Now!

```bash
python audit_generation.py
```

Then share the output and we'll know exactly what to do next.

No code changes yet—just inspection! ✓

