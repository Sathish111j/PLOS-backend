"""
Gemini API Exceptions
Custom exceptions for Gemini API operations and key rotation
"""

from typing import Optional


class GeminiKeyRotationError(Exception):
    """Base exception for key rotation errors"""

    def __init__(
        self,
        message: str,
        key_name: Optional[str] = None,
        is_quota_error: bool = False,
    ):
        self.message = message
        self.key_name = key_name
        self.is_quota_error = is_quota_error
        super().__init__(self.message)


class QuotaExceededError(GeminiKeyRotationError):
    """Raised when API quota is exceeded for a key"""

    def __init__(self, key_name: str):
        super().__init__(
            message=f"Quota exceeded for API key: {key_name}",
            key_name=key_name,
            is_quota_error=True,
        )


class AllKeysExhaustedError(GeminiKeyRotationError):
    """Raised when all API keys are exhausted"""

    def __init__(self, total_keys: int):
        super().__init__(
            message=f"All {total_keys} API keys are currently exhausted. "
            "Please wait for key recovery.",
            is_quota_error=True,
        )


class NoValidKeysError(GeminiKeyRotationError):
    """Raised when no valid API keys are configured"""

    def __init__(self):
        super().__init__(
            message="No valid API keys configured. Please check GEMINI_API_KEYS environment variable."
        )


class InvalidKeyConfigError(GeminiKeyRotationError):
    """Raised when API key configuration is invalid"""

    def __init__(self, reason: str):
        super().__init__(message=f"Invalid API key configuration: {reason}")


class GeminiAPICallError(GeminiKeyRotationError):
    """Raised when Gemini API call fails"""

    def __init__(
        self,
        message: str,
        key_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
        is_quota_error: bool = False,
    ):
        super().__init__(
            message=message,
            key_name=key_name,
            is_quota_error=is_quota_error,
        )
        self.original_error = original_error
