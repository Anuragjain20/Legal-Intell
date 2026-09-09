# Interview Question Bank

Grouped by theme. Each answer is grounded in a specific file/line so you can go deeper if pushed. "Gotcha" questions (marked ⚠️) target this codebase's specific weak spots — expect these if the interviewer has actually opened the repo.

## Architecture and design

**Q: Walk me through what happens when a user asks a question, end to end.**
The Streamlit UI sends `POST /query` to the FastAPI backend. The handler in `src/api/main.py` calls `Retriever.retrieve()`, which embeds the query (BGE + query-instruction prefix), searches Chroma with `top_k=8`, filters to `score >= 0.35`, re-ranks → `GenerationService.answer()` builds context (top 6 sources, 8000-char budget), builds a prompt with a grounding system instruction, calls DeepSeek, then maps `[SOURCE_N]` markers back to trusted retrieval metadata. The response (answer, citations, and a step-by-step trace) travels back over HTTP and Streamlit renders it. See [01](01-architecture.md)–[05](05-generation.md) for the full trace.

**Q: Why is the code split into `ingestion`/`embeddings`/`vectorstore`/`retrieval`/`generation` instead of one pipeline module?**
Each boundary is a `Protocol` (`EmbeddingProvider`, `VectorStore`, `LLMClient`). Swapping the embedding model or vector backend only touches `src/services.py`'s wiring in `build_services()`, not the modules that consume them. I can point at concrete evidence this isn't theoretical: `embeddings/providers.py` already has an unused `LangChainEmbeddingProvider` adapter and `vectorstore/local_store.py` an unused JSON-backed store — both satisfy the same `Protocol`s as the wired implementations. Trade-off I'd own: for a single-developer MVP that may never swap backends, this is more layering than strictly necessary.

**Q: How would this scale beyond a single local Streamlit process?**
I actually did the first step of this, rather than just describing it. The embedding model, vector store, and LLM client now live behind a FastAPI backend (`src/api/main.py`) built once at process startup; Streamlit is a thin HTTP client with zero direct imports from the pipeline. That already gets the model loading once per backend process instead of once per UI worker, and the UI can now be scaled or redeployed independently of the pipeline. What's still true: exactly one API process can run at a time, because Chroma's `PersistentClient` is SQLite-backed and isn't safe for concurrent writers. To go further I'd move Chroma to a client-server deployment (or swap to a hosted vector DB behind the same `VectorStore` protocol — no retrieval/generation code changes needed) and add a queue in front of the DeepSeek call for backpressure.

## Chunking and structure detection

