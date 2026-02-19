import os
from dataclasses import dataclass
from functools import lru_cache

from shared.utils.unified_config import get_unified_settings


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

    @property
    def minio_health_url(self) -> str:
        protocol = "https" if self.minio_secure else "http"
        endpoint = self.minio_endpoint.replace("http://", "").replace("https://", "")
        return f"{protocol}://{endpoint}/minio/health/live"


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache()
def get_kb_config() -> KnowledgeBaseConfig:
    unified = get_unified_settings()
    return KnowledgeBaseConfig(
        service_name=os.getenv("SERVICE_NAME", "knowledge-base"),
        service_port=int(os.getenv("PORT", str(unified.service_port))),
        log_level=os.getenv("LOG_LEVEL", unified.log_level),
        app_env=os.getenv("APP_ENV", unified.app_env),
        debug=_parse_bool(os.getenv("DEBUG"), unified.debug),
        qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "documents_768"),
        qdrant_fallback_collection=os.getenv(
            "QDRANT_FALLBACK_COLLECTION", "documents_fallback_384"
        ),
        embedding_model=os.getenv("EMBEDDING_MODEL", "gemini-embedding-001"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
        embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "100")),
        embedding_retry_max_attempts=int(
            os.getenv("EMBEDDING_RETRY_MAX_ATTEMPTS", "5")
        ),
        embedding_cache_ttl_seconds=int(
            os.getenv("EMBEDDING_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60))
        ),
        embedding_dlq_replay_enabled=_parse_bool(
            os.getenv("EMBEDDING_DLQ_REPLAY_ENABLED"),
            True,
        ),
        embedding_dlq_replay_interval_seconds=int(
            os.getenv("EMBEDDING_DLQ_REPLAY_INTERVAL_SECONDS", "30")
        ),
        embedding_dlq_replay_batch_size=int(
            os.getenv("EMBEDDING_DLQ_REPLAY_BATCH_SIZE", "10")
        ),
        embedding_dlq_replay_max_attempts=int(
            os.getenv("EMBEDDING_DLQ_REPLAY_MAX_ATTEMPTS", "3")
        ),
        embedding_queue_enabled=_parse_bool(
            os.getenv("EMBEDDING_QUEUE_ENABLED"),
            False,
        ),
        celery_broker_url=os.getenv(
            "CELERY_BROKER_URL",
            os.getenv("REDIS_URL", "redis://:plos_redis_secure_2025@redis:6379/0"),
        ),
        celery_backend_url=os.getenv(
            "CELERY_BACKEND_URL",
            os.getenv("REDIS_URL", "redis://:plos_redis_secure_2025@redis:6379/0"),
        ),
        minio_enabled=_parse_bool(os.getenv("MINIO_ENABLED"), True),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
        minio_secure=_parse_bool(os.getenv("MINIO_SECURE"), False),
        minio_bucket=os.getenv("MINIO_BUCKET", "knowledge-base-documents"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "plos_minio_admin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "plos_minio_secure_2026"),
        meilisearch_url=os.getenv("MEILISEARCH_URL", "http://meilisearch:7700"),
        meilisearch_master_key=os.getenv("MEILISEARCH_MASTER_KEY", ""),
        meilisearch_index=os.getenv("MEILISEARCH_INDEX", "kb_chunks"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:plos_db_secure_2025@supabase-db:5432/plos",
        ),
        redis_url=os.getenv(
            "REDIS_URL", "redis://:plos_redis_secure_2025@redis:6379/0"
        ),
        graph_enabled=_parse_bool(os.getenv("GRAPH_ENABLED"), True),
        graph_db_path=os.getenv("GRAPH_DB_PATH", "/var/plos/graph/kuzu_db"),
        graph_ner_window_tokens=int(os.getenv("GRAPH_NER_WINDOW_TOKENS", "2000")),
        graph_ner_overlap_tokens=int(os.getenv("GRAPH_NER_OVERLAP_TOKENS", "200")),
        graph_ner_confidence_threshold=float(
            os.getenv("GRAPH_NER_CONFIDENCE_THRESHOLD", "0.60")
        ),
        graph_disambig_vector_high=float(
            os.getenv("GRAPH_DISAMBIG_VECTOR_HIGH", "0.92")
        ),
        graph_disambig_vector_low=float(
            os.getenv("GRAPH_DISAMBIG_VECTOR_LOW", "0.80")
        ),
        graph_wikidata_cache_ttl_seconds=int(
            os.getenv("GRAPH_WIKIDATA_CACHE_TTL_SECONDS", str(30 * 24 * 60 * 60))
        ),
        graph_pagerank_damping=float(os.getenv("GRAPH_PAGERANK_DAMPING", "0.85")),
        graph_pagerank_iterations=int(os.getenv("GRAPH_PAGERANK_ITERATIONS", "20")),
        graph_celery_queue=os.getenv("GRAPH_CELERY_QUEUE", "graph_extraction"),
    )
