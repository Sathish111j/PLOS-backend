"""
Gemini Configuration Module
Centralized configuration for all Gemini AI models and settings.
This module provides industry-standard configuration management for AI services.
"""

import os
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Dict, Optional

from pydantic import BaseModel, Field


class GeminiModelType(str, Enum):
    """Available Gemini model types for different use cases"""

    # Text Generation Models
    FLASH = "gemini-3-flash-preview"  # Balanced speed + quality for most tasks
    PRO = "gemini-3.1-pro-preview"  # Most capable for complex tasks
    FLASH_LITE = "gemini-3.1-flash-lite-preview"  # Fastest, lowest cost

    # Embedding Models
    EMBEDDING = "gemini-embedding-001"  # Production embedding model
    EMBEDDING_LEGACY = "text-embedding-004"  # Legacy embedding model


class TaskType(str, Enum):
    """Task types that determine which model to use"""

    # Journal Parser Tasks
    JOURNAL_EXTRACTION = "journal_extraction"
    GAP_DETECTION = "gap_detection"
    QUALITY_SCORING = "quality_scoring"

    # Context Broker Tasks
    CONTEXT_ANALYSIS = "context_analysis"
    PATTERN_DETECTION = "pattern_detection"

    # Embedding Tasks
    TEXT_EMBEDDING = "text_embedding"
    DOCUMENT_EMBEDDING = "document_embedding"

    # RAG Tasks
    RAG_GENERATION = "rag_generation"
    RAG_QUERY_REWRITE = "rag_query_rewrite"

    # Social Media Tasks
    SOCIAL_MEDIA_EXTRACTION = "social_media_extraction"

    # General Tasks
    GENERAL = "general"
    VISION = "vision"


@dataclass
class ModelConfig:
    """Configuration for a specific model use case"""

    model: str
    temperature: float = 0.7
    max_output_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40
    system_instruction: Optional[str] = None
    description: str = ""


class GeminiConfig(BaseModel):
    """
    Central Gemini configuration.
    All model configurations are defined here and can be overridden via environment variables.
    """

    model_config = {"protected_namespaces": ()}

    # API Key Configuration
    api_key: Optional[str] = Field(default=None, description="Single API key")
    api_keys: Optional[str] = Field(
        default=None, description="Multiple API keys (format: key1|name1,key2|name2)"
    )

    # Key Rotation Settings
    rotation_enabled: bool = Field(default=True, description="Enable API key rotation")
    rotation_max_retries: int = Field(
        default=5, description="Max retries before giving up"
    )
    rotation_backoff_seconds: int = Field(
        default=60, description="Seconds to wait before retrying exhausted key"
    )

    # Default Models for Different Use Cases
    default_model: str = Field(
        default="gemini-3-flash-preview", description="Default model for general tasks"
    )
    pro_model: str = Field(
        default="gemini-3.1-pro-preview",
        description="Model for complex/important tasks",
    )
    flash_model: str = Field(
        default="gemini-3-flash-preview", description="Fast model for quick tasks"
    )
    flash_lite_model: str = Field(
        default="gemini-3.1-flash-lite-preview",
        description="Cost-efficient model for high-volume tasks",
    )
    vision_model: str = Field(
        default="gemini-3-flash-preview", description="Model for vision/image tasks"
    )
    embedding_model: str = Field(
        default="gemini-embedding-001", description="Model for embeddings"
    )

    # Service-Specific Model Overrides
    journal_parser_model: Optional[str] = Field(
        default=None, description="Override model for journal-parser service"
    )
    context_broker_model: Optional[str] = Field(
        default=None, description="Override model for context-broker service"
    )

    # Caching
    use_caching: bool = Field(default=True, description="Enable response caching")

    # Generation Defaults
    # Gemini 3 docs strongly recommend temperature=1.0 for best reasoning.
    # Lower values may cause looping or degraded performance.
    default_temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    default_max_tokens: int = Field(default=8192, ge=1, le=1000000)

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        """Load configuration from environment variables"""
        return cls(
            api_key=os.getenv("GEMINI_API_KEY"),
            api_keys=os.getenv("GEMINI_API_KEYS"),
            rotation_enabled=os.getenv(
                "GEMINI_API_KEY_ROTATION_ENABLED", "true"
            ).lower()
            == "true",
            rotation_max_retries=int(
                os.getenv("GEMINI_API_KEY_ROTATION_MAX_RETRIES", "5")
            ),
            rotation_backoff_seconds=int(
                os.getenv("GEMINI_API_KEY_ROTATION_BACKOFF_SECONDS", "60")
            ),
            default_model=os.getenv("GEMINI_DEFAULT_MODEL", "gemini-3-flash-preview"),
            pro_model=os.getenv("GEMINI_PRO_MODEL", "gemini-3.1-pro-preview"),
            flash_model=os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
            flash_lite_model=os.getenv(
                "GEMINI_FLASH_LITE_MODEL", "gemini-3.1-flash-lite-preview"
            ),
            vision_model=os.getenv("GEMINI_VISION_MODEL", "gemini-3-flash-preview"),
            embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
            journal_parser_model=os.getenv("GEMINI_JOURNAL_PARSER_MODEL"),
            context_broker_model=os.getenv("GEMINI_CONTEXT_BROKER_MODEL"),
            use_caching=os.getenv("USE_GEMINI_CACHING", "true").lower() == "true",
            default_temperature=float(os.getenv("GEMINI_DEFAULT_TEMPERATURE", "1.0")),
            default_max_tokens=int(os.getenv("GEMINI_DEFAULT_MAX_TOKENS", "8192")),
        )

    def get_model_for_service(self, service_name: str) -> str:
        """
        Get the appropriate model for a specific service.

        Args:
            service_name: Name of the service (journal-parser, context-broker)

        Returns:
            str: Model name to use
        """
        service_models = {
            "journal-parser": self.journal_parser_model,
            "context-broker": self.context_broker_model,
        }

        # Return service-specific model if configured, otherwise default
        return service_models.get(service_name) or self.default_model

    def get_model_for_task(self, task: TaskType) -> str:
        """
        Get the appropriate model for a specific task type.

        Args:
            task: The type of task to perform

        Returns:
            str: Model name to use
        """
        task_models = {
            # Journal Parser - use flash for speed
            TaskType.JOURNAL_EXTRACTION: self.flash_model,
            TaskType.GAP_DETECTION: self.flash_model,
            TaskType.QUALITY_SCORING: self.flash_model,
            # Context Broker
            TaskType.CONTEXT_ANALYSIS: self.flash_model,
            TaskType.PATTERN_DETECTION: self.flash_model,
            # RAG
            TaskType.RAG_GENERATION: self.flash_lite_model,
            TaskType.RAG_QUERY_REWRITE: self.flash_lite_model,
            # Embeddings
            TaskType.TEXT_EMBEDDING: self.embedding_model,
            TaskType.DOCUMENT_EMBEDDING: self.embedding_model,
            # General
            TaskType.GENERAL: self.default_model,
            TaskType.VISION: self.vision_model,
        }

        return task_models.get(task, self.default_model)


