"""
PLOS Context Engine
Core logic for managing user context
"""

import sys
from typing import Any, Dict, Optional
from uuid import UUID

sys.path.append("/app")

from shared.models.context import ContextUpdate, UserContext
from shared.utils.logger import get_logger

from .cache_manager import CacheManager
from .state_manager import StateManager

logger = get_logger(__name__)


class ContextEngine:
    """Manages user context - single source of truth"""

    def __init__(self, state_manager: StateManager, cache_manager: CacheManager):
        self.state_manager = state_manager
        self.cache_manager = cache_manager

    async def get_context(self, user_id: UUID) -> Optional[UserContext]:
        """
        Get user context with <50ms target latency

        Flow:
        1. Check cache first (Redis)
        2. If miss, fetch from database
        3. Aggregate data from multiple sources
        4. Cache result

        Args:
            user_id: User UUID

        Returns:
            UserContext or None
        """
        # Try cache first
        cached = await self.cache_manager.get_context(user_id)
        if cached:
            logger.debug(f"Cache hit for user {user_id}")
            return cached

        # Cache miss - fetch from database
        logger.debug(f"Cache miss for user {user_id}, fetching from DB")
        context = await self.state_manager.fetch_context(user_id)

        if context:
            # Cache for future requests
            await self.cache_manager.set_context(user_id, context)

        return context

    async def update_context(self, update: ContextUpdate) -> None:
        """
        Update user context from event

        Args:
            update: Context update event
        """
        logger.info(f"Updating context for user {update.user_id}: {update.update_type}")

        # Update database
        await self.state_manager.update_state(update)

        # Invalidate cache to force refresh
        await self.cache_manager.invalidate(update.user_id)

        logger.debug(f"Context updated for user {update.user_id}")

    async def get_summary(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get lightweight context summary

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
        Get service statistics

        Returns:
            Stats dict
        """
        cache_stats = await self.cache_manager.get_stats()

        return {
            "service": "context-broker",
            "cache": cache_stats,
            "uptime": "N/A",  # TODO: Implement uptime tracking
        }
