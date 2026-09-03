"""Prompt construction for grounded legal answers."""

from __future__ import annotations

from dataclasses import dataclass

from src.generation.models import GenerationContext


@dataclass
class PromptBuilder:
    """Create a grounded prompt that forbids unsupported answers."""

    system_instruction: str = (
        "You are a legal information assistant.\n"
        "Answer using ONLY the provided sources.\n"
        "If the sources do not contain sufficient information, say so clearly.\n"
        "Do not invent facts, clauses, citations, dates, or legal provisions."
    )

    def build(self, context: GenerationContext) -> str:
        return (
            f"{self.system_instruction}\n\n"
            f"USER QUESTION:\n{context.question}\n\n"
            f"SOURCES:\n{context.rendered_context}\n"
        )

