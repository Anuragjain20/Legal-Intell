"""Environment-driven configuration for the local application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    similarity_threshold: float = 0.35
    chunking_method: str = "legal"
    recursive_chunk_size: int = 1200
    recursive_chunk_overlap: int = 150
    llm_chunker_window_pages: int = 3

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file)
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.35")),
            chunking_method=os.getenv("CHUNKING_METHOD", "legal"),
            recursive_chunk_size=int(os.getenv("RECURSIVE_CHUNK_SIZE", "1200")),
            recursive_chunk_overlap=int(os.getenv("RECURSIVE_CHUNK_OVERLAP", "150")),
            llm_chunker_window_pages=int(os.getenv("LLM_CHUNKER_WINDOW_PAGES", "3")),
        )
