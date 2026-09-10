from __future__ import annotations

import json

import pytest

from src.ingestion.exceptions import LLMChunkingFailure
from src.ingestion.llm_semantic_chunker import LLMChunkerConfig, LLMSemanticChunker
from src.ingestion.models import DocumentPage


def make_pages(texts: list[str], document_id: str = "doc-1") -> list[DocumentPage]:
    return [
        DocumentPage(
            page_number=index + 1,
            text=text,
            extraction_status="extracted" if text.strip() else "no_text",
            document_id=document_id,
            filename="doc.pdf",
            storage_path="/tmp/doc.pdf",
        )
        for index, text in enumerate(texts)
    ]


class ScriptedLLM:
    """Stub LLM client returning a scripted response, following the FakeLLM
    pattern used in tests/test_generation.py."""

    model_name = "scripted-llm"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.response == "__raise__":
            raise RuntimeError("boom")
        return self.response


def test_happy_path_splits_at_anchors():
    text = "ALPHA content is here. BRAVO content follows after that."
    llm = ScriptedLLM(json.dumps(["ALPHA content is here.", "BRAVO content follows"]))
    chunks = LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 2
    assert chunks[0].text.startswith("ALPHA content is here.")
    assert chunks[1].text.startswith("BRAVO content follows")


def test_no_structure_metadata_is_populated():
    text = "Some content for a single chunk without structure."
    llm = ScriptedLLM(json.dumps([]))
    chunks = LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 1
    assert chunks[0].section is None
    assert chunks[0].heading is None


def test_chunks_are_verbatim_substrings_never_model_paraphrase():
    text = "Exact original wording that must survive untouched in the index."
    llm = ScriptedLLM(json.dumps(["Exact original wording"]))
    chunks = LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))

    assert all(c.text in text for c in chunks)


def test_call_failure_raises_llm_chunking_failure():
    llm = ScriptedLLM("__raise__")
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages(["some text here"]))


def test_unparseable_response_raises_llm_chunking_failure():
    llm = ScriptedLLM("this is not JSON at all")
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages(["some text here"]))


def test_invalid_json_type_raises_llm_chunking_failure():
    llm = ScriptedLLM(json.dumps({"not": "a list"}))
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages(["some text here"]))


def test_unlocatable_anchor_raises_llm_chunking_failure():
    llm = ScriptedLLM(json.dumps(["text that does not exist in the source at all"]))
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages(["some other text here"]))


def test_anchor_matches_despite_whitespace_differences_from_source():
    # Real PDF extraction often yields newlines/multi-space runs (e.g. a TOC
    # line) that a model reproduces as single spaces when copying an anchor
    # "verbatim" by reading it visually - this must still resolve to the
    # original text's exact position, not fail as unlocatable.
    text = "Preceding text.\n\n10 \n \nSECTIONS \n197. Imputations, assertions prejudicial to national\nunity."
    llm = ScriptedLLM(json.dumps(["10 SECTIONS 197. Imputations, assertions prejudicial to national"]))
    chunks = LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 2
    assert chunks[0].text == "Preceding text."
    assert chunks[1].text.startswith("10 \n \nSECTIONS \n197.")
    assert all(c.text in text for c in chunks)


def test_mid_word_kerning_artifact_anchor_is_skipped_at_the_slicing_level():
    # Real PDF extraction sometimes inserts a spurious space inside a word
    # from font-kerning quirks (e.g. "c ertain" for "certain"). This is
    # deliberately NOT tolerated by the normalizer (see its docstring - doing
    # so would merge unrelated words elsewhere): the unlocatable anchor is
    # skipped (counted, not fatal on its own) rather than aborting the
    # window - whether the containing *document* then succeeds depends on
    # the overall skip-rate budget, exercised separately below.
    text = "Exception in favour of c ertain prizes for horse racing follows."
    pieces, skipped = LLMSemanticChunker._slice_by_anchors(text, ["Exception in favour of certain prizes for"])

    assert skipped == 1
    assert pieces == [text]


