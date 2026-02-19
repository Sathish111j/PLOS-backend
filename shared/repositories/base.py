"""
PLOS Database Repository Pattern
Industry-standard data access layer abstraction

This module implements the Repository Pattern to:
1. Separate business logic from data access
2. Provide testable database operations
3. Enable easy mocking for unit tests
4. Centralize database query logic
5. Support multiple storage backends
"""

from abc import ABC
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# BASE REPOSITORY (Abstract)
# ============================================================================


class BaseRepository(ABC):
    """Base repository with common database operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None):
        """Execute raw SQL query with parameters"""
        return await self.db.execute(text(query), params or {})

    async def commit(self):
        """Commit transaction"""
        await self.db.commit()

    async def rollback(self):
        """Rollback transaction"""
        await self.db.rollback()


# ============================================================================
# JOURNAL REPOSITORY
# ============================================================================


class JournalRepository(BaseRepository):
    """Repository for journal entries and extractions"""

    async def get_entry_by_date(
        self, user_id: UUID, entry_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get journal entry for specific date"""
        query = text("""
            SELECT id, user_id, entry_date, raw_entry, overall_quality,
                   has_gaps, created_at, updated_at
            FROM journal_extractions
            WHERE user_id = :user_id AND entry_date = :entry_date
        """)

        result = await self.db.execute(
            query, {"user_id": str(user_id), "entry_date": entry_date}
        )
        row = result.fetchone()

        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "entry_date": row[2],
                "raw_entry": row[3],
                "overall_quality": row[4],
                "has_gaps": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
        return None

    async def create_or_update_entry(
        self,
        user_id: UUID,
        entry_date: date,
        raw_entry: str,
        quality: str,
        has_gaps: bool,
        extraction_time_ms: int,
        gemini_model: str,
    ) -> UUID:
        """Create new entry or update existing one"""
        query = text("""
            INSERT INTO journal_extractions
                (user_id, entry_date, raw_entry, overall_quality,
                 has_gaps, extraction_time_ms, gemini_model)
            VALUES
                (:user_id, :entry_date, :raw_entry, CAST(:quality AS extraction_quality),
                 :has_gaps, :time_ms, :model)
            ON CONFLICT (user_id, entry_date)
            DO UPDATE SET
                raw_entry = EXCLUDED.raw_entry,
                overall_quality = EXCLUDED.overall_quality,
                has_gaps = EXCLUDED.has_gaps,
                extraction_time_ms = EXCLUDED.extraction_time_ms,
                gemini_model = EXCLUDED.gemini_model,
                updated_at = NOW()
            RETURNING id
        """)

        result = await self.db.execute(
            query,
            {
                "user_id": str(user_id),
                "entry_date": entry_date,
                "raw_entry": raw_entry,
                "quality": quality,
                "has_gaps": has_gaps,
                "time_ms": extraction_time_ms,
                "model": gemini_model,
            },
        )

        row = result.fetchone()
        return row[0] if row else None

    async def get_recent_entries(
        self, user_id: UUID, days: int = 30, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent journal entries"""
        query = text("""
            SELECT id, entry_date, raw_entry, overall_quality, has_gaps, created_at
            FROM journal_extractions
            WHERE user_id = :user_id
              AND entry_date >= CURRENT_DATE - :days * INTERVAL '1 day'
            ORDER BY entry_date DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            query, {"user_id": str(user_id), "days": days, "limit": limit}
        )

        entries = []
        for row in result:
            entries.append(
                {
                    "id": row[0],
                    "entry_date": row[1],
                    "raw_entry": row[2],
                    "overall_quality": row[3],
                    "has_gaps": row[4],
                    "created_at": row[5],
                }
            )

        return entries

    async def get_user_baseline(
        self, user_id: UUID, days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Calculate user baseline metrics over specified days"""
        query = text("""
            SELECT
                AVG(CAST(metrics->>'mood' AS FLOAT)) as avg_mood,
                AVG(CAST(metrics->>'energy' AS FLOAT)) as avg_energy,
                AVG(CAST(metrics->>'stress' AS FLOAT)) as avg_stress,
                AVG(CAST(sleep->>'duration_hours' AS FLOAT)) as avg_sleep,
                COUNT(*) as entry_count
            FROM journal_extractions je
            LEFT JOIN extraction_metrics em ON je.id = em.extraction_id
            LEFT JOIN extraction_sleep es ON je.id = es.extraction_id
            WHERE je.user_id = :user_id
              AND je.entry_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        """)

        result = await self.db.execute(query, {"user_id": str(user_id), "days": days})
        row = result.fetchone()

        if row and row[4] > 0:  # entry_count > 0
            return {
                "avg_mood": row[0],
                "avg_energy": row[1],
                "avg_stress": row[2],
                "avg_sleep": row[3],
                "entry_count": row[4],
            }
        return None


# ============================================================================
# ACTIVITY REPOSITORY
# ============================================================================


class ActivityRepository(BaseRepository):
    """Repository for user activities"""

    async def save_activity(
        self,
        extraction_id: UUID,
        raw_name: str,
        canonical_name: str,
        category: str,
        duration_minutes: Optional[int] = None,
        time_of_day: Optional[str] = None,
        intensity: Optional[str] = None,
        calories: Optional[int] = None,
    ) -> UUID:
        """Save an activity"""
        query = text("""
            INSERT INTO extraction_activities
                (extraction_id, raw_name, canonical_name, category,
                 duration_minutes, time_of_day, intensity, calories_burned)
            VALUES
                (:extraction_id, :raw_name, :canonical_name, :category,
                 :duration, :time_of_day, :intensity, :calories)
            RETURNING id
        """)

        result = await self.db.execute(
            query,
            {
                "extraction_id": str(extraction_id),
                "raw_name": raw_name,
                "canonical_name": canonical_name,
                "category": category,
                "duration": duration_minutes,
                "time_of_day": time_of_day,
                "intensity": intensity,
                "calories": calories,
            },
        )

        row = result.fetchone()
        return row[0] if row else None

    async def get_user_activities(
        self, user_id: UUID, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get user's recent activities"""
        query = text("""
            SELECT ea.canonical_name, ea.category, ea.duration_minutes,
                   ea.time_of_day, je.entry_date
            FROM extraction_activities ea
            JOIN journal_extractions je ON ea.extraction_id = je.id
            WHERE je.user_id = :user_id
              AND je.entry_date >= CURRENT_DATE - :days * INTERVAL '1 day'
            ORDER BY je.entry_date DESC
        """)

        result = await self.db.execute(query, {"user_id": str(user_id), "days": days})

        activities = []
        for row in result:
            activities.append(
                {
                    "canonical_name": row[0],
                    "category": row[1],
                    "duration_minutes": row[2],
                    "time_of_day": row[3],
                    "entry_date": row[4],
                }
            )

        return activities


# ============================================================================
# METRICS REPOSITORY
# ============================================================================


class MetricsRepository(BaseRepository):
    """Repository for user metrics (mood, energy, etc.)"""

    async def save_metrics(self, extraction_id: UUID, metrics: Dict[str, Any]) -> None:
        """Save metrics for an extraction"""
        query = text("""
            INSERT INTO extraction_metrics
                (extraction_id, mood, energy, stress, productivity,
                 anxiety, confidence, focus, happiness, gratitude, creativity)
            VALUES
                (:extraction_id, :mood, :energy, :stress, :productivity,
                 :anxiety, :confidence, :focus, :happiness, :gratitude, :creativity)
            ON CONFLICT (extraction_id)
            DO UPDATE SET
                mood = EXCLUDED.mood,
                energy = EXCLUDED.energy,
                stress = EXCLUDED.stress,
                productivity = EXCLUDED.productivity,
                anxiety = EXCLUDED.anxiety,
                confidence = EXCLUDED.confidence,
                focus = EXCLUDED.focus,
                happiness = EXCLUDED.happiness,
                gratitude = EXCLUDED.gratitude,
                creativity = EXCLUDED.creativity
        """)

        await self.db.execute(
            query,
            {
                "extraction_id": str(extraction_id),
                "mood": metrics.get("mood"),
                "energy": metrics.get("energy"),
                "stress": metrics.get("stress"),
                "productivity": metrics.get("productivity"),
                "anxiety": metrics.get("anxiety"),
                "confidence": metrics.get("confidence"),
                "focus": metrics.get("focus"),
                "happiness": metrics.get("happiness"),
                "gratitude": metrics.get("gratitude"),
                "creativity": metrics.get("creativity"),
            },
        )


# ============================================================================
# REPOSITORY FACTORY
# ============================================================================


class RepositoryFactory:
    """Factory for creating repository instances"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    def journal_repo(self) -> JournalRepository:
        """Get journal repository"""
        return JournalRepository(self.db_session)

    def activity_repo(self) -> ActivityRepository:
        """Get activity repository"""
        return ActivityRepository(self.db_session)

    def metrics_repo(self) -> MetricsRepository:
        """Get metrics repository"""
        return MetricsRepository(self.db_session)
