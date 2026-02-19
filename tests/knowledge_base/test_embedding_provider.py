import asyncio

import pytest
from app.application.embeddings import GeminiEmbeddingProvider
from app.core.config import get_kb_config


def _run(coroutine):
    return asyncio.run(coroutine)


def test_embedding_provider_outputs_384_dimensions() -> None:
    provider = GeminiEmbeddingProvider(get_kb_config())

    async def scenario() -> None:
        provider._gemini_embedding = lambda _text, task_type: asyncio.sleep(
            0, result=[0.2] * 384
        )
        vector = await provider.embed_text("embedding verification text")
        assert len(vector) == 384

    _run(scenario())


def test_embedding_provider_resize_vector_up_and_down() -> None:
    upscaled = GeminiEmbeddingProvider._resize_vector([1.0, 2.0, 3.0], 6)
    downscaled = GeminiEmbeddingProvider._resize_vector(list(range(1000)), 384)

    assert len(upscaled) == 6
    assert len(downscaled) == 384


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
