from __future__ import annotations

from app.application.embeddings import GeminiEmbeddingProvider
from app.core.config import get_kb_config
from celery import Celery

from shared.gemini import ResilientGeminiClient

config = get_kb_config()
celery_app = Celery(
    "knowledge_base_embeddings",
    broker=config.celery_broker_url,
    backend=config.celery_backend_url,
)
celery_app.conf.task_default_queue = "kb-embeddings"

# Single Gemini client for the embedding worker process
_gemini_client: ResilientGeminiClient | None = None
try:
    _gemini_client = ResilientGeminiClient()
except Exception:
    pass


@celery_app.task(name="knowledge_base.embed_batch")
def embed_batch(
    *,
    texts: list[str],
    embedding_model: str,
    embedding_dimensions: int,
    retry_max_attempts: int,
) -> dict[str, list[list[float]]]:
    import asyncio

    provider = GeminiEmbeddingProvider(config, gemini_client=_gemini_client)
    provider._embedding_model = embedding_model
    provider._dimensions = int(embedding_dimensions)
    provider._max_attempts = int(retry_max_attempts)

    async def _run() -> list[list[float]]:
        return await provider.embed_documents_batch(texts)

    vectors = asyncio.run(_run())
    return {"vectors": vectors}
