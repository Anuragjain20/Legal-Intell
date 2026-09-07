# Ingestion: PDF → Structured Chunks

This is the most bespoke, most defensible-in-an-interview part of the codebase. Generic RAG tutorials chunk by fixed character count; this one tries to chunk along the legal document's actual structure (sections, sub-sections, clauses, headings) first, and falls back to size-based splitting only when structure doesn't help.

## Stage 1 — Validation and storage

`DocumentValidator.validate()` ([validator.py:19-41](../src/ingestion/validator.py#L19-L41)) checks, in order: filename present → `.pdf` extension → non-empty bytes → ≤50MB → parses as a valid PDF via `pypdf.PdfReader` → not encrypted → has ≥1 page. All failures raise `UploadValidationError`, caught in `app.py` and shown as a user-facing message rather than a stack trace.

`DocumentStorage.save()` ([storage.py:27-35](../src/ingestion/storage.py#L27-L35)) writes to `data/documents/<category>/<sha256>-<filename>`. The category comes from `normalize_category()` ([storage.py:14-17](../src/ingestion/storage.py#L14-L17)), which strips unsafe characters and defaults to `"uncategorized"`.

**Document identity is content-addressed:** `document_id = sha256(content).hexdigest()` ([service.py:36](../src/ingestion/service.py#L36)). This makes re-uploading the *same* bytes a safe no-op (Chroma upserts by `chunk_id`, which is derived from `document_id`, so nothing duplicates). It also means **editing a PDF and re-uploading creates a second, entirely separate set of chunks under a new document_id — the old chunks are never cleaned up.** `VectorStore.delete_document()` exists ([vectorstore/base.py:52](../src/vectorstore/base.py#L52), implemented in both stores) but nothing in the upload path calls it. This is a real gap worth naming yourself in an interview rather than waiting to be asked ([08-question-bank.md](08-question-bank.md) has the framing).

## Stage 2 — PDF text extraction

`PDFExtractor.extract()` ([pdf_extractor.py:25-57](../src/ingestion/pdf_extractor.py#L25-L57)) walks pages with `pypdf`, calling `page.extract_text()` per page and tagging each `DocumentPage` with `extraction_status` = `"extracted"` or `"no_text"`. Page numbers are preserved 1-indexed — this is what lets a citation later say "page 12," and it's why extraction is page-by-page rather than one big `reader.extract_text()` call over the whole document.

No OCR fallback: a scanned/image-only PDF yields pages with `extraction_status="no_text"`, chunking produces zero chunks, and `app.py` raises `ValueError(f"{filename} has no extractable text. Scanned PDFs need OCR support.")` ([app.py:84-85](../app.py#L84-L85)).

## Stage 3 — Structure detection

This is a **deterministic regex cascade**, not an ML model. `structure_patterns.py` defines ~15 pattern matchers tried in explicit precedence order via `_PATTERNS` ([structure_patterns.py:343-359](../src/ingestion/structure_patterns.py#L343-L359)), most specific first:

```
section-letter "2(a) ..."  →  nested clause "(iv) ..."  →  lettered subsection "(a) ..."
  →  CHAPTER / PART / Article / Rule / Regulation  →  Schedule / Annexure
  →  keyword "Section N" / "Clause N"  →  frontmatter (PREAMBLE, WHEREAS, RECITALS...)
  →  dotted numbering "1.2.3 ..."  →  simple numbered "10. Short title"
  →  ALL-CAPS heading (e.g. "TERMINATION", "JUDGMENT")
```

`match_line()` ([structure_patterns.py:362-370](../src/ingestion/structure_patterns.py#L362-L370)) returns the *first* matcher that fires — precedence order is the whole design; a section-letter pattern like `2(a)` must be tried before the generic simple-number pattern or it'd be misread as section `"2"` with body text `"(a) ..."`.

**Two escape hatches worth knowing:**
- `accept_numbered_section()` ([structure_patterns.py:373-381](../src/ingestion/structure_patterns.py#L373-L381)) — a bare `"10. Short title"` line is only accepted as a section heading if the *document* shows other statutory signals (chapters/parts/articles/rules/section-keywords found anywhere via `collect_signals()`), or the line's title looks heading-shaped, or confidence is already high. This stops a contract's numbered list item ("10. Payment shall be made...") from being misparsed as a statute section, without hardcoding per-document-type logic.
- `looks_like_narrative()` ([structure_patterns.py:154-163](../src/ingestion/structure_patterns.py#L154-L163)) — a line starting "The/This/It/We..." with 6+ words, or matching a footnote-amendment pattern ("Subs.", "Ins.", "Omitted"), is rejected as a section title even if it numerically matches, because it's prose that happens to start with a number, not a heading.

`StructureDetector.detect()` ([structure_detector.py:81-232](../src/ingestion/structure_detector.py#L81-L232)) is a single-pass state machine over every line of every page. It tracks `current_heading`/`current_section` and buffers body lines until a blank line or a new structural signal forces a `flush()`. The trickiest piece is `_compose_identifier()` ([structure_detector.py:45-71](../src/ingestion/structure_detector.py#L45-L71)), which builds hierarchical IDs correctly:

```
"2" + "(d)"     → "2(d)"       (child composes onto parent)
"2(d)" + "(i)"  → "2(d)(i)"    (nested clause composes onto immediate parent)
"2(a)" + "(d)"  → "2(d)"       (sibling replaces, does NOT become "2(a)(d)")
```

That sibling-replacement rule is the one non-obvious invariant here — without it, a statute with sequential lettered subsections `(a)`, `(b)`, `(c)`, `(d)` under section 2 would produce increasingly nonsensical nested IDs.

`parse_section_structure()` ([section_parser.py:19-64](../src/ingestion/section_parser.py#L19-L64)) then decomposes a composed ID like `"2(d)(i)"` into `section_number="2"`, `subsection="d"`, `clause="i"`, `structure_path=["2","d","i"]` — stored as separate `Chunk` fields for potential structured filtering later (not currently used by retrieval, since metadata filters aren't implemented — see [01-architecture.md](01-architecture.md)).

**Known limitation, test-confirmed:** two tests in `tests/test_structure_detector.py` currently fail against this cascade (see [06-evaluation.md](06-evaluation.md) for the full list, verified by direct run) — a CHAPTER heading absorbing the next line's title instead of yielding a clean short-title heading in one case, and a lettered-subsection match (`3(a)`) grabbing the wrong text as its body (the paragraph's title text ends up as the section's stored body instead of the actual following prose) in another. These are genuine parser edge cases, not flaky tests. Good material for "what would you fix next."

**Real-corpus check worth doing before an interview, not just trusting the pattern list:** the ALL-CAPS judgment-heading patterns (`FACTS`, `ISSUES`, `JUDGMENT`, `HELD`) exist in `_PATTERNS`, but whether they actually fire well depends on the specific PDF's text extraction. Checking `data/chroma` directly shows mixed results across the three Delhi High Court judgments actually indexed: one is 21/36 chunks sectioned, another 22/29, but one (`DLHC010000022019_1_2023-12-13.pdf`) comes back **0/7 sectioned** — every chunk in that document has `section=None`. So the judgment-heading cascade is not uniformly reliable across this corpus; it depends on how cleanly that particular PDF's headings extracted as text. State it this way rather than claiming the judgment patterns "work" — they work on some judgments and silently produce no section metadata on at least one other.

## Stage 4 — Legal-aware chunking

`LegalChunker.chunk()` ([chunker.py:47-81](../src/ingestion/chunker.py#L47-L81)) does not use a fixed-size sliding window over raw text. It:

1. Runs `StructureDetector.detect()` to get `DetectedParagraph`s (each already tagged with section/heading).
2. **Groups consecutive paragraphs sharing the same heading** (`_group_by_heading`, [chunker.py:83-91](../src/ingestion/chunker.py#L83-L91)) — so a chunk boundary never silently crosses from one section into the next.
3. Within each group, packs paragraphs into a chunk up to `target_chunk_size=1200` chars, never splitting a paragraph unless it alone exceeds `max_chunk_size=1600` chars (`_chunk_group`, [chunker.py:93-126](../src/ingestion/chunker.py#L93-L126)).
4. An oversized single paragraph falls back to sentence-boundary splitting (`_split_oversized`, [chunker.py:159-184](../src/ingestion/chunker.py#L159-L184)), and only as a last resort to raw size-based splitting on whitespace (`_split_by_size`, [chunker.py:186-198](../src/ingestion/chunker.py#L186-L198)).
5. A trailing fragment shorter than `min_chunk_size=40` chars is folded into the previous chunk rather than kept standalone or dropped (`_merge_short_pieces`, [chunker.py:128-148](../src/ingestion/chunker.py#L128-L148)) — *unless* it has no predecessor, in which case it's kept as-is (a genuinely tiny but real section, e.g. a one-line notices clause, shouldn't be discarded).
6. `_apply_overlap()` prepends the tail `overlap_size=150` chars of the previous chunk to each subsequent chunk **as implemented — not scoped to only the oversized-paragraph split path the module docstring implies.** In practice, within any multi-chunk heading group, chunk *i* gets chunk *i-1*'s tail prepended, whether or not either was produced by size-splitting. One side effect: the borrowed overlap text keeps chunk *i*'s own `page_number`/`section` metadata — it does not get a blended page range, so a citation can point to a page number that's technically for the chunk's "own" content, with a few characters of prior-chunk text folded in ahead of it. Worth stating precisely like this if asked, rather than reciting the docstring.

Final `Chunk` construction ([chunker.py:55-80](../src/ingestion/chunker.py#L55-L80)) drops any chunk with no alphanumeric content, assigns `chunk_id = f"{document_id}:{index:04d}"`, and attaches the parsed hierarchical fields from stage 3.

## Why structure-first chunking, and the trade-off

**Why:** a fixed 500-char sliding window would happily cut `"2(d) Consideration means..."` in half, landing the definition's key term in one chunk and its explanation in the next — bad for both retrieval (neither half scores well alone) and citation precision (which section does this chunk even belong to?). Structure-first chunking keeps a section's text and its identity together, which is what makes accurate `[SOURCE_N] → Section 2(d), p.12` citations possible at all.

**Trade-off:** the regex cascade is India-statute/contract-shaped (CHAPTER, Article, Schedule, ALL-CAPS `JUDGMENT`/`HELD` headings for case law). It's tuned to the actual corpus in `data/documents/` (Indian Contract Act, Bharatiya Nyaya Sanhita, IT Intermediary Guidelines, CUAD-style contracts, Delhi High Court/Supreme Court judgments — see `doc/06-evaluation.md` for the full inventory). A UK statute or a US-style contract with different heading conventions would likely need new patterns added to `_PATTERNS`. This is the honest answer to "does this generalize" — no, not out of the box, and that's a reasonable scope call for an MVP over a known corpus rather than a flaw to hide.
