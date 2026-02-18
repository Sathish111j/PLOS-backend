"""
PLOS Context Engine
Core logic for managing user context with improved error handling and metrics.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from shared.models.context import ContextUpdate, UserContext
from shared.utils.logger import get_logger

try:
    from shared.utils.metrics import (
        CONTEXT_RETRIEVAL_DURATION,
        record_cache_access,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

from src.infrastructure.cache_manager import CacheManager
from src.infrastructure.state_manager import StateManager

logger = get_logger(__name__)


class ContextEngine:
    """
    Manages user context - single source of truth.

    Improvements:
    - Added metrics tracking
    - Better error handling with fallbacks
    - Cache invalidation on new entries
    - Health check support
    """

    def __init__(self, state_manager: StateManager, cache_manager: CacheManager):
        self.state_manager = state_manager
        self.cache_manager = cache_manager
        self._last_health_check = None
        self._healthy = True

    async def get_context(self, user_id: UUID) -> Optional[UserContext]:
        """
        Get user context with <50ms target latency.

        Flow:
        1. Check cache first (Redis)
        2. If miss, fetch from database
        3. Aggregate data from multiple sources
        4. Cache result

        Args:
            user_id: User UUID

        Returns:
            UserContext or None (never raises exception)
        """
        import time

        start_time = time.time()

        try:
            # Try cache first
            cached = await self.cache_manager.get_context(user_id)
            if cached:
                logger.debug(f"Cache hit for user {user_id}")
                if METRICS_AVAILABLE:
                    record_cache_access("redis", hit=True)
                    duration = time.time() - start_time
                    CONTEXT_RETRIEVAL_DURATION.labels(source="cache").observe(duration)
                return cached

            # Cache miss - fetch from database
            if METRICS_AVAILABLE:
                record_cache_access("redis", hit=False)

            logger.debug(f"Cache miss for user {user_id}, fetching from DB")
            context = await self.state_manager.fetch_context(user_id)

            if context:
                # Cache for future requests
                await self.cache_manager.set_context(user_id, context)

            if METRICS_AVAILABLE:
                duration = time.time() - start_time
                CONTEXT_RETRIEVAL_DURATION.labels(source="database").observe(duration)

            return context

        except Exception as e:
            logger.error(f"Error getting context for user {user_id}: {e}")
            # Return a minimal context instead of None to prevent downstream failures
            return self._get_minimal_context(user_id)

    async def update_context(self, update: ContextUpdate) -> None:
        """
        Update user context from event.

        Args:
            update: Context update event
        """
        logger.info(f"Updating context for user {update.user_id}: {update.update_type}")

        try:
            # Update database
            await self.state_manager.update_state(update)

            # Invalidate cache to force refresh
            await self.cache_manager.invalidate(update.user_id)

            logger.debug(f"Context updated for user {update.user_id}")

        except Exception as e:
            logger.error(f"Error updating context for user {update.user_id}: {e}")
            # Still try to invalidate cache even if DB update fails
            try:
                await self.cache_manager.invalidate(update.user_id)
            except Exception:
                pass
            raise

    async def invalidate_user_cache(self, user_id: UUID) -> None:
        """
        Explicitly invalidate cache for a user.
        Call this after new journal entries are processed.

        Args:
            user_id: User UUID
        """
        try:
            await self.cache_manager.invalidate(user_id)
            logger.debug(f"Cache invalidated for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for user {user_id}: {e}")

    def _get_minimal_context(self, user_id: UUID) -> UserContext:
        """Return minimal context when errors occur"""
        return UserContext(
            user_id=user_id,
            updated_at=datetime.utcnow(),
        )

    async def get_summary(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get lightweight context summary.

        Args:
            user_id: User UUID

        Returns:
            Summary dict
        """
        context = await self.get_context(user_id)

        if not context:
            return {"error": "User not found"}

        return {
            "user_id": str(user_id),
            "mood_score": context.current_mood_score,
            "energy_level": context.current_energy_level,
            "stress_level": context.current_stress_level,
            "active_goals": context.active_goals_count,
            "pending_tasks": context.pending_tasks_count,
            "updated_at": (
                context.updated_at.isoformat() if context.updated_at else None
            ),
        }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.

        Returns:
            Stats dict
        """
        cache_stats = await self.cache_manager.get_stats()

        return {
            "service": "context-broker",
            "cache": cache_stats,
            "healthy": self._healthy,
            "uptime": "N/A",  # TODO: Implement uptime tracking
        }

    async def health_check(self) -> bool:
        """
        Perform health check on dependencies.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check cache connection
            cache_healthy = await self.cache_manager.health_check()

            # Check database connection
            db_healthy = await self.state_manager.health_check()

            self._healthy = cache_healthy and db_healthy
            self._last_health_check = datetime.utcnow()

            return self._healthy

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._healthy = False
            return False
