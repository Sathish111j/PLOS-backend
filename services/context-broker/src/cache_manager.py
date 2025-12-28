"""
PLOS Cache Manager
Redis caching for user context
"""

import json
import sys
from typing import Any, Dict, Optional
from uuid import UUID

sys.path.append("/app")

import redis.asyncio as redis

from shared.models.context import UserContext
from shared.utils.config import get_settings
from shared.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CacheManager:
    """Manages Redis cache for user context"""

    CACHE_TTL = 300  # 5 minutes
    KEY_PREFIX = "context:"

    def __init__(self):
        self.client = None

    async def connect(self) -> None:
        """Initialize Redis connection"""
        try:
            self.client = await redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
            await self.client.ping()
            logger.info("✓ Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")

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
        Get cache statistics

        Returns:
            Stats dict
        """
        try:
            info = await self.client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "total_keys": await self.client.dbsize(),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
