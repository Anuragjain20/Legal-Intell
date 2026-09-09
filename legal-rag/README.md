# Legal RAG

A local retrieval-augmented generation system over legal PDFs — statutes, contracts, and court judgments. It extracts text, detects legal document structure (sections, sub-sections, clauses, chapters), chunks along those boundaries, embeds locally, indexes in Chroma, retrieves with a hybrid dense+BM25 pipeline (chosen by measuring it against three alternatives, not by default), and generates grounded answers with citations that are verified against retrieval metadata rather than trusted from the LLM's output.

**For an honest account of what's actually implemented, tested, and measured — including known gaps and a documented retraction of an earlier fabricated benchmark — see [`doc/README.md`](doc/README.md).** That folder is the source of truth for this project's real state.

## What it does

- PDF text extraction, with legal-structure-aware detection of chapters, sections, lettered sub-sections, nested clauses, and case-law headings (`FACTS`, `ISSUES`, `HELD`)
- Chunking that groups by detected structure first, falling back to size-based splitting only for oversized paragraphs
- Local embeddings (`BAAI/bge-small-en-v1.5` via `sentence-transformers`), persisted in Chroma
- Hybrid retrieval (dense + BM25, Reciprocal Rank Fusion) — measured at Recall@5=0.78 versus dense-only's 0.65 and BM25-only's 0.68 on a 42-question evaluation set; a reranker was also built, measured, and rejected because it made results worse
- Grounded generation via DeepSeek, with citations resolved against retrieval metadata — never trusted from model output
- A reproducible retrieval evaluation harness comparing all four retrieval configurations, with an independently-phrased, span-grounded question set and versioned results per run
- A generation-faithfulness evaluation harness with real measured results: 94.6% groundedness, 77.1% citation faithfulness, 0% unresolved citations, and 100% correct refusal on unanswerable questions — even though the retrieval-layer confidence gate alone measures 0/5 on those same questions (see `doc/06-evaluation.md`)

## What it doesn't do (yet)

No OCR for scanned PDFs, no auth, no metadata filtering at the retrieval layer, no LLM-judge scoring of answer prose quality (the generation eval checks citation faithfulness, not paraphrase quality).

## Architecture

FastAPI (`src/api/main.py`) is the real backend — it owns the embedding model, vector store, and LLM client, built once at startup. Streamlit (`app.py`) is a thin HTTP client with no direct pipeline imports; it calls the API over HTTP. Run exactly one API process at a time: Chroma's SQLite-backed store isn't safe for concurrent writers.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your `DEEPSEEK_API_KEY`.

## Run

Start the API, then the UI, in two terminals:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
streamlit run app.py
```

## Ingest documents

```bash
python scripts/ingest.py --source /path/to/category-organized/pdfs
```

## Run evaluation

```bash
python scripts/run_evaluation.py --method dense
python scripts/run_evaluation.py --method bm25
python scripts/run_evaluation.py --method hybrid
python scripts/run_evaluation.py --method hybrid_rerank
```

Writes a manifest and full results to `data/eval_runs/<timestamp>/results.json` per run. See [`doc/06-evaluation.md`](doc/06-evaluation.md) for the current real numbers, the comparison table, and what they mean.

## Run generation evaluation

```bash
python scripts/run_generation_eval.py
```

Runs the full pipeline (real LLM call included) and needs a funded `DEEPSEEK_API_KEY`. Writes `data/eval_runs/<timestamp>/generation_results.json`.

## Layout

```
app.py                 Streamlit UI - thin HTTP client, no src/ imports
src/
  api/main.py          FastAPI backend: /health, /ingest, /query
  services.py          Composition root - build_services() wires everything
  config/              Environment-driven settings
  ingestion/           PDF -> pages -> structure detection -> chunks
  embeddings/          Chunk/query text -> vectors
  vectorstore/         Chroma persistence + similarity search
  retrieval/           dense, BM25, hybrid (RRF), reranking, hybrid_query_retriever (live path)
  generation/          Context building, prompting, DeepSeek call, citations
  evaluation/          Metrics, span matching, retrieval + generation eval harnesses
scripts/
  ingest.py               Corpus ingestion CLI
  run_evaluation.py       Retrieval evaluation CLI (--method dense|bm25|hybrid|hybrid_rerank)
  run_generation_eval.py  Generation-faithfulness eval CLI
  validate_dataset.py     Verifies the eval dataset's spans against the live index
tests/                 Automated tests, one file per src/ module roughly
data/
  documents/           Uploaded/ingested source PDFs
  chroma/              Persistent vector index
  evaluation_dataset.json   Evaluation question set
  eval_runs/           One directory per evaluation run, with manifest + results
doc/                   Detailed, verified documentation — start at doc/README.md
```
