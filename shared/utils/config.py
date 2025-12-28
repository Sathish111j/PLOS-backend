"""
PLOS Shared Config
Environment configuration management using Pydantic
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    service_name: str = "plos-service"
    service_port: int = 8000
    
    # Gemini API Configuration
    gemini_api_key: str
    gemini_default_model: str = "gemini-2.0-flash-exp"
    gemini_vision_model: str = "gemini-2.0-flash-exp"
    gemini_pro_model: str = "gemini-2.0-flash-exp"
    use_gemini_caching: bool = True
    
    # PostgreSQL
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/plos"
    
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