**Q: Why not just use fixed-size chunking with overlap?**
Legal text has real hierarchical structure — section 2(d)(i) is a specific, addressable unit. Fixed-size windows cut across those boundaries arbitrarily, which both hurts retrieval (half a definition doesn't embed well) and breaks citation precision (which section does this fragment even belong to?). My chunker groups by detected heading first and only falls back to size-based splitting for an oversized single paragraph ([chunker.py:93-126](../src/ingestion/chunker.py#L93-L126)).

**Q: How do you tell a numbered list item in a contract apart from a statute section number?**
`accept_numbered_section()` ([structure_patterns.py:373-381](../src/ingestion/structure_patterns.py#L373-L381)) requires the *document* to show other statutory signals (chapters, articles, rules found anywhere in the doc) before accepting a bare `"10. Text"` line as a section heading, unless the line already looks heading-shaped or matched with high confidence. This avoids hardcoding a document-type flag — it infers document type from what other structural signals are already present.

**Q: ⚠️ Your chunker's overlap logic — does it only apply when splitting an oversized paragraph?**
No, and I want to be precise about this rather than repeat the docstring. `_apply_overlap()` ([chunker.py:200-215](../src/ingestion/chunker.py#L200-L215)) prepends the previous chunk's tail to *every* subsequent chunk within a heading group, regardless of whether either chunk came from the oversized-split path. It's a broader behavior than the module docstring suggests. One consequence: the borrowed overlap text keeps the chunk's own page number metadata even though a few characters of it technically came from the prior page's chunk — a minor precision gap in citation metadata I'd tighten if I revisited this.

**Q: What happens with a scanned, image-only PDF?**
No OCR fallback. `PDFExtractor` tags pages with `extraction_status="no_text"`, chunking produces zero chunks, and `POST /ingest` rejects the upload with an explicit 400 rather than silently indexing nothing.

## Embeddings and vector store

**Q: Why BGE, and what's the query-instruction prefix for?**
`BAAI/bge-small-en-v1.5`, local via `sentence-transformers`, no external API cost or latency. BGE was trained asymmetrically — queries and passages are meant to be embedded differently — so `embed_query()` prepends `"Represent this sentence for searching relevant passages: "` before embedding ([providers.py:29,48-51](../src/embeddings/providers.py#L48-L51)); document chunks get no such prefix. Skipping this (or embedding queries the same way as documents) is a common bug with instruction-tuned retrieval embedding models and measurably hurts ranking.

**Q: ⚠️ Is your similarity threshold comparing distances or similarities? Which direction is "more relevant"?**
Similarity — higher is more relevant. Chroma's collection is configured `hnsw:space: "cosine"` ([chroma_store.py:29-32](../src/vectorstore/chroma_store.py#L29-L32)), and my wrapper computes `score = 1 - distance` ([chroma_store.py:74](../src/vectorstore/chroma_store.py#L74)), which recovers cosine similarity from Chroma's cosine-distance output. My threshold check is `score >= threshold`, keeping the most-similar results — correct given that direction. Getting this backwards is the single easiest mistake to make explaining this system, so I checked it explicitly before this conversation rather than assuming.

**Q: What happens if you re-upload the same document? An edited version of it?**
Same bytes → same `document_id` (content-addressed via `sha256`, [service.py:36](../src/ingestion/service.py#L36)) → Chroma upserts by `chunk_id`, so it's a safe no-op. **Edited** bytes → a new `document_id` → an entirely new set of chunks gets added, and the old chunks for the previous version are never removed. `delete_document()` exists on the `VectorStore` protocol and is implemented, but nothing in the upload path calls it. This is a real gap — I'd fix it by looking up existing chunks for a document with matching filename/category before indexing an edit, and deleting the stale ones.

## Retrieval and ranking

**Q: How many chunks does the LLM actually see, and why?**
`Retriever.retrieve()` is called with `top_k=8` from the `/query` handler; after the similarity threshold filter that's ≤8; `ContextBuilder` then caps at 6 sources and an 8000-character total budget ([context_builder.py:15-16](../src/generation/context_builder.py#L15-L16)). The gap between "candidates searched" and "sources actually shown to the model" is deliberate — search wide, then let a character budget and a source cap protect prompt size and cost.

**Q: What's your retrieval approach — dense, sparse, or hybrid?**
Hybrid, and I picked that by measuring, not by default. I built and evaluated all three — dense (BGE embeddings), BM25 (lexical), and hybrid (both, fused with Reciprocal Rank Fusion) — against the same 42-question dataset. Hybrid won on every metric: Recall@5 of 0.7838 versus dense's 0.6486 and BM25's 0.6757. The interesting part is *why*: BM25 alone is badly weak on `comparison`-type questions (Recall@5 0.1667 — no semantic understanding of paraphrase), and hybrid recovers almost all of that gap (0.6667) while keeping BM25's lexical precision gains elsewhere. That's live in `/query` via `HybridQueryRetriever`.

**Q: ⚠️ Did you try a reranker? What happened?**
Yes, and I'd lead with this if asked about reranking, because the result is more interesting than the reranker itself. I built `QueryTermOverlapReranker` and ran it on top of hybrid retrieval through the same evaluation harness — and it made results *worse*: Recall@5 dropped from hybrid's 0.7838 to 0.6216, MRR from 0.58 to 0.41, worse than dense alone. I didn't ship it. The honest engineering story here isn't "I built a reranker" — it's "I built one, measured it, and rejected it on the evidence instead of assuming a reranking stage is automatically an improvement." A cross-encoder (a real learned reranker, not this hand-rolled term-overlap heuristic) is the thing I'd actually try next, since this result doesn't tell you learned reranking wouldn't help — it tells you *this specific heuristic* doesn't.

**Q: ⚠️ What happens if retrieval finds nothing above your threshold?**
`Retriever.retrieve()` raises `NoRelevantResultsError` rather than returning an empty list ([retriever.py:35-36](../src/retrieval/retriever.py#L35-L36)) — I made that deliberate so every caller has to explicitly decide what "nothing relevant" means for them, rather than silently proceeding with an empty context. The `/query` API handler catches it and returns HTTP 200 with `refused: true` — a refusal is a correct product outcome, not an error, and it's exactly the behavior [06-evaluation.md](06-evaluation.md)'s confidence-gate metric measures.

**Q: Do you support filtering by document, category, or date?**
Not yet — `Retriever.retrieve(..., filters=...)` raises `NotImplementedError` the moment a filter dict is passed ([retriever.py:24-25](../src/retrieval/retriever.py#L24-L25)). The metadata is already there on every chunk (`category`, `document_id`, `section`), and Chroma already supports `where=` filtering internally (used by `delete_document`, [chroma_store.py:48](../src/vectorstore/chroma_store.py#L48)) — so this is plumbing work, not a redesign.

## Generation and citations

**Q: How do you prevent the LLM from hallucinating sources?**
This is the answer I'd give even if not asked directly. The model never generates a citation's facts — it only emits a `[SOURCE_N]` marker inline with its answer. A separate `CitationMapper` resolves each `N` against `ContextSource` metadata that was fixed *before* generation ran, during retrieval ([citations.py:42-74](../src/generation/citations.py#L42-L74)). If the model references a source number that was never in its context, that reference is dropped into `unresolved_source_ids`, not promoted to a trusted `Citation`. So a citation's page number and document name shown to the user are structurally guaranteed correct — they were never at the mercy of the model's text generation.

**Q: ⚠️ What if the model cites some real sources and one fake one?**
Currently, that's silently accepted — the fake reference is dropped with no warning surfaced anywhere ([llm_service.py:66-67](../src/generation/llm_service.py#L66-L67), a bare `pass`). Only a *total* citation failure (every single reference unresolved) raises `GenerationFailure`. I'd fix this by surfacing `unresolved_source_ids` to the UI as a visible warning whenever it's non-empty, even alongside valid citations — partial hallucination shouldn't be invisible just because it wasn't total.

**Q: Why `temperature=0.0`?**
Grounded legal Q&A is a task where creativity is a liability — I want the most deterministic, literal-to-source phrasing I can get, not creative variation between runs on the same question.

## Evaluation — expect the most scrutiny here

**Q: What are your retrieval metrics, and how were they measured?**
Recall@1/3/5, Precision@5, and MRR, computed by `src/evaluation/harness.py` against a 42-question dataset (37 in-corpus, 5 unanswerable), run separately for all four retrieval configurations (`python scripts/run_evaluation.py --method {dense,bm25,hybrid,hybrid_rerank}`). The one that's live is hybrid: Recall@1 0.4459, Recall@5 0.7838, MRR 0.5797 — beats dense-only (Recall@5 0.6486) and BM25-only (0.6757) on every metric. See [06-evaluation.md](06-evaluation.md) for the full comparison table and per-question-type breakdown.

**Q: ⚠️ How were your evaluation questions generated — are they realistic?**
Yes, deliberately more so than an earlier version of this eval. The dataset's 42 questions are independently phrased, not templated from chunk metadata, and ground truth is a verbatim answer span matched against retrieved chunk text (not a chunk ID), so it survives re-chunking. An earlier 22-question version of this harness templated questions directly from the chunk being tested (`"What does the {section} section state about {heading}?"`) — that was data leakage, and I rebuilt the dataset rather than keep reporting numbers from it. See [06-evaluation.md](06-evaluation.md#superseded-the-original-22-question-harness) for exactly what was wrong with it and why the fix isn't just cosmetic.

**Q: ⚠️ Does your system correctly refuse to answer questions it has no evidence for?**
Split answer, and I'd give both halves. At the retrieval layer, no — this is a real, measured weakness. All 5 unanswerable questions in the dataset retrieve a top result scoring 0.72–0.81, above the 0.35 similarity threshold, for both dense and the hybrid path I actually ship, so the confidence gate's measured rate is 0/5. I checked one directly against Chroma: a question about an interest-rate cap that doesn't exist in the corpus retrieved the Contract Act's own short-title section at 0.748, purely on lexical/topical overlap with "Indian Contract Act." But at the system level, yes — I built a second eval that runs the full pipeline including the real LLM call, and all 5 of those same questions were correctly refused, because the model's own grounding instruction catches what the retrieval gate misses (see the next question). I wouldn't stop at the retrieval-layer finding without checking whether it actually breaks the product; it doesn't, here, but I only know that because I measured it rather than assumed it.

**Q: What does your eval cover, and what's still missing?**
Both retrieval and generation now, and I'd be specific about what "generation eval" means here. `src/evaluation/generation_harness.py` runs the full pipeline (real LLM call included) and measures three things without an LLM judge: groundedness (did the model cite something — 94.6%), citation faithfulness (does a cited source actually contain the expected fact, using the same verbatim-span matching as retrieval eval — 77.1%), and unresolved-citation rate (references to sources that weren't in context — 0.0%). What it doesn't cover: whether the answer's *prose* is a faithful, complete paraphrase of the cited fact — that would need an LLM judge, which I deliberately didn't add, since a judge model's own reliability becomes a new thing to validate. That's the honest next layer, not a gap I'd pretend doesn't exist.

**Q: How many tests do you have, and do they all pass?**
311 passing, 4 xfailed, out of 315. Every xfail is a documented, deliberate limitation, not a hidden failure: one structure-detector heading-inheritance inconsistency between two sibling test cases, and three sentences my pattern-based obligation extractor can't parse because they have no grammatical actor for its actor+verb+action model to find.

**Q: ⚠️ Does your judgment-heading detection (FACTS/ISSUES/JUDGMENT/HELD) actually work on your real corpus?**
Partially, and I checked rather than assumed. Querying the actual indexed metadata in Chroma, section-tagging rates across my three Delhi High Court judgments are uneven: 21/36 and 22/29 chunks sectioned in two of them, but the third comes back **0/7 — every chunk has `section=None`.** So the patterns exist and clearly work on some judgment PDFs, but at least one document's extracted text doesn't trigger them at all, likely due to how that specific PDF's headings extracted (spacing, casing, or line-break artifacts from `pypdf`). I'd call this a partially-working feature with an open investigation, not a solved problem — and I'd rather say that than have someone else find the 0/7 first.

## Trade-offs and "what would you change"

**Q: If you had another week, what's first?**
In order: (1) wire up metadata filtering, since the data model already supports it and both retrievers just reject it; (2) handle document re-upload/edit cleanup via the already-implemented but unused `delete_document`; (3) understand *why* the term-overlap reranker hurt hybrid results before trying a learned cross-encoder reranker in its place — a negative result deserves a diagnosis, not just a different tool; (4) an LLM-judge layer on top of the current generation eval, since my faithfulness check only verifies a cited source *contains* the right fact, not that the answer text is a faithful, complete paraphrase of it.

**Q: What was the hardest part to get right?**
The hierarchical identifier composition in structure detection — specifically that `"2(a)" + "(d)"` must produce `"2(d)"` (a sibling replacing a sibling), not `"2(a)(d)"` (which would read as nesting that doesn't exist). Getting the parent/child vs. parent/sibling distinction right (`_compose_identifier()`, [structure_detector.py:45-71](../src/ingestion/structure_detector.py#L45-L71)) was the trickiest invariant in the whole ingestion pipeline, and it's exactly the kind of bug that would silently corrupt citations without ever throwing an error.
