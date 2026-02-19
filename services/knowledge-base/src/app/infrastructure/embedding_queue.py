from __future__ import annotations

from typing import Any

from app.core.config import KnowledgeBaseConfig


def get_celery_app(config: KnowledgeBaseConfig):
    from celery import Celery

    celery_app = Celery(
        "knowledge_base_embeddings",
        broker=config.celery_broker_url,
        backend=config.celery_backend_url,
    )
    celery_app.conf.task_default_queue = "kb-embeddings"
    celery_app.conf.task_routes = {
        "knowledge_base.embed_batch": {"queue": "kb-embeddings"},
    }
    return celery_app


def run_embedding_task(
    *,
    config: KnowledgeBaseConfig,
    texts: list[str],
    timeout_seconds: int = 120,
) -> list[list[float]]:
    celery_app = get_celery_app(config)
    async_result = celery_app.send_task(
        "knowledge_base.embed_batch",
        kwargs={
            "texts": texts,
            "embedding_model": config.embedding_model,
            "embedding_dimensions": config.embedding_dimensions,
            "retry_max_attempts": config.embedding_retry_max_attempts,
        },
        queue="kb-embeddings",
    )
    payload: Any = async_result.get(timeout=timeout_seconds)
    if not isinstance(payload, dict):
        raise RuntimeError("Celery embedding worker returned invalid payload")

    vectors = payload.get("vectors")
    if not isinstance(vectors, list):
        raise RuntimeError("Celery embedding worker did not return vectors")

    normalized_vectors: list[list[float]] = []
    for vector in vectors:
        normalized_vectors.append([float(value) for value in list(vector)])
    return normalized_vectors
