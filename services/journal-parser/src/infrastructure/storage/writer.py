"""
PLOS - Extraction Writer
Write-focused repository for extraction data.
"""

from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from application.extraction.generalized_extraction import (
    DataGap,
    NormalizedActivity,
    NormalizedConsumption,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_EXTRACTION_TABLES = {
    "extraction_metrics",
    "extraction_activities",
    "extraction_consumptions",
    "extraction_social",
    "extraction_notes",
    "extraction_sleep",
    "extraction_locations",
    "extraction_health",
    "extraction_work",
    "extraction_weather",
}


class ExtractionWriter:
    """Write-only repository for extraction-related tables."""

    def __init__(
        self,
        db: AsyncSession,
        parse_time: Callable[[Optional[str]], Optional[Any]],
        normalize_time_of_day: Callable[[Optional[str]], Optional[str]],
    ) -> None:
        self.db = db
        self._parse_time = parse_time
        self._normalize_time_of_day = normalize_time_of_day

    async def _clear_extraction_rows(self, table: str, extraction_id: UUID) -> None:
        if table not in ALLOWED_EXTRACTION_TABLES:
            raise ValueError(f"Unsupported extraction table: {table}")
        await self.db.execute(
            text(f"DELETE FROM {table} WHERE extraction_id = :extraction_id"),
            {"extraction_id": extraction_id},
        )

    async def store_metrics(
        self, extraction_id: UUID, metrics: Dict[str, Dict[str, Any]]
    ) -> None:
        if not metrics:
            return

        await self._clear_extraction_rows("extraction_metrics", extraction_id)

        for metric_name, metric_data in metrics.items():
            value = metric_data.get("value")
            if value is None:
                continue

            metric_type_id = await self._resolve_metric_type(metric_name)
            time_of_day = self._normalize_time_of_day(metric_data.get("time_of_day"))

            await self.db.execute(
                text(
                    """
                    INSERT INTO extraction_metrics
                        (extraction_id, metric_type_id, value, time_of_day, confidence)
                    VALUES
                        (:extraction_id, :metric_type_id, :value, CAST(:time_of_day AS time_of_day), :confidence)
                """
                ),
                {
                    "extraction_id": extraction_id,
                    "metric_type_id": metric_type_id,
                    "value": float(value),
                    "time_of_day": time_of_day,
                    "confidence": metric_data.get("confidence", 0.7),
                },
            )

    async def _resolve_metric_type(self, metric_name: str) -> int:
        result = await self.db.execute(
            text("SELECT id FROM metric_types WHERE name = :name"),
            {"name": metric_name},
        )
        row = result.fetchone()
        if row:
            return row[0]

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
        if row is None:
            raise ValueError(f"Failed to create metric type: {metric_name}")
        return row[0]

    async def store_activities(
        self, extraction_id: UUID, activities: List[NormalizedActivity]
    ) -> None:
        if not activities:
            return

        await self._clear_extraction_rows("extraction_activities", extraction_id)

        for activity in activities:
            time_of_day = None
            if activity.time_of_day:
                time_of_day = self._normalize_time_of_day(activity.time_of_day.value)

            await self.db.execute(
                text(
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
                ),
                {
                    "extraction_id": extraction_id,
                    "activity_raw": activity.raw_name,
                    "activity_category": activity.category,
                    "activity_subcategory": getattr(activity, "subcategory", None),
                    "duration": activity.duration_minutes,
                    "time_of_day": time_of_day,
                    "start_time": self._parse_time(activity.start_time),
                    "end_time": self._parse_time(activity.end_time),
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

    async def store_consumptions(
        self, extraction_id: UUID, consumptions: List[NormalizedConsumption]
    ) -> None:
        if not consumptions:
            return

        await self._clear_extraction_rows("extraction_consumptions", extraction_id)

        for item in consumptions:
            item_raw = item.raw_name
            if isinstance(item_raw, list):
                item_raw = ", ".join(str(value) for value in item_raw if value)

            raw_mention = item.raw_mention
            if isinstance(raw_mention, list):
                raw_mention = ", ".join(str(value) for value in raw_mention if value)

            time_of_day = None
            if item.time_of_day:
                time_of_day = self._normalize_time_of_day(item.time_of_day.value)

            await self.db.execute(
                text(
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
                ),
                {
                    "extraction_id": extraction_id,
                    "item_raw": item_raw,
                    "food_category": getattr(item, "food_category", None),
                    "type": item.consumption_type,
                    "meal_type": item.meal_type,
                    "time_of_day": time_of_day,
                    "time": self._parse_time(item.consumption_time),
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "calories": item.calories,
                    "protein": item.protein_g,
                    "carbs": item.carbs_g,
                    "fat": item.fat_g,
                    "fiber": item.fiber_g,
                    "sugar": item.sugar_g,
                    "sodium": item.sodium_mg,
                    "caffeine_mg": getattr(item, "caffeine_mg", None),
                    "alcohol_units": getattr(item, "alcohol_units", None),
                    "is_processed": getattr(item, "is_processed", None),
                    "water_ml": getattr(item, "water_ml", None),
                    "healthy": item.is_healthy,
                    "home_cooked": item.is_home_cooked,
                    "confidence": item.confidence,
                    "raw_mention": raw_mention,
                },
            )

    async def store_social(
        self, extraction_id: UUID, social: List[Dict[str, Any]]
    ) -> None:
        if not social:
            return

        await self._clear_extraction_rows("extraction_social", extraction_id)

        for interaction in social:
            time_of_day = self._normalize_time_of_day(interaction.get("time_of_day"))

            await self.db.execute(
                text(
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
                ),
                {
                    "extraction_id": extraction_id,
                    "person": interaction.get("person"),
                    "relationship": interaction.get("relationship"),
                    "relationship_category": interaction.get("relationship_category"),
                    "type": interaction.get("interaction_type"),
                    "duration": interaction.get("duration_minutes"),
                    "time_of_day": time_of_day,
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

    async def store_notes(
        self, extraction_id: UUID, notes: List[Dict[str, Any]]
    ) -> None:
        if not notes:
            return

        await self._clear_extraction_rows("extraction_notes", extraction_id)

        for note in notes:
            await self.db.execute(
                text(
                    """
                    INSERT INTO extraction_notes
                        (extraction_id, note_type, content, sentiment, confidence, raw_mention)
                    VALUES
                        (:extraction_id, :type, :content, :sentiment, :confidence, :raw_mention)
                """
                ),
                {
                    "extraction_id": extraction_id,
                    "type": note.get("type", "thought"),
                    "content": note.get("content"),
                    "sentiment": note.get("sentiment"),
                    "confidence": note.get("confidence", 0.7),
                    "raw_mention": note.get("raw_mention"),
                },
            )

    async def store_sleep(self, extraction_id: UUID, sleep: Dict[str, Any]) -> None:
        await self._clear_extraction_rows("extraction_sleep", extraction_id)

        await self.db.execute(
            text(
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
            ),
            {
                "extraction_id": extraction_id,
                "duration": sleep.get("duration_hours"),
                "quality": sleep.get("quality"),
                "bedtime": self._parse_time(sleep.get("bedtime")),
                "waketime": self._parse_time(sleep.get("waketime")),
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

    async def store_locations(
        self, extraction_id: UUID, locations: List[Dict[str, Any]]
    ) -> None:
        if not locations:
            return

        await self._clear_extraction_rows("extraction_locations", extraction_id)

        for loc in locations:
            if not loc.get("location_name"):
                logger.warning(
                    "Skipping location without location_name: %s",
                    loc.get("raw_mention"),
                )
                continue
            time_of_day = self._normalize_time_of_day(loc.get("time_of_day"))

            await self.db.execute(
                text(
                    """
                    INSERT INTO extraction_locations
                        (extraction_id, location_name, location_type, time_of_day,
                         duration_minutes, activity_context, raw_mention)
                    VALUES
                        (:extraction_id, :name, :type, :time_of_day,
                         :duration, :context, :raw_mention)
                """
                ),
                {
                    "extraction_id": extraction_id,
                    "name": loc.get("location_name"),
                    "type": loc.get("location_type"),
                    "time_of_day": time_of_day,
                    "duration": loc.get("duration_minutes"),
                    "context": loc.get("activity_context"),
                    "raw_mention": loc.get("raw_mention"),
                },
            )

    async def store_health(
        self, extraction_id: UUID, health: List[Dict[str, Any]]
    ) -> None:
        if not health:
            return

        await self._clear_extraction_rows("extraction_health", extraction_id)

        for symptom in health:
            if not symptom.get("symptom_type"):
                logger.warning(
                    "Skipping health entry without symptom_type: %s",
                    symptom.get("raw_mention"),
                )
                continue

            time_of_day = self._normalize_time_of_day(symptom.get("time_of_day"))

            await self.db.execute(
                text(
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
                ),
                {
                    "extraction_id": extraction_id,
                    "symptom": symptom.get("symptom_type"),
                    "body_part": symptom.get("body_part"),
                    "severity": symptom.get("severity"),
                    "duration": symptom.get("duration_minutes"),
                    "time_of_day": time_of_day,
                    "cause": symptom.get("possible_cause"),
                    "medication": symptom.get("medication_taken"),
                    "is_resolved": symptom.get("is_resolved"),
                    "impact_score": symptom.get("impact_score"),
                    "triggers": symptom.get("triggers"),
                    "raw_mention": symptom.get("raw_mention"),
                },
            )

    async def store_work(self, extraction_id: UUID, work: List[Dict[str, Any]]) -> None:
        if not work:
            return

        await self._clear_extraction_rows("extraction_work", extraction_id)

        for item in work:
            time_of_day = self._normalize_time_of_day(item.get("time_of_day"))

            await self.db.execute(
                text(
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
                ),
                {
                    "extraction_id": extraction_id,
                    "work_type": item.get("work_type"),
                    "project_name": item.get("project_name"),
                    "duration": item.get("duration_minutes"),
                    "time_of_day": time_of_day,
                    "productivity_score": item.get("productivity_score"),
                    "focus_quality": item.get("focus_quality"),
                    "interruptions": item.get("interruptions"),
                    "accomplishments": item.get("accomplishments"),
                    "blockers": item.get("blockers"),
                    "raw_mention": item.get("raw_mention"),
                },
            )

    async def store_weather(self, extraction_id: UUID, weather: Dict[str, Any]) -> None:
        if not weather:
            return

        await self._clear_extraction_rows("extraction_weather", extraction_id)

        await self.db.execute(
            text(
                """
                INSERT INTO extraction_weather
                    (extraction_id, weather_condition, temperature_feel,
                     mentioned_impact, raw_mention)
                VALUES
                    (:extraction_id, :condition, :temp_feel,
                     :impact, :raw_mention)
            """
            ),
            {
                "extraction_id": extraction_id,
                "condition": weather.get("condition"),
                "temp_feel": weather.get("temperature_feel"),
                "impact": weather.get("impact"),
                "raw_mention": weather.get("raw_mention"),
            },
        )

    async def store_gaps(self, extraction_id: UUID, gaps: List[DataGap]) -> None:
        for gap in gaps:
            await self.db.execute(
                text(
                    """
                    INSERT INTO extraction_gaps
                        (extraction_id, field_category, question, context,
                         original_mention, priority, status)
                    VALUES
                        (:extraction_id, :category, :question, :context,
                         :mention, :priority, 'pending')
                """
                ),
                {
                    "extraction_id": extraction_id,
                    "category": gap.field_category,
                    "question": gap.question,
                    "context": gap.context,
                    "mention": gap.original_mention,
                    "priority": gap.priority.value,
                },
            )