def test_document_aborts_when_skipped_anchors_exceed_budget():
    # A single unlocatable anchor out of one total is a 100% skip rate,
    # over MAX_SKIPPED_ANCHOR_RATE - the document must fail loudly rather
    # than silently index on zero real LLM-placed boundaries.
    text = "Exception in favour of c ertain prizes for horse racing follows."
    llm = ScriptedLLM(json.dumps(["Exception in favour of certain prizes for"]))
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))


def test_document_survives_when_skipped_anchors_stay_under_budget():
    # Twenty-five locatable anchors and one unlocatable (kerning-artifact)
    # anchor is a 1/26 ~= 3.8% skip rate, under the 5% budget - ingestion
    # succeeds, just with one fewer boundary than proposed.
    good_words = [f"word{i} marker text follows here" for i in range(25)]
    text = " ".join(good_words) + " Exception in favour of c ertain prizes for horse racing follows."
    anchors = [f"word{i} marker" for i in range(25)] + ["Exception in favour of certain prizes for"]
    llm = ScriptedLLM(json.dumps(anchors))

    chunks = LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))

    assert len(chunks) == 25  # the 26th (unlocatable) anchor contributed no extra boundary
    assert all(c.text in text for c in chunks)


def test_non_monotonic_anchor_raises_llm_chunking_failure():
    # "content" appears once; asking for it twice as two anchors forces the
    # second forward-only search past the single occurrence to fail.
    text = "some content here and nothing else repeats"
    llm = ScriptedLLM(json.dumps(["some content", "some content"]))
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages([text]))


def test_page_windowing_batches_calls():
    pages = make_pages([f"Page {i} content here." for i in range(7)])
    llm = ScriptedLLM(json.dumps([]))
    LLMSemanticChunker(llm, LLMChunkerConfig(window_pages=3)).chunk(document_id="doc-1", pages=pages)

    # 7 pages / 3 per window -> 3 windows -> 3 calls.
    assert len(llm.calls) == 3


def test_disk_cache_avoids_repeat_llm_calls(tmp_path):
    pages = make_pages(["Some content for the first ingest run."])
    llm = ScriptedLLM(json.dumps([]))
    config = LLMChunkerConfig(cache_dir=tmp_path)
    chunker = LLMSemanticChunker(llm, config)

    chunker.chunk(document_id="doc-1", pages=pages)
    assert len(llm.calls) == 1

    # A second chunker instance (simulating a retry) must hit the cache, not the LLM.
    llm2 = ScriptedLLM("__raise__")
    chunker2 = LLMSemanticChunker(llm2, config)
    chunker2.chunk(document_id="doc-1", pages=pages)
    assert len(llm2.calls) == 0


def test_cached_anchors_are_reused_even_after_a_budget_failure(tmp_path):
    # The cache holds the LLM's raw anchor proposals, which are valid LLM
    # output regardless of whether every anchor turns out to be locatable -
    # only the (deterministic, code-side) matching against source text can
    # change between runs, e.g. after a matcher bugfix. So a retry after a
    # skip-budget failure must NOT re-call the LLM: it reads the same cached
    # anchors and re-runs matching against them locally.
    pages = make_pages(["some content here"])
    config = LLMChunkerConfig(cache_dir=tmp_path)

    bad_llm = ScriptedLLM(json.dumps(["text not present in source"]))
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(bad_llm, config).chunk(document_id="doc-1", pages=pages)

    retry_llm = ScriptedLLM("__raise__")  # would blow up if called - retry must not call it
    with pytest.raises(LLMChunkingFailure):
        LLMSemanticChunker(retry_llm, config).chunk(document_id="doc-1", pages=pages)
    assert len(retry_llm.calls) == 0


def test_empty_pages_produce_no_chunks():
    llm = ScriptedLLM(json.dumps([]))
    chunks = LLMSemanticChunker(llm).chunk(document_id="doc-1", pages=make_pages(["", "   "]))
    assert chunks == []
