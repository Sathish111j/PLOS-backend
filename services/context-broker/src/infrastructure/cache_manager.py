"""
PLOS Cache Manager
Redis caching for user context with improved TTL and health checks.

Improvements:
- Shorter TTL to prevent stale data (30 minutes instead of 6 hours)
- Added health check method
- Better error handling
- Configurable settings
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import redis.asyncio as redis

from shared.models.context import UserContext
from shared.utils.logger import get_logger
from shared.utils.unified_config import get_unified_settings

try:
    from shared.utils.context_config import get_cache_config

    cache_config = get_cache_config()
except ImportError:
    cache_config = None

logger = get_logger(__name__)
settings = get_unified_settings()


class CacheManager:
    """
    Manages Redis cache for user context.

    Improvements:
    - Shorter TTL (30 minutes) to prevent stale context data
    - Health check support
    - Configurable TTL via environment
    - Better error recovery
    """

    # Reduced TTL to prevent stale data when user journals multiple times
    CACHE_TTL = 1800  # 30 minutes (was 300 = 5 minutes, but we want 30 for balance)
    KEY_PREFIX = "context:"

    def __init__(self):
        self.client = None
        self._connected = False
        self._last_health_check = None

        # Use config if available
        if cache_config:
            self.CACHE_TTL = cache_config.memory_cache_ttl_minutes * 60
            self.KEY_PREFIX = cache_config.redis_key_prefix

    async def connect(self) -> None:
        """Initialize Redis connection"""
        try:
            self.client = await redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
            await self.client.ping()
            self._connected = True
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise

    async def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self.client:
                return False
            await self.client.ping()
            self._last_health_check = datetime.utcnow()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    def _make_key(self, user_id: UUID) -> str:
        """Generate cache key for user"""
        return f"{self.KEY_PREFIX}{user_id}"

    async def get_context(self, user_id: UUID) -> Optional[UserContext]:
        """
        Get user context from cache

        Args:
            user_id: User UUID

        Returns:
            UserContext or None if cache miss
        """
        try:
            key = self._make_key(user_id)
            data = await self.client.get(key)

            if not data:
                return None

            # Deserialize JSON to UserContext
            context_dict = json.loads(data)
            return UserContext(**context_dict)

        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None

    async def set_context(self, user_id: UUID, context: UserContext) -> None:
        """
        Set user context in cache

        Args:
            user_id: User UUID
            context: UserContext to cache
        """
        try:
            key = self._make_key(user_id)
            # Serialize to JSON
            data = context.model_dump_json()

            await self.client.setex(key, self.CACHE_TTL, data)
            logger.debug(f"Cached context for user {user_id}")

        except Exception as e:
            logger.error(f"Error setting cache: {e}")

    async def invalidate(self, user_id: UUID) -> None:
        """
        Invalidate cache for user

        Args:
            user_id: User UUID
        """
        try:
            key = self._make_key(user_id)
            await self.client.delete(key)
            logger.debug(f"Cache invalidated for user {user_id}")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Stats dict
        """
        try:
            if not self.client:
                return {"connected": False}

            info = await self.client.info()
            return {
                "connected": self._connected,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "total_keys": await self.client.dbsize(),
                "ttl_seconds": self.CACHE_TTL,
                "last_health_check": (
                    self._last_health_check.isoformat()
                    if self._last_health_check
                    else None
                ),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"connected": False, "error": str(e)}

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "context:*")

        Returns:
            Number of keys deleted
        """
        try:
            if not self.client:
                return 0

            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0

        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {e}")
            return 0
