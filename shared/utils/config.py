"""
PLOS Shared Config
Environment configuration management using Pydantic
"""

from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    service_name: str = "plos-service"
    service_port: int = 8000

    # Gemini API Configuration
    gemini_api_key: Optional[str] = None
    gemini_api_keys: Optional[str] = None
    gemini_default_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_embedding_model: str = "gemini-embedding-001"
    use_gemini_caching: bool = True

    # Gemini API Key Rotation Configuration
    gemini_api_key_rotation_enabled: bool = True
    gemini_api_key_rotation_max_retries: int = 3
    gemini_api_key_rotation_backoff_seconds: int = 60

    # PostgreSQL
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/plos"

    @property
    def postgres_async_url(self) -> str:
        """Get async-compatible PostgreSQL URL for SQLAlchemy async"""
        return self.postgres_url.replace("postgresql://", "postgresql+asyncpg://")

    # Redis
    redis_url: str = "redis://:redis@localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: Optional[str] = None

    # Security
    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600

    # Service Ports (for reference)
    journal_parser_port: int = 8002
    context_broker_port: int = 8001

    # Optional External Services
    openai_api_key: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
