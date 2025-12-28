"""
PLOS State Manager
Database operations for user context state
"""

from uuid import UUID
from typing import Optional
from datetime import datetime
import sys
sys.path.append('/app')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from shared.models.context import UserContext, ContextUpdate
from shared.utils.logger import get_logger
from shared.utils.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class StateManager:
    """Manages database operations for user state"""
    
    def __init__(self):
        self.engine = None
        self.Session = None
    
    async def connect(self) -> None:
        """Initialize database connection"""
        try:
            self.engine = create_engine(
                settings.postgres_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            self.Session = sessionmaker(bind=self.engine)
            logger.info("✓ Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
    
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
                    return UserContext(
                        user_id=user_id,
                        updated_at=datetime.utcnow()
                    )
                
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
                    updated_at=result[10]
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
                query = text("""
                    INSERT INTO user_context_state (user_id, updated_at)
                    VALUES (:user_id, :updated_at)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET updated_at = :updated_at
                """)
                
                session.execute(query, {
                    "user_id": str(update.user_id),
                    "updated_at": update.timestamp
                })
                session.commit()
                
                logger.debug(f"State updated for user {update.user_id}")
                
        except Exception as e:
            logger.error(f"Error updating state: {e}")
            raise
