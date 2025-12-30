"""
PLOS - Context Retrieval Engine
Retrieves user context, baselines, patterns, and historical data for intelligent extraction.

Fixed issues:
- Uses entry_date instead of date.today() for baseline calculation
- Consistent date type handling
- Proper exception handling with fallback values
- Fixed statistics.stdev() crash (requires >= 2 samples)
- Uses shared database models to avoid circular imports
- Optimized JSONB queries
- Uses PostgreSQL UPSERT for caching
- Configuration-based magic numbers
- Safe dictionary navigation
- Comprehensive error recovery
"""

import asyncio
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Float, and_, cast, desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.database import (
    ActivityImpactDB,
    JournalExtractionDB,
    RelationshipHistoryDB,
    SleepDebtLogDB,
    UserPatternDB,
)
from shared.models.extraction import UserBaseline
from shared.utils.context_config import get_context_config
from shared.utils.logger import get_logger
from shared.utils.metrics import (
    record_cache_access,
)

logger = get_logger(__name__)
config = get_context_config()


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class RelationshipStateResponse:
    """Structured response for relationship state"""

    def __init__(
        self,
        state: str = "HARMONY",
        days_in_state: int = 0,
        severity: int = 0,
        trigger: Optional[str] = None,
        expected_resolution_days: Optional[int] = None,
        resolved: bool = False,
    ):
        self.state = state
        self.days_in_state = days_in_state
        self.severity = severity
        self.trigger = trigger
        self.expected_resolution_days = expected_resolution_days
        self.resolved = resolved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "days_in_state": self.days_in_state,
            "severity": self.severity,
            "trigger": self.trigger,
            "expected_resolution_days": self.expected_resolution_days,
            "resolved": self.resolved,
        }


class SevenDayAverages:
    """Structured response for 7-day averages"""

    def __init__(
        self,
        avg_mood_7d: Optional[float] = None,
        avg_energy_7d: Optional[float] = None,
        avg_sleep_7d: Optional[float] = None,
        avg_stress_7d: Optional[float] = None,
    ):
        self.avg_mood_7d = avg_mood_7d
        self.avg_energy_7d = avg_energy_7d
        self.avg_sleep_7d = avg_sleep_7d
        self.avg_stress_7d = avg_stress_7d

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "avg_mood_7d": self.avg_mood_7d,
            "avg_energy_7d": self.avg_energy_7d,
            "avg_sleep_7d": self.avg_sleep_7d,
            "avg_stress_7d": self.avg_stress_7d,
        }


# ============================================================================
# CONTEXT RETRIEVAL ENGINE
# ============================================================================


