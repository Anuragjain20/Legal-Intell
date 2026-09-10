# Legal RAG

A local retrieval-augmented generation system for legal PDFs — statutes, contracts, and court judgments. It detects legal document structure, chunks along real section and clause boundaries instead of fixed-size windows, embeds and indexes everything locally, retrieves with a hybrid dense + BM25 pipeline chosen by measurement rather than default, and generates grounded answers whose citations are verified against retrieval metadata instead of trusted from the model's output.

## Features

- **Structure-aware ingestion** — PDF text extraction with legal-structure detection for chapters, sections, lettered sub-sections, nested clauses, and case-law headings (`FACTS`, `ISSUES`, `HELD`)
- **Three pluggable chunking strategies** — structure-first (default), a recursive character splitter with overlap, and an LLM-proposed semantic chunker, each held in its own vector index so they can be ingested, queried, and evaluated independently (see [Evaluation](#evaluation))
- **Local embeddings** — `BAAI/bge-small-en-v1.5` via `sentence-transformers`, persisted in a local Chroma vector store
- **Measured hybrid retrieval** — dense + BM25 fused with Reciprocal Rank Fusion, selected as the live retrieval path after being benchmarked against three alternatives (see [Evaluation](#evaluation))
- **Grounded generation** — DeepSeek-backed answers with citations resolved against retrieval metadata, never trusted from raw model output
- **Reproducible evaluation harnesses** — a retrieval harness comparing four retrieval configurations and three chunking strategies against a 42-question, span-grounded evaluation set, and a generation-faithfulness harness measuring groundedness, citation faithfulness, and refusal correctness
- **In-UI evaluation runner** — trigger a retrieval evaluation run from the Streamlit Evaluate tab and compare results across past runs without touching the CLI

## Architecture

FastAPI (`src/api/main.py`) is the backend of record — it owns the embedding model, vector store, and LLM client, all built once at startup. Streamlit (`app.py`) is a thin HTTP client with no direct pipeline imports; it talks to the API exclusively over HTTP. Run exactly one API process at a time — Chroma's SQLite-backed store is not safe for concurrent writers.

```
PDF → text extraction → structure detection → structure-first chunking
    → local embeddings → Chroma → hybrid (dense + BM25, RRF) retrieval
    → context assembly → DeepSeek → citation verification → answer
```

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| UI | Streamlit |
| Embeddings | `sentence-transformers` (`BAAI/bge-small-en-v1.5`) |
| Vector store | Chroma |
| Retrieval | Dense similarity search, BM25, Reciprocal Rank Fusion |
| Generation | DeepSeek (`deepseek-chat`) |
| Testing | `pytest` |

## Evaluation

All numbers below come from committed run artifacts in `data/eval_runs/`, reproducible with the commands in [Getting started](#getting-started). Each run scores 42 questions (37 answerable against the indexed corpus, 5 intentionally unanswerable) at `top_k = 5`.

### Retrieval comparison

Four retrieval configurations were benchmarked head-to-head before picking a default. Hybrid (dense + BM25 with Reciprocal Rank Fusion) won on every ranking metric; adding a reranking stage on top of hybrid made results worse, so it was rejected rather than shipped.

| Method | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| Dense only | 0.378 | 0.554 | 0.608 | 0.521 |
| BM25 only | 0.419 | 0.635 | 0.649 | 0.537 |
| **Hybrid (dense + BM25, RRF)** | **0.446** | **0.622** | **0.703** | **0.591** |
| Hybrid + reranker | 0.284 | 0.446 | 0.554 | 0.415 |

*Numbers corrected 2026-09-10 — see the chunking table's note below for what changed and why. The conclusion is unchanged: hybrid wins, reranking loses.*

### Chunking strategy comparison

Three chunking strategies were compared with retrieval held constant at hybrid, each ingested into its own vector index over the same 14-document corpus (the original, evaluation-dataset-matched subset of the now-32-document corpus): the default structure-aware `LegalChunker`, a hand-rolled recursive character splitter (1200 chars, 150-char overlap), and an LLM-proposed semantic chunker (DeepSeek proposes chunk boundaries as short anchor strings; the chunker locates each anchor in the original extracted text and always slices the original string — the model never returns chunk text itself, so it cannot fabricate or reword source content).

| Chunking method | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | Mean chunk chars | Span-findability |
|---|---|---|---|---|---|---|---|
| `legal` (structure-aware, default) | 0.4459 | 0.6216 | 0.7027 | 0.1622 | 0.5910 | 349 | 37/37 |
| `recursive` (character splitter, overlap) | 0.5495 | 0.6757 | 0.7568 | 0.1892 | 0.6878 | 1123 | 36/37 |
| **`llm_semantic` (LLM-proposed boundaries)** | 0.5541 | **0.7703** | **0.7973** | 0.1784 | **0.7027** | 498 | 37/37 |

**Both tables above were corrected on 2026-09-10** after finding a real bug in the evaluation harness: `Recall@K`'s denominator only ever counted relevant chunks that were actually retrieved, so a question with 2 true relevant chunks where only 1 was retrieved scored as 100% recall instead of the correct 50%. This silently inflated recall on every multi-span question (worst for `comparison`-type questions, which are multi-span by design), for every method measured, before this date. It's fixed in `src/evaluation/harness.py` (scored against the full relevant-chunk universe, not just retrieved chunks) with a regression test, and every run above was re-executed against the fix — these are not adjusted or estimated numbers, they're fresh runs. **The ranking is unchanged in both tables** (hybrid still beats the other three retrieval methods; `llm_semantic` still leads Recall@3/5 and MRR among chunking strategies), but margins are smaller than originally published, and `recursive`/`llm_semantic` are now a near-tie on Recall@1 (0.5495 vs 0.5541) rather than `llm_semantic` leading on every metric.

Mean chunk length is reported because comparing chunkers at a fixed `top_k` can otherwise conflate "better retrieval" with "bigger chunks, so more content per retrieved slot." `llm_semantic` still leads Recall@3/5 and MRR despite having the second-*smallest* mean chunk size of the three, so that lead isn't explained by chunk size alone; `recursive`'s clearest win (Precision@5) is exactly what a size-based explanation would predict from having the largest chunks. Span-findability — how many of the 37 answerable evaluation spans are recoverable intact from at least one chunk under that chunker — is reported alongside recall to separate "retrieval missed it" from "the chunk boundary split the answer in two"; `recursive` is the only one of the three to lose a point here (one ground-truth span split across a chunk boundary).

`llm_semantic` was built from 13 of the 14 source documents — one contract exceeded the chunker's 5% skip-anchor budget (a bounded safety threshold: an individual unlocatable LLM-proposed boundary is dropped rather than aborting the whole document, but a document is rejected outright if too many of its boundaries can't be found in the source text) and was excluded rather than force-chunked on a mostly-fallback boundary set. None of the 42 evaluation questions reference that document, so its absence doesn't bias the numbers above.

Pick a chunking method with `--chunking-method {legal,recursive,llm_semantic}` on `scripts/ingest.py` and `scripts/run_evaluation.py`, or from the Streamlit Ingest/Evaluate tabs — each method is held in its own Chroma index, so switching never touches another method's data.

### Generation faithfulness

Measured on the live pipeline (hybrid retrieval → DeepSeek generation → citation verification), with a real LLM call for every question:

| Metric | Result |
|---|---|
| Groundedness rate | 91.9% |
| Citation faithfulness rate | 79.4% |
| Unresolved citation rate | 0.0% |
| Unanswerable-question refusal rate | 100% |

Citations are never trusted from the model's text — a separate verification step resolves every `[SOURCE_N]` marker the model emits against the metadata attached to the retrieved chunks, not against the model's own claims.

## Getting started

All commands below run from the `legal-rag/` directory.

### Installation

```bash
cd legal-rag
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your `DEEPSEEK_API_KEY`.

### Run

Start the API, then the UI, in two terminals:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
streamlit run app.py
```

### Ingest documents

```bash
python scripts/ingest.py --source /path/to/category-organized/pdfs
python scripts/ingest.py --source data/documents_source --chunking-method recursive
python scripts/ingest.py --source data/documents_source --chunking-method llm_semantic
```

`--chunking-method` defaults to `legal`; each method is ingested into its own Chroma directory (`data/chroma`, `data/chroma_recursive`, `data/chroma_llm_semantic`), so re-ingesting under one method never touches another's index. The same picker is available from the Streamlit Ingest tab.

### Run retrieval evaluation

```bash
python scripts/run_evaluation.py --method dense
python scripts/run_evaluation.py --method bm25
python scripts/run_evaluation.py --method hybrid
python scripts/run_evaluation.py --method hybrid_rerank
python scripts/run_evaluation.py --method hybrid --chunking-method recursive
python scripts/run_evaluation.py --method hybrid --chunking-method llm_semantic
```

Each run writes a manifest and full results to `data/eval_runs/<timestamp>/results.json`. The same runs can be triggered from the Streamlit Evaluate tab, which submits the run as a background job and polls it to completion, and lists past runs for comparison.

### Run generation evaluation

```bash
python scripts/run_generation_eval.py
```

Runs the full pipeline, including a real LLM call, and needs a funded `DEEPSEEK_API_KEY`. Writes `data/eval_runs/<timestamp>/generation_results.json`.

### Run tests

```bash
python -m pytest -q
```

## Project layout

```
legal-rag/
  app.py                 Streamlit UI (Ingest / Query / Evaluate tabs) — thin HTTP client, no src/ imports
  src/
    api/main.py          FastAPI backend: /health, /ingest, /query, /evaluate
    services.py          Composition root — build_services() wires everything per chunking method
    config/              Environment-driven settings
    ingestion/           PDF -> pages -> structure detection -> chunks (legal / recursive / llm_semantic)
    embeddings/          Chunk/query text -> vectors
    vectorstore/         Chroma persistence + similarity search
    retrieval/           dense, BM25, hybrid (RRF), reranking, hybrid_query_retriever (live path)
    generation/           Context building, prompting, DeepSeek call, citations
    evaluation/           Metrics, span matching, retrieval + generation eval harnesses, shared runner
  scripts/
    ingest.py               Corpus ingestion CLI (--chunking-method legal|recursive|llm_semantic)
    run_evaluation.py       Retrieval evaluation CLI (--method, --chunking-method)
    run_generation_eval.py  Generation-faithfulness eval CLI
    validate_dataset.py     Verifies the eval dataset's spans against a given chunking method's index
  tests/                  Automated tests, one file per src/ module roughly
  data/
    documents_source/     Committed source corpus (32 documents, category-organized; see SOURCES.md for provenance)
    documents/            Uploaded/ingested source PDFs (generated, gitignored)
    chroma/                Persistent vector index for the default chunking method (generated, gitignored)
    evaluation_dataset.json    Evaluation question set
    eval_runs/              One directory per evaluation run, with manifest + results
```

## License

Distributed under the [MIT License](LICENSE).
