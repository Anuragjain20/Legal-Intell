# Evaluation — What's Actually Measured

**This file was rewritten after the dataset and harness described in "Superseded" below were replaced.** If you see `Recall@1: 0.76` or similar numbers anywhere else in this repo (old root-level markdown, deleted in the cleanup — see [09-retractions.md](09-retractions.md)), those were either illustrative sample output or fabricated. The numbers in this file are traced to a committed JSON file and a script you can re-run.

## Two harnesses: retrieval and generation

`src/evaluation/harness.py` evaluates **retrieval quality** — whether the right chunk shows up in the top-K search results. `src/evaluation/generation_harness.py` runs the full pipeline (retrieval, a real LLM call, citation mapping) and checks whether the *answer* is grounded and faithful, without an LLM judge. See "Generation evaluation, measured" below for real results from the latter.

## Real, measured numbers: four retrieval methods compared

```
python scripts/ingest.py --source <path to the 14 source PDFs>
python scripts/run_evaluation.py --method dense
python scripts/run_evaluation.py --method bm25
python scripts/run_evaluation.py --method hybrid
python scripts/run_evaluation.py --method hybrid_rerank
```

| Method | eval_runs timestamp | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | Gate rate |
|---|---|---|---|---|---|---|---|
| dense | `20260909T180059Z` | 0.4054 | 0.5946 | 0.6486 | 0.1405 | 0.5212 | 0.0000 |
| bm25 | `20260909T180131Z` | 0.4189 | 0.6486 | 0.6757 | 0.1405 | 0.5369 | N/A |
| **hybrid (dense+bm25, RRF)** | `20260909T180205Z` | **0.4459** | **0.7297** | **0.7838** | **0.1622** | **0.5797** | N/A |
| hybrid + reranker | `20260909T180236Z` | 0.2973 | 0.4730 | 0.6216 | 0.1297 | 0.4140 | N/A |

**Hybrid (dense + BM25, Reciprocal Rank Fusion) is the best of the four and is what `/query` runs in production** (`src/services.py`, `src/retrieval/hybrid_query_retriever.py`). It beats dense-only on every metric, and specifically fixes BM25's weakest category — `comparison` questions, where BM25 alone scores 0.1667 Recall@5 (no semantic understanding of paraphrased comparisons) and hybrid recovers to 0.6667.

**The reranker was built, measured, and rejected on the evidence.** `QueryTermOverlapReranker` on top of hybrid *drops* Recall@5 from 0.7838 to 0.6216 and MRR from 0.58 to 0.41 — worse than plain hybrid, worse even than dense alone. It is not wired into `/query`. This table is the reason: a design decision backed by a measurement, not intuition. See [07-interview-narrative.md](07-interview-narrative.md) for how to talk about this.

**Gate rate is only meaningful for dense.** `unanswerable_confidence_gate_rate` compares a candidate's top score against the 0.35 cosine-similarity threshold. BM25's scores are unbounded term-frequency values and hybrid's are ~0.01–0.03-scale RRF scores (`1/(k+rank)` summed across two rankings) — neither is comparable to 0.35, so `scripts/run_evaluation.py` reports `N/A` for both rather than computing a number against the wrong scale. The live `/query` path gates on hybrid results' `dense_score` field instead (the same cosine similarity dense-only produces, carried through the fusion) — see the next section for what that actually measures.

**Unanswerable confidence-gate rate: 0.0000 (dense).** All 5 unanswerable questions retrieved a top result scoring 0.72–0.81 — well above the 0.35 similarity threshold — so the confidence gate never correctly withheld an answer on any of them. Spot-checked directly against Chroma for one case (a question about an interest-rate cap not present in the corpus): the top hit was the Contract Act's own short-title section, scoring 0.748 on lexical/topical overlap with "Indian Contract Act" alone. **The threshold does not actually gate irrelevant queries on this corpus** — this is a real, currently-open finding, not a metric artifact. Wiring hybrid into `/query` does not change this: the same 5 questions' top hybrid result has a `dense_score` of 0.72–0.81 too (checked directly), so the gate is exactly as ineffective live as it is in the dense-only evaluation — an honest inherited weakness, not a regression introduced by hybrid. **This is not the whole story** — see "Generation evaluation, measured" below for what actually happens to these 5 questions once the LLM sees them.

This is a genuinely harder dataset than the one it replaced: 42 independently-phrased questions (not templated from chunk metadata), spans matched against verbatim source text rather than chunk IDs (so the ground truth survives re-chunking), and the 5 unanswerable cases run through the live retriever end to end rather than skipped.

## Generation evaluation, measured

```
python scripts/run_generation_eval.py
```

Real run, `data/eval_runs/20260909T181825Z/generation_results.json`:

```
Total cases: 42  (in-corpus: 37, unanswerable: 5)
Groundedness rate:            0.9459
Citation faithfulness rate:   0.7714
Unresolved-citation rate:     0.0000
Unanswerable refusal rate:    1.0000
```

What each measures, without an LLM judge:

- **Groundedness (0.9459):** fraction of in-corpus questions where the model produced at least one resolved `[SOURCE_N]` citation, rather than declining or citing nothing.
- **Citation faithfulness (0.7714):** among cases with at least one citation, the fraction where a cited source's text actually contains the dataset's verbatim `expected_answer_span` — the same span-matching logic the retrieval harness uses (`src/evaluation/matching.py`), so a chunk only counts as faithful evidence if it really contains the fact, not just if the model pointed at *some* source.
- **Unresolved-citation rate (0.0000):** zero `[SOURCE_N]` references in this run pointed at a source that wasn't actually in the model's context — no direct hallucinated citations observed. This is a rate, not a guarantee; re-running against more/different questions could surface a nonzero rate.
- **Unanswerable refusal rate (1.0000):** all 5 unanswerable questions were correctly declined.

**This last number resolves the retrieval-layer finding above in the system's favor, and it's the most interesting result in this file.** The retrieval confidence gate never fires on these 5 questions (0/5 — every one retrieves a candidate scoring 0.72–0.81, above the 0.35 threshold). But the *system* still refuses all 5, because the LLM's own grounding instruction ("if sources do NOT contain sufficient information, say so") catches what the retrieval gate misses. Checked directly for one case (an interest-rate-cap question): the model's answer was *"I could not find this information in the provided documents. The sources include the short title and extent of the Indian Contract Act... None of these documents contain any provision, clause, or statement about a maximum interest rate cap on loans."* — it transparently explains what it looked at and why it doesn't answer, rather than silently failing or fabricating. The generation harness's `_looks_like_no_answer()` check correctly recognizes this as a refusal even though the model still emits resolved citations to the (irrelevant) sources it's explaining itself against.

**The honest framing, if asked "does your system hallucinate on questions it can't answer":** no, empirically, on this dataset — the retrieval layer's confidence gate is measurably weak (0/5), but the generation layer's grounding instruction is a real second line of defense that is doing its job (5/5), and I measured both independently rather than assuming the weaker layer's failure would propagate.

## Superseded: the original 22-question harness

The first version of this evaluation (`RetrievalEvaluator`, a 22-question dataset templated from chunk metadata, e.g. `"What does the {section} section state about {heading}?"`) had two real problems, found by auditing it rather than trusting its output:

1. **Data leakage.** Questions were generated from the exact chunk being tested, using that chunk's own section/heading metadata as the question's content. Recall@1 of 0.588 on queries this favorable measured "is this chunk retrievable using its own metadata as a query," not natural-language retrieval quality.
2. **A `no_answer_detection_rate` metric that never exercised the retriever.** It computed `out_of_corpus_count / total_count` — dataset composition, not system behavior — because the evaluator returned early for out-of-corpus cases without calling `retriever.retrieve()` on them. Reading the raw per-question data the dataset builder had already logged (but the evaluator never read) showed all 5 out-of-corpus questions scored 0.62–0.66, above the 0.35 threshold: the real detection rate was 0/5, the opposite of what the reported `0.227` implied.

Both problems are structurally fixed in the current harness: an independently-phrased dataset with span-based ground truth, and unanswerable cases run through the real retriever with the actual `NoRelevantResultsError`/threshold behavior scored directly (see "Unanswerable confidence-gate rate" above — which shows the same underlying issue, a threshold too low for this corpus, is still unresolved; the metric now measures it honestly instead of hiding it).

## Metric definitions

`src/evaluation/metrics.py` implements standard Recall@K, Precision@K, and MRR. A retrieved chunk counts as relevant when it comes from an expected document **and** its text contains one of the expected verbatim answer spans (`src/evaluation/matching.py`) — not a chunk-ID match, so the ground truth doesn't break when chunking logic changes.

MRR is standard: `mean(1/rank_of_first_relevant)` over in-corpus questions, `0` contribution for a miss.

## Test suite: real pass/fail count

```
python -m pytest -q
→ 311 passed, 4 xfailed  (315 total)
```

All four modules that were failing wholesale (`bm25_baseline.py`, `query_analyzer.py`, `reranking.py`, `obligation_extraction.py`) are now fixed and wired — see the fix commit for the specific bugs (a double-tokenization crash in BM25, a non-frozen dataclass and an arbitrary tie-break in query intent detection, a mixed-type crash and a wrong-case enum lookup in obligation/risk extraction). The 4 `xfail`s are documented, intentionally-unresolved limitations rather than papered-over bugs: one structure-detector heading-inheritance inconsistency between two sibling test cases, and three sentences with no grammatical actor that this pattern-based obligation extractor cannot parse by design (`tests/test_obligation_extraction.py`).

## Corpus actually indexed (from `data/documents.json`)

14 documents across 4 categories:

- `acts/` — Indian Contract Act 1872, Bharatiya Nyaya Sanhita 2023 (2 statutes)
- `contracts/` — 5 CUAD-style affiliate agreements (Creditcards.com, Cybergy Holdings, Digital Cinema Destinations, LinkPlus Corp, Southern Star Energy)
- `regulations/` — IT Intermediary Guidelines 2021 (updated 2023)
- `high_court_delhi/` + `supreme_court/` — 6 Indian court judgments

This mix (statute, contract, regulation, case law) is exactly why the structure-detection regex cascade in [02-ingestion.md](02-ingestion.md) has to handle CHAPTER/Article/Schedule *and* ALL-CAPS judgment headings (`FACTS`, `ISSUES`, `JUDGMENT`, `HELD`) in the same pattern set.