class ContextRetrievalEngine:
    """
    Retrieves comprehensive user context for intelligent journal extraction.

    Provides:
    - 30-day baseline (mood, sleep, energy averages)
    - 7-day recent entries
    - Day-of-week patterns
    - Relationship state
    - Sleep debt accumulation
    - Activity impact matrix

    All methods use entry_date for calculations, NOT date.today().
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.config = config

    async def get_full_context(self, user_id: UUID, entry_date: date) -> Dict[str, Any]:
        """
        Get complete user context for extraction.

        Args:
            user_id: User UUID
            entry_date: The journal entry date (used for all calculations)

        Returns:
            Complete context dictionary with all available data
        """
        logger.info(f"Retrieving full context for user {user_id}, date {entry_date}")

        try:
            # Execute all queries in parallel for speed
            results = await asyncio.gather(
                self.get_user_baseline(user_id, entry_date),
                self.get_recent_entries(
                    user_id, entry_date, days=self.config.recent_entries_days
                ),
                self.get_day_of_week_pattern(user_id, entry_date.weekday()),
                self.get_relationship_state(user_id, entry_date),
                self.get_sleep_debt(user_id, entry_date),
                self.get_activity_patterns(user_id),
                return_exceptions=True,
            )

            (
                baseline,
                recent_entries,
                dow_pattern,
                rel_state,
                sleep_debt,
                activity_patterns,
            ) = results

            # Handle exceptions with proper fallback values
            if isinstance(baseline, Exception):
                logger.warning(f"Baseline retrieval failed: {baseline}")
                baseline = self._get_default_baseline()

            if isinstance(recent_entries, Exception):
                logger.warning(f"Recent entries retrieval failed: {recent_entries}")
                recent_entries = []

            if isinstance(dow_pattern, Exception):
                logger.warning(f"DOW pattern retrieval failed: {dow_pattern}")
                dow_pattern = {}

            if isinstance(rel_state, Exception):
                logger.warning(f"Relationship state retrieval failed: {rel_state}")
                rel_state = self._get_default_relationship().to_dict()

            if isinstance(sleep_debt, Exception):
                logger.warning(f"Sleep debt retrieval failed: {sleep_debt}")
                sleep_debt = 0.0

            if isinstance(activity_patterns, Exception):
                logger.warning(
                    f"Activity patterns retrieval failed: {activity_patterns}"
                )
                activity_patterns = []

            # Calculate 7-day averages from already-fetched recent entries (no extra query)
            seven_day = self._calculate_seven_day_averages(recent_entries)

            context = {
                "baseline": baseline,
                "recent_entries": recent_entries,
                "day_of_week_pattern": dow_pattern,
                "relationship_state": (
                    rel_state.to_dict()
                    if isinstance(rel_state, RelationshipStateResponse)
                    else rel_state
                ),
                "sleep_debt": sleep_debt,
                "activity_patterns": activity_patterns,
                "seven_day_context": seven_day.to_dict(),
            }

            logger.info(
                f"Retrieved context with {len(context.get('recent_entries', []))} recent entries"
            )
            return context

        except Exception as e:
            logger.error(f"Critical error retrieving context: {e}", exc_info=True)
            return self._get_minimal_context(user_id)

    async def get_user_baseline(
        self, user_id: UUID, entry_date: date, days: Optional[int] = None
    ) -> UserBaseline:
        """
        Calculate user baseline from historical data.

        Args:
            user_id: User UUID
            entry_date: The reference date (NOT today())
            days: Number of days to look back (default from config)

        Returns:
            UserBaseline with averages and standard deviations
        """
        days = days or self.config.baseline_days
        logger.debug(f"Calculating {days}-day baseline for user {user_id}")

        # Try to get from cache first
        cached_baseline = await self._get_cached_baseline(user_id)
        if cached_baseline and self._is_cache_fresh(cached_baseline):
            logger.debug(
                f"Using cached baseline (updated {cached_baseline.last_updated})"
            )
            record_cache_access("database", hit=True)
            return cached_baseline

        record_cache_access("database", hit=False)

        # Calculate from entry_date, NOT today()
        from_date = entry_date - timedelta(days=days)

        # Optimized query: extract JSONB fields in database
        if self.config.use_optimized_queries:
            baseline = await self._get_baseline_optimized(
                user_id, from_date, entry_date, days
            )
        else:
            baseline = await self._get_baseline_standard(
                user_id, from_date, entry_date, days
            )

        # Cache for future use
        if baseline.sample_count > 0:
            await self._cache_baseline(user_id, baseline, days)

        logger.info(
            f"Calculated baseline: sleep={baseline.sleep_hours:.1f}"
            f"+/-{baseline.sleep_stddev:.1f}, "
            f"mood={baseline.mood_score:.1f}+/-{baseline.mood_stddev:.1f}"
        )

        return baseline

    async def _get_baseline_optimized(
        self, user_id: UUID, from_date: date, entry_date: date, days: int
    ) -> UserBaseline:
        """Get baseline using optimized JSONB extraction in database"""
        query = select(
            cast(
                JournalExtractionDB.extracted_data["health"]["sleep_hours"], Float
            ).label("sleep_hours"),
            cast(JournalExtractionDB.extracted_data["mood"]["score"], Float).label(
                "mood_score"
            ),
            cast(
                JournalExtractionDB.extracted_data["health"]["energy_level"], Float
            ).label("energy_level"),
            cast(
                JournalExtractionDB.extracted_data["health"]["stress_level"], Float
            ).label("stress_level"),
        ).where(
            and_(
                JournalExtractionDB.user_id == user_id,
                JournalExtractionDB.entry_date >= from_date,
                JournalExtractionDB.entry_date < entry_date,
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            logger.warning(f"No entries found for user {user_id} in last {days} days")
            return self._get_default_baseline()

        # Extract values with None filtering
        sleep_hours = [row.sleep_hours for row in rows if row.sleep_hours is not None]
        mood_scores = [row.mood_score for row in rows if row.mood_score is not None]
        energy_levels = [
            row.energy_level for row in rows if row.energy_level is not None
        ]
        stress_levels = [
            row.stress_level for row in rows if row.stress_level is not None
        ]

        return self._calculate_baseline_stats(
            sleep_hours, mood_scores, energy_levels, stress_levels, len(rows)
        )

    async def _get_baseline_standard(
        self, user_id: UUID, from_date: date, entry_date: date, days: int
    ) -> UserBaseline:
        """Get baseline using standard query (fallback)"""
        query = (
            select(JournalExtractionDB)
            .where(
                and_(
                    JournalExtractionDB.user_id == user_id,
                    JournalExtractionDB.entry_date >= from_date,
                    JournalExtractionDB.entry_date < entry_date,
                )
            )
            .order_by(desc(JournalExtractionDB.entry_date))
        )

        result = await self.db.execute(query)
        entries = result.scalars().all()

        if not entries:
            logger.warning(f"No entries found for user {user_id} in last {days} days")
            return self._get_default_baseline()

        # Extract metrics with safe navigation
        sleep_hours = []
        mood_scores = []
        energy_levels = []
        stress_levels = []

        for entry in entries:
            data = entry.extracted_data or {}

            # Safe navigation for health data
            health = data.get("health") or {}
            sleep_val = health.get("sleep_hours")
            if sleep_val is not None:
                try:
                    sleep_hours.append(float(sleep_val))
                except (ValueError, TypeError):
                    pass

            energy_val = health.get("energy_level")
            if energy_val is not None:
                try:
                    energy_levels.append(float(energy_val))
                except (ValueError, TypeError):
                    pass

            stress_val = health.get("stress_level")
            if stress_val is not None:
                try:
                    stress_levels.append(float(stress_val))
                except (ValueError, TypeError):
                    pass

            # Safe navigation for mood data
            mood = data.get("mood") or {}
            mood_val = mood.get("score")
            if mood_val is not None:
                try:
                    mood_scores.append(float(mood_val))
                except (ValueError, TypeError):
                    pass

        return self._calculate_baseline_stats(
            sleep_hours, mood_scores, energy_levels, stress_levels, len(entries)
        )

    def _calculate_baseline_stats(
        self,
        sleep_hours: List[float],
        mood_scores: List[float],
        energy_levels: List[float],
        stress_levels: List[float],
        sample_count: int,
    ) -> UserBaseline:
        """Calculate statistics for baseline with proper stdev handling"""
        min_samples = self.config.min_samples_for_stdev

        return UserBaseline(
            sleep_hours=(
                statistics.mean(sleep_hours)
                if sleep_hours
                else self.config.default_sleep_hours
            ),
            sleep_stddev=(
                statistics.stdev(sleep_hours)
                if len(sleep_hours) >= min_samples
                else self.config.default_sleep_stddev
            ),
            mood_score=(
                statistics.mean(mood_scores)
                if mood_scores
                else self.config.default_mood_score
            ),
            mood_stddev=(
                statistics.stdev(mood_scores)
                if len(mood_scores) >= min_samples
                else self.config.default_mood_stddev
            ),
            energy_level=(
                statistics.mean(energy_levels)
                if energy_levels
                else self.config.default_energy_level
            ),
            energy_stddev=(
                statistics.stdev(energy_levels)
                if len(energy_levels) >= min_samples
                else self.config.default_energy_stddev
            ),
            stress_level=(
                statistics.mean(stress_levels)
                if stress_levels
                else self.config.default_stress_level
            ),
            stress_stddev=(
                statistics.stdev(stress_levels)
                if len(stress_levels) >= min_samples
                else self.config.default_stress_stddev
            ),
            sample_count=sample_count,
            last_updated=datetime.utcnow(),
        )

    async def _get_cached_baseline(self, user_id: UUID) -> Optional[UserBaseline]:
        """Get cached baseline from user_patterns table"""
        try:
            query = select(UserPatternDB).where(
                and_(
                    UserPatternDB.user_id == user_id,
                    UserPatternDB.pattern_type
                    == f"baseline_{self.config.baseline_days}d",
                    UserPatternDB.day_of_week.is_(None),
                )
            )

            result = await self.db.execute(query)
            pattern = result.scalar_one_or_none()

            if not pattern:
                return None

            metadata = pattern.metadata or {}
            return UserBaseline(
                sleep_hours=metadata.get(
                    "sleep_hours", self.config.default_sleep_hours
                ),
                sleep_stddev=metadata.get(
                    "sleep_stddev", self.config.default_sleep_stddev
                ),
                mood_score=metadata.get("mood_score", self.config.default_mood_score),
                mood_stddev=metadata.get(
                    "mood_stddev", self.config.default_mood_stddev
                ),
                energy_level=metadata.get(
                    "energy_level", self.config.default_energy_level
                ),
                energy_stddev=metadata.get(
                    "energy_stddev", self.config.default_energy_stddev
                ),
                stress_level=metadata.get(
                    "stress_level", self.config.default_stress_level
                ),
                stress_stddev=metadata.get(
                    "stress_stddev", self.config.default_stress_stddev
                ),
                sample_count=pattern.sample_count or 0,
                last_updated=pattern.last_updated or datetime.utcnow(),
            )

        except Exception as e:
            logger.warning(f"Error getting cached baseline: {e}")
            return None

    def _is_cache_fresh(self, baseline: UserBaseline) -> bool:
        """Check if cached baseline is still fresh"""
        if not baseline.last_updated:
            return False
        age = datetime.utcnow() - baseline.last_updated
        return age < timedelta(hours=self.config.cache_ttl_hours)

    async def _cache_baseline(
        self, user_id: UUID, baseline: UserBaseline, days: int
    ) -> None:
        """Cache baseline using PostgreSQL UPSERT"""
        metadata = {
            "sleep_hours": baseline.sleep_hours,
            "sleep_stddev": baseline.sleep_stddev,
            "mood_score": baseline.mood_score,
            "mood_stddev": baseline.mood_stddev,
            "energy_level": baseline.energy_level,
            "energy_stddev": baseline.energy_stddev,
            "stress_level": baseline.stress_level,
            "stress_stddev": baseline.stress_stddev,
        }

        confidence = self._calculate_confidence(baseline.sample_count, days)

        try:
            if self.config.use_upsert_for_cache:
                # Single UPSERT query (no N+1 problem)
                stmt = (
                    insert(UserPatternDB)
                    .values(
                        user_id=user_id,
                        pattern_type=f"baseline_{days}d",
                        day_of_week=None,
                        metadata=metadata,
                        sample_count=baseline.sample_count,
                        last_updated=datetime.utcnow(),
                        confidence=confidence,
                    )
                    .on_conflict_do_update(
                        index_elements=["user_id", "pattern_type", "day_of_week"],
                        set_={
                            "metadata": metadata,
                            "sample_count": baseline.sample_count,
                            "last_updated": datetime.utcnow(),
                            "confidence": confidence,
                        },
                    )
                )

                await self.db.execute(stmt)
            else:
                # Fallback: manual upsert
                query = select(UserPatternDB).where(
                    and_(
                        UserPatternDB.user_id == user_id,
                        UserPatternDB.pattern_type == f"baseline_{days}d",
                        UserPatternDB.day_of_week.is_(None),
                    )
                )

                result = await self.db.execute(query)
                pattern = result.scalar_one_or_none()

                if pattern:
                    pattern.metadata = metadata
                    pattern.sample_count = baseline.sample_count
                    pattern.last_updated = datetime.utcnow()
                    pattern.confidence = confidence
                else:
                    pattern = UserPatternDB(
                        user_id=user_id,
                        pattern_type=f"baseline_{days}d",
                        metadata=metadata,
                        sample_count=baseline.sample_count,
                        last_updated=datetime.utcnow(),
                        confidence=confidence,
                    )
                    self.db.add(pattern)

            await self.db.commit()

        except Exception as e:
            logger.error(f"Error caching baseline: {e}")
            await self.db.rollback()

    def _calculate_confidence(self, sample_count: int, expected_samples: int) -> float:
        """Calculate confidence based on sample size"""
        if sample_count == 0:
            return 0.0
        if expected_samples == 0:
            return 0.0
        if sample_count >= expected_samples:
            return 1.0
        return min(sample_count / expected_samples, 1.0)

    def _get_default_baseline(self) -> UserBaseline:
        """Default baseline for new users (population average)"""
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
            last_updated=datetime.utcnow(),
        )

    def _get_default_relationship(self) -> RelationshipStateResponse:
        """Default relationship state"""
        return RelationshipStateResponse(
            state="HARMONY",
            days_in_state=0,
            severity=0,
            trigger=None,
            expected_resolution_days=None,
            resolved=False,
        )

    def _get_minimal_context(self, user_id: UUID) -> Dict[str, Any]:
        """Minimal valid context when queries fail"""
        return {
            "baseline": self._get_default_baseline(),
            "recent_entries": [],
            "day_of_week_pattern": {},
            "relationship_state": self._get_default_relationship().to_dict(),
            "sleep_debt": 0.0,
            "activity_patterns": [],
            "seven_day_context": SevenDayAverages().to_dict(),
        }

    async def get_recent_entries(
        self, user_id: UUID, entry_date: date, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get recent entries (last N days before entry_date)"""
        from_date = entry_date - timedelta(days=days)

        query = (
            select(JournalExtractionDB)
            .where(
                and_(
                    JournalExtractionDB.user_id == user_id,
                    JournalExtractionDB.entry_date >= from_date,
                    JournalExtractionDB.entry_date < entry_date,
                )
            )
            .order_by(desc(JournalExtractionDB.entry_date))
            .limit(self.config.max_recent_entries)
        )

        result = await self.db.execute(query)
        entries = result.scalars().all()

        return [
            {
                "id": str(entry.id),
                "entry_date": entry.entry_date.isoformat(),
                "extracted_data": entry.extracted_data or {},
                "relationship_state": entry.relationship_state,
                "mood_trajectory": entry.mood_trajectory,
                "sleep_debt_cumulative": entry.sleep_debt_cumulative or 0.0,
            }
            for entry in entries
        ]

    async def get_day_of_week_pattern(
        self, user_id: UUID, day_of_week: int
    ) -> Dict[str, Any]:
        """Get pattern for specific day of week (0=Monday, 6=Sunday)"""
        try:
            query = select(UserPatternDB).where(
                and_(
                    UserPatternDB.user_id == user_id,
                    UserPatternDB.day_of_week == day_of_week,
                )
            )

            result = await self.db.execute(query)
            patterns = result.scalars().all()

            if not patterns:
                return {}

            return {
                pattern.pattern_type: {
                    "value": pattern.value,
                    "std_dev": pattern.std_dev,
                    "confidence": pattern.confidence,
                    "sample_count": pattern.sample_count,
                }
                for pattern in patterns
            }

        except Exception as e:
            logger.warning(f"Error getting day-of-week pattern: {e}")
            return {}

    async def get_relationship_state(
        self, user_id: UUID, entry_date: date
    ) -> RelationshipStateResponse:
        """Get current relationship state"""
        try:
            # Get most recent relationship event before entry_date
            query = (
                select(RelationshipHistoryDB)
                .where(
                    and_(
                        RelationshipHistoryDB.user_id == user_id,
                        RelationshipHistoryDB.event_date <= entry_date,
                    )
                )
                .order_by(desc(RelationshipHistoryDB.event_date))
                .limit(1)
            )

            result = await self.db.execute(query)
            event = result.scalar_one_or_none()

            if not event:
                return self._get_default_relationship()

            days_in_state = (entry_date - event.event_date).days

            return RelationshipStateResponse(
                state=event.state_after or "HARMONY",
                days_in_state=days_in_state,
                severity=event.severity or 0,
                trigger=event.trigger,
                expected_resolution_days=event.resolution_days,
                resolved=event.resolution_date is not None,
            )

        except Exception as e:
            logger.warning(f"Error getting relationship state: {e}")
            return self._get_default_relationship()

    async def get_sleep_debt(self, user_id: UUID, entry_date: date) -> float:
        """Get cumulative sleep debt as of entry_date"""
        try:
            # Get most recent sleep debt entry
            query = (
                select(SleepDebtLogDB)
                .where(
                    and_(
                        SleepDebtLogDB.user_id == user_id,
                        SleepDebtLogDB.entry_date < entry_date,
                    )
                )
                .order_by(desc(SleepDebtLogDB.entry_date))
                .limit(1)
            )

            result = await self.db.execute(query)
            log = result.scalar_one_or_none()

            return log.debt_cumulative if log and log.debt_cumulative else 0.0

        except Exception as e:
            logger.warning(f"Error getting sleep debt: {e}")
            return 0.0

    async def get_activity_patterns(
        self, user_id: UUID, min_occurrences: int = 3
    ) -> List[Dict[str, Any]]:
        """Get activity impact patterns"""
        try:
            query = (
                select(ActivityImpactDB)
                .where(
                    and_(
                        ActivityImpactDB.user_id == user_id,
                        ActivityImpactDB.occurrence_count >= min_occurrences,
                    )
                )
                .order_by(desc(ActivityImpactDB.avg_mood_impact))
                .limit(self.config.max_activity_patterns)
            )

            result = await self.db.execute(query)
            impacts = result.scalars().all()

            return [
                {
                    "activity_type": impact.activity_type,
                    "occurrence_count": impact.occurrence_count,
                    "avg_mood_impact": impact.avg_mood_impact,
                    "avg_energy_impact": impact.avg_energy_impact,
                    "avg_sleep_impact": impact.avg_sleep_impact,
                    "avg_duration_minutes": impact.avg_duration_minutes,
                    "confidence": impact.confidence,
                }
                for impact in impacts
            ]

        except Exception as e:
            logger.warning(f"Error getting activity patterns: {e}")
            return []

    def _calculate_seven_day_averages(
        self, recent_entries: List[Dict[str, Any]]
    ) -> SevenDayAverages:
        """
        Calculate 7-day averages from already-fetched recent entries.
        Pure function - no database access needed.
        """
        if not recent_entries:
            return SevenDayAverages()

        mood_scores = []
        energy_levels = []
        sleep_hours = []
        stress_levels = []

        for entry in recent_entries:
            data = entry.get("extracted_data") or {}

            # Safe navigation for mood
            mood = data.get("mood") or {}
            mood_val = mood.get("score")
            if mood_val is not None:
                try:
                    mood_scores.append(float(mood_val))
                except (ValueError, TypeError):
                    pass

            # Safe navigation for health
            health = data.get("health") or {}

            energy_val = health.get("energy_level")
            if energy_val is not None:
                try:
                    energy_levels.append(float(energy_val))
                except (ValueError, TypeError):
                    pass

            sleep_val = health.get("sleep_hours")
            if sleep_val is not None:
                try:
                    sleep_hours.append(float(sleep_val))
                except (ValueError, TypeError):
                    pass

            stress_val = health.get("stress_level")
            if stress_val is not None:
                try:
                    stress_levels.append(float(stress_val))
                except (ValueError, TypeError):
                    pass

        return SevenDayAverages(
            avg_mood_7d=statistics.mean(mood_scores) if mood_scores else None,
            avg_energy_7d=statistics.mean(energy_levels) if energy_levels else None,
            avg_sleep_7d=statistics.mean(sleep_hours) if sleep_hours else None,
            avg_stress_7d=statistics.mean(stress_levels) if stress_levels else None,
        )
