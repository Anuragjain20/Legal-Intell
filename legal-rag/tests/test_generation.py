from __future__ import annotations

import pytest

from src.generation.citations import CitationMapper
from src.generation.context_builder import ContextBuilder
from src.generation.llm_service import GenerationService, LLMService
from src.generation.exceptions import GenerationFailure
from src.generation.prompt import PromptBuilder
from src.retrieval.models import RetrievalResult
from src.vectorstore.base import VectorRecord


def make_result(rank: int, score: float, chunk_id: str, page_number: int, text: str, heading: str | None = "TERMINATION") -> RetrievalResult:
    return RetrievalResult(
        rank=rank,
        score=score,
        record=VectorRecord(
            chunk_id=chunk_id,
            document_id="doc-1",
            vector=[0.1, 0.2, 0.3],
            text=text,
            page_number=page_number,
            section="7",
            heading=heading,
            embedding_model="fake",
            embedding_version="1",
        ),
    )


class FakeLLM:
    model_name = "fake-llm"

    def __init__(self, response: str = "Grounded answer.") -> None:
        self.response = response
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        if self.response == "__raise__":
            raise RuntimeError("boom")
        return self.response


def build_service(llm: FakeLLM | None = None) -> GenerationService:
    return GenerationService(
        llm_service=LLMService(client=llm or FakeLLM()),
        context_builder=ContextBuilder(),
        prompt_builder=PromptBuilder(),
        citation_mapper=CitationMapper(),
    )


def test_context_builder_includes_source_boundaries():
    builder = ContextBuilder(max_sources=5, max_context_chars=2000)
    context = builder.build(
        "What are the termination conditions?",
        [make_result(1, 0.95, "chunk-1", 12, "Termination requires written notice.")],
    )

    assert "SOURCE 1" in context.rendered_context
    assert "Document: doc-1" in context.rendered_context
    assert "Chunk: chunk-1" in context.rendered_context
    assert "Page: 12" in context.rendered_context
    assert "Termination requires written notice." in context.rendered_context


def test_context_builder_respects_context_limit():
    builder = ContextBuilder(max_sources=5, max_context_chars=150)
    context = builder.build(
        "Question",
        [
            make_result(1, 0.95, "chunk-1", 1, "A" * 120),
            make_result(2, 0.90, "chunk-2", 2, "B" * 120),
        ],
    )

    assert len(context.rendered_context) <= 150
    assert len(context.sources) == 1


def test_prompt_contains_grounding_instructions_and_sources():
    context = ContextBuilder().build(
        "What are the termination conditions?",
        [make_result(1, 0.95, "chunk-1", 12, "Termination requires written notice.")],
    )
    prompt = PromptBuilder().build(context)

    assert "USER QUESTION:" in prompt
    assert "SOURCES:" in prompt
    assert "Answer using ONLY the provided sources." in prompt
    assert "If the sources do not contain sufficient information" in prompt
    assert "What are the termination conditions?" in prompt


def test_empty_retrieval_returns_insufficient_evidence_response():
    service = build_service()

    result = service.answer("What are the termination conditions?", [])

    assert result.insufficient_evidence is True
    assert "sufficient information" in result.answer


def test_generation_service_calls_llm_with_grounded_prompt():
    fake_llm = FakeLLM()
    service = build_service(fake_llm)

    result = service.answer("What are the termination conditions?", [make_result(1, 0.95, "chunk-1", 12, "Termination requires written notice.")])

    assert result.answer == "Grounded answer."
    assert fake_llm.last_prompt is not None
    assert "Termination requires written notice." in fake_llm.last_prompt


def test_llm_failure_is_controlled():
    service = build_service(FakeLLM(response="__raise__"))

    with pytest.raises(GenerationFailure):
        service.answer("What are the termination conditions?", [make_result(1, 0.95, "chunk-1", 12, "Termination requires written notice.")])


def test_valid_citation_maps_to_trusted_metadata():
    context = ContextBuilder().build(
        "What are the termination conditions?",
        [make_result(1, 0.95, "chunk-abc", 12, "Termination requires written notice.")],
    )
    mapping = CitationMapper().map("The agreement may be terminated with notice. [SOURCE_1]", context)

    assert len(mapping.citations) == 1
    citation = mapping.citations[0]
    assert citation.citation_id == 1
    assert citation.document_id == "doc-1"
    assert citation.page_number == 12
    assert citation.chunk_id == "chunk-abc"
    assert citation.section == "7"


def test_multiple_citations_map_in_order():
    context = ContextBuilder().build(
        "Question",
        [
            make_result(1, 0.95, "chunk-1", 12, "Clause A"),
            make_result(2, 0.90, "chunk-2", 13, "Clause B", heading="TERMINATION FOR CAUSE"),
        ],
    )
    mapping = CitationMapper().map("Claim one [SOURCE_1]. Claim two [SOURCE_2].", context)

    assert [citation.citation_id for citation in mapping.citations] == [1, 2]
    assert [citation.page_number for citation in mapping.citations] == [12, 13]


def test_invalid_source_is_rejected():
    context = ContextBuilder().build(
        "Question",
        [make_result(1, 0.95, "chunk-1", 12, "Clause A")],
    )
    mapping = CitationMapper().map("Unsupported claim [SOURCE_99].", context)

    assert mapping.unresolved_source_ids == ["SOURCE_99"]
    assert mapping.citations == []


def test_duplicate_source_reuses_single_citation():
    context = ContextBuilder().build(
        "Question",
        [make_result(1, 0.95, "chunk-1", 12, "Clause A")],
    )
    mapping = CitationMapper().map("Claim one [SOURCE_1]. Claim two [SOURCE_1].", context)

    assert len(mapping.citations) == 1
    assert mapping.citations[0].citation_id == 1


def test_missing_citation_is_detected():
    context = ContextBuilder().build(
        "Question",
        [make_result(1, 0.95, "chunk-1", 12, "Clause A")],
    )
    mapping = CitationMapper().map("This answer has no citations.", context)

    assert mapping.referenced_source_ids == []
    assert mapping.citations == []
