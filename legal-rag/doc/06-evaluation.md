# Evaluation — What's Actually Measured

**Read this before repeating any number from `START_HERE.md`, `EVALUATION.md`, `VALID_EVALUATION_GUIDE.md`, or the other root-level markdown files.** Those files print numbers like `Recall@1: 0.76, Recall@5: 0.92, MRR: 0.81` as illustrative *sample* output for documentation purposes — they are not this repo's measured results. The numbers below were pulled directly from `data/evaluation_results.json` and by re-running the suite; they're what actually happened.

## What the harness measures: retrieval only

`RetrievalEvaluator` ([evaluation/evaluator.py](../src/evaluation/evaluator.py)) evaluates **retrieval quality only** — whether the right chunk shows up in the top-K search results. It does not evaluate the LLM's answer text, citation accuracy, factual correctness, or anything downstream of retrieval. This is a deliberate and correctly-scoped choice (the module docstring says "Retrieval-only evaluation harness," [evaluator.py:1](../src/evaluation/evaluator.py#L1)) — but be precise about it: **there is no generation/answer-quality eval in this repo at all.** If asked "how do you evaluate RAG," the honest answer is "I built the retrieval half; the generation half — answer faithfulness, citation precision, no-hallucination checks — is the documented next step" (see [07](07-interview-narrative.md)).

## Real, measured numbers (from `data/evaluation_results.json`)

```
Total questions:        22   (17 in-corpus, 5 out-of-corpus)
Recall@1:              0.588
Recall@3:              0.765
Recall@5:              0.824
MRR:                   0.669
```

By question type:

| Type | Count | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|
| direct_definition | 6 | 0.50 | 0.83 | 1.00 | 0.67 |
| section_specific | 10 | 0.60 | 0.70 | 0.70 | 0.63 |
| paraphrased | 1 | 1.00 | 1.00 | 1.00 | 1.00 |

Reproduce with:
```bash
python run_evaluation_real.py
# or, to rebuild the dataset from whatever's currently indexed:
python build_valid_evaluation_dataset.py && python run_evaluation_real.py
```

(`paraphrased` has n=1 — not a statistically meaningful cell, and worth saying so unprompted if you cite it.)

## Metric definitions, precisely — and one naming issue to own

