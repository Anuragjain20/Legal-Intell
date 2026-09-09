# Legal RAG — Documentation Index

This folder documents the actual, as-implemented system in `legal-rag/`, for two purposes:

1. Understand the project end to end (architecture, data flow, design decisions).
2. Prepare to defend it in a RAG-focused interview — what's built, what's fake/aspirational in the repo's other markdown files, what's missing, and how to answer follow-up questions.

**Ground rule used throughout this doc set:** every claim is backed by `file.py:line`, a test, or a command you can re-run. This `doc/` folder is the only place in the repo that states what was actually measured, with the command used to measure it — an earlier set of root-level markdown files made aspirational or outright fabricated claims (including a benchmark table that was never produced by any script) and has been removed; see [09-retractions.md](09-retractions.md).

## 60-second pitch

A local FastAPI backend, with a thin Streamlit UI over it, that turns legal PDFs (statutes, contracts, judgments) into a retrieval-augmented Q&A system:

`PDF → text extraction → legal-structure-aware chunking → local embeddings → Chroma vector store → cosine-similarity retrieval + hand-rolled re-rank → context assembly → DeepSeek LLM → citation verification against retrieved metadata`

The one deliberate design bet worth leading with in an interview: **citations are never trusted from the LLM's text.** The model is asked to emit `[SOURCE_N]` markers; a separate `CitationMapper` (`src/generation/citations.py`) resolves each marker against the *retrieval* metadata, not the model's claims. See [05-generation.md](05-generation.md).

## Files in this set

| File | Covers |
|---|---|
| [01-architecture.md](01-architecture.md) | End-to-end system map: ingest-time path vs. query-time path, module boundaries, why they're split this way |
| [02-ingestion.md](02-ingestion.md) | PDF extraction → structure detection (regex cascade) → legal-aware chunking. The most bespoke part of the codebase |
| [03-embeddings-vectorstore.md](03-embeddings-vectorstore.md) | Embedding provider abstraction, BGE model, Chroma vs. local JSON store, score semantics |
| [04-retrieval.md](04-retrieval.md) | Query embedding → similarity search → threshold filter → hand-rolled re-rank. Exact funnel numbers |
| [05-generation.md](05-generation.md) | Context building, prompt construction, DeepSeek call, citation verification as the trust boundary |
| [06-evaluation.md](06-evaluation.md) | What the eval harness actually measures, real numbers from this repo, a genuine bug in it, and what it doesn't measure |
| [07-interview-narrative.md](07-interview-narrative.md) | A rehearsable story: what I built, why, trade-offs, what I'd do next |
| [08-question-bank.md](08-question-bank.md) | Likely interview questions with grounded answers (file/line citations), including "gotcha" questions about this specific codebase's weak spots |
| [09-retractions.md](09-retractions.md) | What was fabricated in an earlier version of this repo, and why it was removed rather than quietly fixed |

## How to re-verify anything in this doc set yourself

```bash
# Run the real test suite (254 pass / 59 fail / 1 xfail as of this writing — see 06 for why)
python -m pytest -q

# Re-ingest the corpus from source PDFs into a fresh Chroma collection
python scripts/ingest.py --source <path to source PDFs>

# Re-run retrieval evaluation against the current index
python scripts/run_evaluation.py
cat data/eval_runs/<latest timestamp>/results.json

# Start the app: API first (owns the pipeline), then the UI (needs
# DEEPSEEK_API_KEY in .env on the API side for the generation step)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
streamlit run app.py
```

## Repo orientation

```
legal-rag/
  app.py                     Streamlit UI - thin HTTP client, zero src/ imports
  src/
    api/main.py               FastAPI backend: /health, /ingest, /query
    services.py                Composition root - build_services() wires everything
    config/settings.py       Env-driven Settings dataclass
    ingestion/                PDF → pages → structure → chunks
    embeddings/                Chunk/query text → vectors
    vectorstore/                Vector persistence + similarity search
    retrieval/                  Query → ranked results
    generation/                  Context + prompt + LLM call + citations
    evaluation/                  Retrieval-only eval harness (metrics.py, matching.py, harness.py)
  scripts/
    ingest.py                  Corpus ingestion CLI
    run_evaluation.py          Retrieval evaluation CLI, writes data/eval_runs/<timestamp>/
    validate_dataset.py        Verifies eval dataset spans still match the live index
  tests/                      314 tests, one per src/ module roughly
  data/
    documents.json            Upload registry
    chroma/                    Persistent Chroma collection (the real index)
    evaluation_dataset.json    Independently-phrased, span-grounded eval questions (see 06)
    eval_runs/<timestamp>/     Each evaluation run's manifest + results, one directory per run
```
