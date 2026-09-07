# Embeddings and Vector Store

## Embedding provider abstraction

`EmbeddingProvider` ([embeddings/base.py:21-35](../src/embeddings/base.py#L21-L35)) is a `Protocol` — structural typing, no inheritance required. Any object with `embed_documents`, `embed_query`, and `embedding_dimension` satisfies it. Two implementations exist in `providers.py`, but **only one is wired into `app.py`**:

### Wired: `LocalHuggingFaceEmbeddingProvider` ([providers.py:19-55](../src/embeddings/providers.py#L19-L55))

- Model: `BAAI/bge-small-en-v1.5` (default, configurable via `EMBEDDING_MODEL` env var — see [settings.py:17](../src/config/settings.py#L17)), loaded via `sentence-transformers`.
- **Dimension: 384** (verified by loading the model directly, not assumed from documentation — `get_sentence_embedding_dimension()`, exposed via `embedding_dimension` property).
- Runs **locally, in-process** — no external embedding API call, no per-call cost or latency to a remote service. This is a deliberate MVP trade-off: free and simple, but the model lives in the Streamlit worker's memory (`@st.cache_resource` keeps one instance per worker process — see [01-architecture.md](01-architecture.md) on scaling).
- **Query/document asymmetry:** `embed_query()` prepends `"Represent this sentence for searching relevant passages: "` before embedding ([providers.py:29](../src/embeddings/providers.py#L29), used at [providers.py:48-51](../src/embeddings/providers.py#L48-L51)). This is BGE's documented convention — the model was trained so that queries and passages occupy the embedding space differently, and this instruction string is what tells it "this text is a query, not a passage." Document chunks are embedded via `embed_documents()` with no such prefix. **Getting this backwards (or forgetting it) is a common bug with BGE models** — worth stating unprompted if asked about embedding model choice.
- **Normalization:** `normalize_embeddings=True` ([providers.py:45](../src/embeddings/providers.py#L45)) — vectors are unit-length, which is what makes cosine similarity and dot product equivalent and is required for Chroma's `hnsw:space: "cosine"` index to behave as expected.

### Present but unused in the wired app: `LangChainEmbeddingProvider` ([providers.py:58-118](../src/embeddings/providers.py#L58-L118))

A generic adapter around any LangChain embeddings object (`backend.embed_documents`/`embed_query`), plus a `build_langchain_provider()` factory supporting `"huggingface"` and `"openai"` backend names. This exists to make a future swap to a hosted embedding API a config change, not a rewrite — `app.py`'s wiring is the only place that would need to change. It's untested against a live OpenAI/HF call in this repo; treat it as scaffolding, not a proven path.

### `EmbeddingService` — the batch layer ([service.py:12-56](../src/embeddings/service.py#L12-L56))

Thin wrapper that: extracts `.text` from a list of `Chunk`s, calls `provider.embed_documents()` once for the batch, validates the returned vector count matches the chunk count (`strict=True` zip, [service.py:29](../src/embeddings/service.py#L29)), and validates each vector's dimension against `provider.embedding_dimension` before wrapping it as an `EmbeddedChunk`. This is where a provider bug (wrong dimension, mismatched batch size) surfaces immediately with a clear `ValueError` rather than propagating into the vector store as a silent corruption.

## Vector store abstraction

`VectorStore` ([vectorstore/base.py:42-62](../src/vectorstore/base.py#L42-L62)) is another `Protocol`: `add`, `delete_document`, `get_by_chunk_id`, `list_document_ids`, `search`. Two implementations:

### Wired: `ChromaVectorStore` ([chroma_store.py:14-113](../src/vectorstore/chroma_store.py#L14-L113))

- Persistent local Chroma via `chromadb.PersistentClient(path=storage_dir)` ([chroma_store.py:28](../src/vectorstore/chroma_store.py#L28)), collection `"legal_rag"`, `metadata={"hnsw:space": "cosine"}` ([chroma_store.py:29-32](../src/vectorstore/chroma_store.py#L29-L32)) — explicitly configures the HNSW index to use cosine distance rather than Chroma's default (squared L2).
- **`add()` is an upsert by `chunk_id`** ([chroma_store.py:34-45](../src/vectorstore/chroma_store.py#L34-L45)) via `collection.upsert()` — re-indexing the same chunk (same `chunk_id`, same content) overwrites in place rather than duplicating. This is what makes re-uploading an unchanged PDF idempotent (see [02-ingestion.md](02-ingestion.md) for the caveat about *edited* PDFs getting a new `document_id` and orphaning old chunks).
- **Score = `1 - distance`** ([chroma_store.py:74](../src/vectorstore/chroma_store.py#L74)). Because the collection is configured for cosine space and embeddings are normalized, Chroma's returned "distance" is cosine distance (`1 - cosine_similarity`), so `1 - distance` recovers cosine similarity directly, in `[-1, 1]` in theory, `[0, 1]` in practice for this model's output. **This is the number the `similarity_threshold` in `Retriever` is compared against — a cosine similarity, not a raw distance.** Getting this backwards (thinking higher = further, like a raw distance) is the single most common way to misread this codebase's scoring.
- `_metadata()`/`_record()` ([chroma_store.py:84-113](../src/vectorstore/chroma_store.py#L84-L113)) handle the round-trip between the dataclass `VectorRecord` and Chroma's flat string-keyed metadata dict, including the awkward `None → ""` coercion Chroma's metadata schema forces (`section or ""`), reversed back to `None` on read (`metadata["section"] or None`).

### Present but unused in the wired app: `LocalVectorStore` ([local_store.py:14-103](../src/vectorstore/local_store.py#L14-L103))

A dependency-free JSON-file-backed store: all records held in a `dict[str, VectorRecord]` in memory, persisted to `index.json` on every `add`/`delete`, cosine similarity computed by hand (`_cosine_similarity`, [local_store.py:73-79](../src/vectorstore/local_store.py#L73-L79)) and brute-force scored against every record on every search (`search()`, [local_store.py:52-59](../src/vectorstore/local_store.py#L52-L59) — `O(n)` per query, no ANN index). This exists as a zero-dependency fallback/testing double for `ChromaVectorStore` — same `Protocol`, same score semantics (cosine similarity, not distance) — useful to mention as evidence the abstraction is real, not just a single-implementation wrapper pretending to be pluggable.

## Score semantics, stated once clearly

Both stores return a **similarity** score, higher = more relevant, roughly bounded to `[0, 1]` given normalized BGE embeddings. `Retriever.similarity_threshold` (default `0.35`, from `SIMILARITY_THRESHOLD` env var, [settings.py:18](../src/config/settings.py#L18)) is a **minimum cosine similarity to keep**, not a distance cutoff. See [04-retrieval.md](04-retrieval.md) for how this threshold interacts with `top_k`.
