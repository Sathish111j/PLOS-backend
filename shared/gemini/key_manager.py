"""
Gemini API Key Manager
Manages API key rotation based on quota usage and error detection
"""

import asyncio
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from shared.gemini.exceptions import (
    InvalidKeyConfigError,
    NoValidKeysError,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ApiKeyMetrics:
    """Metrics for tracking API key usage and health"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    quota_errors: int = 0
    other_errors: int = 0
    last_used_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None

    def get_error_rate(self) -> float:
        """Get error rate percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100


@dataclass
class ApiKeyConfig:
    """Configuration for a single API key"""

    value: str
    name: str
    is_active: bool = True
    quota_exceeded_at: Optional[datetime] = None
    retry_after: Optional[datetime] = None
    metrics: ApiKeyMetrics = field(default_factory=ApiKeyMetrics)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "is_active": self.is_active,
            "quota_exceeded_at": (
                self.quota_exceeded_at.isoformat() if self.quota_exceeded_at else None
            ),
            "retry_after": self.retry_after.isoformat() if self.retry_after else None,
            "metrics": asdict(self.metrics),
        }


class GeminiKeyManager:
    """
    Manages API key rotation with quota-aware strategy.

    Features:
    - Automatic key rotation on quota exhaustion
    - Configurable backoff periods before key retry
    - Thread-safe key selection
    - Metrics tracking per key
    - Support for unlimited number of keys
    """

    def __init__(
        self,
        rotation_enabled: bool = True,
        backoff_seconds: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize the key manager.

        Args:
            rotation_enabled: Enable automatic key rotation
            backoff_seconds: Seconds to wait before retrying exhausted key
            max_retries: Maximum retry attempts before marking key as exhausted
        """
        self.rotation_enabled = rotation_enabled
        self.backoff_seconds = backoff_seconds
        self.max_retries = max_retries
        self.keys: List[ApiKeyConfig] = []
        self.current_key_index = 0
        self.lock = asyncio.Lock()

        self._parse_keys_from_env()

        if not self.keys:
            raise NoValidKeysError()

        logger.info(
            f"Initialized GeminiKeyManager with {len(self.keys)} keys. "
            f"Rotation: {'enabled' if rotation_enabled else 'disabled'}"
        )

    def _parse_keys_from_env(self) -> None:
        """
        Parse API keys from environment variables.

        Supports two formats:
        1. Comma-separated: key1|name1,key2|name2,key3|name3
        2. Legacy format: GEMINI_API_KEY, GEMINI_API_KEY_2, etc.

        Raises:
            InvalidKeyConfigError: If configuration format is invalid
        """
        keys_str = os.getenv("GEMINI_API_KEYS", "").strip()

        if keys_str:
            self._parse_config_format(keys_str)
        else:
            self._parse_legacy_format()

    def _parse_config_format(self, keys_str: str) -> None:
        """Parse comma-separated key configuration"""
        try:
            for i, key_pair in enumerate(keys_str.split(",")):
                key_pair = key_pair.strip()
                if not key_pair:
                    continue

                parts = key_pair.split("|")
                if len(parts) < 1:
                    continue

                value = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else f"key_{i+1}"

                if not value:
                    raise InvalidKeyConfigError(f"Empty API key at position {i}")

                self.keys.append(ApiKeyConfig(value=value, name=name))
                logger.debug(f"Loaded API key: {name}")

        except Exception as e:
            logger.warning(f"Failed to parse GEMINI_API_KEYS config: {e}")
            raise InvalidKeyConfigError(str(e))

    def _parse_legacy_format(self) -> None:
        """Parse legacy format: GEMINI_API_KEY, GEMINI_API_KEY_2, etc."""
        key_index = 1
        while key_index <= 10:
            env_var = (
                "GEMINI_API_KEY" if key_index == 1 else f"GEMINI_API_KEY_{key_index}"
            )
            key = os.getenv(env_var, "").strip()

            if key:
                name = "primary" if key_index == 1 else f"backup-{key_index-1}"
                self.keys.append(ApiKeyConfig(value=key, name=name))
                logger.debug(f"Loaded API key from {env_var}: {name}")
                key_index += 1
            else:
                break

    async def get_active_key(self) -> str:
        """
        Get the current active API key.

        Returns:
            str: The active API key value

        Raises:
            AllKeysExhaustedError: If all keys are exhausted
        """
        async with self.lock:
            if not self.rotation_enabled or len(self.keys) == 1:
                return self.keys[0].value

            for attempt in range(len(self.keys)):
                key_config = self.keys[self.current_key_index]

                if not key_config.is_active:
                    if (
                        key_config.retry_after
                        and datetime.utcnow() < key_config.retry_after
                    ):
                        self._rotate_to_next_key()
                        continue
                    else:
                        key_config.is_active = True
                        key_config.quota_exceeded_at = None
                        key_config.retry_after = None
                        logger.info(
                            f"Key '{key_config.name}' recovered from quota exhaustion"
                        )
                        return key_config.value

                return key_config.value

            from shared.gemini.exceptions import AllKeysExhaustedError

            raise AllKeysExhaustedError(total_keys=len(self.keys))

    def _rotate_to_next_key(self) -> None:
        """Rotate to the next key in the list"""
        if len(self.keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            logger.debug(f"Rotated to key: {self.keys[self.current_key_index].name}")

    async def mark_key_quota_exceeded(self, api_key: str) -> None:
        """
        Mark an API key as quota-exhausted and rotate to next key.

        Args:
            api_key: The API key that exceeded quota
        """
        async with self.lock:
            for key_config in self.keys:
                if key_config.value == api_key:
                    key_config.is_active = False
                    key_config.quota_exceeded_at = datetime.utcnow()
                    key_config.retry_after = datetime.utcnow() + timedelta(
                        seconds=self.backoff_seconds
                    )
                    key_config.metrics.quota_errors += 1

                    logger.warning(
                        f"API key '{key_config.name}' marked as quota-exhausted. "
                        f"Retry after {self.backoff_seconds}s"
                    )

                    if self.rotation_enabled and len(self.keys) > 1:
                        self._rotate_to_next_key()
                    break

    async def mark_key_request_success(self, api_key: str) -> None:
        """
        Record a successful API request.

        Args:
            api_key: The API key used
        """
        async with self.lock:
            for key_config in self.keys:
                if key_config.value == api_key:
                    key_config.metrics.total_requests += 1
                    key_config.metrics.successful_requests += 1
                    key_config.metrics.last_used_at = datetime.utcnow()
                    break

    async def mark_key_request_error(
        self, api_key: str, error: str, is_quota_error: bool = False
    ) -> None:
        """
        Record a failed API request.

        Args:
            api_key: The API key used
            error: Error message
            is_quota_error: Whether this is a quota-related error
        """
        async with self.lock:
            for key_config in self.keys:
                if key_config.value == api_key:
                    key_config.metrics.total_requests += 1
                    key_config.metrics.failed_requests += 1
                    key_config.metrics.last_error_at = datetime.utcnow()
                    key_config.metrics.last_error_message = error

                    if is_quota_error:
                        key_config.metrics.quota_errors += 1
                    else:
                        key_config.metrics.other_errors += 1
                    break

    def get_metrics(self) -> Dict:
        """
        Get current metrics for all keys.

        Returns:
            dict: Metrics including active keys, error rates, and per-key stats
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_keys": len(self.keys),
            "active_keys": sum(1 for k in self.keys if k.is_active),
            "rotation_enabled": self.rotation_enabled,
            "backoff_seconds": self.backoff_seconds,
            "current_key_index": self.current_key_index,
            "keys": [key.to_dict() for key in self.keys],
        }

    def get_status_summary(self) -> str:
        """
        Get a human-readable status summary.

        Returns:
            str: Formatted status string
        """
        active_count = sum(1 for k in self.keys if k.is_active)
        lines = [
            "Gemini Key Manager Status",
            f"  Total Keys: {len(self.keys)}",
            f"  Active Keys: {active_count}",
            f"  Rotation: {'Enabled' if self.rotation_enabled else 'Disabled'}",
        ]

        for i, key in enumerate(self.keys):
            status = "ACTIVE" if key.is_active else "EXHAUSTED"
            lines.append(
                f"  [{i}] {key.name}: {status} "
                f"(success={key.metrics.successful_requests}, "
                f"failed={key.metrics.failed_requests}, "
                f"error_rate={key.metrics.get_error_rate():.1f}%)"
            )

        return "\n".join(lines)
