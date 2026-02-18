"""
PLOS - Context Retrieval Configuration
Configuration settings for context retrieval and caching.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class ContextConfig(BaseSettings):
    """Configuration for context retrieval engine"""

    # Baseline calculation
    baseline_days: int = Field(
        default=30, description="Days to calculate baseline from"
    )
    recent_entries_days: int = Field(default=7, description="Days for recent entries")

    # Cache settings
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")
    cache_ttl_minutes: int = Field(
        default=30, description="Memory cache TTL in minutes"
    )

    # Statistical thresholds
    min_samples_for_stdev: int = Field(
        default=2, description="Minimum samples for stddev calculation"
    )
    min_samples_for_confidence: int = Field(
        default=10, description="Samples for full confidence"
    )
    confidence_threshold: float = Field(
        default=0.7, description="Minimum confidence threshold"
    )

    # Query limits
    max_recent_entries: int = Field(
        default=30, description="Max recent entries to fetch"
    )
    max_activity_patterns: int = Field(
        default=50, description="Max activity patterns to return"
    )

    # Default values (population averages)
    default_sleep_hours: float = Field(default=7.0, description="Default sleep hours")
    default_sleep_stddev: float = Field(
        default=1.0, description="Default sleep std deviation"
    )
    default_mood_score: float = Field(default=6.5, description="Default mood score")
    default_mood_stddev: float = Field(
        default=1.5, description="Default mood std deviation"
    )
    default_energy_level: float = Field(default=6.0, description="Default energy level")
    default_energy_stddev: float = Field(
        default=1.5, description="Default energy std deviation"
    )
    default_stress_level: float = Field(default=4.0, description="Default stress level")
    default_stress_stddev: float = Field(
        default=1.5, description="Default stress std deviation"
    )

    # Feature flags
    use_optimized_queries: bool = Field(
        default=True, description="Use JSONB extraction in queries"
    )
    use_upsert_for_cache: bool = Field(
        default=True, description="Use PostgreSQL UPSERT for caching"
    )
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")

    class Config:
        env_prefix = "CONTEXT_"
        case_sensitive = False


class CacheConfig(BaseSettings):
    """Configuration for cache manager"""

    # Redis settings
    redis_ttl_seconds: int = Field(default=300, description="Redis cache TTL")
    redis_key_prefix: str = Field(default="context:", description="Redis key prefix")

    # Memory cache settings
    memory_cache_ttl_minutes: int = Field(
        default=30, description="Memory cache TTL in minutes"
    )
    memory_cache_max_size: int = Field(
        default=1000, description="Max items in memory cache"
    )

    # Cache invalidation
    invalidate_on_new_entry: bool = Field(
        default=True, description="Invalidate cache on new journal entry"
    )

    class Config:
        env_prefix = "CACHE_"
        case_sensitive = False


class MetricsConfig(BaseSettings):
    """Configuration for observability metrics"""

    enable_prometheus: bool = Field(
        default=True, description="Enable Prometheus metrics"
    )
    metrics_port: int = Field(default=9090, description="Prometheus metrics port")

    # Histogram buckets
    latency_buckets: list = Field(
        default=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        description="Latency histogram buckets",
    )

    class Config:
        env_prefix = "METRICS_"
        case_sensitive = False


# Singleton instances
_context_config: Optional[ContextConfig] = None
_cache_config: Optional[CacheConfig] = None


def get_context_config() -> ContextConfig:
    """Get context configuration singleton"""
    global _context_config
    if _context_config is None:
        _context_config = ContextConfig()
    return _context_config


def get_cache_config() -> CacheConfig:
    """Get cache configuration singleton"""
    global _cache_config
    if _cache_config is None:
        _cache_config = CacheConfig()
    return _cache_config
