# Interview Narrative — A Story You Can Actually Tell

A rehearsable walkthrough. Each section is meant to be said out loud in under a minute; the file/line citations are there so you can go deeper the instant someone asks "show me."

## The 30-second version

"I built a local RAG system over legal documents — statutes, contracts, and court judgments. The interesting problem wasn't wiring an LLM to a vector store, it was that legal text has real structure — sections, sub-sections, clauses — and naive fixed-size chunking destroys that structure and makes citations unreliable. So most of the engineering effort went into a deterministic structure detector that parses that hierarchy before chunking, and into making sure every citation the system shows a user is provably correct rather than trusted from the model's output."

## The 3-minute version, in five beats

**1. The chunking problem, and why it's not generic.**
A statute has nested identifiers like `2(d)(i)` — subsection `d` under section `2`, clause `i` under that. A fixed-size sliding window will cut a definition clause in half. I wrote a regex-cascade structure detector (`structure_patterns.py`, ~15 pattern matchers tried in precedence order, [02-ingestion.md](02-ingestion.md)) that recognizes chapters, articles, lettered subsections, nested clauses, frontmatter (preambles/recitals), and even ALL-CAPS judgment headings like `HELD`/`ISSUES` for case law — because my corpus includes Delhi High Court and Supreme Court judgments, not just statutes. Chunking then groups by detected heading first, and only falls back to sentence- or size-based splitting when a single paragraph is too large on its own.

**2. Retrieval, and being precise about what "similarity" means.**
Local BGE embeddings (384-dim, `sentence-transformers`), stored in a persistent Chroma collection configured for cosine space. I can tell you exactly why `score = 1 - distance` in my Chroma wrapper — because with normalized embeddings and a cosine-space index, that recovers cosine similarity from Chroma's distance output, and it's the number my similarity threshold gets compared against. I added a small hand-rolled re-ranker on top — not a cross-encoder, a tuple sort — that pushes preamble/recital text to the top for "what's the purpose of this act" style questions, because pure similarity search doesn't reliably know that a preamble is the *canonical* place to look for stated purpose.

**3. The citation trust boundary — this is the part I'm proudest of.**
The LLM never generates a citation's facts. It's instructed to write `[SOURCE_N]` inline after claims; a separate mapper resolves each `N` against metadata I already have from retrieval — document name, page number, section — before the LLM ever ran. If the model invents a source number that wasn't in its context, that reference is dropped, not trusted. So even in a worst case where the answer text itself has a mistake, every citation shown to the user points to a page number and document that's guaranteed to be real, because I never asked the model to produce that fact — only to select among facts I already verified.

**4. Evaluation, told honestly.**
I built a retrieval-only eval harness — Recall@1/3/5, Precision@5, and MRR — measured against a 42-question dataset with independently-phrased questions and verbatim-span ground truth, so a chunk counts as relevant based on its text, not a fragile chunk-ID match. Real numbers on my last run: Recall@1 of 0.41, Recall@5 of 0.65, MRR of 0.52, on 37 in-corpus questions. I'd flag the most important finding myself before anyone asks: the 5 unanswerable questions in the dataset run through the *real* retriever end to end, and every single one retrieved a top result scoring 0.72–0.81 — above my 0.35 similarity threshold. My confidence gate's actual measured rate is 0/5; the system never abstains on a question it has no evidence for. I checked one directly — an interest-rate-cap question with no basis in the corpus — and the top hit was the Contract Act's own short-title section, matched on generic legal vocabulary. An earlier version of this eval had a metric with this exact name that never actually called the retriever on out-of-corpus cases, so it silently reported dataset composition instead of behavior; I rebuilt the harness so the number is real, even though the number itself is bad news.

**5. What I'd build next, in priority order.**
A real out-of-corpus detection metric (the fix above). A generation/faithfulness eval — right now nothing checks whether the LLM's answer text actually matches what the cited sources say, only whether retrieval found the right chunk. Metadata filters — the data model already carries `category`/`document_id`/`section` on every chunk, but `Retriever.retrieve()` raises `NotImplementedError` the moment you pass a filter; the plumbing exists, the query-side logic doesn't. And a cross-encoder rerank pass, since the current re-ranker is a hand-tuned heuristic that only really helps "purpose" questions.

## Things to say unprompted (they read as seniority, not weakness)

- "I found a benchmark table in my own repo's history claiming numbers for a BM25/hybrid/reranker comparison that was never actually run — I deleted it and wrote a retraction rather than quietly fix it, because the honest story is stronger than the polished one."
- "One of my own tests documents a case where the structure detector gets a chapter/short-title sequence wrong — I know exactly which one and why."
- "My test suite is 254 passing, 59 failing, 1 xfailed out of 314 — the 59 failures are all in modules that exist but aren't wired into the live retrieval path yet (BM25, query analysis, reranking, obligation extraction), and I know exactly why each one fails."
- "My confidence gate's real measured rate on unanswerable questions is 0/5, not some rosier number a naive metric might imply — I built the harness specifically so unanswerable cases run through the real retriever instead of being scored as automatic passes." (see beat 4) — this is a strong signal you actually understand your own measurement code rather than trusting a summary line.
- "My judgment-heading detection patterns exist in the code, but checking the actual indexed corpus shows they only reliably fire on some of the three Delhi High Court judgments I indexed — one comes back with zero section metadata on every chunk. I'd say that's a partially-working feature, not a working one."

## What NOT to do

- Don't claim OCR, auth, hybrid search, or metadata filtering exist — they don't (see [01-architecture.md](01-architecture.md)'s explicit absence list), and claiming otherwise is the fastest way to lose credibility if the interviewer opens the code.
- Don't describe the re-ranker as "a reranking model" — it's a tuple sort. Precision here signals you understand your own system rather than pattern-matching to RAG buzzwords.