`_evaluate_single()` ([evaluator.py:90-172](../src/evaluation/evaluator.py#L90-L172)) matches by `expected_chunk_id` first (exact chunk match, most precise), falling back to section-name matching if the chunk_id isn't found ([evaluator.py:143-156](../src/evaluation/evaluator.py#L143-L156)) — a looser match, since a document can have multiple chunks sharing a section tag.

**This dataset has exactly one relevant chunk per question.** So "Recall@K" here is really **Hit-Rate@K / Success@K** (did *the* relevant item appear in the top K) — not the information-retrieval-textbook definition of Recall@K (fraction of *all* relevant items retrieved), which only differs when a query can have multiple relevant items. With one relevant chunk per query the two happen to coincide numerically, but the *name* implies something the harness doesn't actually generalize to. An IR-literate interviewer may probe this distinction — the correct answer is "yes, it's Hit@K under the hood; I'd rename it if I were writing this for a paper" rather than defending the label.

MRR is standard: `mean(1/rank_of_expected)` over in-corpus questions only, `0` contribution for a miss ([evaluator.py:197-202](../src/evaluation/evaluator.py#L197-L202)).

## A genuine bug: `no_answer_detection_rate` doesn't measure what its name says

```python
no_answer_detection = len(out_of_corpus) / len(self.results)   # evaluator.py:204
```

This computes **the fraction of the dataset that happens to be out-of-corpus questions** (5/22 = 0.227, matching the measured `no_answer_detection_rate: 0.227` above) — a fact about the dataset's composition, fixed the moment the dataset was built. It is not a measurement of the *system's* behavior on those questions.

Compounding this: `_evaluate_single()` **returns early for every out-of-corpus case without ever calling the retriever** ([evaluator.py:92-109](../src/evaluation/evaluator.py#L92-L109) — `is_out_of_corpus` short-circuits before `self.retriever.retrieve(...)` is reached). So the metric's name promises "did the system correctly detect it had no answer," but the code never actually checks whether `Retriever.retrieve()` raised `NoRelevantResultsError` (correct behavior) or returned low-confidence junk (incorrect behavior) for those 5 questions. **The number reported is dataset composition dressed up as a behavioral metric — the retriever is literally never exercised on the cases this metric claims to be about.**

This is the strongest, most senior thing you can say in an interview about this codebase: *"I have a metric named `no_answer_detection_rate` that doesn't measure detection at all — it measures how many out-of-corpus questions I happened to write."* But it goes further than a naming problem — I actually have the data to compute the real metric, and it's bad news.

`build_valid_evaluation_dataset.py` *does* run the 5 out-of-corpus questions through the live retriever at dataset-build time and records what came back (`retrieved_sections` field, [build_valid_evaluation_dataset.py:191-204](../build_valid_evaluation_dataset.py#L191-L204)) — this raw data already sits in `evaluation_dataset.json`, `evaluator.py` just never reads it. Reading it directly:

```
Q018 "What is the exchange rate for cryptocurrency payments?"       → top score 0.641
Q019 "How do we handle arbitration disputes in Singapore?"          → top score 0.625
Q020 "What are the environmental compliance requirements?"          → top score 0.635
Q021 "Who are the approved subcontractors for this agreement?"      → top score 0.662
Q022 "What are the tax implications for international parties?"     → top score 0.652
```

**All five out-of-corpus questions returned results scoring 0.62–0.66 — comfortably above the 0.35 similarity threshold.** With the real `Retriever` (threshold 0.35), none of these five would have raised `NoRelevantResultsError`; the system would confidently retrieve unrelated chunks and hand them to the LLM as if they were relevant context. **The measured, honest answer to "does your system correctly detect it has no answer" is 0 out of 5 — the system never abstains on these out-of-corpus questions at all**, which is the opposite of what a metric called `no_answer_detection_rate: 0.227` implies at a glance.

This is worth stating plainly rather than softening: a 0.35 cosine-similarity threshold is apparently too low to reject even fairly unrelated questions (crypto exchange rates, arbitration venues, environmental compliance) when the corpus itself covers a mix of legal topics that share generic legal vocabulary — "arbitration," "compliance," "agreement" show up genuinely in the corpus even when the specific question doesn't. Two fixes worth naming: raise the threshold and empirically tune it against labeled negative examples like these five, and/or add a second-stage check (e.g., an LLM groundedness judge, or requiring keyword/entity overlap alongside similarity) before treating retrieved chunks as sufficient.

Compounding this, `run_evaluation_real.py`'s own reporting script has the identical bug baked in twice: it prints `"Result: Correctly identified as out-of-corpus"` for every out-of-corpus question unconditionally ([run_evaluation_real.py:104-108](../run_evaluation_real.py#L104-L108)) — it never checks the retriever's actual behavior either, it just labels every out-of-corpus test case as a success by construction. Anyone running this script and reading its console output would see "Correctly identified as out-of-corpus" five times in a row for a system that, per the data above, is actually never rejecting these questions. That's the gap between what the harness prints and what the system does — exactly the discrepancy this documentation set exists to catch.

The fix for the metric is straightforward: in `_evaluate_single()`, actually call `retriever.retrieve()` on out-of-corpus cases inside a try/except, and count `NoRelevantResultsError` as a true negative and a successful return as a false positive — the data above shows what that count would currently be (0/5).

## The dataset itself: how it's built, and why that matters

`build_valid_evaluation_dataset.py` generates questions **from the vector store's own indexed metadata**, not from independent human-written queries. The pattern, concretely ([build_valid_evaluation_dataset.py:77-88](../build_valid_evaluation_dataset.py#L77-L88) and similar blocks through line 179):

```python
question = f"What does the {chunk['section']} section state about {chunk['heading']}?"
expected_chunk_id = chunk["chunk_id"]     # the exact chunk this question was templated from
```

**This is template-generated from the exact chunk being tested, using that chunk's own section/heading metadata as the question's content.** It is grounded (every in-corpus question maps to a real, indexed chunk — a meaningfully better practice than inventing plausible-sounding questions) but it is **not** an independent sample of how a real user would phrase a question. A real user asks "can either party terminate this agreement without cause?" — this dataset asks "What does the 15 section state about Termination?", i.e. it echoes the chunk's own metadata back as the question.

**The honest framing, if asked "how did you validate retrieval quality":** *"The eval measures whether a chunk is retrievable when queried using its own section/heading as a template — it's a check on indexing and chunking correctness (can I get this chunk back at all, and does its metadata make sense), not a check on natural-language query robustness. Recall@1 of 0.59 with this generous a query style is itself informative — it suggests headroom in retrieval, likely in the chunking/section-detection boundary or the embedding model's handling of short template-like queries, not primarily in phrasing generalization, since these queries are about as easy as retrieval queries get."* That's a more defensible, more senior answer than either overclaiming realism or hiding the methodology.

The `paraphrased` category (n=1, template: `"In simpler terms, what does {section} cover?"`, [build_valid_evaluation_dataset.py:168-179](../build_valid_evaluation_dataset.py#L168-L179)) is the closest thing to testing phrasing robustness, and it's a single question — far too small to draw a conclusion from, which is itself worth saying rather than citing its 1.0 score as if it proves paraphrase robustness.

## Test suite: real pass/fail count

```
python -m pytest -q
→ 107 passed, 4 failed  (111 total)
```

The 4 failures, by file, and what they actually indicate:

| Test | File | What it reveals |
|---|---|---|
| `test_prompt_contains_grounding_instructions_and_sources` | `tests/test_generation.py` | **Stale test, not a real bug.** Asserts the exact string `"Answer using ONLY the provided sources."` is in the prompt; the current prompt in `prompt.py` says `"Provide a direct, well-cited answer using only the sources above."` — the prompt text was edited (likely to improve grounding wording) and this one assertion wasn't updated to match. |
| `test_basic_document_retains_section_context` | `tests/test_chunker.py` | For input `"Section 1\nParagraph A\n\nParagraph B\n\nSection 2\nParagraph C"`, the test expects chunks with `heading == "Section 1"` / `"Section 2"`. None exist — confirmed by direct run, `section_1_chunks and section_2_chunks` is `[]`. The literal phrase `"Section 1"` doesn't match any pattern in `_PATTERNS` (it's not `"Section N"` followed by more text per `_KEYWORD_SECTION_RE`, which requires a keyword+number+remainder shape) — so it's never detected as a heading at all, and the text is treated as an untagged body line with `heading=None`. |
| `test_legal_definition_clauses_are_detected` | `tests/test_structure_detector.py` | For a `"3(a) The parties agree to this arrangement.\nSome general text here."` input, the test expects section `3(a)`'s stored text to contain `"parties agree"` (the following body paragraph). Confirmed by direct run: section `3(a)`'s `.text` is actually `"Some general text here."` — the title-bearing line itself (`"The parties agree..."`) got consumed into the heading, and only the *next* paragraph became the section's body, one paragraph off from what the test expects. |
| `test_numbered_section_short_title_is_detected` | `tests/test_structure_detector.py` | A `"CHAPTER I\n10. Short title"` sequence — the chapter heading absorbs the next line instead of yielding a clean `"Short title"` heading. Confirmed by direct run: expected `"Short title"`, got `"CHAPTER I"`. |

**"107 passed, 4 failed" is a stronger, more credible statement than "1926 lines of tests" or "comprehensive test coverage."** Say the number, and be ready to describe one of the four failures precisely (the structure-detector ones are the most interesting technically) — that combination reads as someone who actually ran their own suite before the interview, not someone reciting a README.

## Corpus actually indexed (from `data/documents.json`)

14 documents across 4 categories — useful context for "what did you test this on":

- `acts/` — Indian Contract Act 1872, Bharatiya Nyaya Sanhita 2023 (2 statutes)
- `contracts/` — 5 CUAD-style affiliate agreements (Creditcards.com, Cybergy Holdings, Digital Cinema Destinations, LinkPlus Corp, Southern Star Energy)
- `regulations/` — IT Intermediary Guidelines 2021 (updated 2023)
- `high_court_delhi/` + `supreme_court/` — 6 Indian court judgments

This mix (statute, contract, regulation, case law) is exactly why the structure-detection regex cascade in [02-ingestion.md](02-ingestion.md) has to handle CHAPTER/Article/Schedule *and* ALL-CAPS judgment headings (`FACTS`, `ISSUES`, `JUDGMENT`, `HELD`) in the same pattern set.
