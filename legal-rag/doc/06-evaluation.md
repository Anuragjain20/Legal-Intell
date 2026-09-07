# Evaluation — What's Actually Measured

**This file was rewritten after the dataset and harness described in "Superseded" below were replaced.** If you see `Recall@1: 0.76` or similar numbers anywhere else in this repo (old root-level markdown, deleted in the cleanup — see [09-retractions.md](09-retractions.md)), those were either illustrative sample output or fabricated. The numbers in this file are traced to a committed JSON file and a script you can re-run.

## What the harness measures: retrieval only

`src/evaluation/harness.py` evaluates **retrieval quality only** — whether the right chunk shows up in the top-K search results. It does not evaluate the LLM's answer text, citation accuracy, factual correctness, or anything downstream of retrieval. **There is no generation/answer-quality eval in this repo.** If asked "how do you evaluate RAG," the honest answer is "I built the retrieval half; the generation half — answer faithfulness, citation precision, no-hallucination checks — is the documented next step."

## Real, measured numbers (from `data/eval_runs/20260907T072408Z/results.json`)

```
python scripts/ingest.py --source <path to the 14 source PDFs>
python scripts/run_evaluation.py
```

```
Total cases:      42   (37 in-corpus, 5 unanswerable)
Recall@1:         0.4054
Recall@3:         0.5946
Recall@5:         0.6486
Precision@5:      0.1405
MRR:              0.5212
```

By question type:

| Type | Count | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|
| comparison | 6 | — | — | 0.50 | 0.4167 |
| direct_factual | 10 | — | — | 0.60 | 0.475 |
| multi_section | 5 | — | — | 0.80 | 0.70 |
| obligation_risk | 8 | — | — | 0.50 | 0.3167 |
| section_clause | 8 | — | — | 0.875 | 0.75 |

**Unanswerable confidence-gate rate: 0.0000.** All 5 unanswerable questions retrieved a top result scoring 0.72–0.81 — well above the 0.35 similarity threshold — so the retriever's confidence gate never correctly withheld an answer on any of them. Spot-checked directly against Chroma for one case (a question about an interest-rate cap not present in the corpus): the top hit was the Contract Act's own short-title section, scoring 0.748 on lexical/topical overlap with "Indian Contract Act" alone. **The threshold does not actually gate irrelevant queries on this corpus** — this is a real, currently-open finding, not a metric artifact.

This is a genuinely harder dataset than the one it replaced: 42 independently-phrased questions (not templated from chunk metadata), spans matched against verbatim source text rather than chunk IDs (so the ground truth survives re-chunking), and the 5 unanswerable cases run through the live retriever end to end rather than skipped.

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
→ 254 passed, 59 failed, 1 xfailed  (314 total)
```

The 59 failures are concentrated in `bm25_baseline.py`, `query_analyzer.py`, `reranking.py`, and `obligation_extraction.py` — modules that exist in the codebase but are not wired into the live retrieval path yet (see [01-architecture.md](01-architecture.md) for what's actually connected). The 1 `xfail` is a documented, intentionally-unresolved inconsistency in the structure-detector's heading-inheritance rules between two sibling test cases (`tests/test_structure_detector.py`) — marked rather than papered over with a heuristic that would have broken the passing sibling test.

## Corpus actually indexed (from `data/documents.json`)

14 documents across 4 categories:

- `acts/` — Indian Contract Act 1872, Bharatiya Nyaya Sanhita 2023 (2 statutes)
- `contracts/` — 5 CUAD-style affiliate agreements (Creditcards.com, Cybergy Holdings, Digital Cinema Destinations, LinkPlus Corp, Southern Star Energy)
- `regulations/` — IT Intermediary Guidelines 2021 (updated 2023)
- `high_court_delhi/` + `supreme_court/` — 6 Indian court judgments

This mix (statute, contract, regulation, case law) is exactly why the structure-detection regex cascade in [02-ingestion.md](02-ingestion.md) has to handle CHAPTER/Article/Schedule *and* ALL-CAPS judgment headings (`FACTS`, `ISSUES`, `JUDGMENT`, `HELD`) in the same pattern set.
