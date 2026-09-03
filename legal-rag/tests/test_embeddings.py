from __future__ import annotations

import pytest

from src.embeddings.providers import EmptyTextError
from src.embeddings.service import EmbeddingService
from src.ingestion.models import Chunk


class FakeEmbeddingProvider:
    model_name = "fake-local-model"
    model_version = "2026.09"

    @property
    def embedding_dimension(self) -> int:
        return 4

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            if not text.strip():
                raise EmptyTextError("Embedding text must not be blank.")
            base = float(len(text))
            vectors.append([base, base + 1.0, base + 2.0, base + 3.0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def make_chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        page_number=1,
        end_page_number=1,
        section="1",
        heading="TERMS",
        text=text,
    )


def test_single_chunk_is_embedded():
    service = EmbeddingService(provider=FakeEmbeddingProvider())
    chunks = [make_chunk("chunk-1", "Either party may terminate this agreement.")]

    embedded = service.embed_chunks(chunks)

    assert len(embedded) == 1
    assert embedded[0].chunk.chunk_id == "chunk-1"
    assert len(embedded[0].embedding) == 4
    assert embedded[0].embedding_model == "fake-local-model"


def test_multiple_chunks_keep_chunk_association():
    service = EmbeddingService(provider=FakeEmbeddingProvider())
    chunks = [
        make_chunk("chunk-1", "Termination is permitted."),
        make_chunk("chunk-2", "Notices must be in writing."),
    ]

    embedded = service.embed_chunks(chunks)

    assert [item.chunk.chunk_id for item in embedded] == ["chunk-1", "chunk-2"]
    assert len(embedded) == len(chunks)


def test_dimension_is_consistent():
    service = EmbeddingService(provider=FakeEmbeddingProvider())

    assert service.embedding_dimension() == 4
    embedded = service.embed_chunks([make_chunk("chunk-1", "Some text here.")])
    assert all(len(item.embedding) == service.embedding_dimension() for item in embedded)


def test_empty_input_returns_empty_list():
    service = EmbeddingService(provider=FakeEmbeddingProvider())

    assert service.embed_chunks([]) == []


def test_blank_chunk_text_is_rejected():
    service = EmbeddingService(provider=FakeEmbeddingProvider())

    with pytest.raises(EmptyTextError):
        service.embed_chunks([make_chunk("chunk-1", "   ")])


def test_embedding_is_repeatable_for_same_text():
    service = EmbeddingService(provider=FakeEmbeddingProvider())
    chunk = make_chunk("chunk-1", "Consistent clause text.")

    first = service.embed_chunks([chunk])[0].embedding
    second = service.embed_chunks([chunk])[0].embedding

    assert first == second

