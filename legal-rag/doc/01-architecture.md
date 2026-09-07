# Architecture

## Two paths, one wiring point

Everything wires together in `build_services()` in [app.py:35-63](../app.py#L35-L63), a `@st.cache_resource`-decorated function that runs once per Streamlit process. This is the composition root — the only place that knows every concrete class. Every `src/` package exposes only interfaces (Python `Protocol`s or plain dataclasses) to its neighbors.

```
Settings.from_env()
  → LocalHuggingFaceEmbeddingProvider(model_name)
  → EmbeddingService(provider)
  → ChromaVectorStore(storage_dir, dimension=embedding_service.embedding_dimension())
  → DocumentUploadService, VectorIndexService, Retriever, GenerationService
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

Driven by `DocumentUploadService.upload()` ([service.py:31-57](../src/ingestion/service.py#L31-L57)), called from `app.py`'s `index_document()` ([app.py:76-87](../app.py#L76-L87)) for both single-file upload and folder-batch indexing.

### Path 2 — Query (request-time)

```
question: str
  → Retriever.retrieve()                                            src/retrieval/retriever.py
      embed_query → vector_store.search(top_k=8) → threshold filter → hand-rolled re-rank
  → GenerationService.answer()                                      src/generation/llm_service.py
      ContextBuilder.build()  → PromptBuilder.build() → LLMService.generate() (DeepSeek) → CitationMapper.map()
```

Driven by `answer_question()` in [app.py:389-464](../app.py#L389-L464), which also builds a `trace_data` dict for the UI's debug panels — a nice side effect: the trace structure documents each stage's expected shape better than any docstring does.

## Module boundaries and why they exist

| Package | Owns | Deliberately does not know about |
|---|---|---|
| `ingestion` | PDF → `Chunk` objects with structural metadata | embeddings, vector storage, the LLM |
| `embeddings` | `Chunk`/text → `list[float]`, via a `Protocol` (`EmbeddingProvider`) | which vector store the vectors end up in |
| `vectorstore` | Persistence + nearest-neighbor search, via a `Protocol` (`VectorStore`) | how vectors were produced, ranking policy |
| `retrieval` | Turning a query into ranked `RetrievalResult`s | prompt format, citation format, the LLM |
| `generation` | Context assembly, prompting, calling the LLM, mapping citations | how retrieval scored things internally |
| `evaluation` | Measuring retrieval quality only | generation quality (there is no generation eval — see [06](06-evaluation.md)) |

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

- **Metadata filters** — `Retriever.retrieve(..., filters=None)` raises `NotImplementedError` the moment `filters` is truthy ([retriever.py:24-25](../src/retrieval/retriever.py#L24-L25)).
- **Hybrid search / BM25** — pure dense vector search, no keyword/sparse component.
- **Query rewriting / HyDE / multi-query** — the query string goes straight to `embed_query`.
- **Cross-encoder reranking** — re-ranking is a hand-rolled tuple sort (frontmatter priority, similarity, term overlap, specificity), not a learned reranker. See [04-retrieval.md](04-retrieval.md).
- **OCR** — scanned PDFs produce empty-text pages; `DocumentUploadService` raises rather than falling back to OCR ([app.py:84-85](../app.py#L84-L85)).
- **Auth / multi-tenancy** — single local Streamlit process, no user separation.
- **Horizontal scaling** — `@st.cache_resource` holds one embedding model and one Chroma client in-process per Streamlit worker; there's no shared service layer.
