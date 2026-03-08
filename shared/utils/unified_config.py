"""
PLOS Unified Configuration Management
Single source of truth for all application settings
Industry-standard configuration using Pydantic Settings v2
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class UnifiedSettings(BaseSettings):
    """
    Unified application settings - Single source of truth

    This replaces the fragmented configuration across:
    - shared.utils.config.Settings
    - shared.gemini.config.GeminiConfig
    - shared.utils.context_config (multiple configs)

    Design Principles:
    1. Single source of truth for all settings
    2. Environment variable driven
    3. Type-safe with Pydantic validation
    4. Cached for performance
    5. Delegate specialized configs to sub-modules
    """

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    # --- APPLICATION SETTINGS ---
    app_env: str = Field(default="development", description="Environment (dev/prod)")
    debug: bool = Field(default=True, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    service_name: str = Field(default="plos-service", description="Service identifier")
    service_port: int = Field(default=8000, description="Service port")

    # =========================================================================
    # DATABASE SETTINGS
    # =========================================================================
    postgres_url: str = Field(
        default="postgresql://postgres:postgres@supabase-db:5432/plos",
        description="PostgreSQL connection URL",
    )

    @property
    def postgres_async_url(self) -> str:
        """Get async-compatible PostgreSQL URL for SQLAlchemy async"""
        return self.postgres_url.replace("postgresql://", "postgresql+asyncpg://")

    # Database Connection Pool Settings
    db_pool_min_size: int = Field(default=5, description="Min DB pool size")
    db_pool_max_size: int = Field(default=20, description="Max DB pool size")
    db_pool_recycle: int = Field(default=3600, description="Connection recycle time")
    db_pool_timeout: int = Field(default=30, description="Pool acquisition timeout")

    # =========================================================================
    # CACHE SETTINGS (Redis)
    # =========================================================================
    redis_url: str = Field(
        default="redis://:redis@localhost:6379/0", description="Redis URL"
    )
    redis_ttl_seconds: int = Field(default=300, description="Redis cache TTL")
    redis_key_prefix: str = Field(default="plos:", description="Redis key prefix")

    # =========================================================================
    # MESSAGE BROKER (Kafka)
    # =========================================================================
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", description="Kafka bootstrap servers"
    )
    kafka_consumer_group: Optional[str] = Field(
        default=None, description="Kafka consumer group"
    )
    kafka_enable_auto_commit: bool = Field(default=True, description="Auto commit")
    kafka_compression_type: str = Field(
        default="gzip", description="Message compression"
    )

    # =========================================================================
    # GEMINI AI SETTINGS
    # =========================================================================
    gemini_api_key: Optional[str] = Field(default=None, description="Single API key")
    gemini_api_keys: Optional[str] = Field(
        default=None, description="Multiple API keys (pipe-separated)"
    )
    gemini_default_model: str = Field(
        default="gemini-3-flash-preview", description="Default model"
    )
    gemini_pro_model: str = Field(
        default="gemini-3.1-pro-preview", description="Pro model"
    )
    gemini_vision_model: str = Field(
        default="gemini-3-flash-preview", description="Vision model"
    )
    gemini_embedding_model: str = Field(
        default="text-embedding-004", description="Embedding model"
    )

    # Gemini API Key Rotation
    gemini_api_key_rotation_enabled: bool = Field(
        default=True, description="Enable key rotation"
    )
    gemini_api_key_rotation_max_retries: int = Field(
        default=3, description="Max retries"
    )
    gemini_api_key_rotation_backoff_seconds: int = Field(
        default=60, description="Backoff time"
    )
    use_gemini_caching: bool = Field(default=True, description="Enable caching")

    # =========================================================================
    # CONTEXT RETRIEVAL SETTINGS
    # =========================================================================
    context_baseline_days: int = Field(
        default=30, description="Days for baseline calculation"
    )
    context_recent_entries_days: int = Field(
        default=7, description="Recent entries window"
    )
    context_cache_ttl_hours: int = Field(default=24, description="Context cache TTL")
    context_min_samples_for_confidence: int = Field(
        default=10, description="Min samples for confidence"
    )

    # =========================================================================
    # SECURITY SETTINGS
    # =========================================================================
    jwt_secret: str = Field(
        default="change-this-in-production", description="JWT secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration: int = Field(default=3600, description="JWT expiration (seconds)")

    # =========================================================================
    # SERVICE PORTS (for reference/routing)
    # =========================================================================
    journal_parser_port: int = Field(default=8002, description="Journal parser port")
    context_broker_port: int = Field(default=8001, description="Context broker port")

    # =========================================================================
    # SERVICE URLS
    # =========================================================================
    context_broker_url: str = Field(
        default="http://context-broker:8001",
        description="Context broker service URL",
    )
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed CORS origins",
    )

    # =========================================================================
    # KNOWLEDGE-BASE SETTINGS
    # =========================================================================
    qdrant_url: str = Field(
        default="http://qdrant:6333", description="Qdrant vector DB URL"
    )
    qdrant_collection: str = Field(
        default="documents_768", description="Primary Qdrant collection"
    )
    qdrant_fallback_collection: str = Field(
        default="documents_fallback_384", description="Fallback Qdrant collection"
    )
    embedding_model: str = Field(
        default="text-embedding-004", description="Embedding model name"
    )
    embedding_dimensions: int = Field(
        default=768, description="Embedding vector dimensions"
    )
    embedding_batch_size: int = Field(default=100, description="Embedding batch size")
    embedding_retry_max_attempts: int = Field(
        default=5, description="Max embedding retry attempts"
    )
    embedding_cache_ttl_seconds: int = Field(
        default=604800, description="Embedding cache TTL (7 days)"
    )
    embedding_dlq_replay_enabled: bool = Field(
        default=True, description="Enable DLQ replay"
    )
    embedding_dlq_replay_interval_seconds: int = Field(
        default=30, description="DLQ replay interval"
    )
    embedding_dlq_replay_batch_size: int = Field(
        default=10, description="DLQ replay batch size"
    )
    embedding_dlq_replay_max_attempts: int = Field(
        default=3, description="DLQ replay max attempts"
    )
    embedding_queue_enabled: bool = Field(
        default=False, description="Enable async embedding queue"
    )
    celery_broker_url: str = Field(default="", description="Celery broker URL")
    celery_backend_url: str = Field(default="", description="Celery backend URL")
    minio_enabled: bool = Field(default=True, description="Enable MinIO storage")
    minio_endpoint: str = Field(default="minio:9000", description="MinIO endpoint")
    minio_secure: bool = Field(default=False, description="MinIO TLS")
    minio_bucket: str = Field(
        default="knowledge-base-documents", description="MinIO bucket"
    )
    minio_access_key: str = Field(default="", description="MinIO access key")
    minio_secret_key: str = Field(default="", description="MinIO secret key")
    meilisearch_url: str = Field(
        default="http://meilisearch:7700", description="Meilisearch URL"
    )
    meilisearch_master_key: str = Field(
        default="", description="Meilisearch master key"
    )
    meilisearch_index: str = Field(default="kb_chunks", description="Meilisearch index")
    database_url: str = Field(default="", description="Async DB URL for knowledge-base")
    graph_enabled: bool = Field(default=True, description="Enable knowledge graph")
    graph_db_path: str = Field(
        default="/var/plos/graph/kuzu_db", description="Graph DB path"
    )
    graph_ner_window_tokens: int = Field(default=2000, description="NER window")
    graph_ner_overlap_tokens: int = Field(default=200, description="NER overlap")
    graph_ner_confidence_threshold: float = Field(
        default=0.60, description="NER confidence"
    )
    graph_disambig_vector_high: float = Field(default=0.92, description="Disambig high")
    graph_disambig_vector_low: float = Field(default=0.80, description="Disambig low")
    graph_wikidata_cache_ttl_seconds: int = Field(
        default=2592000, description="Wikidata cache TTL (30 days)"
    )
    graph_pagerank_damping: float = Field(default=0.85, description="PageRank damping")
    graph_pagerank_iterations: int = Field(
        default=20, description="PageRank iterations"
    )
    graph_celery_queue: str = Field(
        default="graph_extraction", description="Graph Celery queue"
    )
    rag_model: str = Field(default="gemini-3-flash-preview", description="RAG model")
    rag_max_context_tokens: int = Field(
        default=100000, description="RAG max context tokens"
    )
    rag_max_chunks: int = Field(default=15, description="RAG max chunks")
    rag_conversation_max_messages: int = Field(
        default=20, description="RAG max conversation messages"
    )
    rag_session_ttl_hours: int = Field(
        default=168, description="RAG session TTL (hours)"
    )
    rag_stream_enabled: bool = Field(default=True, description="Enable RAG streaming")

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "UnifiedSettings":
        """Prevent startup with the insecure default JWT secret outside development."""
        if (
            self.jwt_secret == "change-this-in-production"
            and self.app_env != "development"
        ):
            raise ValueError(
                "JWT_SECRET is still set to the insecure default "
                "'change-this-in-production'. Set a strong secret via the "
                "JWT_SECRET environment variable before running in "
                f"'{self.app_env}' mode."
            )
        return self

    # =========================================================================
    # SPECIALIZED CONFIGURATION ACCESSORS
    # =========================================================================

    @property
    def context_config(self):
        """Get specialized context retrieval configuration (lazy import)"""
        from shared.utils.context_config import ContextConfig

        return ContextConfig(
            baseline_days=self.context_baseline_days,
            recent_entries_days=self.context_recent_entries_days,
            cache_ttl_hours=self.context_cache_ttl_hours,
            min_samples_for_confidence=self.context_min_samples_for_confidence,
        )

    @property
    def cache_config(self):
        """Get specialized cache configuration (lazy import)"""
        from shared.utils.context_config import CacheConfig

        return CacheConfig(
            redis_ttl_seconds=self.redis_ttl_seconds,
            redis_key_prefix=self.redis_key_prefix,
        )


@lru_cache()
def get_unified_settings() -> UnifiedSettings:
    """
    Get cached unified settings instance

    This is the PRIMARY way to access configuration throughout the application.
    Use this instead of individual config classes.

    Usage:
        from shared.utils.unified_config import get_unified_settings

        settings = get_unified_settings()
        db_url = settings.postgres_async_url
        gemini_cfg = settings.gemini_config
    """
    return UnifiedSettings()


# Backward compatibility - export original function for gradual migration
get_settings = get_unified_settings
