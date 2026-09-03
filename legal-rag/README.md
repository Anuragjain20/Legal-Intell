# Legal RAG

This repository is the skeleton for a legal retrieval-augmented generation application.

The goal of this phase is to establish clean boundaries before any RAG logic is added. The app currently ships as a basic Streamlit shell with separate packages reserved for ingestion, retrieval, generation, embeddings, vector store, and configuration concerns.

## What the project does

Right now, the project provides:

- A Streamlit entry point in `app.py`
- A source layout that separates future responsibilities
- Dedicated folders for uploaded documents and processed artifacts
- A lightweight foundation for tests and configuration

It does not yet process documents, generate embeddings, query a vector store, or call an LLM.

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If you want to configure environment variables, copy `.env.example` to `.env` and fill in the values later.

## Run

Start the application with:

```bash
streamlit run app.py
```

## Current architecture

The structure is intentionally simple:

- `app.py` - Streamlit application entry point
- `src/ingestion/` - future document ingestion and preprocessing
- `src/retrieval/` - future search and ranking logic
- `src/generation/` - future response generation orchestration
- `src/embeddings/` - future embedding helpers
- `src/vectorstore/` - future vector store integration
- `src/config/` - future configuration and environment handling
- `tests/` - automated tests
- `data/documents/` - raw uploaded documents
- `data/processed/` - processed artifacts such as chunks or indexes

## Current implementation status

Implemented:

- Project scaffold and package boundaries
- Streamlit shell
- Dependency list
- Placeholder environment file

Not implemented yet:

- Document ingestion
- Embeddings
- Vector search
- RAG orchestration
- LangGraph
- Authentication or RBAC
- Database infrastructure

## Notes

The current design keeps application concerns separated so the codebase can grow without turning `app.py` into a monolith.
