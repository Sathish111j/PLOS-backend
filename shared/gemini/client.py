"""
Resilient Gemini API Client
Wrapper around Google's Generative AI API with automatic key rotation and error handling
Uses the new google-genai SDK (not the deprecated google-generativeai)
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Union

from google import genai
from google.genai import types

from shared.gemini.config import TaskType, get_gemini_config, get_task_config
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
        self._client: Optional[genai.Client] = None

    @property
    async def raw_client(self) -> genai.Client:
        """
        Get the underlying genai.Client for advanced operations.

        Use this for operations not directly supported by ResilientGeminiClient,
        such as file uploads, multimodal content, etc.

        Note: This ensures API key is configured before returning the client.

        Returns:
            genai.Client instance configured with active API key
        """
        api_key = await self.key_manager.get_active_key()
        self._configure_api_key(api_key)
        return self._client

    def _load_config(
        self,
        rotation_enabled: Optional[bool],
        backoff_seconds: Optional[int],
        max_retries: Optional[int],
    ) -> None:
        """Load configuration from centralized Gemini config"""
        config = get_gemini_config()

        self.rotation_enabled = (
            rotation_enabled
            if rotation_enabled is not None
            else config.rotation_enabled
        )
        self.backoff_seconds = (
            backoff_seconds
            if backoff_seconds is not None
            else config.rotation_backoff_seconds
        )
        self.max_retries = (
            max_retries if max_retries is not None else config.rotation_max_retries
        )

        # Store config reference for model selection
        self._config = config

        logger.info(
            f"ResilientGeminiClient configured: "
            f"rotation={self.rotation_enabled}, "
            f"backoff={self.backoff_seconds}s, "
            f"max_retries={self.max_retries}"
        )

    def _configure_api_key(self, api_key: str) -> None:
        """Configure the Gemini API client with the given key"""
        if self.current_api_key != api_key:
            self._client = genai.Client(api_key=api_key)
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
        prompt: Union[str, List[types.Part]],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Generate content using Gemini API with automatic key rotation.

        Args:
            prompt: The prompt to send to Gemini (string or list of Parts)
            model: Model name (defaults to GEMINI_DEFAULT_MODEL)
            system_instruction: Optional system instruction for the model
            temperature: Optional temperature for generation (0.0 to 2.0)
            max_output_tokens: Optional maximum tokens to generate
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

                # Build generation config if parameters provided
                config_kwargs = {}
                if temperature is not None:
                    config_kwargs["temperature"] = temperature
                if max_output_tokens is not None:
                    config_kwargs["max_output_tokens"] = max_output_tokens
                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction

                config = (
                    types.GenerateContentConfig(**config_kwargs)
                    if config_kwargs
                    else None
                )

                # Use async generate_content from new SDK
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config=config,
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
                    logger.warning(
                        f"Retrying after {wait_time}s due to error: {type(error).__name__}: {error}"
                    )
                    await asyncio.sleep(wait_time)
                    continue

        logger.error(f"Gemini API call failed after {self.max_retries} attempts. Last error: {last_error}")
        raise GeminiAPICallError(
            message=f"Failed to generate content after {self.max_retries} retries",
            original_error=last_error,
            is_quota_error=self._is_quota_error(last_error) if last_error else False,
        )

    async def embed_content(
        self,
        content: Union[str, List[str]],
        model: Optional[str] = None,
        **kwargs,
    ) -> List[float]:
        """
        Generate embeddings using Gemini API with automatic key rotation.

        Args:
            content: The content to embed (string or list of strings)
            model: Model name (defaults to GEMINI_EMBEDDING_MODEL)
            **kwargs: Additional arguments

        Returns:
            list: Embedding vector

        Raises:
            AllKeysExhaustedError: If all API keys are exhausted
            GeminiAPICallError: If the API call fails after retries
        """
        model = model or os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                api_key = await self.key_manager.get_active_key()
                self._configure_api_key(api_key)

                logger.debug(
                    f"Attempting embedding call (attempt {attempt + 1}/{self.max_retries}) "
                    f"with model={model}"
                )

                # Use new SDK embed_content
                result = await asyncio.to_thread(
                    self._client.models.embed_content,
                    model=model,
                    contents=content,
                )

                await self.key_manager.mark_key_request_success(api_key)
                logger.debug("Embedding call successful")

                # New SDK returns embeddings in a different structure
                if hasattr(result, "embeddings") and result.embeddings:
                    return result.embeddings[0].values
                return result.embedding.values

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

    async def generate_for_task(
        self,
        task: TaskType,
        prompt: str,
        **kwargs,
    ) -> str:
        """
        Generate content using task-specific configuration.

        This method uses the centralized config to select the appropriate
        model and parameters for the given task type.

        Args:
            task: The type of task (from TaskType enum)
            prompt: The prompt to send
            **kwargs: Override any task-specific settings

        Returns:
            str: Generated text response
        """
        task_config = get_task_config(task)

        # Use task config as defaults, allow kwargs to override
        model = kwargs.pop("model", task_config.model)
        temperature = kwargs.pop("temperature", task_config.temperature)
        max_output_tokens = kwargs.pop(
            "max_output_tokens", task_config.max_output_tokens
        )
        system_instruction = kwargs.pop(
            "system_instruction", task_config.system_instruction
        )

        return await self.generate_content(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
            **kwargs,
        )

    def get_model_for_service(self, service_name: str) -> str:
        """
        Get the configured model for a specific service.

        Args:
            service_name: Name of the service (journal-parser, knowledge-system, etc.)

        Returns:
            str: Model name to use
        """
        return self._config.get_model_for_service(service_name)

    def get_model_for_task(self, task: TaskType) -> str:
        """
        Get the configured model for a specific task type.

        Args:
            task: TaskType enum value

        Returns:
            str: Model name to use
        """
        return self._config.get_model_for_task(task)
