"""
Gemini Integration Module
Exports key rotation, resilient client, and configuration components
"""

from shared.gemini.client import ResilientGeminiClient
from shared.gemini.config import (
    TASK_CONFIGS,
    GeminiConfig,
    ModelConfig,
    TaskType,
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
    "TaskType",
    "ModelConfig",
    "TASK_CONFIGS",
    "get_gemini_config",
    "get_task_config",
    "get_model_for_service",
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
