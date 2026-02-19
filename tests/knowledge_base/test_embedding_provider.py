import asyncio

import pytest
from app.application.embeddings import GeminiEmbeddingProvider
from app.core.config import get_kb_config


def _run(coroutine):
    return asyncio.run(coroutine)


def test_embedding_provider_outputs_768_dimensions() -> None:
    provider = GeminiEmbeddingProvider(get_kb_config())

    async def scenario() -> None:
        provider._gemini_embedding = lambda _text, task_type: asyncio.sleep(
            0, result=[0.2] * 768
        )
        vector = await provider.embed_text("embedding verification text")
        assert len(vector) == 768

    _run(scenario())


def test_embedding_provider_resize_vector_up_and_down() -> None:
    upscaled = GeminiEmbeddingProvider._resize_vector([1.0, 2.0, 3.0], 6)
    downscaled = GeminiEmbeddingProvider._resize_vector(list(range(1000)), 768)

    assert len(upscaled) == 6
    assert len(downscaled) == 768


def test_embedding_provider_batch_outputs_768_dimensions() -> None:
    provider = GeminiEmbeddingProvider(get_kb_config())

    async def scenario() -> None:
        async def _batch(texts, *, task_type: str):
            return [[0.1] * 768 for _ in texts]

        provider._gemini_embeddings_batch = _batch
        vectors = await provider.embed_documents_batch(["a", "b", "c"])
        assert len(vectors) == 3
        assert all(len(vector) == 768 for vector in vectors)

    _run(scenario())


def test_embedding_provider_normalize_is_unit_vector() -> None:
    normalized = GeminiEmbeddingProvider._normalize([3.0, 4.0])
    magnitude = (normalized[0] ** 2 + normalized[1] ** 2) ** 0.5
    assert abs(magnitude - 1.0) < 1e-6


def test_embedding_provider_raises_when_gemini_fails() -> None:
    provider = GeminiEmbeddingProvider(get_kb_config())

    async def scenario() -> None:
        async def _raise(_text: str, *, task_type: str) -> list[float]:
            raise RuntimeError("gemini unavailable")

        provider._gemini_embedding = _raise
        with pytest.raises(RuntimeError, match="gemini unavailable"):
            await provider.embed_text("strict failure check")

    _run(scenario())
