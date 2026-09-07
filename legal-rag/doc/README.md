# Legal RAG — Documentation Index

This folder documents the actual, as-implemented system in `legal-rag/`, for two purposes:

1. Understand the project end to end (architecture, data flow, design decisions).
2. Prepare to defend it in a RAG-focused interview — what's built, what's fake/aspirational in the repo's other markdown files, what's missing, and how to answer follow-up questions.

**Ground rule used throughout this doc set:** every claim is backed by `file.py:line`, a test, or a command you can re-run. The repository root already contains ~13 markdown files (`START_HERE.md`, `EVALUATION.md`, etc.) written in an aspirational, marketing-ish voice — one of them prints `Recall@1: 0.76` as a *sample* output, not a measured result. **Treat those as untrusted.** This `doc/` folder is the only place in the repo that states what was actually measured, with the command used to measure it.

## 60-second pitch

A local, single-process Streamlit app that turns legal PDFs (statutes, contracts, judgments) into a retrieval-augmented Q&A system:

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

## How to re-verify anything in this doc set yourself

```bash
# Run the real test suite (107 pass / 4 fail as of this writing — see 06 for why)
python -m pytest -q

# See the real, measured retrieval numbers (not the ones in START_HERE.md)
cat data/evaluation_results.json

# Regenerate the eval dataset from whatever is currently indexed in Chroma
python build_valid_evaluation_dataset.py

# Re-run evaluation against the current index
python run_evaluation_real.py

# Start the app (needs DEEPSEEK_API_KEY in .env for the generation step)
streamlit run app.py
```

## Repo orientation

```
legal-rag/
  app.py                     Streamlit UI + service wiring (composition root)
  src/
    config/settings.py       Env-driven Settings dataclass
    ingestion/                PDF → pages → structure → chunks
    embeddings/                Chunk/query text → vectors
    vectorstore/                Vector persistence + similarity search
    retrieval/                  Query → ranked results
    generation/                  Context + prompt + LLM call + citations
    evaluation/                  Retrieval-only eval harness
  tests/                      111 tests, one per src/ module roughly
  data/
    documents.json            Upload registry
    chroma/                    Persistent Chroma collection (the real index)
    evaluation_dataset.json    Template-generated eval questions (see 06)
    evaluation_results.json    Last real run's output
```
