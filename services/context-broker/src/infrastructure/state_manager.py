"""
PLOS State Manager
Database operations for user context state with improved health checks.
"""

import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.context import ContextUpdate, UserContext
from shared.utils.logger import get_logger
from shared.utils.unified_config import get_unified_settings

logger = get_logger(__name__)
settings = get_unified_settings()


class StateManager:
    """
    Manages database operations for user state.

    Improvements:
    - Added health check method
    - Better connection management
    - Improved error handling
    """

    def __init__(self):
        self.engine = None
        self.Session = None
        self._connected = False
        self._last_health_check = None

    async def connect(self) -> None:
        """Initialize database connection"""
        try:
            self.engine = create_engine(
                settings.postgres_url, pool_size=10, max_overflow=20, pool_pre_ping=True
            )
            self.Session = sessionmaker(bind=self.engine)
            self._connected = True
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self._connected = False
            raise

    async def close(self) -> None:
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            self._connected = False
            logger.info("Database connection closed")

    async def health_check(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self.Session:
                return False

            with self.Session() as session:
                session.execute(text("SELECT 1"))

            self._last_health_check = datetime.utcnow()
            return True

        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False

    async def fetch_context(self, user_id: UUID) -> Optional[UserContext]:
        """
        Fetch user context from database

        Args:
            user_id: User UUID

        Returns:
            UserContext or None
        """
        try:
            with self.Session() as session:
                # Fetch from user_context_state table
                query = text("""
                    SELECT
                        user_id,
                        current_mood_score,
                        current_energy_level,
                        current_stress_level,
                        sleep_quality_avg_7d,
                        productivity_score_avg_7d,
                        active_goals_count,
                        pending_tasks_count,
                        completed_tasks_today,
                        context_data,
                        updated_at
                    FROM user_context_state
                    WHERE user_id = :user_id
                """)

                result = session.execute(query, {"user_id": str(user_id)}).fetchone()

                if not result:
                    # User exists but no context yet - return empty context
                    return UserContext(user_id=user_id, updated_at=datetime.utcnow())

                raw_user_id = result[0]
                user_id = (
                    raw_user_id
                    if isinstance(raw_user_id, UUID)
                    else UUID(str(raw_user_id))
                )

                # Convert to UserContext model
                return UserContext(
                    user_id=user_id,
                    current_mood_score=result[1],
                    current_energy_level=result[2],
                    current_stress_level=result[3],
                    sleep_quality_avg_7d=float(result[4]) if result[4] else None,
                    productivity_score_avg_7d=float(result[5]) if result[5] else None,
                    active_goals_count=result[6] or 0,
                    pending_tasks_count=result[7] or 0,
                    completed_tasks_today=result[8] or 0,
                    context_data=result[9] or {},
                    updated_at=result[10],
                )

        except Exception as e:
            logger.error(f"Error fetching context for {user_id}: {e}")
            return None

    async def update_state(self, update: ContextUpdate) -> None:
        """
        Update user context state in database

        Args:
            update: Context update event
        """
        try:
            with self.Session() as session:
                data = update.data or {}
                context_data = data.get("context_data")
                context_data_json = (
                    json.dumps(context_data) if context_data is not None else None
                )

                query = text("""
                    INSERT INTO user_context_state (
                        user_id,
                        updated_at,
                        current_mood_score,
                        current_energy_level,
                        current_stress_level,
                        sleep_quality_avg_7d,
                        productivity_score_avg_7d,
                        active_goals_count,
                        pending_tasks_count,
                        completed_tasks_today,
                        context_data
                    )
                    VALUES (
                        :user_id,
                        :updated_at,
                        :current_mood_score,
                        :current_energy_level,
                        :current_stress_level,
                        :sleep_quality_avg_7d,
                        :productivity_score_avg_7d,
                        :active_goals_count,
                        :pending_tasks_count,
                        :completed_tasks_today,
                        :context_data
                    )
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        updated_at = :updated_at,
                        current_mood_score = COALESCE(:current_mood_score, user_context_state.current_mood_score),
                        current_energy_level = COALESCE(:current_energy_level, user_context_state.current_energy_level),
                        current_stress_level = COALESCE(:current_stress_level, user_context_state.current_stress_level),
                        sleep_quality_avg_7d = COALESCE(:sleep_quality_avg_7d, user_context_state.sleep_quality_avg_7d),
                        productivity_score_avg_7d = COALESCE(:productivity_score_avg_7d, user_context_state.productivity_score_avg_7d),
                        active_goals_count = COALESCE(:active_goals_count, user_context_state.active_goals_count),
                        pending_tasks_count = COALESCE(:pending_tasks_count, user_context_state.pending_tasks_count),
                        completed_tasks_today = COALESCE(:completed_tasks_today, user_context_state.completed_tasks_today),
                        context_data = CASE
                            WHEN :context_data IS NULL THEN user_context_state.context_data
                            ELSE COALESCE(user_context_state.context_data, '{}'::jsonb) || CAST(:context_data AS jsonb)
                        END
                """)

                session.execute(
                    query,
                    {
                        "user_id": str(update.user_id),
                        "updated_at": update.timestamp,
                        "current_mood_score": data.get("current_mood_score"),
                        "current_energy_level": data.get("current_energy_level"),
                        "current_stress_level": data.get("current_stress_level"),
                        "sleep_quality_avg_7d": data.get("sleep_quality_avg_7d"),
                        "productivity_score_avg_7d": data.get(
                            "productivity_score_avg_7d"
                        ),
                        "active_goals_count": data.get("active_goals_count"),
                        "pending_tasks_count": data.get("pending_tasks_count"),
                        "completed_tasks_today": data.get("completed_tasks_today"),
                        "context_data": context_data_json,
                    },
                )
                session.commit()

                logger.debug(f"State updated for user {update.user_id}")

        except Exception as e:
            logger.error(f"Error updating state: {e}")
            raise
