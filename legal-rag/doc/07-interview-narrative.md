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
I built a retrieval-only eval harness — Recall@1/3/5 and MRR — measured against a dataset I generated from the corpus's own indexed chunk metadata, so every question is grounded in something real rather than invented. Real numbers on my last run: Recall@1 of 0.59, Recall@5 of 0.82, MRR of 0.67, on 22 questions. I'd flag two things about that number myself before anyone asks: the eval questions are templated from each chunk's own section/heading, so it's really testing "is this chunk retrievable at all" more than "does this handle natural user phrasing" — and I found a real bug in my own harness while preparing this. A metric called `no_answer_detection_rate` doesn't actually run the retriever on the out-of-corpus test cases at all, so it reports dataset composition, not detection behavior — and when I went and checked the raw retrieval scores that were already being logged elsewhere, all five of my out-of-corpus questions actually scored 0.62–0.66, well above my 0.35 similarity threshold. My system doesn't abstain on any of them; it would confidently hand the LLM unrelated context for every one. That's a real, measured finding my eval's own summary metric was hiding.

**5. What I'd build next, in priority order.**
A real out-of-corpus detection metric (the fix above). A generation/faithfulness eval — right now nothing checks whether the LLM's answer text actually matches what the cited sources say, only whether retrieval found the right chunk. Metadata filters — the data model already carries `category`/`document_id`/`section` on every chunk, but `Retriever.retrieve()` raises `NotImplementedError` the moment you pass a filter; the plumbing exists, the query-side logic doesn't. And a cross-encoder rerank pass, since the current re-ranker is a hand-tuned heuristic that only really helps "purpose" questions.

## Things to say unprompted (they read as seniority, not weakness)

- "The docs in the repo root print sample numbers like Recall@1: 0.76 as illustrative output — I want to be clear the numbers I'm giving you are from actually re-running `data/evaluation_results.json`, not those."
- "One of my own tests documents a case where the structure detector gets a chapter/short-title sequence wrong — I know exactly which one and why."
- "My test suite is 107 passing, 4 failing, out of 111 — I know what each of the 4 failures is; one's a stale assertion, three are real parser edge cases."
- "I found a bug in my own eval harness while re-verifying these numbers for this conversation, and when I checked the underlying data, my out-of-corpus detection is actually 0/5, not the 0.227 the summary metric implies" (see beat 4) — this is a strong signal you actually understand your own measurement code rather than trusting the summary line.
- "My judgment-heading detection patterns exist in the code, but checking the actual indexed corpus shows they only reliably fire on some of the three Delhi High Court judgments I indexed — one comes back with zero section metadata on every chunk. I'd say that's a partially-working feature, not a working one."

## What NOT to do

- Don't quote `START_HERE.md`'s `Recall@1: 0.76 / MRR: 0.81` numbers — they're not measured, and if pressed on "how did you get these" you have no answer.
- Don't claim OCR, auth, hybrid search, or metadata filtering exist — they don't (see [01-architecture.md](01-architecture.md)'s explicit absence list), and claiming otherwise is the fastest way to lose credibility if the interviewer opens the code.
- Don't describe the re-ranker as "a reranking model" — it's a tuple sort. Precision here signals you understand your own system rather than pattern-matching to RAG buzzwords.
