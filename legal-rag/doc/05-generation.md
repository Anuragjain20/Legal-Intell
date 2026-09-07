# Generation: Context, Prompt, LLM Call, and the Citation Trust Boundary

This is the layer worth being most articulate about in an interview, because it contains the single best design decision in the codebase: **citations are computed from retrieval metadata, never trusted from LLM output text.**

## The pipeline

`GenerationService.answer()` ([llm_service.py:45-80](../src/generation/llm_service.py#L45-L80)) orchestrates four collaborators, all injected at construction (see `app.py:51-61`):

```
retrieved_results: list[RetrievalResult]
  → ContextBuilder.build()      →  GenerationContext (sources + rendered text block)
  → if no sources: return canned "insufficient evidence" response, skip the LLM call entirely
  → PromptBuilder.build()       →  a single prompt string
  → LLMService.generate()       →  raw answer string (DeepSeek)
  → if answer is blank: raise InsufficientEvidenceError
  → CitationMapper.map()        →  CitationMapping (trusted citations + any unresolved references)
  → GenerationResult
```

## Context building: source-separated, budget-aware

`ContextBuilder.build()` ([context_builder.py:18-47](../src/generation/context_builder.py#L18-L47)) takes at most `max_sources=6` of the retriever's (already re-ranked) results and renders each as a labeled block:

```
[SOURCE_1]
Document: indian_contract_act_1872.pdf
Chunk: <sha256>:0007
Section/Heading: 2(d). "Consideration" means...
Category: 2(d)
Page: 3

<chunk text>
```

(`_render_source()`, [context_builder.py:49-63](../src/generation/context_builder.py#L49-L63) — note "Category" here is actually the raw `section` field, a slightly confusing label choice worth just being upfront about if asked.)

Two budget mechanisms, both worth naming precisely:
- **Source count budget:** hard cap at 6, via Python slicing — `results[:self.max_sources]` ([context_builder.py:19](../src/generation/context_builder.py#L19)), silently drops anything past rank 6 rather than erroring.
- **Character budget:** `max_context_chars=8000` running total. If adding a source's block would exceed the remaining budget, and at least one source has already been included, the loop stops there — the over-budget source is dropped entirely, not truncated ([context_builder.py:37,41](../src/generation/context_builder.py#L37)). **Exception:** if the very *first* source alone exceeds 8000 chars, it gets truncated to fit rather than producing an empty context ([context_builder.py:38-40](../src/generation/context_builder.py#L38-L40)) — a context with one truncated source beats a context with zero sources.

## Prompt construction: an explicit grounding contract

`PromptBuilder.build()` ([prompt.py:38-44](../src/generation/prompt.py#L38-L44)) assembles a static system instruction + the question + the rendered context into one string (this DeepSeek client takes a single prompt string via `ChatOpenAI.invoke(prompt)`, not a structured messages list — see below). The system instruction ([prompt.py:14-36](../src/generation/prompt.py#L14-L36)) is worth reading in full; the load-bearing rules are:

1. Answer only from provided sources — no invented provisions.
2. **Every factual claim must carry `[SOURCE_N]` immediately after it.**
3. If sources are insufficient, say so explicitly (a specific fallback string), rather than guessing.
4. Quote verbatim for definitions/legal terms rather than paraphrasing.
5. For "purpose/intent" questions, prefer preambles/recitals/long titles as evidence — this is the same domain heuristic that shows up in the retriever's re-ranker ([04-retrieval.md](04-retrieval.md)); the two layers reinforce each other rather than fighting.

Few-shot examples are baked directly into the system prompt (a ❌ bad / ✓ good / ✓ better triplet, [prompt.py:31-35](../src/generation/prompt.py#L31-L35)) rather than relying purely on instruction-following — a reasonable choice for a smaller/cheaper model like `deepseek-chat` where instruction-following alone may be less reliable than with a frontier model.

## The LLM call

`DeepSeekLLMClient` ([providers.py:9-35](../src/generation/providers.py#L9-L35)) wraps DeepSeek's OpenAI-compatible API via `langchain_openai.ChatOpenAI`, `temperature=0.0` (deterministic-as-possible, appropriate for a grounded-answer task where creativity is a liability, not a feature). `LLMService` ([llm_service.py:22-29](../src/generation/llm_service.py#L22-L29)) is a one-method pass-through — its only job is to be the `Protocol` boundary (`LLMClient`, [llm_service.py:13-19](../src/generation/llm_service.py#L13-L19)) so `GenerationService` never imports `langchain_openai` or knows DeepSeek exists. Swapping to OpenAI/Anthropic/a local model means writing one new class with a `generate(prompt) -> str` method and changing one line in `app.py`.

## Citations: the trust boundary, precisely

This is the part to lead with if asked "what's a good design decision you made."

The model is instructed to emit inline markers like `[SOURCE_2]` in its answer text. `CitationMapper.map()` ([citations.py:42-74](../src/generation/citations.py#L42-L74)) then:

1. Regex-extracts every `[SOURCE_N]` the model wrote (`SOURCE_REF_PATTERN`, [citations.py:12](../src/generation/citations.py#L12); `_extract_source_ids`, [citations.py:76-77](../src/generation/citations.py#L76-L77)).
2. For each one, looks it up against `context.sources` — the `ContextSource` list **built during retrieval, before the LLM ever ran** ([citations.py:43](../src/generation/citations.py#L43)).
3. Builds a `Citation` object using **only fields copied from that `ContextSource`** — `document_id`, `page_number`, `chunk_id`, `section`, `heading` ([citations.py:56-67](../src/generation/citations.py#L56-L67)). None of this data is parsed or trusted from the LLM's answer text itself.
4. A `[SOURCE_N]` the model invents (references a rank that wasn't actually in the context) lands in `unresolved_source_ids`, not `citations` — it never becomes a trusted `Citation`.

**Why this matters:** it means the UI's "Sources" panel ([app.py:513-519](../app.py#L513-L519)) is showing the user page numbers and document names that are *guaranteed correct*, because they were never generated by the LLM — the LLM only ever chose *which* of the already-known sources to point at, by emitting a number. Even if the LLM hallucinates the answer text itself, it cannot hallucinate a citation's page number or document name, because the citation's factual payload was fixed before generation started. This is a general pattern worth having ready for any "how do you prevent hallucination" question: **don't ask the model to produce facts you can otherwise derive deterministically — ask it to select among facts you already trust.**

## A real gap in this layer, worth naming yourself

`GenerationService.answer()` ([llm_service.py:66-71](../src/generation/llm_service.py#L66-L71)):

```python
if citation_mapping.unresolved_source_ids and citation_mapping.citations:
    pass                                    # partial failure: silently ignored
elif citation_mapping.unresolved_source_ids:
    raise GenerationFailure(...)            # total failure: raised
```

If the model cites a mix of real and invented source numbers, the invented ones are silently dropped — no warning surfaces to the caller or the UI, `unresolved_source_ids` is populated on the returned `GenerationResult` but nothing in `app.py` currently reads or displays it. Only a *total* citation failure (every reference unresolved) raises. This is a defensible "fail open when partially correct" choice, but it's undocumented as a choice — it reads like an oversight (a `pass` with no comment) rather than a decision. Good self-critique material for an interview: state what it does, then state what you'd add — logging or a UI warning badge when `unresolved_source_ids` is non-empty, so a partial hallucination isn't invisible.

One more precision point: `context_builder` and `prompt_builder` on `GenerationService` are typed as bare `object` ([llm_service.py:37-38](../src/generation/llm_service.py#L37-L38)), not as `Protocol`s the way `LLMClient` is. Minor inconsistency — worth noticing, not worth overstating.
