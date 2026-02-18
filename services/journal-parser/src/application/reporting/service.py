"""Reporting queries for journal analytics."""

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ReportService:
    """Runs reporting queries for journal data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _resolve_date_range(days: int, end_date: Optional[date]) -> Tuple[date, date]:
        end = end_date or date.today()
        start = end - timedelta(days=max(days, 1) - 1)
        return start, end

    @staticmethod
    def _build_date_series(start_date: date, end_date: date) -> List[date]:
        days = (end_date - start_date).days
        return [start_date + timedelta(days=offset) for offset in range(days + 1)]

    @staticmethod
    def _sum(values: Iterable[Optional[float]]) -> Optional[float]:
        total = 0.0
        has_value = False
        for value in values:
            if value is None:
                continue
            total += float(value)
            has_value = True
        return total if has_value else None

    @staticmethod
    def _average(values: Iterable[Optional[float]]) -> Optional[float]:
        total = 0.0
        count = 0
        for value in values:
            if value is None:
                continue
            total += float(value)
            count += 1
        if count == 0:
            return None
        return total / count

    async def get_context_snapshot(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Fetch the latest context snapshot from context broker state."""
        result = await self.db.execute(
            text(
                """
                SELECT
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
            ),
            {"user_id": user_id},
        )

        row = result.fetchone()
        if not row:
            return None

        return {
            "current_mood_score": row[0],
            "current_energy_level": row[1],
            "current_stress_level": row[2],
            "sleep_quality_avg_7d": float(row[3]) if row[3] is not None else None,
            "productivity_score_avg_7d": float(row[4]) if row[4] is not None else None,
            "active_goals_count": row[5],
            "pending_tasks_count": row[6],
            "completed_tasks_today": row[7],
            "context_data": row[8] or {},
            "updated_at": row[9],
        }

    async def get_daily_calories(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Optional[float]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    SUM(calories_in) AS calories
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        return {
            row[0]: float(row[1]) if row[1] is not None else None
            for row in result.fetchall()
        }

    async def get_daily_sleep(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Dict[str, Optional[float]]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    AVG(sleep_hours) AS sleep_hours,
                    AVG(sleep_quality) AS sleep_quality
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        data: Dict[date, Dict[str, Optional[float]]] = {}
        for row in result.fetchall():
            data[row[0]] = {
                "sleep_hours": float(row[1]) if row[1] is not None else None,
                "sleep_quality": float(row[2]) if row[2] is not None else None,
            }
        return data

    async def get_daily_activity(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Dict[str, Optional[int]]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    SUM(activity_minutes) AS minutes,
                    SUM(activity_calories) AS calories
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        data: Dict[date, Dict[str, Optional[int]]] = {}
        for row in result.fetchall():
            data[row[0]] = {
                "minutes": int(row[1]) if row[1] is not None else None,
                "calories": int(row[2]) if row[2] is not None else None,
            }
        return data

    async def get_daily_mood(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Optional[float]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    AVG(mood_score) AS mood_score
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        return {
            row[0]: float(row[1]) if row[1] is not None else None
            for row in result.fetchall()
        }

    async def get_daily_water(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Optional[float]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    SUM(water_ml) AS water_ml
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        return {
            row[0]: float(row[1]) if row[1] is not None else None
            for row in result.fetchall()
        }

    async def get_daily_steps(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Optional[int]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    SUM(steps) AS steps
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        return {
            row[0]: int(row[1]) if row[1] is not None else None
            for row in result.fetchall()
        }

    async def get_daily_nutrition(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[date, Dict[str, Optional[float]]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket('1 day', ts)::date AS entry_date,
                    SUM(calories_in) AS calories,
                    SUM(protein_g) AS protein_g,
                    SUM(carbs_g) AS carbs_g,
                    SUM(fat_g) AS fat_g
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY 1
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        data: Dict[date, Dict[str, Optional[float]]] = {}
        for row in result.fetchall():
            data[row[0]] = {
                "calories": float(row[1]) if row[1] is not None else None,
                "protein_g": float(row[2]) if row[2] is not None else None,
                "carbs_g": float(row[3]) if row[3] is not None else None,
                "fat_g": float(row[4]) if row[4] is not None else None,
            }
        return data

    async def get_social_summary(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        daily_result = await self.db.execute(
            text(
                """
                SELECT
                    je.entry_date AS entry_date,
                    COUNT(*) AS interactions
                FROM journal_extractions je
                JOIN extraction_social es ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
                GROUP BY je.entry_date
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        daily = {
            row[0]: int(row[1]) if row[1] is not None else None
            for row in daily_result.fetchall()
        }

        totals_result = await self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_interactions
                FROM journal_extractions je
                JOIN extraction_social es ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        total_interactions = totals_result.scalar() or 0

        relationship_result = await self.db.execute(
            text(
                """
                SELECT
                    COALESCE(es.relationship_category, 'other') AS category,
                    COUNT(*) AS count
                FROM journal_extractions je
                JOIN extraction_social es ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
                GROUP BY COALESCE(es.relationship_category, 'other')
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        by_relationship_category = {
            row[0]: int(row[1]) for row in relationship_result.fetchall()
        }

        top_people_result = await self.db.execute(
            text(
                """
                SELECT
                    COALESCE(es.person_name, es.relationship, 'unknown') AS person,
                    COUNT(*) AS interactions
                FROM journal_extractions je
                JOIN extraction_social es ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
                GROUP BY COALESCE(es.person_name, es.relationship, 'unknown')
                ORDER BY interactions DESC
                LIMIT 10
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        top_people = [
            {"person": row[0], "interactions": int(row[1])}
            for row in top_people_result.fetchall()
        ]

        return {
            "daily": daily,
            "summary": {
                "total_interactions": int(total_interactions),
                "by_relationship_category": by_relationship_category,
                "top_people": top_people,
            },
        }

    async def get_health_summary(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        daily_result = await self.db.execute(
            text(
                """
                SELECT
                    je.entry_date AS entry_date,
                    COUNT(*) AS symptoms
                FROM journal_extractions je
                JOIN extraction_health eh ON eh.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
                GROUP BY je.entry_date
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        daily = {
            row[0]: int(row[1]) if row[1] is not None else None
            for row in daily_result.fetchall()
        }

        total_result = await self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_symptoms
                FROM journal_extractions je
                JOIN extraction_health eh ON eh.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        total_symptoms = total_result.scalar() or 0

        top_result = await self.db.execute(
            text(
                """
                SELECT
                    eh.symptom_type,
                    COUNT(*) AS count
                FROM journal_extractions je
                JOIN extraction_health eh ON eh.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
                GROUP BY eh.symptom_type
                ORDER BY count DESC
                LIMIT 10
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        top_symptoms = [
            {"symptom": row[0], "count": int(row[1])} for row in top_result.fetchall()
        ]

        return {
            "daily": daily,
            "summary": {
                "total_symptoms": int(total_symptoms),
                "top_symptoms": top_symptoms,
            },
        }

    async def get_work_summary(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        daily_result = await self.db.execute(
            text(
                """
                SELECT
                    je.entry_date AS entry_date,
                    SUM(ew.duration_minutes) AS minutes,
                    AVG(ew.productivity_score) AS productivity_avg
                FROM journal_extractions je
                JOIN extraction_work ew ON ew.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date BETWEEN :start_date AND :end_date
                GROUP BY je.entry_date
            """
            ),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )

        daily = {
            row[0]: {
                "minutes": int(row[1]) if row[1] is not None else None,
                "productivity_avg": float(row[2]) if row[2] is not None else None,
            }
            for row in daily_result.fetchall()
        }

        total_minutes = self._sum(
            [item["minutes"] for item in daily.values() if item.get("minutes")]
        )
        avg_productivity = self._average(
            [
                item["productivity_avg"]
                for item in daily.values()
                if item.get("productivity_avg") is not None
            ]
        )

        return {
            "daily": daily,
            "summary": {
                "total_minutes": int(total_minutes) if total_minutes else None,
                "avg_productivity": avg_productivity,
            },
        }

    async def get_weekly_overview(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        calories_by_day = await self.get_daily_calories(user_id, start_date, end_date)
        sleep_by_day = await self.get_daily_sleep(user_id, start_date, end_date)
        mood_by_day = await self.get_daily_mood(user_id, start_date, end_date)
        water_by_day = await self.get_daily_water(user_id, start_date, end_date)
        steps_by_day = await self.get_daily_steps(user_id, start_date, end_date)
        activity_by_day = await self.get_daily_activity(user_id, start_date, end_date)
        context_snapshot = await self.get_context_snapshot(user_id)

        date_series = self._build_date_series(start_date, end_date)
        daily = []
        for day in date_series:
            sleep_values = sleep_by_day.get(day, {})
            activity_values = activity_by_day.get(day, {})
            daily.append(
                {
                    "date": day,
                    "calories_in": calories_by_day.get(day),
                    "water_ml": water_by_day.get(day),
                    "steps": steps_by_day.get(day),
                    "sleep_hours": sleep_values.get("sleep_hours"),
                    "sleep_quality": sleep_values.get("sleep_quality"),
                    "mood_score": mood_by_day.get(day),
                    "activity_minutes": activity_values.get("minutes"),
                    "activity_calories": activity_values.get("calories"),
                }
            )

        summary = {
            "total_calories_in": self._sum([item["calories_in"] for item in daily]),
            "avg_sleep_hours": self._average([item["sleep_hours"] for item in daily]),
            "avg_sleep_quality": self._average(
                [item["sleep_quality"] for item in daily]
            ),
            "avg_mood_score": self._average([item["mood_score"] for item in daily]),
            "total_water_ml": self._sum([item["water_ml"] for item in daily]),
            "total_steps": None,
            "avg_steps": self._average([item["steps"] for item in daily]),
            "total_activity_minutes": None,
            "total_activity_calories": None,
        }

        activity_minutes_total = self._sum([item["activity_minutes"] for item in daily])
        activity_calories_total = self._sum(
            [item["activity_calories"] for item in daily]
        )
        summary["total_activity_minutes"] = (
            int(activity_minutes_total) if activity_minutes_total is not None else None
        )
        summary["total_activity_calories"] = (
            int(activity_calories_total)
            if activity_calories_total is not None
            else None
        )
        steps_total = self._sum([item["steps"] for item in daily])
        summary["total_steps"] = int(steps_total) if steps_total is not None else None

        return {
            "daily": daily,
            "summary": summary,
            "context_snapshot": context_snapshot,
        }

    async def get_timeseries_overview(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        bucket_interval: timedelta,
    ) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    time_bucket(:bucket_interval, ts) AS bucket_time,
                    SUM(calories_in) AS calories_in,
                    AVG(sleep_hours) AS sleep_hours,
                    AVG(sleep_quality) AS sleep_quality,
                    AVG(mood_score) AS mood_score,
                    SUM(water_ml) AS water_ml,
                    SUM(steps) AS steps,
                    SUM(activity_minutes) AS activity_minutes,
                    SUM(activity_calories) AS activity_calories,
                    SUM(protein_g) AS protein_g,
                    SUM(carbs_g) AS carbs_g,
                    SUM(fat_g) AS fat_g
                FROM journal_timeseries
                WHERE user_id = :user_id
                  AND entry_date BETWEEN :start_date AND :end_date
                GROUP BY bucket_time
                ORDER BY bucket_time
                """
            ),
            {
                "bucket_interval": bucket_interval,
                "user_id": user_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        rows = []
        for row in result.fetchall():
            rows.append(
                {
                    "bucket_time": row[0],
                    "calories_in": float(row[1]) if row[1] is not None else None,
                    "sleep_hours": float(row[2]) if row[2] is not None else None,
                    "sleep_quality": float(row[3]) if row[3] is not None else None,
                    "mood_score": float(row[4]) if row[4] is not None else None,
                    "water_ml": float(row[5]) if row[5] is not None else None,
                    "steps": int(row[6]) if row[6] is not None else None,
                    "activity_minutes": int(row[7]) if row[7] is not None else None,
                    "activity_calories": int(row[8]) if row[8] is not None else None,
                    "protein_g": float(row[9]) if row[9] is not None else None,
                    "carbs_g": float(row[10]) if row[10] is not None else None,
                    "fat_g": float(row[11]) if row[11] is not None else None,
                }
            )
        return rows
