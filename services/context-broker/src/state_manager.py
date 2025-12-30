"""
PLOS State Manager
Database operations for user context state with improved health checks.
"""

import sys
from datetime import datetime
from typing import Optional
from uuid import UUID

sys.path.append("/app")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.context import ContextUpdate, UserContext
from shared.utils.config import get_settings
from shared.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


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
                query = text(
                    """
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
                """
                )

                result = session.execute(query, {"user_id": str(user_id)}).fetchone()

                if not result:
                    # User exists but no context yet - return empty context
                    return UserContext(user_id=user_id, updated_at=datetime.utcnow())

                # Convert to UserContext model
                return UserContext(
                    user_id=UUID(result[0]),
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
                # Upsert user context state
                query = text(
                    """
                    INSERT INTO user_context_state (user_id, updated_at)
                    VALUES (:user_id, :updated_at)
                    ON CONFLICT (user_id)
                    DO UPDATE SET updated_at = :updated_at
                """
                )

                session.execute(
                    query,
                    {"user_id": str(update.user_id), "updated_at": update.timestamp},
                )
                session.commit()

                logger.debug(f"State updated for user {update.user_id}")

        except Exception as e:
            logger.error(f"Error updating state: {e}")
            raise
