"""
PLOS v2.0 - Context Retrieval Engine
Retrieves user context, baselines, patterns, and historical data for intelligent extraction
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    ActivityImpact,
    RelationshipEvent,
    RelationshipState,
    SleepDebtLog,
    UserBaseline,
    UserPattern,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# CONTEXT RETRIEVAL ENGINE
# ============================================================================

class ContextRetrievalEngine:
    """
    Retrieves comprehensive user context for intelligent journal extraction
    
    Provides:
    - 30-day baseline (mood, sleep, energy averages)
    - 7-day recent entries
    - Day-of-week patterns
    - Relationship state
    - Sleep debt accumulation
    - Activity impact matrix
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_full_context(
        self,
        user_id: UUID,
        entry_date: date
    ) -> Dict[str, Any]:
        """
        Get complete user context for extraction
        
        Returns:
        {
            "baseline": UserBaseline,
            "recent_entries": List[Dict],
            "day_of_week_pattern": Dict,
            "relationship_state": Dict,
            "sleep_debt": float,
            "activity_patterns": List[ActivityImpact],
            "health_alerts": List,
            "seven_day_context": Dict
        }
        """
        logger.info(f"Retrieving full context for user {user_id}, date {entry_date}")
        
        # Execute all queries in parallel for speed
        results = await asyncio.gather(
            self.get_user_baseline(user_id),
            self.get_recent_entries(user_id, entry_date, days=7),
            self.get_day_of_week_pattern(user_id, entry_date.weekday()),
            self.get_relationship_state(user_id, entry_date),
            self.get_sleep_debt(user_id, entry_date),
            self.get_activity_patterns(user_id),
            self.get_seven_day_averages(user_id, entry_date),
            return_exceptions=True
        )
        
        baseline, recent_entries, dow_pattern, rel_state, sleep_debt, activity_patterns, seven_day = results
        
        context = {
            "baseline": baseline,
            "recent_entries": recent_entries if not isinstance(recent_entries, Exception) else [],
            "day_of_week_pattern": dow_pattern if not isinstance(dow_pattern, Exception) else {},
            "relationship_state": rel_state if not isinstance(rel_state, Exception) else {},
            "sleep_debt": sleep_debt if not isinstance(sleep_debt, Exception) else 0.0,
            "activity_patterns": activity_patterns if not isinstance(activity_patterns, Exception) else [],
            "seven_day_context": seven_day if not isinstance(seven_day, Exception) else {},
        }
        
        logger.info(f"Retrieved context with {len(context.get('recent_entries', []))} recent entries")
        return context
    
    async def get_user_baseline(
        self,
        user_id: UUID,
        days: int = 30
    ) -> UserBaseline:
        """
        Calculate 30-day baseline for user
        
        Returns average and stddev for:
        - Sleep hours
        - Mood score
        - Energy level
        - Stress level
        """
        logger.debug(f"Calculating {days}-day baseline for user {user_id}")
        
        # Try to get from user_patterns table first (cached)
        cached_baseline = await self._get_cached_baseline(user_id)
        if cached_baseline:
            logger.debug(f"Using cached baseline (updated {cached_baseline.last_updated})")
            return cached_baseline
        
        # Calculate fresh baseline from journal_extractions
        from_date = date.today() - timedelta(days=days)
        
        # Import here to avoid circular dependency
        from services.journal_parser.models import JournalExtractionDB
        
        query = select(JournalExtractionDB).where(
            and_(
                JournalExtractionDB.user_id == user_id,
                JournalExtractionDB.entry_date >= from_date
            )
        ).order_by(desc(JournalExtractionDB.entry_date))
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        if not entries:
            logger.warning(f"No entries found for user {user_id} in last {days} days")
            return self._get_default_baseline()
        
        # Extract metrics
        sleep_hours = []
        mood_scores = []
        energy_levels = []
        stress_levels = []
        
        for entry in entries:
            data = entry.extracted_data
            if data:
                if "health" in data and data["health"].get("sleep_hours"):
                    sleep_hours.append(float(data["health"]["sleep_hours"]))
                if "mood" in data and data["mood"].get("score"):
                    mood_scores.append(float(data["mood"]["score"]))
                if "health" in data and data["health"].get("energy_level"):
                    energy_levels.append(float(data["health"]["energy_level"]))
                if "health" in data and data["health"].get("stress_level"):
                    stress_levels.append(float(data["health"]["stress_level"]))
        
        # Calculate statistics
        import statistics
        
        baseline = UserBaseline(
            sleep_hours=statistics.mean(sleep_hours) if sleep_hours else 7.0,
            sleep_stddev=statistics.stdev(sleep_hours) if len(sleep_hours) > 1 else 1.0,
            mood_score=statistics.mean(mood_scores) if mood_scores else 6.5,
            mood_stddev=statistics.stdev(mood_scores) if len(mood_scores) > 1 else 1.5,
            energy_level=statistics.mean(energy_levels) if energy_levels else 6.0,
            energy_stddev=statistics.stdev(energy_levels) if len(energy_levels) > 1 else 1.5,
            stress_level=statistics.mean(stress_levels) if stress_levels else 4.0,
            stress_stddev=statistics.stdev(stress_levels) if len(stress_levels) > 1 else 1.5,
            sample_count=len(entries),
            last_updated=datetime.now()
        )
        
        # Cache for future use
        await self._cache_baseline(user_id, baseline)
        
        logger.info(f"Calculated baseline: sleep={baseline.sleep_hours:.1f}±{baseline.sleep_stddev:.1f}, "
                   f"mood={baseline.mood_score:.1f}±{baseline.mood_stddev:.1f}")
        
        return baseline
    
    async def _get_cached_baseline(self, user_id: UUID) -> Optional[UserBaseline]:
        """Get cached baseline from user_patterns table"""
        from services.journal_parser.models import UserPatternDB
        
        query = select(UserPatternDB).where(
            and_(
                UserPatternDB.user_id == user_id,
                UserPatternDB.pattern_type == "baseline_30d",
                UserPatternDB.day_of_week.is_(None)
            )
        )
        
        result = await self.db.execute(query)
        pattern = result.scalar_one_or_none()
        
        if not pattern:
            return None
        
        # Check if it's fresh (updated in last 24 hours)
        if datetime.now() - pattern.last_updated > timedelta(hours=24):
            return None
        
        metadata = pattern.metadata or {}
        return UserBaseline(
            sleep_hours=metadata.get("sleep_hours", 7.0),
            sleep_stddev=metadata.get("sleep_stddev", 1.0),
            mood_score=metadata.get("mood_score", 6.5),
            mood_stddev=metadata.get("mood_stddev", 1.5),
            energy_level=metadata.get("energy_level", 6.0),
            energy_stddev=metadata.get("energy_stddev", 1.5),
            stress_level=metadata.get("stress_level", 4.0),
            stress_stddev=metadata.get("stress_stddev", 1.5),
            sample_count=pattern.sample_count,
            last_updated=pattern.last_updated
        )
    
    async def _cache_baseline(self, user_id: UUID, baseline: UserBaseline):
        """Cache baseline in user_patterns table"""
        from services.journal_parser.models import UserPatternDB
        
        # Upsert pattern
        query = select(UserPatternDB).where(
            and_(
                UserPatternDB.user_id == user_id,
                UserPatternDB.pattern_type == "baseline_30d",
                UserPatternDB.day_of_week.is_(None)
            )
        )
        
        result = await self.db.execute(query)
        pattern = result.scalar_one_or_none()
        
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
        
        if pattern:
            pattern.metadata = metadata
            pattern.sample_count = baseline.sample_count
            pattern.last_updated = datetime.now()
            pattern.confidence = min(baseline.sample_count / 30.0, 1.0)
        else:
            pattern = UserPatternDB(
                user_id=user_id,
                pattern_type="baseline_30d",
                metadata=metadata,
                sample_count=baseline.sample_count,
                last_updated=datetime.now(),
                confidence=min(baseline.sample_count / 30.0, 1.0)
            )
            self.db.add(pattern)
        
        await self.db.commit()
    
    def _get_default_baseline(self) -> UserBaseline:
        """Default baseline for new users (population average)"""
        return UserBaseline(
            sleep_hours=7.0,
            sleep_stddev=1.0,
            mood_score=6.5,
            mood_stddev=1.5,
            energy_level=6.0,
            energy_stddev=1.5,
            stress_level=4.0,
            stress_stddev=1.5,
            sample_count=0,
            last_updated=datetime.now()
        )
    
    async def get_recent_entries(
        self,
        user_id: UUID,
        entry_date: date,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get recent entries (last N days before entry_date)"""
        from_date = entry_date - timedelta(days=days)
        
        from services.journal_parser.models import JournalExtractionDB
        
        query = select(JournalExtractionDB).where(
            and_(
                JournalExtractionDB.user_id == user_id,
                JournalExtractionDB.entry_date >= from_date,
                JournalExtractionDB.entry_date < entry_date
            )
        ).order_by(desc(JournalExtractionDB.entry_date)).limit(days)
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        return [
            {
                "id": str(entry.id),
                "entry_date": entry.entry_date.isoformat(),
                "extracted_data": entry.extracted_data,
                "relationship_state": entry.relationship_state,
                "mood_trajectory": entry.mood_trajectory,
                "sleep_debt_cumulative": entry.sleep_debt_cumulative,
            }
            for entry in entries
        ]
    
    async def get_day_of_week_pattern(
        self,
        user_id: UUID,
        day_of_week: int
    ) -> Dict[str, Any]:
        """Get pattern for specific day of week (0=Monday, 6=Sunday)"""
        from services.journal_parser.models import UserPatternDB
        
        query = select(UserPatternDB).where(
            and_(
                UserPatternDB.user_id == user_id,
                UserPatternDB.day_of_week == day_of_week
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
                "sample_count": pattern.sample_count
            }
            for pattern in patterns
        }
    
    async def get_relationship_state(
        self,
        user_id: UUID,
        entry_date: date
    ) -> Dict[str, Any]:
        """Get current relationship state"""
        from services.journal_parser.models import RelationshipHistoryDB
        
        # Get most recent relationship event before entry_date
        query = select(RelationshipHistoryDB).where(
            and_(
                RelationshipHistoryDB.user_id == user_id,
                RelationshipHistoryDB.event_date <= entry_date
            )
        ).order_by(desc(RelationshipHistoryDB.event_date)).limit(1)
        
        result = await self.db.execute(query)
        event = result.scalar_one_or_none()
        
        if not event:
            return {
                "state": "HARMONY",
                "days_in_state": 0,
                "severity": 0,
                "trigger": None,
                "expected_resolution_days": None
            }
        
        days_in_state = (entry_date - event.event_date).days
        
        return {
            "state": event.state_after,
            "days_in_state": days_in_state,
            "severity": event.severity or 0,
            "trigger": event.trigger,
            "expected_resolution_days": event.resolution_days,
            "resolved": event.resolution_date is not None
        }
    
    async def get_sleep_debt(
        self,
        user_id: UUID,
        entry_date: date
    ) -> float:
        """Get cumulative sleep debt as of entry_date"""
        from services.journal_parser.models import SleepDebtLogDB
        
        # Get most recent sleep debt entry
        query = select(SleepDebtLogDB).where(
            and_(
                SleepDebtLogDB.user_id == user_id,
                SleepDebtLogDB.entry_date < entry_date
            )
        ).order_by(desc(SleepDebtLogDB.entry_date)).limit(1)
        
        result = await self.db.execute(query)
        log = result.scalar_one_or_none()
        
        return log.debt_cumulative if log else 0.0
    
    async def get_activity_patterns(
        self,
        user_id: UUID,
        min_occurrences: int = 3
    ) -> List[ActivityImpact]:
        """Get activity impact patterns"""
        from services.journal_parser.models import ActivityImpactDB
        
        query = select(ActivityImpactDB).where(
            and_(
                ActivityImpactDB.user_id == user_id,
                ActivityImpactDB.occurrence_count >= min_occurrences
            )
        ).order_by(desc(ActivityImpactDB.avg_mood_impact))
        
        result = await self.db.execute(query)
        impacts = result.scalars().all()
        
        return [
            ActivityImpact.model_validate(impact)
            for impact in impacts
        ]
    
    async def get_seven_day_averages(
        self,
        user_id: UUID,
        entry_date: date
    ) -> Dict[str, float]:
        """Get 7-day rolling averages"""
        recent_entries = await self.get_recent_entries(user_id, entry_date, days=7)
        
        if not recent_entries:
            return {}
        
        mood_scores = []
        energy_levels = []
        sleep_hours = []
        stress_levels = []
        
        for entry in recent_entries:
            data = entry.get("extracted_data", {})
            if "mood" in data and data["mood"].get("score"):
                mood_scores.append(float(data["mood"]["score"]))
            if "health" in data:
                health = data["health"]
                if health.get("energy_level"):
                    energy_levels.append(float(health["energy_level"]))
                if health.get("sleep_hours"):
                    sleep_hours.append(float(health["sleep_hours"]))
                if health.get("stress_level"):
                    stress_levels.append(float(health["stress_level"]))
        
        import statistics
        
        return {
            "avg_mood_7d": statistics.mean(mood_scores) if mood_scores else None,
            "avg_energy_7d": statistics.mean(energy_levels) if energy_levels else None,
            "avg_sleep_7d": statistics.mean(sleep_hours) if sleep_hours else None,
            "avg_stress_7d": statistics.mean(stress_levels) if stress_levels else None,
        }
