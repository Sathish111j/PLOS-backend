import os
from dataclasses import dataclass
from functools import lru_cache

from shared.utils.unified_config import get_unified_settings


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class KnowledgeBaseConfig:
    service_name: str
    service_port: int
    log_level: str
    app_env: str
    debug: bool
    qdrant_url: str
    qdrant_collection: str
    qdrant_fallback_collection: str
    embedding_model: str
    embedding_dimensions: int
    embedding_batch_size: int
    embedding_retry_max_attempts: int
    embedding_cache_ttl_seconds: int
    embedding_dlq_replay_enabled: bool
    embedding_dlq_replay_interval_seconds: int
    embedding_dlq_replay_batch_size: int
    embedding_dlq_replay_max_attempts: int
    embedding_queue_enabled: bool
    celery_broker_url: str
    celery_backend_url: str
    minio_enabled: bool
    minio_endpoint: str
    minio_secure: bool
    minio_bucket: str
    minio_access_key: str
    minio_secret_key: str
    meilisearch_url: str
    meilisearch_master_key: str
    meilisearch_index: str
    database_url: str
    redis_url: str
    # --- graph ---
    graph_enabled: bool
    graph_db_path: str
    graph_ner_window_tokens: int
    graph_ner_overlap_tokens: int
    graph_ner_confidence_threshold: float
    graph_disambig_vector_high: float
    graph_disambig_vector_low: float
    graph_wikidata_cache_ttl_seconds: int
    graph_pagerank_damping: float
    graph_pagerank_iterations: int
    graph_celery_queue: str
    # --- RAG ---
    rag_model: str
    rag_max_context_tokens: int
    rag_max_chunks: int
    rag_conversation_max_messages: int
    rag_session_ttl_hours: int
    rag_stream_enabled: bool
    context_broker_url: str
    cors_origins: str

    @property
    def minio_health_url(self) -> str:
        protocol = "https" if self.minio_secure else "http"
        endpoint = self.minio_endpoint.replace("http://", "").replace("https://", "")
        return f"{protocol}://{endpoint}/minio/health/live"


@lru_cache()
def get_kb_config() -> KnowledgeBaseConfig:
    """Build KnowledgeBaseConfig from UnifiedSettings (single source of truth)."""
    u = get_unified_settings()

    # A few overrides may still arrive as env vars that are specific to
    # the knowledge-base deployment and not present in UnifiedSettings.
    # We prefer the unified value but allow a local env-var override.
    return KnowledgeBaseConfig(
        service_name=os.getenv("SERVICE_NAME", u.service_name),
        service_port=int(os.getenv("PORT", str(u.service_port))),
        log_level=u.log_level,
        app_env=u.app_env,
        debug=u.debug,
        qdrant_url=u.qdrant_url,
        qdrant_collection=u.qdrant_collection,
        qdrant_fallback_collection=u.qdrant_fallback_collection,
        embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", u.embedding_model),
        embedding_dimensions=u.embedding_dimensions,
        embedding_batch_size=u.embedding_batch_size,
        embedding_retry_max_attempts=u.embedding_retry_max_attempts,
        embedding_cache_ttl_seconds=u.embedding_cache_ttl_seconds,
        embedding_dlq_replay_enabled=u.embedding_dlq_replay_enabled,
        embedding_dlq_replay_interval_seconds=u.embedding_dlq_replay_interval_seconds,
        embedding_dlq_replay_batch_size=u.embedding_dlq_replay_batch_size,
        embedding_dlq_replay_max_attempts=u.embedding_dlq_replay_max_attempts,
        embedding_queue_enabled=u.embedding_queue_enabled,
        celery_broker_url=u.celery_broker_url or u.redis_url,
        celery_backend_url=u.celery_backend_url or u.redis_url,
        minio_enabled=u.minio_enabled,
        minio_endpoint=u.minio_endpoint,
        minio_secure=u.minio_secure,
        minio_bucket=u.minio_bucket,
        minio_access_key=u.minio_access_key,
        minio_secret_key=u.minio_secret_key,
        meilisearch_url=u.meilisearch_url,
        meilisearch_master_key=u.meilisearch_master_key,
        meilisearch_index=u.meilisearch_index,
        database_url=u.database_url or u.postgres_async_url,
        redis_url=u.redis_url,
        graph_enabled=u.graph_enabled,
        graph_db_path=u.graph_db_path,
        graph_ner_window_tokens=u.graph_ner_window_tokens,
        graph_ner_overlap_tokens=u.graph_ner_overlap_tokens,
        graph_ner_confidence_threshold=u.graph_ner_confidence_threshold,
        graph_disambig_vector_high=u.graph_disambig_vector_high,
        graph_disambig_vector_low=u.graph_disambig_vector_low,
        graph_wikidata_cache_ttl_seconds=u.graph_wikidata_cache_ttl_seconds,
        graph_pagerank_damping=u.graph_pagerank_damping,
        graph_pagerank_iterations=u.graph_pagerank_iterations,
        graph_celery_queue=u.graph_celery_queue,
        rag_model=u.rag_model,
        rag_max_context_tokens=u.rag_max_context_tokens,
        rag_max_chunks=u.rag_max_chunks,
        rag_conversation_max_messages=u.rag_conversation_max_messages,
        rag_session_ttl_hours=u.rag_session_ttl_hours,
        rag_stream_enabled=u.rag_stream_enabled,
        context_broker_url=u.context_broker_url,
        cors_origins=u.cors_origins,
    )
