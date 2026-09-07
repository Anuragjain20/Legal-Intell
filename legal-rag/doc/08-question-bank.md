# Interview Question Bank

Grouped by theme. Each answer is grounded in a specific file/line so you can go deeper if pushed. "Gotcha" questions (marked ⚠️) target this codebase's specific weak spots — expect these if the interviewer has actually opened the repo.

## Architecture and design

**Q: Walk me through what happens when a user asks a question, end to end.**
`app.answer_question()` ([app.py:389](../app.py#L389)) → `Retriever.retrieve()` embeds the query (BGE + query-instruction prefix), searches Chroma with `top_k=8`, filters to `score >= 0.35`, re-ranks → `GenerationService.answer()` builds context (top 6 sources, 8000-char budget), builds a prompt with a grounding system instruction, calls DeepSeek, then maps `[SOURCE_N]` markers back to trusted retrieval metadata. See [01](01-architecture.md)–[05](05-generation.md) for the full trace.

**Q: Why is the code split into `ingestion`/`embeddings`/`vectorstore`/`retrieval`/`generation` instead of one pipeline module?**
Each boundary is a `Protocol` (`EmbeddingProvider`, `VectorStore`, `LLMClient`). Swapping the embedding model or vector backend only touches `app.py`'s wiring in `build_services()`, not the modules that consume them. I can point at concrete evidence this isn't theoretical: `embeddings/providers.py` already has an unused `LangChainEmbeddingProvider` adapter and `vectorstore/local_store.py` an unused JSON-backed store — both satisfy the same `Protocol`s as the wired implementations. Trade-off I'd own: for a single-developer MVP that may never swap backends, this is more layering than strictly necessary.

**Q: How would this scale beyond a single local Streamlit process?**
Honestly — not well as-is. `@st.cache_resource` ([app.py:35](../app.py#L35)) holds one embedding model and one Chroma client per worker process, in-memory. To scale I'd pull embedding + retrieval behind a stateless service (so the model loads once, not per worker), move Chroma to a client-server deployment (or swap to a hosted vector DB behind the same `VectorStore` protocol — no retrieval/generation code changes needed), and add a queue in front of the LLM call for backpressure.

## Chunking and structure detection

**Q: Why not just use fixed-size chunking with overlap?**
Legal text has real hierarchical structure — section 2(d)(i) is a specific, addressable unit. Fixed-size windows cut across those boundaries arbitrarily, which both hurts retrieval (half a definition doesn't embed well) and breaks citation precision (which section does this fragment even belong to?). My chunker groups by detected heading first and only falls back to size-based splitting for an oversized single paragraph ([chunker.py:93-126](../src/ingestion/chunker.py#L93-L126)).

**Q: How do you tell a numbered list item in a contract apart from a statute section number?**
`accept_numbered_section()` ([structure_patterns.py:373-381](../src/ingestion/structure_patterns.py#L373-L381)) requires the *document* to show other statutory signals (chapters, articles, rules found anywhere in the doc) before accepting a bare `"10. Text"` line as a section heading, unless the line already looks heading-shaped or matched with high confidence. This avoids hardcoding a document-type flag — it infers document type from what other structural signals are already present.

**Q: ⚠️ Your chunker's overlap logic — does it only apply when splitting an oversized paragraph?**
No, and I want to be precise about this rather than repeat the docstring. `_apply_overlap()` ([chunker.py:200-215](../src/ingestion/chunker.py#L200-L215)) prepends the previous chunk's tail to *every* subsequent chunk within a heading group, regardless of whether either chunk came from the oversized-split path. It's a broader behavior than the module docstring suggests. One consequence: the borrowed overlap text keeps the chunk's own page number metadata even though a few characters of it technically came from the prior page's chunk — a minor precision gap in citation metadata I'd tighten if I revisited this.

**Q: What happens with a scanned, image-only PDF?**
No OCR fallback. `PDFExtractor` tags pages with `extraction_status="no_text"`, chunking produces zero chunks, and the upload is rejected with an explicit message rather than silently indexing nothing ([app.py:84-85](../app.py#L84-L85)).

## Embeddings and vector store

**Q: Why BGE, and what's the query-instruction prefix for?**
`BAAI/bge-small-en-v1.5`, local via `sentence-transformers`, no external API cost or latency. BGE was trained asymmetrically — queries and passages are meant to be embedded differently — so `embed_query()` prepends `"Represent this sentence for searching relevant passages: "` before embedding ([providers.py:29,48-51](../src/embeddings/providers.py#L48-L51)); document chunks get no such prefix. Skipping this (or embedding queries the same way as documents) is a common bug with instruction-tuned retrieval embedding models and measurably hurts ranking.

**Q: ⚠️ Is your similarity threshold comparing distances or similarities? Which direction is "more relevant"?**
Similarity — higher is more relevant. Chroma's collection is configured `hnsw:space: "cosine"` ([chroma_store.py:29-32](../src/vectorstore/chroma_store.py#L29-L32)), and my wrapper computes `score = 1 - distance` ([chroma_store.py:74](../src/vectorstore/chroma_store.py#L74)), which recovers cosine similarity from Chroma's cosine-distance output. My threshold check is `score >= threshold`, keeping the most-similar results — correct given that direction. Getting this backwards is the single easiest mistake to make explaining this system, so I checked it explicitly before this conversation rather than assuming.

**Q: What happens if you re-upload the same document? An edited version of it?**
Same bytes → same `document_id` (content-addressed via `sha256`, [service.py:36](../src/ingestion/service.py#L36)) → Chroma upserts by `chunk_id`, so it's a safe no-op. **Edited** bytes → a new `document_id` → an entirely new set of chunks gets added, and the old chunks for the previous version are never removed. `delete_document()` exists on the `VectorStore` protocol and is implemented, but nothing in the upload path calls it. This is a real gap — I'd fix it by looking up existing chunks for a document with matching filename/category before indexing an edit, and deleting the stale ones.

## Retrieval and ranking

**Q: How many chunks does the LLM actually see, and why?**
`Retriever.retrieve()` is called with `top_k=8` ([app.py:403](../app.py#L403)); after the similarity threshold filter that's ≤8; `ContextBuilder` then caps at 6 sources and an 8000-character total budget ([context_builder.py:15-16](../src/generation/context_builder.py#L15-L16)). The gap between "candidates searched" and "sources actually shown to the model" is deliberate — search wide, then let a character budget and a source cap protect prompt size and cost.

**Q: What's your re-ranking approach, and why not a cross-encoder?**
A hand-rolled tuple sort ([retriever.py:39-64](../src/retrieval/retriever.py#L39-L64)): frontmatter priority for purpose/intent-style questions, then similarity, then keyword overlap, then a specificity tiebreak. Not a learned reranker. I chose this for an MVP over a small, fixed corpus — it's free, deterministic, unit-testable, and encodes one specific domain insight (statute purpose lives in preambles) that pure similarity search might miss if the preamble's wording doesn't lexically match the question. The honest trade-off: it doesn't generalize past the patterns it was written for. A cross-encoder reranker is the first thing I'd add if this needed to handle more diverse query styles.

**Q: ⚠️ What happens if retrieval finds nothing above your threshold?**
`Retriever.retrieve()` raises `NoRelevantResultsError` rather than returning an empty list ([retriever.py:35-36](../src/retrieval/retriever.py#L35-L36)) — I made that deliberate so every caller has to explicitly decide what "nothing relevant" means for them, rather than silently proceeding with an empty context. `app.py` catches it alongside `RetrievalError`/`GenerationError`/`ValueError` and surfaces the message directly ([app.py:455-460](../app.py#L455-L460)).

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
Recall@1/3/5, Precision@5, and MRR, computed by `src/evaluation/harness.py` against a 42-question dataset (37 in-corpus, 5 unanswerable). Real last-run numbers: Recall@1 0.4054, Recall@3 0.5946, Recall@5 0.6486, MRR 0.5212 — traced to `data/eval_runs/20260907T072408Z/results.json`, reproducible via `python scripts/run_evaluation.py`. See [06-evaluation.md](06-evaluation.md) for the full per-question-type breakdown.

**Q: ⚠️ How were your evaluation questions generated — are they realistic?**
Yes, deliberately more so than an earlier version of this eval. The dataset's 42 questions are independently phrased, not templated from chunk metadata, and ground truth is a verbatim answer span matched against retrieved chunk text (not a chunk ID), so it survives re-chunking. An earlier 22-question version of this harness templated questions directly from the chunk being tested (`"What does the {section} section state about {heading}?"`) — that was data leakage, and I rebuilt the dataset rather than keep reporting numbers from it. See [06-evaluation.md](06-evaluation.md#superseded-the-original-22-question-harness) for exactly what was wrong with it and why the fix isn't just cosmetic.

**Q: ⚠️ Does your system correctly refuse to answer questions it has no evidence for?**
No, and this is the most important open finding in the current results, not a hidden one. All 5 unanswerable questions in the dataset retrieved a top result scoring 0.72–0.81 — above the 0.35 similarity threshold — so the confidence gate's real measured rate is 0/5. I checked one directly against Chroma: a question about an interest-rate cap that doesn't exist in the corpus retrieved the Contract Act's own short-title section at 0.748, purely on lexical/topical overlap with "Indian Contract Act." The threshold is too low to gate irrelevant queries on a corpus where every document shares generic legal vocabulary. Fixes worth naming: raise and empirically tune the threshold against labeled negatives like these five, or add a second-stage check (keyword/entity overlap, or an LLM groundedness judge) before treating a retrieved chunk as sufficient.

**Q: What does your eval *not* cover?**
Generation quality entirely — nothing checks whether the LLM's answer text is faithful to the cited sources, whether it hallucinates beyond what's cited, or answer completeness. It's a retrieval-only harness by design (correctly scoped for what it is), but I'd flag that gap myself before being asked, since "did you evaluate the LLM's output" is the natural next question.

**Q: How many tests do you have, and do they all pass?**
254 passing, 59 failing, 1 xfailed, out of 314. The 59 failures are concentrated in four modules — `bm25_baseline.py`, `query_analyzer.py`, `reranking.py`, `obligation_extraction.py` — that exist in the codebase but aren't wired into the live retrieval path; I'd rather say that plainly than have it discovered. The xfail is a documented, intentionally-unresolved inconsistency between two structure-detector test cases' heading-inheritance expectations (`tests/test_structure_detector.py`) — marking it honestly rather than forcing a heuristic fix that would have broken the passing sibling test.

**Q: ⚠️ Does your judgment-heading detection (FACTS/ISSUES/JUDGMENT/HELD) actually work on your real corpus?**
Partially, and I checked rather than assumed. Querying the actual indexed metadata in Chroma, section-tagging rates across my three Delhi High Court judgments are uneven: 21/36 and 22/29 chunks sectioned in two of them, but the third comes back **0/7 — every chunk has `section=None`.** So the patterns exist and clearly work on some judgment PDFs, but at least one document's extracted text doesn't trigger them at all, likely due to how that specific PDF's headings extracted (spacing, casing, or line-break artifacts from `pypdf`). I'd call this a partially-working feature with an open investigation, not a solved problem — and I'd rather say that than have someone else find the 0/7 first.

## Trade-offs and "what would you change"

**Q: If you had another week, what's first?**
In order: (1) fix `no_answer_detection_rate` to actually exercise the retriever, since it's currently measuring nothing behavioral; (2) build a generation-quality eval — faithfulness/citation-precision checks, since none exists; (3) wire up metadata filtering, since the data model already supports it and `Retriever` just rejects it; (4) handle document re-upload/edit cleanup via the already-implemented but unused `delete_document`; (5) a cross-encoder reranker to replace the hand-rolled heuristic for queries outside the "purpose question" pattern it was tuned for.

**Q: What was the hardest part to get right?**
The hierarchical identifier composition in structure detection — specifically that `"2(a)" + "(d)"` must produce `"2(d)"` (a sibling replacing a sibling), not `"2(a)(d)"` (which would read as nesting that doesn't exist). Getting the parent/child vs. parent/sibling distinction right (`_compose_identifier()`, [structure_detector.py:45-71](../src/ingestion/structure_detector.py#L45-L71)) was the trickiest invariant in the whole ingestion pipeline, and it's exactly the kind of bug that would silently corrupt citations without ever throwing an error.
