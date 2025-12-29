"""
Gemini Integration Module
Exports key rotation and resilient client components
"""

from shared.gemini.client import ResilientGeminiClient
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
    "ResilientGeminiClient",
    "GeminiKeyManager",
    "GeminiKeyRotationError",
    "QuotaExceededError",
    "AllKeysExhaustedError",
    "NoValidKeysError",
    "InvalidKeyConfigError",
    "GeminiAPICallError",
]
