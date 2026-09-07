"""Concrete LLM clients used by the generation service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DeepSeekLLMClient:
    """DeepSeek chat client through LangChain's OpenAI-compatible adapter."""

    api_key: str
    model_name: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.0

    def __post_init__(self) -> None:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise ImportError("DeepSeekLLMClient requires 'langchain-openai'.") from exc
        self._client: Any = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
        )

    def generate(self, prompt: str) -> str:
        response = self._client.invoke(prompt)
        content = response.content
        if isinstance(content, str):
            return content
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
