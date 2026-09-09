# Interview Narrative — A Story You Can Actually Tell

A rehearsable walkthrough. Each section is meant to be said out loud in under a minute; the file/line citations are there so you can go deeper the instant someone asks "show me."

## The 30-second version

"I built a local RAG system over legal documents — statutes, contracts, and court judgments. The interesting problem wasn't wiring an LLM to a vector store, it was that legal text has real structure — sections, sub-sections, clauses — and naive fixed-size chunking destroys that structure and makes citations unreliable. So most of the engineering effort went into a deterministic structure detector that parses that hierarchy before chunking, and into making sure every citation the system shows a user is provably correct rather than trusted from the model's output."

## The 3-minute version, in five beats

**1. The chunking problem, and why it's not generic.**
A statute has nested identifiers like `2(d)(i)` — subsection `d` under section `2`, clause `i` under that. A fixed-size sliding window will cut a definition clause in half. I wrote a regex-cascade structure detector (`structure_patterns.py`, ~15 pattern matchers tried in precedence order, [02-ingestion.md](02-ingestion.md)) that recognizes chapters, articles, lettered subsections, nested clauses, frontmatter (preambles/recitals), and even ALL-CAPS judgment headings like `HELD`/`ISSUES` for case law — because my corpus includes Delhi High Court and Supreme Court judgments, not just statutes. Chunking then groups by detected heading first, and only falls back to sentence- or size-based splitting when a single paragraph is too large on its own.

**2. Retrieval is hybrid, and I can show you the measurement that justifies it.**
Local BGE embeddings (384-dim, `sentence-transformers`) in a Chroma collection, fused with a BM25 lexical index via Reciprocal Rank Fusion. I built and evaluated all three — dense-only, BM25-only, hybrid — against the same 42-question dataset before deciding what to ship: hybrid won on every metric (Recall@5 0.7838 vs dense's 0.6486), and specifically fixed BM25's collapse on paraphrased "comparison" questions (0.1667 → 0.6667 Recall@5) while keeping its lexical precision gains elsewhere. I also built a hand-rolled reranker on top and measured it too — it made results *worse* (Recall@5 down to 0.6216), so it's not shipped. That's the story I'd lead with on retrieval: not "I chose hybrid," but "I measured three approaches and a fourth that didn't work, and shipped the one with evidence behind it."

**3. The citation trust boundary — this is the part I'm proudest of.**
The LLM never generates a citation's facts. It's instructed to write `[SOURCE_N]` inline after claims; a separate mapper resolves each `N` against metadata I already have from retrieval — document name, page number, section — before the LLM ever ran. If the model invents a source number that wasn't in its context, that reference is dropped, not trusted. So even in a worst case where the answer text itself has a mistake, every citation shown to the user points to a page number and document that's guaranteed to be real, because I never asked the model to produce that fact — only to select among facts I already verified.

**4. Evaluation, at both layers, told honestly.**
Retrieval: Recall@1/3/5, Precision@5, and MRR against a 42-question dataset with independently-phrased questions and verbatim-span ground truth, run against all four retrieval configurations, not just the one I shipped (see beat 2). The confidence gate's measured rate is 0/5 on the dataset's 5 unanswerable questions — every one retrieves a top result scoring 0.72–0.81, above my 0.35 threshold, for both dense and the hybrid path that's actually live. I'd flag that as a real, open weakness before anyone asks.

But retrieval isn't the whole system, so I built a second harness that runs the full pipeline — real LLM call included — and measures groundedness, citation faithfulness, and unresolved-citation rate without an LLM judge. Real numbers: 94.6% groundedness, 77.1% citation faithfulness, 0% unresolved citations, and — this is the finding I'd lead with — **100% correct refusal on those same 5 unanswerable questions.** The retrieval gate misses all 5; the LLM's own grounding instruction catches all 5. I checked one directly: asked about an interest-rate cap not in the corpus, the model answered *"I could not find this information in the provided documents,"* then explained exactly which irrelevant sources it had checked and why none of them applied. That's a second line of defense actually doing its job, and I only know that because I measured it separately instead of assuming a weak retrieval gate means a broken system.

**5. What I'd build next, in priority order.**
Metadata filters — the data model already carries `category`/`document_id`/`section` on every chunk, but both retrievers raise `NotImplementedError` the moment you pass a filter; the plumbing exists, the query-side logic doesn't. Understanding *why* my reranker hurt results before reaching for a learned cross-encoder — a negative result is a lead, not a dead end, and I haven't run it down yet. And an LLM-judge layer on top of my current generation eval, since my faithfulness check only verifies a cited source *contains* the right fact, not that the answer's prose is a faithful, complete paraphrase of it.

## Things to say unprompted (they read as seniority, not weakness)

- "I found a benchmark table in my own repo's history claiming numbers for a BM25/hybrid/reranker comparison that was never actually run — I deleted it, wrote a retraction, and then actually built and ran that comparison for real. The real numbers don't match what was fabricated, and the real reranker measurement says the opposite of what a reader would assume."
- "One of my own tests documents a case where the structure detector gets a chapter/short-title sequence wrong — I know exactly which one and why."
- "My test suite is 311 passing, 4 xfailed, out of 315 — every xfail is a documented, deliberate limitation (a structure-detector ambiguity, three sentences my pattern-based obligation extractor can't parse because they have no grammatical actor), not a hidden failure."
- "My confidence gate's real measured rate on unanswerable questions is 0/5 for both dense and the hybrid path I actually ship — not some rosier number a naive metric might imply — because I built the harness specifically so unanswerable cases run through the real retriever instead of being scored as automatic passes." (see beat 4) — this is a strong signal you actually understand your own measurement code rather than trusting a summary line.
- "The retrieval layer's confidence gate is measurably weak, but I didn't stop at that finding — I built a second eval for the generation layer and found it catches 100% of what retrieval misses. Measuring one layer and assuming the failure propagates would have been the lazier, less accurate story."
- "My judgment-heading detection patterns exist in the code, but checking the actual indexed corpus shows they only reliably fire on some of the three Delhi High Court judgments I indexed — one comes back with zero section metadata on every chunk. I'd say that's a partially-working feature, not a working one."

## What NOT to do

- Don't claim OCR, auth, or metadata filtering exist — they don't (see [01-architecture.md](01-architecture.md)'s explicit absence list), and claiming otherwise is the fastest way to lose credibility if the interviewer opens the code.
- Don't describe the shipped reranker as "a reranking model" — there isn't one live; the measured reranker was rejected. Precision here signals you understand your own system rather than pattern-matching to RAG buzzwords.
- Don't overclaim what the generation eval checks — it verifies a cited source contains the right fact, not that the answer's prose faithfully paraphrases it. That's a real, stated limitation (no LLM judge), not a weaker version of "we checked everything."
