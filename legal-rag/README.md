# Legal RAG

This repository is a small local retrieval-augmented generation application for legal PDFs.

The goal of this phase is to establish clean boundaries before any RAG logic is added. The app currently ships as a basic Streamlit shell with separate packages reserved for ingestion, retrieval, generation, embeddings, vector store, and configuration concerns.

## What the project does

Right now, the project provides:

- A Streamlit entry point in `app.py`
- A source layout that separates future responsibilities
- Dedicated folders for uploaded documents and processed artifacts
- A lightweight foundation for tests and configuration

It extracts text from PDFs, chunks and embeds it locally, stores vectors in persistent Chroma,
retrieves relevant passages, and uses DeepSeek for grounded answers with source citations.

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your `DEEPSEEK_API_KEY` before asking questions.

## Run

Start the application with:

```bash
streamlit run app.py
```

## Current architecture

The structure is intentionally simple:

- `app.py` - Streamlit application entry point
- `src/ingestion/` - PDF validation, extraction, and legal-aware chunking
- `src/retrieval/` - embedding search and ranking
- `src/generation/` - prompt construction, DeepSeek generation, and citations
- `src/embeddings/` - local Hugging Face embedding provider
- `src/vectorstore/` - Chroma persistence behind a small interface
- `src/config/` - environment settings
- `tests/` - automated tests
- `data/documents/` - raw uploaded documents
- `data/processed/` - processed artifacts such as chunks or indexes

## Current implementation status

The MVP deliberately does not include authentication, OCR for scanned PDFs, metadata filters,
or agent workflows such as LangGraph.

## Embedding strategy

The embedding layer is designed around a provider interface so the rest of the app does not depend on one model or API.

- Local/default option: a Hugging Face `sentence-transformers` model, currently `BAAI/bge-small-en-v1.5`
- Server-side options: LangChain adapters can wrap providers such as Hugging Face, OpenAI, or other supported backends

This keeps chunking, embedding, vector storage, and retrieval separate while still allowing model swaps later without rewriting ingestion logic.

## Vector store strategy

For the MVP, the project uses persistent local Chroma behind a `VectorStore` abstraction.
The same interface can later support a hosted Chroma instance, pgvector, or another backend.

Duplicate indexing is handled as an upsert by `chunk_id`, so reprocessing the same document updates existing records instead of silently creating duplicates.

## Notes

The current design keeps application concerns separated so the codebase can grow without turning `app.py` into a monolith.
