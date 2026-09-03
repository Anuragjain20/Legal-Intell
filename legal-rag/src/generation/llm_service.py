"""LLM abstraction for grounded answer generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.generation.citations import CitationMapper
from src.generation.exceptions import GenerationFailure, InsufficientEvidenceError
from src.generation.models import GenerationContext, GenerationResult


class LLMClient(Protocol):
    """Minimal interface for a text-generation backend."""

    model_name: str

    def generate(self, prompt: str) -> str:
        ...


@dataclass
class LLMService:
    """Generate a grounded answer using an injected LLM client."""

    client: LLMClient

    def generate(self, prompt: str) -> str:
        return self.client.generate(prompt)


@dataclass
class GenerationService:
    """Build prompt context and call the LLM with controlled failure handling."""

    llm_service: LLMService
    context_builder: object
    prompt_builder: object
    citation_mapper: CitationMapper
    insufficient_evidence_response: str = (
        "I could not find sufficient information in the provided documents to answer this question."
    )

    def answer(self, question: str, retrieved_results: list) -> GenerationResult:
        context = self.context_builder.build(question, retrieved_results)
        if not context.sources:
            return GenerationResult(
                answer=self.insufficient_evidence_response,
                model=self.llm_service.client.model_name,
                used_context=context,
                insufficient_evidence=True,
            )

        prompt = self.prompt_builder.build(context)
        try:
            answer = self.llm_service.generate(prompt)
        except Exception as exc:  # pragma: no cover - exercised in tests
            raise GenerationFailure(f"LLM generation failed: {exc}") from exc

        if not answer.strip():
            raise InsufficientEvidenceError("LLM returned an empty answer.")

        citation_mapping = self.citation_mapper.map(answer, context)
        if citation_mapping.unresolved_source_ids:
            raise GenerationFailure(
                f"LLM referenced unknown sources: {', '.join(citation_mapping.unresolved_source_ids)}"
            )

        return GenerationResult(
            answer=answer,
            model=self.llm_service.client.model_name,
            used_context=context,
            citations=citation_mapping.citations,
            unresolved_source_ids=citation_mapping.unresolved_source_ids,
            insufficient_evidence=False,
        )
