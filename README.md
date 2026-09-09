# Legal RAG

A local retrieval-augmented generation system for legal PDFs — statutes, contracts, and court judgments. It detects legal document structure, chunks along real section and clause boundaries instead of fixed-size windows, embeds and indexes everything locally, retrieves with a hybrid dense + BM25 pipeline chosen by measurement rather than default, and generates grounded answers whose citations are verified against retrieval metadata instead of trusted from the model's output.

## Features

- **Structure-aware ingestion** — PDF text extraction with legal-structure detection for chapters, sections, lettered sub-sections, nested clauses, and case-law headings (`FACTS`, `ISSUES`, `HELD`)
- **Structure-first chunking** — groups content by detected structure, falling back to size-based splitting only for oversized paragraphs
- **Local embeddings** — `BAAI/bge-small-en-v1.5` via `sentence-transformers`, persisted in a local Chroma vector store
- **Measured hybrid retrieval** — dense + BM25 fused with Reciprocal Rank Fusion, selected as the live retrieval path after being benchmarked against three alternatives (see [Evaluation](#evaluation))
- **Grounded generation** — DeepSeek-backed answers with citations resolved against retrieval metadata, never trusted from raw model output
- **Reproducible evaluation harnesses** — a retrieval harness comparing four retrieval configurations against a 42-question, span-grounded evaluation set, and a generation-faithfulness harness measuring groundedness, citation faithfulness, and refusal correctness

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
| Dense only | 0.405 | 0.595 | 0.649 | 0.521 |
| BM25 only | 0.419 | 0.649 | 0.676 | 0.537 |
| **Hybrid (dense + BM25, RRF)** | **0.446** | **0.730** | **0.784** | **0.580** |
| Hybrid + reranker | 0.297 | 0.473 | 0.622 | 0.414 |

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
```

### Run retrieval evaluation

```bash
python scripts/run_evaluation.py --method dense
python scripts/run_evaluation.py --method bm25
python scripts/run_evaluation.py --method hybrid
python scripts/run_evaluation.py --method hybrid_rerank
```

Each run writes a manifest and full results to `data/eval_runs/<timestamp>/results.json`.

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
  app.py                 Streamlit UI — thin HTTP client, no src/ imports
  src/
    api/main.py          FastAPI backend: /health, /ingest, /query
    services.py          Composition root — build_services() wires everything
    config/              Environment-driven settings
    ingestion/           PDF -> pages -> structure detection -> chunks
    embeddings/          Chunk/query text -> vectors
    vectorstore/         Chroma persistence + similarity search
    retrieval/           dense, BM25, hybrid (RRF), reranking, hybrid_query_retriever (live path)
    generation/           Context building, prompting, DeepSeek call, citations
    evaluation/           Metrics, span matching, retrieval + generation eval harnesses
  scripts/
    ingest.py               Corpus ingestion CLI
    run_evaluation.py       Retrieval evaluation CLI (--method dense|bm25|hybrid|hybrid_rerank)
    run_generation_eval.py  Generation-faithfulness eval CLI
    validate_dataset.py     Verifies the eval dataset's spans against the live index
  tests/                  Automated tests, one file per src/ module roughly
  data/
    documents/            Uploaded/ingested source PDFs
    chroma/                Persistent vector index
    evaluation_dataset.json    Evaluation question set
    eval_runs/              One directory per evaluation run, with manifest + results
```

## License

Distributed under the [MIT License](LICENSE).
