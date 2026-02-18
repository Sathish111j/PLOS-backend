"""
PLOS - Storage Service
Stores extracted journal data in normalized tables with controlled vocabulary.
Matches the journal_schema.sql generalized schema.
"""

import os
from datetime import date, datetime
from datetime import time as time_type
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from application.extraction.generalized_extraction import (
    DataGap,
    ExtractionResult,
    NormalizedActivity,
    NormalizedConsumption,
)
from infrastructure.storage.writer import ExtractionWriter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.kafka.producer import KafkaProducerService
from shared.kafka.topics import KafkaTopics
from shared.models.context import ContextUpdate
from shared.utils.logger import get_logger
from shared.utils.unified_config import get_unified_settings

logger = get_logger(__name__)

VALID_TIME_OF_DAY = {
    "early_morning",
    "morning",
    "afternoon",
    "evening",
    "night",
    "late_night",
}


class StorageService:
    """
    Stores extraction data in normalized tables with organic vocabulary.

    Tables used:
    - journal_extractions: Base extraction record
    - extraction_metrics: Numeric scores (mood, energy, stress, etc.)
    - extraction_activities: Activities with organic categories and subcategories
    - extraction_consumptions: Food/drinks with organic categories
    - extraction_social: Social interactions
    - extraction_notes: Goals, gratitude, symptoms, thoughts
    - extraction_sleep: Sleep data
    - extraction_gaps: Clarification questions

    Note: Vocabulary is organic (no pre-seeded reference tables).
    Gemini receives existing terms and can reuse or create new ones.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        kafka_producer: Optional[KafkaProducerService] = None,
    ):
        self.db = db_session
        self.kafka = kafka_producer
        settings = get_unified_settings()
        self.context_broker_url = os.getenv(
            "CONTEXT_BROKER_URL",
            f"http://context-broker:{settings.context_broker_port}",
        )
        self.writer = ExtractionWriter(
            db_session,
            self._parse_time_string,
            self._normalize_time_of_day,
        )

    def _parse_time_string(self, time_str: Optional[str]) -> Optional[time_type]:
        """Parse a time string like '12:00' or '09:30' to a datetime.time object."""
        if not time_str:
            return None
        try:
            # Handle HH:MM format
            parts = time_str.split(":")
            if len(parts) >= 2:
                return time_type(int(parts[0]), int(parts[1]))
            return None
        except (ValueError, TypeError):
            return None

    def _normalize_time_of_day(self, value: Optional[str]) -> Optional[str]:
        """Normalize time_of_day values to supported enum strings."""
        if not value:
            return None
        if value in VALID_TIME_OF_DAY:
            return value
        return None

    # ========================================================================
    # MAIN STORAGE METHOD
    # ========================================================================

    async def store_extraction(
        self,
        user_id: UUID,
        entry_date: date,
        raw_entry: str,
        extraction: ExtractionResult,
        extraction_time_ms: int = 0,
        gemini_model: str = "gemini-2.5-flash",
    ) -> UUID:
        """
        Store complete extraction in normalized tables.

        Args:
            user_id: User UUID
            entry_date: Date of the journal entry
            raw_entry: Original journal text
            extraction: ExtractionResult from GeminiExtractor
            extraction_time_ms: Time taken to extract
            gemini_model: Model used for extraction

        Returns:
            extraction_id: UUID of the journal extraction record
        """
        try:
            logger.info(
                f"StorageService.store_extraction - START for user {user_id}, date {entry_date}"
            )
            logger.info(
                f"Extraction summary: quality={extraction.quality}, has_gaps={extraction.has_gaps}, activities={len(extraction.activities)}, consumptions={len(extraction.consumptions)}"
            )

            # 1. Insert/update base journal extraction
            logger.info("Step 1: Upserting journal entry to journal_extractions table")
            extraction_id = await self._upsert_journal_entry(
                user_id=user_id,
                entry_date=entry_date,
                raw_entry=raw_entry,
                quality=extraction.quality,
                has_gaps=extraction.has_gaps,
                extraction_time_ms=extraction_time_ms,
                gemini_model=gemini_model,
            )
            logger.info(
                f"Journal entry created/updated with extraction_id: {extraction_id}"
            )

            # 2. Store metrics (mood, energy, stress, etc.)
            logger.info(
                f"Step 2: Storing metrics (count: {len(extraction.metrics) if extraction.metrics else 0})"
            )
            await self._store_metrics(extraction_id, extraction.metrics)
            logger.info("Metrics stored successfully")

            # 3. Store activities with vocabulary resolution
            logger.info(
                f"Step 3: Storing activities (count: {len(extraction.activities)})"
            )
            await self._store_activities(extraction_id, extraction.activities)
            logger.info(f"Activities stored: {len(extraction.activities)} items")

            # 4. Store consumptions (food/drinks)
            logger.info(
                f"Step 4: Storing consumptions (count: {len(extraction.consumptions)})"
            )
            await self._store_consumptions(extraction_id, extraction.consumptions)
            logger.info(f"Consumptions stored: {len(extraction.consumptions)} items")

            # 5. Store social interactions
            logger.info(
                f"Step 5: Storing social interactions (count: {len(extraction.social) if extraction.social else 0})"
            )
            await self._store_social(extraction_id, extraction.social)
            logger.info("Social interactions stored")

            # 6. Store notes (goals, gratitude, etc.)
            logger.info(
                f"Step 6: Storing notes (count: {len(extraction.notes) if extraction.notes else 0})"
            )
            await self._store_notes(extraction_id, extraction.notes)
            logger.info("Notes stored")

            # 7. Store sleep data
            if extraction.sleep:
                logger.info(f"Step 7: Storing sleep data: {extraction.sleep}")
                await self._store_sleep(extraction_id, extraction.sleep)
                logger.info("Sleep data stored")
            else:
                logger.info("Step 7: No sleep data to store")

            # 8. Store locations
            if hasattr(extraction, "locations") and extraction.locations:
                logger.info(
                    f"Step 8: Storing locations (count: {len(extraction.locations)})"
                )
                await self._store_locations(extraction_id, extraction.locations)
                logger.info("Locations stored")
            else:
                logger.info("Step 8: No location data to store")

            # 9. Store health symptoms
            if hasattr(extraction, "health") and extraction.health:
                logger.info(
                    f"Step 9: Storing health symptoms (count: {len(extraction.health)})"
                )
                await self._store_health(extraction_id, extraction.health)
                logger.info("Health symptoms stored")
            else:
                logger.info("Step 9: No health data to store")

            # 10. Store work/productivity data
            if hasattr(extraction, "work") and extraction.work:
                logger.info(f"Step 10: Storing work data: {extraction.work}")
                await self._store_work(extraction_id, extraction.work)
                logger.info("Work data stored")
            else:
                logger.info("Step 10: No work data to store")

            # 11. Store weather context
            if hasattr(extraction, "weather") and extraction.weather:
                logger.info(f"Step 11: Storing weather data: {extraction.weather}")
                await self._store_weather(extraction_id, extraction.weather)
                logger.info("Weather data stored")
            else:
                logger.info("Step 11: No weather data to store")

            # 12. Store gaps for clarification
            if extraction.gaps:
                logger.info(f"Step 12: Storing gaps (count: {len(extraction.gaps)})")
                await self._store_gaps(extraction_id, extraction.gaps)
                logger.info(
                    f"Gaps stored: {len(extraction.gaps)} clarification questions"
                )
            else:
                logger.info("Step 12: No gaps to store")

            # 12.5. Store analytics snapshot in time-series table
            logger.info("Step 12.5: Storing journal time-series snapshot")
            await self._store_timeseries_snapshot(
                extraction_id=extraction_id,
                user_id=user_id,
                entry_date=entry_date,
            )
            logger.info("Time-series snapshot stored")

            # 13. Commit transaction
            logger.info("Step 13: Committing database transaction")
            await self.db.commit()
            logger.info("Transaction committed successfully")

            logger.info(
                f"STORAGE COMPLETE for extraction_id={extraction_id}: "
                f"activities={len(extraction.activities)}, "
                f"consumptions={len(extraction.consumptions)}, "
                f"gaps={len(extraction.gaps)}, "
                f"quality={extraction.quality}"
            )

            # 14. Publish events to Kafka
            if self.kafka:
                logger.info("Step 14: Publishing events to Kafka")
                await self._publish_events(
                    extraction_id, user_id, entry_date, extraction
                )
                logger.info("Kafka events published successfully")
            else:
                logger.info("Step 14: Kafka not available, skipping event publishing")

            # 15. Update context-broker state (best effort)
            await self._notify_context_broker(user_id, entry_date, extraction)

            logger.info(
                f"StorageService.store_extraction - COMPLETE for extraction_id={extraction_id}"
            )
            return extraction_id

        except Exception as e:
            logger.error(
                f"StorageService.store_extraction - FAILED: {e}", exc_info=True
            )
            await self.db.rollback()
            logger.error("Database transaction rolled back")
            raise

    # ========================================================================
    # JOURNAL ENTRY
    # ========================================================================

    async def _upsert_journal_entry(
        self,
        user_id: UUID,
        entry_date: date,
        raw_entry: str,
        quality: str,
        has_gaps: bool,
        extraction_time_ms: int,
        gemini_model: str,
    ) -> UUID:
        """Insert or update base journal extraction."""
        query = text(
            """
            INSERT INTO journal_extractions
                (id, user_id, entry_date, raw_entry, overall_quality,
                 has_gaps, extraction_time_ms, gemini_model)
            VALUES
                (gen_random_uuid(), :user_id, :entry_date, :raw_entry, CAST(:quality AS extraction_quality),
                 :has_gaps, :time_ms, :model)
            RETURNING id
        """
        )

        result = await self.db.execute(
            query,
            {
                "user_id": user_id,
                "entry_date": entry_date,
                "raw_entry": raw_entry,
                "quality": quality,
                "has_gaps": has_gaps,
                "time_ms": extraction_time_ms,
                "model": gemini_model,
            },
        )

        row = result.fetchone()
        if not row:
            raise ValueError("Failed to insert journal extraction")
        return row[0]

    # ========================================================================
    # METRICS
    # ========================================================================

    async def _store_metrics(
        self, extraction_id: UUID, metrics: Dict[str, Dict[str, Any]]
    ) -> None:
        """Store extraction metrics (mood, energy, stress, etc.)."""
        await self.writer.store_metrics(extraction_id, metrics)

    async def _store_timeseries_snapshot(
        self,
        extraction_id: UUID,
        user_id: UUID,
        entry_date: date,
    ) -> None:
        """Store per-extraction analytics snapshot in journal_timeseries."""
        metric_names_mood = ["mood_score", "mood", "mood_level"]
        metric_names_steps = ["steps", "step_count", "steps_count", "walking_steps"]
        metric_names_water = ["water_intake_liters", "water_intake", "water"]

        snapshot_result = await self.db.execute(
            text(
                """
                WITH consumptions AS (
                    SELECT
                        SUM(calories) AS calories_in,
                        SUM(water_ml) AS water_ml,
                        SUM(protein_g) AS protein_g,
                        SUM(carbs_g) AS carbs_g,
                        SUM(fat_g) AS fat_g
                    FROM extraction_consumptions
                    WHERE extraction_id = :extraction_id
                ),
                sleep_data AS (
                    SELECT
                        AVG(duration_hours) AS sleep_hours,
                        AVG(quality) AS sleep_quality
                    FROM extraction_sleep
                    WHERE extraction_id = :extraction_id
                ),
                activity_data AS (
                    SELECT
                        SUM(duration_minutes) AS activity_minutes,
                        SUM(calories_burned) AS activity_calories
                    FROM extraction_activities
                    WHERE extraction_id = :extraction_id
                ),
                mood_data AS (
                    SELECT AVG(em.value) AS mood_score
                    FROM extraction_metrics em
                    JOIN metric_types mt ON mt.id = em.metric_type_id
                    WHERE em.extraction_id = :extraction_id
                      AND mt.name = ANY(:metric_names_mood)
                ),
                steps_data AS (
                    SELECT SUM(em.value) AS steps
                    FROM extraction_metrics em
                    JOIN metric_types mt ON mt.id = em.metric_type_id
                    WHERE em.extraction_id = :extraction_id
                      AND mt.name = ANY(:metric_names_steps)
                ),
                water_metric_data AS (
                    SELECT
                        SUM(
                            CASE
                                WHEN mt.name LIKE '%liter%' THEN em.value * 1000.0
                                ELSE em.value
                            END
                        ) AS water_ml
                    FROM extraction_metrics em
                    JOIN metric_types mt ON mt.id = em.metric_type_id
                    WHERE em.extraction_id = :extraction_id
                      AND mt.name = ANY(:metric_names_water)
                )
                SELECT
                    c.calories_in,
                    s.sleep_hours,
                    s.sleep_quality,
                    m.mood_score,
                    COALESCE(c.water_ml, 0) + COALESCE(wm.water_ml, 0) AS water_ml,
                    st.steps,
                    a.activity_minutes,
                    a.activity_calories,
                    c.protein_g,
                    c.carbs_g,
                    c.fat_g
                FROM consumptions c
                CROSS JOIN sleep_data s
                CROSS JOIN activity_data a
                CROSS JOIN mood_data m
                CROSS JOIN steps_data st
                CROSS JOIN water_metric_data wm
                """
            ),
            {
                "extraction_id": extraction_id,
                "metric_names_mood": metric_names_mood,
                "metric_names_steps": metric_names_steps,
                "metric_names_water": metric_names_water,
            },
        )

        snapshot = snapshot_result.fetchone()

        await self.db.execute(
            text("DELETE FROM journal_timeseries WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        await self.db.execute(
            text(
                """
                INSERT INTO journal_timeseries (
                    user_id,
                    ts,
                    extraction_id,
                    entry_date,
                    calories_in,
                    sleep_hours,
                    sleep_quality,
                    mood_score,
                    water_ml,
                    steps,
                    activity_minutes,
                    activity_calories,
                    protein_g,
                    carbs_g,
                    fat_g,
                    updated_at
                )
                VALUES (
                    :user_id,
                    :ts,
                    :extraction_id,
                    :entry_date,
                    :calories_in,
                    :sleep_hours,
                    :sleep_quality,
                    :mood_score,
                    :water_ml,
                    :steps,
                    :activity_minutes,
                    :activity_calories,
                    :protein_g,
                    :carbs_g,
                    :fat_g,
                    NOW()
                )
                """
            ),
            {
                "user_id": user_id,
                "ts": datetime.combine(entry_date, time_type.min),
                "extraction_id": extraction_id,
                "entry_date": entry_date,
                "calories_in": float(snapshot[0]) if snapshot and snapshot[0] is not None else None,
                "sleep_hours": float(snapshot[1]) if snapshot and snapshot[1] is not None else None,
                "sleep_quality": float(snapshot[2]) if snapshot and snapshot[2] is not None else None,
                "mood_score": float(snapshot[3]) if snapshot and snapshot[3] is not None else None,
                "water_ml": float(snapshot[4]) if snapshot and snapshot[4] is not None else None,
                "steps": int(snapshot[5]) if snapshot and snapshot[5] is not None else None,
                "activity_minutes": int(snapshot[6]) if snapshot and snapshot[6] is not None else None,
                "activity_calories": int(snapshot[7]) if snapshot and snapshot[7] is not None else None,
                "protein_g": float(snapshot[8]) if snapshot and snapshot[8] is not None else None,
                "carbs_g": float(snapshot[9]) if snapshot and snapshot[9] is not None else None,
                "fat_g": float(snapshot[10]) if snapshot and snapshot[10] is not None else None,
            },
        )

    # ========================================================================
    # ACTIVITIES
    # ========================================================================

    async def _store_activities(
        self, extraction_id: UUID, activities: List[NormalizedActivity]
    ) -> None:
        """Store activities with vocabulary resolution."""
        if not activities:
            return

        # Clear existing activities for this extraction
        await self.db.execute(
            text(
                "DELETE FROM extraction_activities WHERE extraction_id = :extraction_id"
            ),
            {"extraction_id": extraction_id},
        )

        for activity in activities:
            time_of_day = None
            if activity.time_of_day:
                time_of_day = activity.time_of_day.value

            query = text(
                """
                INSERT INTO extraction_activities
                    (extraction_id, activity_raw, activity_category,
                     activity_subcategory, duration_minutes, time_of_day, start_time,
                     end_time, intensity, satisfaction, calories_burned, confidence,
                     raw_mention, needs_clarification, is_outdoor, with_others,
                     location, mood_before, mood_after)
                VALUES
                    (:extraction_id, :activity_raw, :activity_category,
                     :activity_subcategory, :duration, CAST(:time_of_day AS time_of_day),
                     :start_time, :end_time, :intensity, :satisfaction, :calories,
                     :confidence, :raw_mention, :needs_clarification, :is_outdoor,
                     :with_others, :location, :mood_before, :mood_after)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "activity_raw": activity.raw_name,  # Always store raw activity name
                    "activity_category": activity.category,  # Store category for aggregation
                    "activity_subcategory": getattr(
                        activity, "subcategory", None
                    ),  # Store subcategory
                    "duration": activity.duration_minutes,
                    "time_of_day": time_of_day,
                    "start_time": self._parse_time_string(activity.start_time),
                    "end_time": self._parse_time_string(activity.end_time),
                    "intensity": activity.intensity,
                    "satisfaction": activity.satisfaction,
                    "calories": activity.calories_burned,
                    "confidence": activity.confidence,
                    "raw_mention": activity.raw_mention,
                    "needs_clarification": activity.needs_clarification,
                    "is_outdoor": activity.is_outdoor,
                    "with_others": activity.with_others,
                    "location": activity.location,
                    "mood_before": activity.mood_before,
                    "mood_after": activity.mood_after,
                },
            )

    # ========================================================================
    # CONSUMPTIONS
    # ========================================================================

    async def _store_consumptions(
        self, extraction_id: UUID, consumptions: List[NormalizedConsumption]
    ) -> None:
        """Store food/drink consumptions with vocabulary resolution."""
        await self.writer.store_consumptions(extraction_id, consumptions)

    # ========================================================================
    # SOCIAL
    # ========================================================================

    async def _store_social(
        self, extraction_id: UUID, social: List[Dict[str, Any]]
    ) -> None:
        """Store social interactions with deep relationship tracking."""
        await self.writer.store_social(extraction_id, social)

    # ========================================================================
    # NOTES
    # ========================================================================

    async def _store_notes(
        self, extraction_id: UUID, notes: List[Dict[str, Any]]
    ) -> None:
        """Store notes (goals, gratitude, symptoms, thoughts)."""
        await self.writer.store_notes(extraction_id, notes)

    # ========================================================================
    # SLEEP
    # ========================================================================

    async def _store_sleep(self, extraction_id: UUID, sleep: Dict[str, Any]) -> None:
        """Store sleep data."""
        await self.writer.store_sleep(extraction_id, sleep)

    # ========================================================================
    # GAPS
    # ========================================================================

    async def _store_gaps(self, extraction_id: UUID, gaps: List[DataGap]) -> None:
        """Store extraction gaps for user clarification."""
        await self.writer.store_gaps(extraction_id, gaps)

    # ========================================================================
    # LOCATIONS
    # ========================================================================

    async def _store_locations(
        self, extraction_id: UUID, locations: List[Dict[str, Any]]
    ) -> None:
        """Store location data."""
        await self.writer.store_locations(extraction_id, locations)

    # ========================================================================
    # HEALTH SYMPTOMS
    # ========================================================================

    async def _store_health(
        self, extraction_id: UUID, health: List[Dict[str, Any]]
    ) -> None:
        """Store health symptom data."""
        await self.writer.store_health(extraction_id, health)

    # ========================================================================
    # WORK / PRODUCTIVITY
    # ========================================================================

    async def _store_work(
        self, extraction_id: UUID, work: List[Dict[str, Any]]
    ) -> None:
        """Store work/productivity data."""
        await self.writer.store_work(extraction_id, work)

    # ========================================================================
    # WEATHER CONTEXT
    # ========================================================================

    async def _store_weather(
        self, extraction_id: UUID, weather: Dict[str, Any]
    ) -> None:
        """Store weather context data."""
        await self.writer.store_weather(extraction_id, weather)

    # ========================================================================
    # GAP RESOLUTION
    # ========================================================================

    async def resolve_gap(
        self,
        gap_id: UUID,
        user_response: str,
    ) -> None:
        """Mark a gap as resolved with user's response."""
        logger.info(
            f"STORAGE: Resolving gap {gap_id} with response: {user_response[:50]}..."
        )

        # First verify the gap exists and is in pending status
        check_result = await self.db.execute(
            text(
                """
                SELECT id, status FROM extraction_gaps
                WHERE id = :gap_id
            """
            ),
            {"gap_id": gap_id},
        )
        existing_gap = check_result.fetchone()

        if not existing_gap:
            logger.error(f"STORAGE: Gap {gap_id} not found")
            raise ValueError(f"Gap with ID {gap_id} not found")

        if existing_gap.status != "pending":
            logger.error(
                f"STORAGE: Gap {gap_id} status is {existing_gap.status}, not pending"
            )
            raise ValueError(
                f"Gap {gap_id} is already {existing_gap.status}, cannot resolve"
            )

        # Now update the gap
        logger.info(f"STORAGE: Updating gap {gap_id} to answered status")
        await self.db.execute(
            text(
                """
                UPDATE extraction_gaps
                SET status = 'answered',
                    user_response = :response,
                    resolved_at = NOW()
                WHERE id = :gap_id AND status = 'pending'
            """
            ),
            {"gap_id": gap_id, "response": user_response},
        )

        await self.db.commit()
        logger.info(f"STORAGE: Successfully resolved gap {gap_id}")

    async def get_pending_gaps(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get pending gaps for a user."""
        result = await self.db.execute(
            text(
                """
                SELECT g.id, g.field_category, g.question, g.context,
                       g.original_mention, g.priority, g.created_at, je.entry_date
                FROM extraction_gaps g
                JOIN journal_extractions je ON g.extraction_id = je.id
                WHERE je.user_id = :user_id AND g.status = 'pending'
                ORDER BY g.priority ASC, je.entry_date DESC
            """
            ),
            {"user_id": user_id},
        )

        return [
            {
                "gap_id": row[0],
                "field": row[1],
                "question": row[2],
                "context": row[3],
                "raw_value": row[4],
                "priority": (
                    "high" if row[5] == 1 else "medium" if row[5] == 2 else "low"
                ),
                "created_at": row[6].isoformat() if row[6] else None,
                "entry_date": row[7].isoformat() if row[7] else None,
            }
            for row in result.fetchall()
        ]

    # ========================================================================
    # QUERY HELPERS
    # ========================================================================

    async def get_user_activities(
        self,
        user_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user activities with optional filters."""
        query = """
            SELECT
                ea.activity_raw as activity,
                ea.activity_category as category,
                ea.activity_subcategory,
                ea.duration_minutes,
                ea.time_of_day,
                ea.intensity,
                ea.calories_burned,
                je.entry_date
            FROM extraction_activities ea
            JOIN journal_extractions je ON ea.extraction_id = je.id
            WHERE je.user_id = :user_id
        """
        params: Dict[str, Any] = {"user_id": user_id}

        if start_date:
            query += " AND je.entry_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND je.entry_date <= :end_date"
            params["end_date"] = end_date
        if category:
            query += " AND ea.activity_category = :category"
            params["category"] = category

        query += " ORDER BY je.entry_date DESC, ea.time_of_day"

        result = await self.db.execute(text(query), params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_activity_summary(
        self,
        user_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get activity summary for the last N days."""
        result = await self.db.execute(
            text(
                """
                SELECT
                    ea.activity_raw as activity,
                    ea.activity_category as category,
                    COUNT(*) as count,
                    SUM(ea.duration_minutes) as total_minutes,
                    AVG(ea.duration_minutes) as avg_minutes,
                    SUM(ea.calories_burned) as total_calories
                FROM extraction_activities ea
                JOIN journal_extractions je ON ea.extraction_id = je.id
                WHERE je.user_id = :user_id
                                    AND je.entry_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                GROUP BY ea.activity_raw, ea.activity_category
                ORDER BY count DESC
            """
            ),
            {"user_id": user_id, "days": days},
        )

        activities = [dict(row._mapping) for row in result.fetchall()]

        # Group by category
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for act in activities:
            cat = act["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(act)

        return {
            "activities": activities,
            "by_category": by_category,
            "total_activities": len(activities),
        }

    # ========================================================================
    # GAP RESOLUTION METHODS
    # ========================================================================

    async def get_entry_gaps(self, entry_id: UUID) -> List[Dict[str, Any]]:
        """Get all unresolved gaps for an entry."""
        result = await self.db.execute(
            text(
                """
                SELECT
                    id as gap_id,
                    field_category,
                    question,
                    context,
                    original_mention,
                    priority
                FROM extraction_gaps
                WHERE extraction_id = :entry_id
                  AND status = 'pending'
                ORDER BY priority ASC
            """
            ),
            {"entry_id": entry_id},
        )

        gaps = []
        for row in result.fetchall():
            gap = dict(row._mapping)
            gaps.append(gap)

        return gaps

    async def get_extraction_result(self, entry_id: UUID) -> "ExtractionResult":
        """
        Reconstruct ExtractionResult from database for an entry.
        Used when resolving gaps to update existing extraction.
        """
        from application.extraction.generalized_extraction import (
            ExtractionResult,
            NormalizedActivity,
            NormalizedConsumption,
            TimeOfDay,
        )

        # Get activities
        activities = []
        result = await self.db.execute(
            text(
                """
                SELECT
                    ea.activity_raw,
                    ea.activity_category as category,
                    ea.activity_subcategory,
                    ea.duration_minutes,
                    ea.time_of_day,
                    ea.start_time,
                    ea.end_time,
                    ea.intensity,
                    ea.satisfaction,
                    ea.calories_burned,
                    ea.confidence,
                    ea.raw_mention,
                    ea.needs_clarification
                FROM extraction_activities ea
                WHERE ea.extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )

        for row in result.fetchall():
            r = dict(row._mapping)
            time_of_day = None
            if r.get("time_of_day"):
                try:
                    time_of_day = TimeOfDay(r["time_of_day"])
                except ValueError:
                    pass

            activities.append(
                NormalizedActivity(
                    canonical_name=None,
                    raw_name=r.get("activity_raw") or "",
                    category=r.get("category", "other"),
                    subcategory=r.get("activity_subcategory"),
                    duration_minutes=r.get("duration_minutes"),
                    time_of_day=time_of_day,
                    start_time=str(r["start_time"]) if r.get("start_time") else None,
                    end_time=str(r["end_time"]) if r.get("end_time") else None,
                    intensity=r.get("intensity"),
                    satisfaction=r.get("satisfaction"),
                    calories_burned=r.get("calories_burned"),
                    confidence=r.get("confidence", 0.7),
                    needs_clarification=r.get("needs_clarification", False),
                    raw_mention=r.get("raw_mention"),
                )
            )

        # Get consumptions
        consumptions = []
        result = await self.db.execute(
            text(
                """
                SELECT
                    ec.item_raw as food_raw,
                    ec.food_category,
                    ec.consumption_type,
                    ec.meal_type,
                    ec.time_of_day,
                    ec.consumption_time,
                    ec.quantity,
                    ec.unit,
                    ec.calories,
                    ec.is_healthy,
                    ec.is_home_cooked,
                    ec.confidence
                FROM extraction_consumptions ec
                WHERE ec.extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )

        for row in result.fetchall():
            r = dict(row._mapping)
            time_of_day = None
            if r.get("time_of_day"):
                try:
                    time_of_day = TimeOfDay(r["time_of_day"])
                except ValueError:
                    pass

            consumptions.append(
                NormalizedConsumption(
                    canonical_name=None,
                    raw_name=r.get("food_raw") or "",
                    food_category=r.get("food_category"),
                    consumption_type=r.get("consumption_type", "meal"),
                    meal_type=r.get("meal_type"),
                    time_of_day=time_of_day,
                    consumption_time=(
                        str(r["consumption_time"])
                        if r.get("consumption_time")
                        else None
                    ),
                    quantity=r.get("quantity", 1.0),
                    unit=r.get("unit", "serving"),
                    calories=r.get("calories"),
                    is_healthy=r.get("is_healthy"),
                    is_home_cooked=r.get("is_home_cooked"),
                    confidence=r.get("confidence", 0.7),
                )
            )

        # Get metrics
        metrics = {}
        result = await self.db.execute(
            text(
                """
                SELECT mt.name, em.value, em.time_of_day, em.confidence
                FROM extraction_metrics em
                JOIN metric_types mt ON em.metric_type_id = mt.id
                WHERE em.extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )

        for row in result.fetchall():
            r = dict(row._mapping)
            metrics[r["name"]] = {
                "value": r.get("value"),
                "time_of_day": r.get("time_of_day"),
                "confidence": r.get("confidence", 0.7),
            }

        # Get social
        social = []
        result = await self.db.execute(
            text(
                """
                SELECT person_name, relationship, interaction_type,
                       quality_score, duration_minutes, sentiment, topic
                FROM extraction_social
                WHERE extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )
        for row in result.fetchall():
            social.append(dict(row._mapping))

        # Get notes
        notes = []
        result = await self.db.execute(
            text(
                """
                SELECT note_type, content, sentiment
                FROM extraction_notes
                WHERE extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )
        for row in result.fetchall():
            notes.append(dict(row._mapping))

        # Get sleep
        sleep = None
        result = await self.db.execute(
            text(
                """
                SELECT duration_hours, quality, bedtime, waketime, disruptions
                FROM extraction_sleep
                WHERE extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )
        row = result.fetchone()
        if row:
            sleep = dict(row._mapping)

        # Get gap count
        result = await self.db.execute(
            text(
                "SELECT COUNT(*) FROM extraction_gaps WHERE extraction_id = :entry_id AND status = 'pending'"
            ),
            {"entry_id": entry_id},
        )
        gap_count = result.scalar() or 0

        return ExtractionResult(
            metrics=metrics,
            activities=activities,
            consumptions=consumptions,
            social=social,
            sleep=sleep,
            notes=notes,
            gaps=[],  # Gaps handled separately
            has_gaps=gap_count > 0,
            quality="medium",  # Would need to recalculate
        )

    async def update_extraction_from_resolution(
        self,
        entry_id: UUID,
        extraction: "ExtractionResult",
        resolved_gap_count: int,
    ) -> None:
        """
        Update extraction data after gap resolution.
        Adds newly resolved activities/consumptions and marks gaps as resolved.
        """
        # Store any new activities
        await self._store_activities(entry_id, extraction.activities)

        # Store any new consumptions
        await self._store_consumptions(entry_id, extraction.consumptions)

        # Mark resolved gaps
        if resolved_gap_count > 0:
            # Get the oldest unresolved gaps and mark them resolved
            await self.db.execute(
                text(
                    """
                    UPDATE extraction_gaps
                    SET status = 'answered', resolved_at = NOW()
                    WHERE id IN (
                        SELECT id FROM extraction_gaps
                        WHERE extraction_id = :entry_id AND status = 'pending'
                        ORDER BY priority ASC
                        LIMIT :count
                    )
                """
                ),
                {"entry_id": entry_id, "count": resolved_gap_count},
            )

        # Update has_gaps flag on main extraction
        result = await self.db.execute(
            text(
                "SELECT COUNT(*) FROM extraction_gaps WHERE extraction_id = :entry_id AND status = 'pending'"
            ),
            {"entry_id": entry_id},
        )
        remaining_gaps = result.scalar() or 0

        await self.db.execute(
            text(
                """
                UPDATE journal_extractions
                SET has_gaps = :has_gaps, updated_at = NOW()
                WHERE id = :entry_id
            """
            ),
            {"entry_id": entry_id, "has_gaps": remaining_gaps > 0},
        )

        await self.db.commit()

        logger.info(
            f"Updated extraction {entry_id}: {resolved_gap_count} gaps resolved, "
            f"{remaining_gaps} remaining"
        )

    # ========================================================================
    # EVENTS
    # ========================================================================

    async def _publish_events(
        self,
        extraction_id: UUID,
        user_id: UUID,
        entry_date: date,
        extraction: ExtractionResult,
    ) -> None:
        """Publish extraction events to Kafka."""
        if not self.kafka:
            return

        try:
            await self.kafka.publish(
                topic=KafkaTopics.JOURNAL_EXTRACTION_COMPLETE,
                message={
                    "extraction_id": str(extraction_id),
                    "user_id": str(user_id),
                    "entry_date": entry_date.isoformat(),
                    "activity_count": len(extraction.activities),
                    "consumption_count": len(extraction.consumptions),
                    "has_gaps": extraction.has_gaps,
                    "quality": extraction.quality,
                },
                key=str(user_id),
            )
        except Exception as e:
            logger.warning(f"Failed to publish extraction event: {e}")

    async def _notify_context_broker(
        self,
        user_id: UUID,
        entry_date: date,
        extraction: ExtractionResult,
    ) -> None:
        """Send a context update to context-broker."""
        metrics = extraction.metrics or {}
        sleep = extraction.sleep or {}

        def _metric_value(name: str) -> Optional[float]:
            value = metrics.get(name, {})
            if isinstance(value, dict):
                return value.get("value")
            if isinstance(value, (int, float)):
                return float(value)
            return None

        calories_in = (
            sum([c.calories for c in extraction.consumptions if c.calories])
            if extraction.consumptions
            else None
        )
        activity_minutes = (
            sum(
                [
                    a.duration_minutes
                    for a in extraction.activities
                    if a.duration_minutes
                ]
            )
            if extraction.activities
            else None
        )
        activity_calories = (
            sum([a.calories_burned for a in extraction.activities if a.calories_burned])
            if extraction.activities
            else None
        )

        water_ml = (
            sum([c.water_ml for c in extraction.consumptions if c.water_ml])
            if extraction.consumptions
            else None
        )
        water_liters = _metric_value("water_intake_liters")
        if water_liters is not None:
            water_ml = (water_ml or 0) + float(water_liters) * 1000.0

        context_data = {
            "last_journal_entry": entry_date.isoformat(),
            "steps": _metric_value("steps"),
            "water_ml": water_ml,
            "calories_in": calories_in,
            "activity_minutes": activity_minutes,
            "activity_calories": activity_calories,
        }
        context_data = {k: v for k, v in context_data.items() if v is not None}

        update = ContextUpdate(
            user_id=user_id,
            update_type="journal",
            data={
                "current_mood_score": _metric_value("mood_score"),
                "current_energy_level": _metric_value("energy_level"),
                "current_stress_level": _metric_value("stress_level"),
                "sleep_quality_avg_7d": sleep.get("quality"),
                "productivity_score_avg_7d": _metric_value("productivity_score"),
                "context_data": context_data,
            },
            timestamp=datetime.utcnow(),
        )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.context_broker_url}/context/update",
                    json=update.model_dump(mode="json"),
                )
        except Exception as e:
            logger.warning(f"Failed to update context-broker: {e}")
