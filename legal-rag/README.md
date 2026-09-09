# Legal RAG

A local retrieval-augmented generation system over legal PDFs — statutes, contracts, and court judgments. It extracts text, detects legal document structure (sections, sub-sections, clauses, chapters), chunks along those boundaries, embeds locally, indexes in Chroma, retrieves by cosine similarity, and generates grounded answers with citations that are verified against retrieval metadata rather than trusted from the LLM's output.

**For an honest account of what's actually implemented, tested, and measured — including known gaps and a documented retraction of an earlier fabricated benchmark — see [`doc/README.md`](doc/README.md).** That folder is the source of truth for this project's real state.

## What it does

- PDF text extraction, with legal-structure-aware detection of chapters, sections, lettered sub-sections, nested clauses, and case-law headings (`FACTS`, `ISSUES`, `HELD`)
- Chunking that groups by detected structure first, falling back to size-based splitting only for oversized paragraphs
- Local embeddings (`BAAI/bge-small-en-v1.5` via `sentence-transformers`), persisted in Chroma
- Dense retrieval with a similarity threshold and a hand-rolled re-ranker
- Grounded generation via DeepSeek, with citations resolved against retrieval metadata — never trusted from model output
- A reproducible retrieval evaluation harness: an independently-phrased, span-grounded question set, run via a CLI script, with versioned results written per run

## What it doesn't do (yet)

No OCR for scanned PDFs, no auth, no metadata filtering at the retrieval layer, no generation/faithfulness evaluation. BM25, query analysis, and reranking modules exist in `src/` but are not wired into the live retrieval path — see `doc/01-architecture.md`.

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
python scripts/run_evaluation.py
```

Writes a manifest and full results to `data/eval_runs/<timestamp>/results.json`. See [`doc/06-evaluation.md`](doc/06-evaluation.md) for the current real numbers and what they mean.

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
  retrieval/           Query -> ranked results
  generation/          Context building, prompting, DeepSeek call, citations
  evaluation/          Metrics, span matching, evaluation harness
scripts/
  ingest.py            Corpus ingestion CLI
  run_evaluation.py    Retrieval evaluation CLI
  validate_dataset.py  Verifies the eval dataset's spans against the live index
tests/                 Automated tests, one file per src/ module roughly
data/
  documents/           Uploaded/ingested source PDFs
  chroma/              Persistent vector index
  evaluation_dataset.json   Evaluation question set
  eval_runs/           One directory per evaluation run, with manifest + results
doc/                   Detailed, verified documentation — start at doc/README.md
```
