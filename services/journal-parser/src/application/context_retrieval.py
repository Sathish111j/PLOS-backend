"""
PLOS - Context Retrieval Engine (Normalized Schema)
Retrieves user context, baselines, patterns, and historical data.

Uses the ACTUAL normalized database structure:
- journal_extractions (base with user_id, entry_date)
- extraction_metrics (linked via extraction_id, column: value)
- extraction_sleep (linked via extraction_id, column: duration_hours)
- extraction_activities (linked via extraction_id)
- extraction_consumptions (linked via extraction_id)
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.extraction import UserBaseline
from shared.utils.context_config import get_context_config
from shared.utils.logger import get_logger

logger = get_logger(__name__)
config = get_context_config()


# ============================================================================
# METRIC TYPE IDS (from metric_types table)
# ============================================================================


class MetricTypeID:
    """Database MetricTypeID constants"""

    SLEEP_DURATION = 1
    SLEEP_QUALITY = 2
    MOOD_SCORE = 3
    ENERGY_LEVEL = 4
    STRESS_LEVEL = 5
    PRODUCTIVITY_SCORE = 6
    FOCUS_LEVEL = 7
    WATER_INTAKE = 8
    COFFEE_CUPS = 9
    WORK_HOURS = 10
    SCREEN_TIME = 11


# ============================================================================
# CONTEXT RETRIEVAL ENGINE
# ============================================================================


class ContextRetrievalEngine:
    """Optimized context retrieval using normalized schema with raw SQL"""

    def __init__(self, db_session: AsyncSession):
        self.session = db_session
        self.config = config

    async def get_full_context(self, user_id: UUID, entry_date: date) -> Dict[str, Any]:
        """
        Get comprehensive user context for journal extraction.
        This is the main entry point used by the orchestrator.

        IMPORTANT: On any error, we rollback to avoid corrupting the transaction
        state for subsequent operations (like storage).
        """
        try:
            # Get baseline
            baseline = await self._get_user_baseline(user_id, entry_date)

            # Get recent activities
            recent_activities = await self._get_recent_activities(user_id, entry_date)

            # Get recent sleep
            recent_sleep = await self._get_recent_sleep(user_id, entry_date)

            # Get 7-day averages
            seven_day_avgs = await self._get_seven_day_averages(user_id, entry_date)

            # Get user's vocabulary for Gemini to reuse
            vocabulary = await self.get_user_vocabulary(user_id)
            logger.info(
                f"Vocabulary fetched: {len(vocabulary.get('activities', []))} activities, {len(vocabulary.get('foods', []))} foods"
            )

            context = {
                "baseline": {
                    "mood_score": baseline.mood_score,
                    "mood_stddev": baseline.mood_stddev,
                    "energy_level": baseline.energy_level,
                    "energy_stddev": baseline.energy_stddev,
                    "stress_level": baseline.stress_level,
                    "stress_stddev": baseline.stress_stddev,
                    "sleep_hours": baseline.sleep_hours,
                    "sleep_stddev": baseline.sleep_stddev,
                    "sample_count": baseline.sample_count,
                },
                "recent_entries": recent_activities,
                "recent_sleep": recent_sleep,
                "recent_consumptions": [],
                "recent_metrics": {},
                "known_aliases": {},
                "seven_day_averages": seven_day_avgs,
                "entries_count": len(recent_activities),
                "vocabulary": vocabulary,
            }

            logger.info(
                f"Full context retrieved for user {user_id}: baseline sample_count={baseline.sample_count}, "
                f"vocab: {len(vocabulary.get('activities', []))} activities, {len(vocabulary.get('foods', []))} foods"
            )
            return context

        except Exception as e:
            logger.error(f"Error getting full context for user {user_id}: {e}")
            # CRITICAL: Rollback to clear any failed transaction state
            try:
                await self.session.rollback()
            except Exception:
                pass  # Ignore rollback errors
            # Return minimal fallback context
            return self._get_fallback_context()

    async def _get_user_baseline(self, user_id: UUID, entry_date: date) -> UserBaseline:
        """Calculate user baseline using raw SQL with proper joins"""
        try:
            baseline_start = entry_date - timedelta(days=self.config.baseline_days)

            # Query metrics (mood, energy, stress) with proper join
            metrics_query = text(
                """
                SELECT
                    em.metric_type_id,
                    AVG(em.value) as avg_value,
                    STDDEV_POP(em.value) as stddev_value,
                    COUNT(em.value) as sample_count
                FROM extraction_metrics em
                JOIN journal_extractions je ON em.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date >= :start_date
                  AND je.entry_date <= :end_date
                  AND em.metric_type_id IN (:mood_id, :energy_id, :stress_id)
                GROUP BY em.metric_type_id
            """
            )

            metrics_result = await self.session.execute(
                metrics_query,
                {
                    "user_id": user_id,
                    "start_date": baseline_start,
                    "end_date": entry_date,
                    "mood_id": MetricTypeID.MOOD_SCORE,
                    "energy_id": MetricTypeID.ENERGY_LEVEL,
                    "stress_id": MetricTypeID.STRESS_LEVEL,
                },
            )

            metrics_data = {}
            for row in metrics_result:
                metrics_data[row.metric_type_id] = {
                    "avg": float(row.avg_value) if row.avg_value else None,
                    "stddev": float(row.stddev_value) if row.stddev_value else 0.0,
                    "count": row.sample_count or 0,
                }

            # Query sleep hours with proper join
            sleep_query = text(
                """
                SELECT
                    AVG(es.duration_hours) as avg_sleep,
                    STDDEV_POP(es.duration_hours) as stddev_sleep,
                    COUNT(es.duration_hours) as sleep_count
                FROM extraction_sleep es
                JOIN journal_extractions je ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date >= :start_date
                  AND je.entry_date <= :end_date
            """
            )

            sleep_result = await self.session.execute(
                sleep_query,
                {
                    "user_id": user_id,
                    "start_date": baseline_start,
                    "end_date": entry_date,
                },
            )
            sleep_row = sleep_result.first()

            # Build baseline with safe defaults
            mood_data = metrics_data.get(MetricTypeID.MOOD_SCORE, {})
            energy_data = metrics_data.get(MetricTypeID.ENERGY_LEVEL, {})
            stress_data = metrics_data.get(MetricTypeID.STRESS_LEVEL, {})

            return UserBaseline(
                sleep_hours=(
                    float(sleep_row.avg_sleep)
                    if sleep_row and sleep_row.avg_sleep
                    else config.default_sleep_hours
                ),
                sleep_stddev=(
                    float(sleep_row.stddev_sleep)
                    if sleep_row and sleep_row.stddev_sleep
                    else config.default_sleep_stddev
                ),
                mood_score=mood_data.get("avg") or config.default_mood_score,
                mood_stddev=mood_data.get("stddev") or config.default_mood_stddev,
                energy_level=energy_data.get("avg") or config.default_energy_level,
                energy_stddev=energy_data.get("stddev") or config.default_energy_stddev,
                stress_level=stress_data.get("avg") or config.default_stress_level,
                stress_stddev=stress_data.get("stddev") or config.default_stress_stddev,
                sample_count=mood_data.get("count", 0),
                last_updated=datetime.now(),
            )

        except Exception as e:
            logger.warning(f"Error calculating baseline for user {user_id}: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return self._get_fallback_baseline()

    async def _get_recent_activities(
        self, user_id: UUID, entry_date: date
    ) -> List[Dict[str, Any]]:
        """Get recent activities from extraction_activities"""
        try:
            start_date = entry_date - timedelta(days=self.config.recent_entries_days)

            query = text(
                """
                SELECT
                    ea.activity_raw as activity_name,
                    ea.duration_minutes,
                    ea.activity_category as category,
                    je.entry_date
                FROM extraction_activities ea
                JOIN journal_extractions je ON ea.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date >= :start_date
                  AND je.entry_date <= :end_date
                ORDER BY je.entry_date DESC
                LIMIT :limit
            """
            )

            result = await self.session.execute(
                query,
                {
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": entry_date,
                    "limit": self.config.max_recent_entries,
                },
            )

            return [
                {
                    "activity_name": row.activity_name,
                    "duration_minutes": row.duration_minutes,
                    "category": row.category,
                    "entry_date": str(row.entry_date),
                }
                for row in result
            ]

        except Exception as e:
            logger.warning(f"Error fetching recent activities: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return []

    async def _get_recent_sleep(
        self, user_id: UUID, entry_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get most recent sleep data"""
        try:
            query = text(
                """
                SELECT
                    es.duration_hours as sleep_hours,
                    es.bedtime,
                    es.waketime,
                    es.quality,
                    je.entry_date
                FROM extraction_sleep es
                JOIN journal_extractions je ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date <= :end_date
                ORDER BY je.entry_date DESC
                LIMIT 1
            """
            )

            result = await self.session.execute(
                query,
                {
                    "user_id": user_id,
                    "end_date": entry_date,
                },
            )
            row = result.first()

            if row:
                return {
                    "sleep_hours": row.sleep_hours,
                    "bedtime": str(row.bedtime) if row.bedtime else None,
                    "waketime": str(row.waketime) if row.waketime else None,
                    "quality": row.quality,
                    "entry_date": str(row.entry_date),
                }
            return None

        except Exception as e:
            logger.warning(f"Error fetching recent sleep: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return None

    async def _get_seven_day_averages(
        self, user_id: UUID, entry_date: date
    ) -> Dict[str, Optional[float]]:
        """Calculate 7-day averages for mood, energy, sleep, stress"""
        try:
            seven_days_ago = entry_date - timedelta(days=7)

            # Get metric averages
            metrics_query = text(
                """
                SELECT
                    em.metric_type_id,
                    AVG(em.value) as avg_value
                FROM extraction_metrics em
                JOIN journal_extractions je ON em.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date >= :start_date
                  AND je.entry_date <= :end_date
                  AND em.metric_type_id IN (:mood_id, :energy_id, :stress_id)
                GROUP BY em.metric_type_id
            """
            )

            metrics_result = await self.session.execute(
                metrics_query,
                {
                    "user_id": user_id,
                    "start_date": seven_days_ago,
                    "end_date": entry_date,
                    "mood_id": MetricTypeID.MOOD_SCORE,
                    "energy_id": MetricTypeID.ENERGY_LEVEL,
                    "stress_id": MetricTypeID.STRESS_LEVEL,
                },
            )

            metrics = {}
            for row in metrics_result:
                metrics[row.metric_type_id] = (
                    float(row.avg_value) if row.avg_value else None
                )

            # Get sleep average
            sleep_query = text(
                """
                SELECT AVG(es.duration_hours) as avg_sleep
                FROM extraction_sleep es
                JOIN journal_extractions je ON es.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND je.entry_date >= :start_date
                  AND je.entry_date <= :end_date
            """
            )

            sleep_result = await self.session.execute(
                sleep_query,
                {
                    "user_id": user_id,
                    "start_date": seven_days_ago,
                    "end_date": entry_date,
                },
            )
            sleep_row = sleep_result.first()

            return {
                "avg_mood_7d": metrics.get(MetricTypeID.MOOD_SCORE),
                "avg_energy_7d": metrics.get(MetricTypeID.ENERGY_LEVEL),
                "avg_stress_7d": metrics.get(MetricTypeID.STRESS_LEVEL),
                "avg_sleep_7d": (
                    float(sleep_row.avg_sleep)
                    if sleep_row and sleep_row.avg_sleep
                    else None
                ),
            }

        except Exception as e:
            logger.warning(f"Error calculating 7-day averages: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return {
                "avg_mood_7d": None,
                "avg_energy_7d": None,
                "avg_stress_7d": None,
                "avg_sleep_7d": None,
            }

    def _get_fallback_baseline(self) -> UserBaseline:
        """Return fallback baseline with config defaults"""
        return UserBaseline(
            sleep_hours=self.config.default_sleep_hours,
            sleep_stddev=self.config.default_sleep_stddev,
            mood_score=self.config.default_mood_score,
            mood_stddev=self.config.default_mood_stddev,
            energy_level=self.config.default_energy_level,
            energy_stddev=self.config.default_energy_stddev,
            stress_level=self.config.default_stress_level,
            stress_stddev=self.config.default_stress_stddev,
            sample_count=0,
            last_updated=datetime.now(),
        )

    def _get_fallback_context(self) -> Dict[str, Any]:
        """Return fallback context with defaults"""
        baseline = self._get_fallback_baseline()
        return {
            "baseline": {
                "mood_score": baseline.mood_score,
                "mood_stddev": baseline.mood_stddev,
                "energy_level": baseline.energy_level,
                "energy_stddev": baseline.energy_stddev,
                "stress_level": baseline.stress_level,
                "stress_stddev": baseline.stress_stddev,
                "sleep_hours": baseline.sleep_hours,
                "sleep_stddev": baseline.sleep_stddev,
                "sample_count": 0,
            },
            "recent_entries": [],
            "recent_sleep": None,
            "recent_consumptions": [],
            "recent_metrics": {},
            "known_aliases": {},
            "seven_day_averages": {},
            "entries_count": 0,
            "vocabulary": {
                "activity_categories": [],
                "activities": [],
                "food_categories": [],
                "foods": [],
                "meal_types": [],
            },
        }

    async def get_user_vocabulary(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get user's existing vocabulary (categories, activities, foods).
        This helps Gemini reuse existing terms for consistency.
        """
        try:
            logger.info(f"Fetching vocabulary for user {user_id}")

            # Get activity categories the user has used
            categories_query = text(
                """
                SELECT DISTINCT ea.activity_category, ea.activity_subcategory
                FROM extraction_activities ea
                JOIN journal_extractions je ON ea.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND ea.activity_category IS NOT NULL
                ORDER BY ea.activity_category
            """
            )

            categories_result = await self.session.execute(
                categories_query, {"user_id": user_id}
            )

            activity_categories = []
            subcategories_by_category = {}
            for row in categories_result:
                if row.activity_category not in [
                    c["name"] for c in activity_categories
                ]:
                    activity_categories.append({"name": row.activity_category})
                if row.activity_subcategory:
                    cat = row.activity_category
                    if cat not in subcategories_by_category:
                        subcategories_by_category[cat] = set()
                    subcategories_by_category[cat].add(row.activity_subcategory)

            # Add subcategories to categories
            for cat in activity_categories:
                cat["subcategories"] = list(
                    subcategories_by_category.get(cat["name"], [])
                )

            # Get specific activities the user has done (top 50 by frequency)
            activities_query = text(
                """
                SELECT ea.activity_raw, ea.activity_category, COUNT(*) as freq
                FROM extraction_activities ea
                JOIN journal_extractions je ON ea.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND ea.activity_raw IS NOT NULL
                GROUP BY ea.activity_raw, ea.activity_category
                ORDER BY freq DESC
                LIMIT 50
            """
            )

            activities_result = await self.session.execute(
                activities_query, {"user_id": user_id}
            )

            activities = [
                {"name": row.activity_raw, "category": row.activity_category}
                for row in activities_result
            ]

            # Get food categories the user has consumed
            food_cat_query = text(
                """
                SELECT DISTINCT ec.food_category
                FROM extraction_consumptions ec
                JOIN journal_extractions je ON ec.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND ec.food_category IS NOT NULL
                ORDER BY ec.food_category
            """
            )

            food_cat_result = await self.session.execute(
                food_cat_query, {"user_id": user_id}
            )

            food_categories = [row.food_category for row in food_cat_result]

            # Get specific foods the user has consumed (top 50 by frequency)
            foods_query = text(
                """
                SELECT ec.item_raw, ec.food_category, ec.meal_type, COUNT(*) as freq
                FROM extraction_consumptions ec
                JOIN journal_extractions je ON ec.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND ec.item_raw IS NOT NULL
                GROUP BY ec.item_raw, ec.food_category, ec.meal_type
                ORDER BY freq DESC
                LIMIT 50
            """
            )

            foods_result = await self.session.execute(foods_query, {"user_id": user_id})

            foods = [
                {
                    "name": row.item_raw,
                    "category": row.food_category,
                    "typical_meal": row.meal_type,
                }
                for row in foods_result
            ]

            # Get meal types the user has used
            meal_types_query = text(
                """
                SELECT DISTINCT ec.meal_type
                FROM extraction_consumptions ec
                JOIN journal_extractions je ON ec.extraction_id = je.id
                WHERE je.user_id = :user_id
                  AND ec.meal_type IS NOT NULL
                ORDER BY ec.meal_type
            """
            )

            meal_types_result = await self.session.execute(
                meal_types_query, {"user_id": user_id}
            )

            meal_types = [row.meal_type for row in meal_types_result]

            result = {
                "activity_categories": activity_categories,
                "activities": activities,
                "food_categories": food_categories,
                "foods": foods,
                "meal_types": meal_types,
            }

            logger.info(
                f"Vocabulary result: {len(activity_categories)} categories, "
                f"{len(activities)} activities, {len(foods)} foods"
            )

            return result

        except Exception as e:
            logger.warning(f"Error fetching user vocabulary: {e}", exc_info=True)
            try:
                await self.session.rollback()
            except Exception:
                pass
            return {
                "activity_categories": [],
                "activities": [],
                "food_categories": [],
                "foods": [],
                "meal_types": [],
            }


# ============================================================================
# MODULE FUNCTIONS
# ============================================================================


async def get_context_engine(db_session: AsyncSession) -> ContextRetrievalEngine:
    """Factory function to create context retrieval engine"""
    return ContextRetrievalEngine(db_session)
