# Architecture

## Two processes, one wiring point

FastAPI (`src/api/main.py`) is the real backend — it owns the embedding model, vector store, and LLM client as process-lifetime singletons, built once in a `lifespan` handler. Streamlit (`app.py`) is a thin HTTP client with zero `src/` imports: it calls `/health`, `/ingest`, and `/query` over HTTP and renders the JSON it gets back. This split exists because `ChromaVectorStore` opens a SQLite-backed `PersistentClient` on `data/chroma/`, which is not safe for two processes to write to concurrently — so exactly one process may hold the pipeline at a time, and that process is the API.

Everything wires together in `build_services()` in [src/services.py](../src/services.py) — the composition root, the only place that knows every concrete class. Every other `src/` package exposes only interfaces (Python `Protocol`s or plain dataclasses) to its neighbors. Both `src/api/main.py` and the CLI scripts (`scripts/ingest.py`, `scripts/run_evaluation.py`) call this same function rather than constructing services themselves.

```
Settings.from_env()
  → LocalHuggingFaceEmbeddingProvider(model_name)
  → EmbeddingService(provider)
  → ChromaVectorStore(storage_dir, dimension=embedding_service.embedding_dimension())
  → DenseRetriever + BM25Retriever(chunks=vector_store.get_all()) → HybridRetriever
  → DocumentUploadService, VectorIndexService, HybridQueryRetriever, GenerationService
```

Note `dimension=embedding_service.embedding_dimension()` — the vector store doesn't hardcode 384, it asks the embedding provider at construction time. Swap the model, the store adapts automatically (though existing persisted vectors of the old dimension would then fail `_validate_vector`).

### Path 1 — Ingestion (index-time)

```
PDF bytes
  → DocumentValidator            (type/size/encryption checks)      src/ingestion/validator.py
  → DocumentStorage.save()       (content-hash filename, category folder)  src/ingestion/storage.py
  → PDFExtractor.extract()       (page-level text via pypdf)        src/ingestion/pdf_extractor.py
  → LegalChunker.chunk()         (structure detection + packing)    src/ingestion/chunker.py
  → EmbeddingService.embed_chunks()                                 src/embeddings/service.py
  → VectorIndexService.index_embeddings()  (upsert into Chroma)     src/vectorstore/service.py
```

