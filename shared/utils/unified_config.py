"""
PLOS Unified Configuration Management
Single source of truth for all application settings
Industry-standard configuration using Pydantic Settings v2
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Optional

from pydantic import Field
from pydantic_settings import BaseSettings

# Lazy imports to avoid circular dependencies and unnecessary deps
if TYPE_CHECKING:
    pass


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

    # =========================================================================
    # APPLICATION SETTINGS
    # =========================================================================
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
        default="gemini-2.5-flash", description="Default model"
    )
    gemini_pro_model: str = Field(default="gemini-2.5-pro", description="Pro model")
    gemini_vision_model: str = Field(
        default="gemini-2.5-flash", description="Vision model"
    )
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", description="Embedding model"
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
    # EXTERNAL SERVICES
    # =========================================================================
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")

    # =========================================================================
    # SPECIALIZED CONFIGURATION ACCESSORS
    # =========================================================================

    @property
    def gemini_config(self):
        """Get specialized Gemini configuration (lazy import)"""
        from shared.gemini.config import GeminiConfig

        return GeminiConfig(
            api_key=self.gemini_api_key,
            api_keys=self.gemini_api_keys,
            rotation_enabled=self.gemini_api_key_rotation_enabled,
            rotation_max_retries=self.gemini_api_key_rotation_max_retries,
            rotation_backoff_seconds=self.gemini_api_key_rotation_backoff_seconds,
            default_model=self.gemini_default_model,
            pro_model=self.gemini_pro_model,
            vision_model=self.gemini_vision_model,
            embedding_model=self.gemini_embedding_model,
            use_caching=self.use_gemini_caching,
        )

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

    @property
    def metrics_config(self):
        """Get specialized metrics configuration (lazy import)"""
        from shared.utils.context_config import MetricsConfig

        return MetricsConfig()


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