# Task-specific model configurations with optimized parameters
TASK_CONFIGS: Dict[TaskType, ModelConfig] = {
    TaskType.JOURNAL_EXTRACTION: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.3,  # Lower for more consistent extraction
        max_output_tokens=8192,
        description="Extract structured data from journal entries",
        system_instruction="""You are a precise data extraction assistant.
Extract structured information from journal entries accurately and consistently.
Focus on: sleep, mood, activities, meals, and notable events.""",
    ),
    TaskType.GAP_DETECTION: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.5,
        max_output_tokens=2048,
        description="Detect ambiguous or missing information in journal entries",
    ),
    TaskType.QUALITY_SCORING: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.2,  # Very low for consistent scoring
        max_output_tokens=1024,
        description="Score extraction quality and confidence",
    ),
    TaskType.CONTEXT_ANALYSIS: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.3,
        max_output_tokens=4096,
        description="Analyze user context and patterns",
    ),
    TaskType.PATTERN_DETECTION: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.4,
        max_output_tokens=4096,
        description="Detect patterns in user behavior",
    ),
    TaskType.GENERAL: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.7,
        max_output_tokens=8192,
        description="General purpose generation",
    ),
    TaskType.VISION: ModelConfig(
        model="gemini-3-flash-preview",
        temperature=0.5,
        max_output_tokens=4096,
        description="Vision and image analysis",
    ),
    TaskType.RAG_GENERATION: ModelConfig(
        model="gemini-3.1-flash-lite-preview",
        temperature=0.4,
        max_output_tokens=16384,
        top_p=0.92,
        description="RAG answer generation with citations",
        system_instruction=(
            "You are a helpful knowledge assistant. Answer the user's question "
            "using ONLY the provided context chunks. For every factual claim, "
            "include an inline citation like [1], [2], etc. referring to the "
            "chunk index. If the context does not contain enough information, "
            "say so honestly. Never fabricate information."
        ),
    ),
    TaskType.RAG_QUERY_REWRITE: ModelConfig(
        model="gemini-3.1-flash-lite-preview",
        temperature=0.2,
        max_output_tokens=512,
        description="Rewrite user query for better retrieval",
    ),
}


@lru_cache()
def get_gemini_config() -> GeminiConfig:
    """
    Get cached Gemini configuration instance.
    Configuration is loaded once and cached for performance.
    """
    return GeminiConfig.from_env()


def get_task_config(task: TaskType) -> ModelConfig:
    """
    Get the configuration for a specific task type.

    Args:
        task: The task type

    Returns:
        ModelConfig: Configuration for the task
    """
    config = get_gemini_config()

    # Get base task config -- return a copy to avoid mutating the global dict
    from dataclasses import replace as _dc_replace

    task_config = TASK_CONFIGS.get(task, TASK_CONFIGS[TaskType.GENERAL])
    task_config = _dc_replace(task_config)

    # Override model from environment if set
    env_model = config.get_model_for_task(task)
    if env_model:
        task_config.model = env_model

    return task_config


def get_model_for_service(service_name: str) -> str:
    """
    Convenience function to get model for a service.

    Args:
        service_name: Name of the service

    Returns:
        str: Model name
    """
    return get_gemini_config().get_model_for_service(service_name)