Driven by `DocumentUploadService.upload()` ([service.py:31-57](../src/ingestion/service.py#L31-L57)), called from the API's `POST /ingest` handler ([src/api/main.py](../src/api/main.py)) for single-file upload via the UI, or from `scripts/ingest.py` for bulk corpus ingestion (drops and rebuilds the Chroma collection first).

### Path 2 — Query (request-time)

```
question: str
  → HybridQueryRetriever.retrieve()                                 src/retrieval/hybrid_query_retriever.py
      HybridRetriever.retrieve_hybrid()                              src/retrieval/hybrid_retrieval.py
        DenseRetriever.retrieve_dense(top_k*2)  ──┐
        BM25Retriever.retrieve_bm25(top_k*2)    ──┴→ Reciprocal Rank Fusion
      → threshold filter on dense_score (not the RRF score - see below)
  → GenerationService.answer()                                      src/generation/llm_service.py
      ContextBuilder.build()  → PromptBuilder.build() → LLMService.generate() (DeepSeek) → CitationMapper.map()
```

Driven by the API's `POST /query` handler, which also builds a `trace` dict describing each pipeline stage and returns it in the response body — the trace structure documents each stage's expected shape better than any docstring does. Streamlit stores that trace as-is and renders it; it never recomputes anything the API already decided. A refusal (`NoRelevantResultsError`, no candidate cleared the confidence threshold) is a **200 response with `refused: true`**, not an error status — it's a correct product outcome, and the whole evaluation story in [06-evaluation.md](06-evaluation.md) is about how often that gate actually fires.

**Retrieval is hybrid (dense + BM25, RRF-fused), not dense-only, and that's a measured choice, not a default.** `scripts/run_evaluation.py --method {dense,bm25,hybrid,hybrid_rerank}` ran all four configurations against the same 42-question dataset; hybrid won on every metric (Recall@5 0.7838 vs dense's 0.6486), and a hand-rolled reranker on top of hybrid was measured and *rejected* — it dropped Recall@5 to 0.6216. See [06-evaluation.md](06-evaluation.md) for the full comparison table. Because RRF's fused score (`1/(k+rank)` summed across two rankings, ~0.01–0.03 scale) isn't a cosine similarity, `HybridQueryRetriever` gates confidence on each result's `dense_score` field instead — the same similarity dense-only retrieval already produces, carried through the fusion untouched, so the existing `SIMILARITY_THRESHOLD` still means the same thing.

## Module boundaries and why they exist

| Package | Owns | Deliberately does not know about |
|---|---|---|
| `ingestion` | PDF → `Chunk` objects with structural metadata | embeddings, vector storage, the LLM |
| `embeddings` | `Chunk`/text → `list[float]`, via a `Protocol` (`EmbeddingProvider`) | which vector store the vectors end up in |
| `vectorstore` | Persistence + nearest-neighbor search, via a `Protocol` (`VectorStore`) | how vectors were produced, ranking policy |
| `retrieval` | Turning a query into ranked `RetrievalResult`s — dense, BM25, hybrid (RRF), and reranking, all measured against each other | prompt format, citation format, the LLM |
| `generation` | Context assembly, prompting, calling the LLM, mapping citations | how retrieval scored things internally |
| `evaluation` | Retrieval quality across all four methods, plus a generation-faithfulness harness with real measured results (see [06](06-evaluation.md)) | — |

This is standard hexagonal/ports-and-adapters styling applied to a RAG pipeline: `EmbeddingProvider` and `VectorStore` are `Protocol`s ([embeddings/base.py:21-35](../src/embeddings/base.py#L21-L35), [vectorstore/base.py:42-62](../src/vectorstore/base.py#L42-L62)), so a production swap (OpenAI embeddings, pgvector, a hosted Chroma) touches only `app.py`'s wiring, not `retrieval/` or `generation/`.

**Trade-off worth naming in an interview:** this is more layering than a single-developer MVP strictly needs. It pays off if you expect to swap the embedding model or vector backend (which the repo's README explicitly plans for — LangChain adapters for OpenAI/HF embeddings already exist in `embeddings/providers.py`, unused by the wired app). If that swap never happens, it's just extra indirection. Own that trade-off rather than pretending it was free.

## Data model spine

`Chunk` ([ingestion/models.py:32-56](../src/ingestion/models.py#L32-L56)) is the unit that flows through the whole system, gaining fields as it moves:

```
Chunk (ingestion)
  → EmbeddedChunk (embeddings/base.py)      adds: embedding vector, model name/version
  → VectorRecord (vectorstore/base.py)      the persisted form (drops embedding-service-only fields)
  → SearchResult (vectorstore/base.py)      VectorRecord + similarity score
  → RetrievalResult (retrieval/models.py)   SearchResult + rank (post re-rank)
  → ContextSource (generation/models.py)    RetrievalResult flattened for prompt rendering
  → Citation (generation/citations.py)      ContextSource, but only for sources the LLM actually cited
```

Every one of these is a frozen dataclass. No mutation, no hidden state — a result object built at step N is safe to hand to step N+2 without re-validating it. This matters for the citation trust boundary discussed in [05-generation.md](05-generation.md): `Citation` objects are built strictly from `ContextSource` (retrieval-derived) fields, never from parsing the LLM's answer text for facts.

## What's explicitly not built

Grep-verified absences, useful to state proactively rather than get caught by:

- **Metadata filters** — `HybridQueryRetriever.retrieve(..., filters=...)` raises `NotImplementedError` the moment `filters` is truthy.
- **BM25 incremental updates** — `BM25Retriever`'s inverted index is a one-shot build from a snapshot of Chroma's contents; `POST /ingest` rebuilds it after every upload (`Services.rebuild_bm25_index()`), which is fine at 2848 chunks but wouldn't scale to frequent uploads against a much larger corpus without a real incremental index.
- **Query rewriting / HyDE / multi-query** — the query string goes straight to `embed_query`/BM25 tokenization, unmodified.
- **Cross-encoder reranking** — a hand-rolled `QueryTermOverlapReranker` exists and was measured on top of hybrid retrieval, but it made results worse (Recall@5 0.7838 → 0.6216) and isn't wired into `/query`. See [06-evaluation.md](06-evaluation.md).
- **OCR** — scanned PDFs produce empty-text pages; `DocumentUploadService` raises rather than falling back to OCR.
- **LLM-judge-based generation evaluation** — `scripts/run_generation_eval.py` measures groundedness, citation faithfulness, and unresolved-citation rate without a judge model (see [06-evaluation.md](06-evaluation.md)); it does not score answer fluency, completeness, or anything requiring a second LLM to assess.
- **Auth / multi-tenancy** — the API has no auth layer and Chroma's SQLite backend means exactly one API process may run at a time; there's no user separation.
- **Horizontal scaling of the API itself** — the FastAPI backend is a single process holding one embedding model and one Chroma client. It can now be scaled independently of the UI (that was the point of the split), but scaling *it* past one process would need Chroma moved to a client-server deployment or swapped for a hosted vector DB behind the same `VectorStore` protocol, plus a queue in front of the DeepSeek call for backpressure — neither exists yet.
