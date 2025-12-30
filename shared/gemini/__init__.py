"""
Gemini Integration Module
Exports key rotation, resilient client, and configuration components
"""

from shared.gemini.client import ResilientGeminiClient
from shared.gemini.config import (
    DEFAULT_MODEL,
    EMBEDDING_MODEL,
    PRO_MODEL,
    TASK_CONFIGS,
    GeminiConfig,
    GeminiModelType,
    ModelConfig,
    TaskType,
    get_embedding_model,
    get_gemini_config,
    get_model_for_service,
    get_task_config,
)
from shared.gemini.exceptions import (
    AllKeysExhaustedError,
    GeminiAPICallError,
    GeminiKeyRotationError,
    InvalidKeyConfigError,
    NoValidKeysError,
    QuotaExceededError,
)
from shared.gemini.key_manager import GeminiKeyManager

__all__ = [
    # Client
    "ResilientGeminiClient",
    # Config
    "GeminiConfig",
    "GeminiModelType",
    "TaskType",
    "ModelConfig",
    "TASK_CONFIGS",
    "get_gemini_config",
    "get_task_config",
    "get_model_for_service",
    "get_embedding_model",
    "DEFAULT_MODEL",
    "EMBEDDING_MODEL",
    "PRO_MODEL",
    # Key Manager
    "GeminiKeyManager",
    # Exceptions
    "GeminiKeyRotationError",
    "QuotaExceededError",
    "AllKeysExhaustedError",
    "NoValidKeysError",
    "InvalidKeyConfigError",
    "GeminiAPICallError",
]
