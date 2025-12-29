"""
Resilient Gemini API Client
Wrapper around Google's Generative AI API with automatic key rotation and error handling
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import google.generativeai as genai

from shared.gemini.exceptions import GeminiAPICallError
from shared.gemini.key_manager import GeminiKeyManager

logger = logging.getLogger(__name__)


class ResilientGeminiClient:
    """
    Resilient Gemini API client with automatic key rotation.

    Features:
    - Automatic API key rotation on quota exhaustion
    - Configurable retry logic with exponential backoff
    - Quota error detection and handling
    - Request tracking and metrics
    - Support for different model types
    """

    def __init__(
        self,
        rotation_enabled: Optional[bool] = None,
        backoff_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize the resilient Gemini client.

        Args:
            rotation_enabled: Override GEMINI_API_KEY_ROTATION_ENABLED env var
            backoff_seconds: Override GEMINI_API_KEY_ROTATION_BACKOFF_SECONDS env var
            max_retries: Override GEMINI_API_KEY_ROTATION_MAX_RETRIES env var
        """
        self._load_config(rotation_enabled, backoff_seconds, max_retries)
        self.key_manager = GeminiKeyManager(
            rotation_enabled=self.rotation_enabled,
            backoff_seconds=self.backoff_seconds,
            max_retries=self.max_retries,
        )
        self.current_api_key: Optional[str] = None

    def _load_config(
        self,
        rotation_enabled: Optional[bool],
        backoff_seconds: Optional[int],
        max_retries: Optional[int],
    ) -> None:
        """Load configuration from environment variables"""
        if rotation_enabled is not None:
            self.rotation_enabled = rotation_enabled
        else:
            self.rotation_enabled = (
                os.getenv("GEMINI_API_KEY_ROTATION_ENABLED", "true").lower() == "true"
            )

        if backoff_seconds is not None:
            self.backoff_seconds = backoff_seconds
        else:
            self.backoff_seconds = int(
                os.getenv("GEMINI_API_KEY_ROTATION_BACKOFF_SECONDS", "60")
            )

        if max_retries is not None:
            self.max_retries = max_retries
        else:
            self.max_retries = int(
                os.getenv("GEMINI_API_KEY_ROTATION_MAX_RETRIES", "3")
            )

        logger.info(
            f"ResilientGeminiClient configured: "
            f"rotation={self.rotation_enabled}, "
            f"backoff={self.backoff_seconds}s, "
            f"max_retries={self.max_retries}"
        )

    def _configure_api_key(self, api_key: str) -> None:
        """Configure the Gemini API with the given key"""
        genai.configure(api_key=api_key)
        self.current_api_key = api_key

    def _is_quota_error(self, error: Exception) -> bool:
        """
        Detect if an error is related to quota exhaustion.

        Checks for common quota error patterns in exception messages.

        Args:
            error: The exception to check

        Returns:
            bool: True if quota-related error
        """
        error_str = str(error).lower()
        quota_indicators = [
            "quota",
            "rate_limit",
            "rate limit",
            "resource_exhausted",
            "429",
            "429 too many requests",
            "too many requests",
        ]
        return any(indicator in error_str for indicator in quota_indicators)

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate content using Gemini API with automatic key rotation.

        Args:
            prompt: The prompt to send to Gemini
            model: Model name (defaults to GEMINI_DEFAULT_MODEL)
            **kwargs: Additional arguments to pass to generate_content

        Returns:
            str: Generated content from Gemini

        Raises:
            AllKeysExhaustedError: If all API keys are exhausted
            GeminiAPICallError: If the API call fails after retries
        """
        model = model or os.getenv("GEMINI_DEFAULT_MODEL", "gemini-2.5-flash")
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                api_key = await self.key_manager.get_active_key()
                self._configure_api_key(api_key)

                logger.debug(
                    f"Attempting Gemini API call (attempt {attempt + 1}/{self.max_retries}) "
                    f"with model={model}, key={self.key_manager.keys[self.key_manager.current_key_index].name}"
                )

                genai_model = genai.GenerativeModel(model)
                response = await asyncio.to_thread(
                    genai_model.generate_content, prompt, **kwargs
                )

                await self.key_manager.mark_key_request_success(api_key)
                logger.debug("Gemini API call successful")

                return response.text

            except Exception as error:
                last_error = error
                is_quota_error = self._is_quota_error(error)
                api_key = self.current_api_key or (
                    await self.key_manager.get_active_key()
                )

                await self.key_manager.mark_key_request_error(
                    api_key=api_key,
                    error=str(error),
                    is_quota_error=is_quota_error,
                )

                if is_quota_error:
                    logger.warning(
                        f"Quota error detected for key {self.key_manager.keys[self.key_manager.current_key_index].name}. "
                        f"Attempting rotation..."
                    )
                    await self.key_manager.mark_key_quota_exceeded(api_key)

                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.info(
                        f"Retrying after {wait_time}s due to error: {type(error).__name__}"
                    )
                    await asyncio.sleep(wait_time)
                    continue

        logger.error(f"Gemini API call failed after {self.max_retries} attempts")
        raise GeminiAPICallError(
            message=f"Failed to generate content after {self.max_retries} retries",
            original_error=last_error,
            is_quota_error=self._is_quota_error(last_error) if last_error else False,
        )

    async def embed_content(
        self,
        content: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> list:
        """
        Generate embeddings using Gemini API with automatic key rotation.

        Args:
            content: The content to embed
            model: Model name (defaults to GEMINI_EMBEDDING_MODEL)
            **kwargs: Additional arguments

        Returns:
            list: Embedding vector

        Raises:
            AllKeysExhaustedError: If all API keys are exhausted
            GeminiAPICallError: If the API call fails after retries
        """
        model = model or os.getenv("GEMINI_EMBEDDING_MODEL", "models/embedding-001")
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                api_key = await self.key_manager.get_active_key()
                self._configure_api_key(api_key)

                logger.debug(
                    f"Attempting embedding call (attempt {attempt + 1}/{self.max_retries}) "
                    f"with model={model}"
                )

                result = await asyncio.to_thread(
                    genai.embed_content, model=model, content=content, **kwargs
                )

                await self.key_manager.mark_key_request_success(api_key)
                logger.debug("Embedding call successful")

                return result["embedding"]

            except Exception as error:
                last_error = error
                is_quota_error = self._is_quota_error(error)
                api_key = self.current_api_key or (
                    await self.key_manager.get_active_key()
                )

                await self.key_manager.mark_key_request_error(
                    api_key=api_key,
                    error=str(error),
                    is_quota_error=is_quota_error,
                )

                if is_quota_error:
                    await self.key_manager.mark_key_quota_exceeded(api_key)

                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                    continue

        raise GeminiAPICallError(
            message=f"Failed to embed content after {self.max_retries} retries",
            original_error=last_error,
            is_quota_error=self._is_quota_error(last_error) if last_error else False,
        )

    def get_key_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for all API keys.

        Returns:
            dict: Metrics including usage statistics and key status
        """
        return self.key_manager.get_metrics()

    def get_status_summary(self) -> str:
        """
        Get a human-readable status summary of all keys.

        Returns:
            str: Formatted status string
        """
        return self.key_manager.get_status_summary()

    def log_status(self) -> None:
        """Log the current status of all keys"""
        logger.info(f"\n{self.get_status_summary()}")
