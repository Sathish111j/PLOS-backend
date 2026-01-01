"""
PLOS - Storage Service
Stores extracted journal data in normalized tables with controlled vocabulary.
Matches the journal_schema.sql generalized schema.
"""

from datetime import date
from datetime import time as time_type
from typing import Any, Dict, List, Optional
from uuid import UUID

from generalized_extraction import (
    DataGap,
    ExtractionResult,
    NormalizedActivity,
    NormalizedConsumption,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.kafka.producer import KafkaProducerService
from shared.kafka.topics import KafkaTopics
from shared.utils.logger import get_logger

logger = get_logger(__name__)


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
            # 1. Insert/update base journal extraction
            extraction_id = await self._upsert_journal_entry(
                user_id=user_id,
                entry_date=entry_date,
                raw_entry=raw_entry,
                quality=extraction.quality,
                has_gaps=extraction.has_gaps,
                extraction_time_ms=extraction_time_ms,
                gemini_model=gemini_model,
            )

            # 2. Store metrics (mood, energy, stress, etc.)
            await self._store_metrics(extraction_id, extraction.metrics)

            # 3. Store activities with vocabulary resolution
            await self._store_activities(extraction_id, extraction.activities)

            # 4. Store consumptions (food/drinks)
            await self._store_consumptions(extraction_id, extraction.consumptions)

            # 5. Store social interactions
            await self._store_social(extraction_id, extraction.social)

            # 6. Store notes (goals, gratitude, etc.)
            await self._store_notes(extraction_id, extraction.notes)

            # 7. Store sleep data
            if extraction.sleep:
                await self._store_sleep(extraction_id, extraction.sleep)

            # 8. Store locations
            if hasattr(extraction, "locations") and extraction.locations:
                await self._store_locations(extraction_id, extraction.locations)

            # 9. Store health symptoms
            if hasattr(extraction, "health") and extraction.health:
                await self._store_health(extraction_id, extraction.health)

            # 10. Store work/productivity data
            if hasattr(extraction, "work") and extraction.work:
                await self._store_work(extraction_id, extraction.work)

            # 11. Store weather context
            if hasattr(extraction, "weather") and extraction.weather:
                await self._store_weather(extraction_id, extraction.weather)

            # 12. Store gaps for clarification
            if extraction.gaps:
                await self._store_gaps(extraction_id, extraction.gaps)

            # 13. Commit transaction
            await self.db.commit()

            logger.info(
                f"Stored extraction for user {user_id}, date {entry_date}: "
                f"{len(extraction.activities)} activities, "
                f"{len(extraction.consumptions)} consumptions, "
                f"{len(extraction.gaps)} gaps"
            )

            # 10. Publish events to Kafka
            if self.kafka:
                await self._publish_events(
                    extraction_id, user_id, entry_date, extraction
                )

            return extraction_id

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to store extraction: {e}")
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
        if not metrics:
            return

        # Valid time_of_day enum values
        valid_time_of_day = {
            "early_morning",
            "morning",
            "afternoon",
            "evening",
            "night",
            "late_night",
        }

        # First, clear existing metrics for this extraction
        await self.db.execute(
            text("DELETE FROM extraction_metrics WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        for metric_name, metric_data in metrics.items():
            value = metric_data.get("value")
            if value is None:
                continue

            # Resolve metric type from vocabulary (returns int, not UUID)
            metric_type_id = await self._resolve_metric_type(metric_name)

            time_of_day = metric_data.get("time_of_day")
            # Validate time_of_day is a valid enum value, otherwise set to None
            if time_of_day and time_of_day not in valid_time_of_day:
                time_of_day = None

            query = text(
                """
                INSERT INTO extraction_metrics
                    (extraction_id, metric_type_id, value, time_of_day, confidence)
                VALUES
                    (:extraction_id, :metric_type_id, :value, CAST(:time_of_day AS time_of_day), :confidence)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "metric_type_id": metric_type_id,
                    "value": float(value),
                    "time_of_day": time_of_day if time_of_day else None,
                    "confidence": metric_data.get("confidence", 0.7),
                },
            )

    async def _resolve_metric_type(self, metric_name: str) -> int:
        """Get or create metric type from vocabulary."""
        # Try to find existing
        result = await self.db.execute(
            text("SELECT id FROM metric_types WHERE name = :name"),
            {"name": metric_name},
        )
        row = result.fetchone()
        if row:
            return row[0]

        # Create new metric type (SERIAL id)
        result = await self.db.execute(
            text(
                """
                INSERT INTO metric_types (name, display_name, unit, min_value, max_value)
                VALUES (:name, :display, 'score', 1, 10)
                RETURNING id
            """
            ),
            {"name": metric_name, "display": metric_name.replace("_", " ").title()},
        )
        row = result.fetchone()
        return row[0]

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
        if not consumptions:
            return

        # Clear existing
        await self.db.execute(
            text(
                "DELETE FROM extraction_consumptions WHERE extraction_id = :extraction_id"
            ),
            {"extraction_id": extraction_id},
        )

        for item in consumptions:
            # Use nutrition from Gemini extraction directly
            calories = item.calories
            protein = item.protein_g
            carbs = item.carbs_g
            fat = item.fat_g
            fiber = item.fiber_g
            sugar = item.sugar_g
            sodium = item.sodium_mg

            time_of_day = None
            if item.time_of_day:
                time_of_day = item.time_of_day.value

            query = text(
                """
                INSERT INTO extraction_consumptions
                    (extraction_id, item_raw, food_category, consumption_type, meal_type,
                     time_of_day, consumption_time, quantity, unit,
                     calories, protein_g, carbs_g, fat_g, fiber_g, sugar_g, sodium_mg,
                     caffeine_mg, alcohol_units, is_processed, water_ml,
                     is_healthy, is_home_cooked, confidence, raw_mention)
                VALUES
                    (:extraction_id, :item_raw, :food_category, :type, :meal_type,
                     CAST(:time_of_day AS time_of_day), :time, :quantity, :unit,
                     :calories, :protein, :carbs, :fat, :fiber, :sugar, :sodium,
                     :caffeine_mg, :alcohol_units, :is_processed, :water_ml,
                     :healthy, :home_cooked, :confidence, :raw_mention)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "item_raw": item.raw_name,  # Always store raw item name
                    "food_category": getattr(
                        item, "food_category", None
                    ),  # Store category for aggregation
                    "type": item.consumption_type,
                    "meal_type": item.meal_type,
                    "time_of_day": time_of_day,
                    "time": self._parse_time_string(item.consumption_time),
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fat": fat,
                    "fiber": fiber,
                    "sugar": sugar,
                    "sodium": sodium,
                    "caffeine_mg": getattr(item, "caffeine_mg", None),
                    "alcohol_units": getattr(item, "alcohol_units", None),
                    "is_processed": getattr(item, "is_processed", None),
                    "water_ml": getattr(item, "water_ml", None),
                    "healthy": item.is_healthy,
                    "home_cooked": item.is_home_cooked,
                    "confidence": item.confidence,
                    "raw_mention": item.raw_mention,
                },
            )

    # ========================================================================
    # SOCIAL
    # ========================================================================

    async def _store_social(
        self, extraction_id: UUID, social: List[Dict[str, Any]]
    ) -> None:
        """Store social interactions with deep relationship tracking."""
        if not social:
            return

        # Valid time_of_day enum values
        valid_time_of_day = {
            "early_morning",
            "morning",
            "afternoon",
            "evening",
            "night",
            "late_night",
        }

        # Clear existing
        await self.db.execute(
            text("DELETE FROM extraction_social WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        for interaction in social:
            time_of_day = interaction.get("time_of_day")
            # Validate time_of_day is a valid enum value
            if time_of_day and time_of_day not in valid_time_of_day:
                time_of_day = None

            query = text(
                """
                INSERT INTO extraction_social
                    (extraction_id, person_name, relationship, relationship_category,
                     interaction_type, duration_minutes, time_of_day, sentiment,
                     quality_score, conflict_level, mood_before, mood_after,
                     emotional_impact, interaction_outcome, initiated_by,
                     is_virtual, location, topic, confidence, raw_mention)
                VALUES
                    (:extraction_id, :person, :relationship, :relationship_category,
                     :type, :duration, CAST(:time_of_day AS time_of_day), :sentiment,
                     :quality_score, :conflict_level, :mood_before, :mood_after,
                     :emotional_impact, :interaction_outcome, :initiated_by,
                     :is_virtual, :location, :topic, :confidence, :raw_mention)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "person": interaction.get("person"),
                    "relationship": interaction.get("relationship"),
                    "relationship_category": interaction.get("relationship_category"),
                    "type": interaction.get("interaction_type"),
                    "duration": interaction.get("duration_minutes"),
                    "time_of_day": time_of_day if time_of_day else None,
                    "sentiment": interaction.get("sentiment"),
                    "quality_score": interaction.get("quality_score"),
                    "conflict_level": interaction.get("conflict_level"),
                    "mood_before": interaction.get("mood_before"),
                    "mood_after": interaction.get("mood_after"),
                    "emotional_impact": interaction.get("emotional_impact"),
                    "interaction_outcome": interaction.get("interaction_outcome"),
                    "initiated_by": interaction.get("initiated_by"),
                    "is_virtual": interaction.get("is_virtual"),
                    "location": interaction.get("location"),
                    "topic": interaction.get("topic"),
                    "confidence": interaction.get("confidence", 0.7),
                    "raw_mention": interaction.get("raw_mention"),
                },
            )

    # ========================================================================
    # NOTES
    # ========================================================================

    async def _store_notes(
        self, extraction_id: UUID, notes: List[Dict[str, Any]]
    ) -> None:
        """Store notes (goals, gratitude, symptoms, thoughts)."""
        if not notes:
            return

        # Clear existing
        await self.db.execute(
            text("DELETE FROM extraction_notes WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        for note in notes:
            query = text(
                """
                INSERT INTO extraction_notes
                    (extraction_id, note_type, content, sentiment, confidence, raw_mention)
                VALUES
                    (:extraction_id, :type, :content, :sentiment, :confidence, :raw_mention)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "type": note.get("type", "thought"),
                    "content": note.get("content"),
                    "sentiment": note.get("sentiment"),
                    "confidence": note.get("confidence", 0.7),
                    "raw_mention": note.get("raw_mention"),
                },
            )

    # ========================================================================
    # SLEEP
    # ========================================================================

    async def _store_sleep(self, extraction_id: UUID, sleep: Dict[str, Any]) -> None:
        """Store sleep data."""
        # Delete existing sleep for this extraction
        await self.db.execute(
            text("DELETE FROM extraction_sleep WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        query = text(
            """
            INSERT INTO extraction_sleep
                (extraction_id, duration_hours, quality, bedtime, waketime,
                 disruptions, trouble_falling_asleep, woke_up_tired,
                 nap_duration_minutes, sleep_environment, pre_sleep_activity,
                 dreams_noted, confidence, raw_mention)
            VALUES
                (:extraction_id, :duration, :quality, :bedtime, :waketime,
                 :disruptions, :trouble_falling_asleep, :woke_up_tired,
                 :nap, :sleep_environment, :pre_sleep_activity,
                 :dreams_noted, :confidence, :raw_mention)
        """
        )

        await self.db.execute(
            query,
            {
                "extraction_id": extraction_id,
                "duration": sleep.get("duration_hours"),
                "quality": sleep.get("quality"),
                "bedtime": self._parse_time_string(sleep.get("bedtime")),
                "waketime": self._parse_time_string(sleep.get("waketime")),
                "disruptions": sleep.get("disruptions", 0),
                "trouble_falling_asleep": sleep.get("trouble_falling_asleep"),
                "woke_up_tired": sleep.get("woke_up_tired"),
                "nap": sleep.get("nap_minutes", 0),
                "sleep_environment": sleep.get("sleep_environment"),
                "pre_sleep_activity": sleep.get("pre_sleep_activity"),
                "dreams_noted": sleep.get("dreams_noted"),
                "confidence": sleep.get("confidence", 0.7),
                "raw_mention": sleep.get("raw_mention"),
            },
        )

    # ========================================================================
    # GAPS
    # ========================================================================

    async def _store_gaps(self, extraction_id: UUID, gaps: List[DataGap]) -> None:
        """Store extraction gaps for user clarification."""
        for gap in gaps:
            query = text(
                """
                INSERT INTO extraction_gaps
                    (extraction_id, field_category, question, context,
                     original_mention, priority, status)
                VALUES
                    (:extraction_id, :category, :question, :context,
                     :mention, :priority, 'pending')
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "category": gap.field_category,
                    "question": gap.question,
                    "context": gap.context,
                    "mention": gap.original_mention,
                    "priority": gap.priority.value,
                },
            )

    # ========================================================================
    # LOCATIONS
    # ========================================================================

    async def _store_locations(
        self, extraction_id: UUID, locations: List[Dict[str, Any]]
    ) -> None:
        """Store location data."""
        if not locations:
            return

        # Clear existing
        await self.db.execute(
            text(
                "DELETE FROM extraction_locations WHERE extraction_id = :extraction_id"
            ),
            {"extraction_id": extraction_id},
        )

        for loc in locations:
            time_of_day = loc.get("time_of_day")

            query = text(
                """
                INSERT INTO extraction_locations
                    (extraction_id, location_name, location_type, time_of_day,
                     duration_minutes, activity_context, raw_mention)
                VALUES
                    (:extraction_id, :name, :type, :time_of_day,
                     :duration, :context, :raw_mention)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "name": loc.get("location_name"),
                    "type": loc.get("location_type"),
                    "time_of_day": time_of_day if time_of_day else None,
                    "duration": loc.get("duration_minutes"),
                    "context": loc.get("activity_context"),
                    "raw_mention": loc.get("raw_mention"),
                },
            )

    # ========================================================================
    # HEALTH SYMPTOMS
    # ========================================================================

    async def _store_health(
        self, extraction_id: UUID, health: List[Dict[str, Any]]
    ) -> None:
        """Store health symptom data."""
        if not health:
            return

        # Clear existing
        await self.db.execute(
            text("DELETE FROM extraction_health WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        for symptom in health:
            time_of_day = symptom.get("time_of_day")

            query = text(
                """
                INSERT INTO extraction_health
                    (extraction_id, symptom_type, body_part, severity,
                     duration_minutes, time_of_day, possible_cause,
                     medication_taken, is_resolved, impact_score, triggers, raw_mention)
                VALUES
                    (:extraction_id, :symptom, :body_part, :severity,
                     :duration, :time_of_day, :cause,
                     :medication, :is_resolved, :impact_score, :triggers, :raw_mention)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "symptom": symptom.get("symptom_type"),
                    "body_part": symptom.get("body_part"),
                    "severity": symptom.get("severity"),
                    "duration": symptom.get("duration_minutes"),
                    "time_of_day": time_of_day if time_of_day else None,
                    "cause": symptom.get("possible_cause"),
                    "medication": symptom.get("medication_taken"),
                    "is_resolved": symptom.get("is_resolved"),
                    "impact_score": symptom.get("impact_score"),
                    "triggers": symptom.get("triggers"),
                    "raw_mention": symptom.get("raw_mention"),
                },
            )

    # ========================================================================
    # WORK / PRODUCTIVITY
    # ========================================================================

    async def _store_work(
        self, extraction_id: UUID, work: List[Dict[str, Any]]
    ) -> None:
        """Store work/productivity data."""
        if not work:
            return

        # Clear existing
        await self.db.execute(
            text("DELETE FROM extraction_work WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        for item in work:
            time_of_day = item.get("time_of_day")

            query = text(
                """
                INSERT INTO extraction_work
                    (extraction_id, work_type, project_name, duration_minutes,
                     time_of_day, productivity_score, focus_quality, interruptions,
                     accomplishments, blockers, raw_mention)
                VALUES
                    (:extraction_id, :work_type, :project_name, :duration,
                     :time_of_day, :productivity_score, :focus_quality, :interruptions,
                     :accomplishments, :blockers, :raw_mention)
            """
            )

            await self.db.execute(
                query,
                {
                    "extraction_id": extraction_id,
                    "work_type": item.get("work_type"),
                    "project_name": item.get("project_name"),
                    "duration": item.get("duration_minutes"),
                    "time_of_day": time_of_day if time_of_day else None,
                    "productivity_score": item.get("productivity_score"),
                    "focus_quality": item.get("focus_quality"),
                    "interruptions": item.get("interruptions"),
                    "accomplishments": item.get("accomplishments"),
                    "blockers": item.get("blockers"),
                    "raw_mention": item.get("raw_mention"),
                },
            )

    # ========================================================================
    # WEATHER CONTEXT
    # ========================================================================

    async def _store_weather(
        self, extraction_id: UUID, weather: Dict[str, Any]
    ) -> None:
        """Store weather context data."""
        if not weather:
            return

        # Clear existing
        await self.db.execute(
            text("DELETE FROM extraction_weather WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

        query = text(
            """
            INSERT INTO extraction_weather
                (extraction_id, weather_condition, temperature_feel,
                 mentioned_impact, raw_mention)
            VALUES
                (:extraction_id, :condition, :temp_feel,
                 :impact, :raw_mention)
        """
        )

        await self.db.execute(
            query,
            {
                "extraction_id": extraction_id,
                "condition": weather.get("condition"),
                "temp_feel": weather.get("temperature_feel"),
                "impact": weather.get("impact"),
                "raw_mention": weather.get("raw_mention"),
            },
        )

    # ========================================================================
    # GAP RESOLUTION
    # ========================================================================

    async def resolve_gap(
        self,
        gap_id: UUID,
        user_response: str,
    ) -> None:
        """Mark a gap as resolved with user's response."""
        await self.db.execute(
            text(
                """
                UPDATE extraction_gaps
                SET status = 'answered',
                    user_response = :response,
                    resolved_at = NOW()
                WHERE id = :gap_id
            """
            ),
            {"gap_id": gap_id, "response": user_response},
        )
        await self.db.commit()

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
                  AND je.entry_date >= CURRENT_DATE - :days
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
        from generalized_extraction import (
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
                SELECT person_name, relationship_type, interaction_type,
                       quality, duration_minutes, context
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
                SELECT note_type, content, importance
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
                SELECT hours, quality, bed_time, wake_time, interruptions, dreams_noted
                FROM extraction_sleep
                WHERE extraction_id = :entry_id
            """
            ),
            {"entry_id": entry_id},
        )
        row = result.fetchone()
        if row:
            sleep = dict(row._mapping)
            sleep["duration_hours"] = sleep.pop("hours", None)

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
