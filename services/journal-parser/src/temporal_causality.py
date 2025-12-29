"""
PLOS v2.0 - Temporal Causality Linking
Links current entry to previous entries to detect cause-effect relationships
Architecture Stage 6: Temporal Causality Linking
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# TEMPORAL CAUSALITY ENGINE
# ============================================================================

class TemporalCausalityEngine:
    """
    Links current entry to previous events to detect cause-effect
    
    Per architecture:
    - Yesterday's conflict → Today's poor sleep?
    - Yesterday's heavy meal → Today's digestive discomfort?
    - Yesterday's late work → Today's fatigue?
    - Conflict state progression tracking
    - Sleep debt accumulation tracking
    - Activity pattern impact tracking
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def analyze_temporal_links(
        self,
        user_id: UUID,
        current_date: date,
        current_data: Dict[str, Any],
        previous_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze temporal causality links
        
        Returns:
        {
            "previous_entry_id": UUID,
            "causality_detected": List[Dict],
            "conflict_progression": Dict,
            "sleep_debt_trajectory": Dict,
            "activity_impacts": List[Dict]
        }
        """
        if not previous_entries:
            return {
                "previous_entry_id": None,
                "causality_detected": [],
                "conflict_progression": None,
                "sleep_debt_trajectory": None,
                "activity_impacts": []
            }
        
        # Get yesterday's entry (most recent)
        yesterday = previous_entries[0] if previous_entries else None
        previous_entry_id = yesterday.get("id") if yesterday else None
        
        # Detect causal links
        causality = []
        
        # Link 1: Conflict → Sleep impact
        conflict_sleep_link = self._analyze_conflict_to_sleep(
            yesterday, current_data
        )
        if conflict_sleep_link:
            causality.append(conflict_sleep_link)
        
        # Link 2: Late work → Next-day fatigue
        work_fatigue_link = self._analyze_work_to_fatigue(
            yesterday, current_data
        )
        if work_fatigue_link:
            causality.append(work_fatigue_link)
        
        # Link 3: Heavy meal → Digestive discomfort
        meal_digestion_link = self._analyze_meal_to_digestion(
            yesterday, current_data
        )
        if meal_digestion_link:
            causality.append(meal_digestion_link)
        
        # Link 4: Exercise → Sleep quality
        exercise_sleep_link = self._analyze_exercise_to_sleep(
            yesterday, current_data
        )
        if exercise_sleep_link:
            causality.append(exercise_sleep_link)
        
        # Link 5: Screen time → Sleep delay
        screen_sleep_link = self._analyze_screen_to_sleep(
            yesterday, current_data
        )
        if screen_sleep_link:
            causality.append(screen_sleep_link)
        
        # Analyze conflict progression
        conflict_progression = self._analyze_conflict_progression(
            previous_entries, current_data
        )
        
        # Analyze sleep debt trajectory
        sleep_debt_trajectory = self._analyze_sleep_debt_trajectory(
            previous_entries, current_data
        )
        
        # Analyze activity impacts
        activity_impacts = self._analyze_activity_impacts(
            previous_entries, current_data
        )
        
        logger.info(f"Detected {len(causality)} causal links for user {user_id}")
        
        return {
            "previous_entry_id": previous_entry_id,
            "causality_detected": causality,
            "conflict_progression": conflict_progression,
            "sleep_debt_trajectory": sleep_debt_trajectory,
            "activity_impacts": activity_impacts
        }
    
    # ========================================================================
    # CAUSAL LINK DETECTORS
    # ========================================================================
    
    def _analyze_conflict_to_sleep(
        self,
        yesterday: Optional[Dict],
        today: Dict
    ) -> Optional[Dict]:
        """
        Detect: Yesterday's conflict → Today's poor sleep
        """
        if not yesterday:
            return None
        
        # Check if conflict yesterday
        yesterday_state = yesterday.get("relationship_state")
        if yesterday_state not in ["CONFLICT", "TENSION"]:
            return None
        
        # Check if sleep affected today
        today_sleep = today.get("sleep_hours")
        yesterday_sleep = yesterday.get("sleep_hours")
        
        if not today_sleep or not yesterday_sleep:
            return None
        
        sleep_reduction = yesterday_sleep - today_sleep
        
        if sleep_reduction >= 1.5:  # At least 1.5 hours less
            return {
                "type": "conflict_to_sleep",
                "cause": f"Conflict/tension yesterday (state: {yesterday_state})",
                "effect": f"Sleep reduced by {sleep_reduction:.1f} hours",
                "confidence": 0.75,
                "impact_severity": "high" if sleep_reduction >= 2.5 else "medium",
                "recommendation": "Consider addressing relationship issues to improve sleep"
            }
        
        return None
    
    def _analyze_work_to_fatigue(
        self,
        yesterday: Optional[Dict],
        today: Dict
    ) -> Optional[Dict]:
        """
        Detect: Yesterday's late/long work → Today's fatigue
        """
        if not yesterday:
            return None
        
        yesterday_work = yesterday.get("work_hours", 0)
        yesterday_bedtime = yesterday.get("bedtime")
        
        # Check for late work (>8 hours or late bedtime)
        if yesterday_work < 8 and not (yesterday_bedtime and "23" in str(yesterday_bedtime)):
            return None
        
        # Check for low energy today
        today_energy = today.get("energy_level")
        if not today_energy or today_energy >= 5:
            return None
        
        return {
            "type": "work_to_fatigue",
            "cause": f"Long work hours yesterday ({yesterday_work}h) or late bedtime",
            "effect": f"Low energy today ({today_energy}/10)",
            "confidence": 0.65,
            "impact_severity": "medium",
            "recommendation": "Consider earlier sleep after long work days"
        }
    
    def _analyze_meal_to_digestion(
        self,
        yesterday: Optional[Dict],
        today: Dict
    ) -> Optional[Dict]:
        """
        Detect: Yesterday's heavy meal → Today's digestive issues
        """
        if not yesterday:
            return None
        
        # Check for heavy meal indicators
        yesterday_meals = yesterday.get("meals", [])
        heavy_meal = any(
            "heavy" in str(meal).lower() or
            "large" in str(meal).lower() or
            "feast" in str(meal).lower()
            for meal in yesterday_meals
        )
        
        if not heavy_meal:
            return None
        
        # Check for digestive symptoms today
        today_symptoms = today.get("symptoms", [])
        digestive_issues = any(
            "digest" in str(symptom).lower() or
            "stomach" in str(symptom).lower() or
            "bloat" in str(symptom).lower()
            for symptom in today_symptoms
        )
        
        if digestive_issues:
            return {
                "type": "meal_to_digestion",
                "cause": "Heavy meal yesterday",
                "effect": "Digestive discomfort today",
                "confidence": 0.60,
                "impact_severity": "low",
                "recommendation": "Monitor portion sizes and meal timing"
            }
        
        return None
    
    def _analyze_exercise_to_sleep(
        self,
        yesterday: Optional[Dict],
        today: Dict
    ) -> Optional[Dict]:
        """
        Detect: Yesterday's exercise → Today's better sleep
        """
        if not yesterday:
            return None
        
        yesterday_exercise = yesterday.get("exercise_duration", 0)
        if yesterday_exercise < 30:  # At least 30 minutes
            return None
        
        # Check sleep quality
        today_sleep_quality = today.get("sleep_quality")
        yesterday_sleep_quality = yesterday.get("sleep_quality")
        
        if not today_sleep_quality or not yesterday_sleep_quality:
            return None
        
        quality_improvement = today_sleep_quality - yesterday_sleep_quality
        
        if quality_improvement >= 1.5:
            return {
                "type": "exercise_to_sleep",
                "cause": f"Exercise yesterday ({yesterday_exercise} min)",
                "effect": f"Sleep quality improved by {quality_improvement:.1f} points",
                "confidence": 0.70,
                "impact_severity": "positive",
                "recommendation": "Continue regular exercise for better sleep"
            }
        
        return None
    
    def _analyze_screen_to_sleep(
        self,
        yesterday: Optional[Dict],
        today: Dict
    ) -> Optional[Dict]:
        """
        Detect: Yesterday's late screen time → Today's sleep delay
        """
        if not yesterday:
            return None
        
        # Check for late screen time
        yesterday_activities = yesterday.get("activities", [])
        late_screen_time = any(
            ("instagram" in str(act).lower() or "phone" in str(act).lower())
            and yesterday.get("bedtime") and "23" in str(yesterday["bedtime"])
            for act in yesterday_activities
        )
        
        if not late_screen_time:
            return None
        
        # Check for delayed sleep
        today_sleep_hours = today.get("sleep_hours")
        expected_sleep = 7.5
        
        if today_sleep_hours and today_sleep_hours < expected_sleep - 1:
            return {
                "type": "screen_to_sleep",
                "cause": "Late screen time before bed yesterday",
                "effect": f"Reduced sleep ({today_sleep_hours}h)",
                "confidence": 0.65,
                "impact_severity": "medium",
                "recommendation": "Avoid screens 1-2 hours before bedtime"
            }
        
        return None
    
    # ========================================================================
    # PROGRESSION ANALYZERS
    # ========================================================================
    
    def _analyze_conflict_progression(
        self,
        previous_entries: List[Dict],
        current_data: Dict
    ) -> Optional[Dict]:
        """
        Track conflict state progression
        
        Per architecture:
        - Day 1: Conflict occurs (mood -3)
        - Day 2: Unresolved (mood -2)
        - Day 3: Coldness (mood -1)
        - Day 4: Reconciliation (mood +1)
        - Day 5: Harmony restored (mood +2)
        """
        # Find conflict entries in last 7 days
        conflict_entries = [
            e for e in previous_entries[-7:]
            if e.get("relationship_state") in ["CONFLICT", "COLD_WAR", "RECOVERY"]
        ]
        
        if not conflict_entries:
            return None
        
        # Analyze progression
        states = [e["relationship_state"] for e in conflict_entries]
        moods = [e.get("mood_score", 6.5) for e in conflict_entries]
        
        # Current state
        current_state = current_data.get("relationship_state", "HARMONY")
        current_mood = current_data.get("mood_score")
        
        return {
            "days_in_conflict_phase": len(conflict_entries),
            "state_progression": states,
            "mood_progression": moods,
            "current_state": current_state,
            "current_mood": current_mood,
            "is_improving": (
                states[-1] == "RECOVERY" if states else False
            ),
            "expected_resolution_days": max(0, 5 - len(conflict_entries))
        }
    
    def _analyze_sleep_debt_trajectory(
        self,
        previous_entries: List[Dict],
        current_data: Dict
    ) -> Optional[Dict]:
        """
        Track sleep debt accumulation
        
        Per architecture:
        - Day 1: -1.5 hrs (owe 1.5 hours)
        - Day 2: -3.5 hrs (owe 3.5 hours, cumulative 5)
        - Day 3: -2.0 hrs (owe 2 hours, cumulative 7)
        - Prediction: Need 11+ hrs recovery sleep
        """
        if not previous_entries:
            return None
        
        # Calculate debt trajectory
        baseline_sleep = 7.5
        debt_trajectory = []
        cumulative_debt = 0.0
        
        for entry in previous_entries[-7:]:
            sleep_hours = entry.get("sleep_hours")
            if sleep_hours:
                daily_debt = baseline_sleep - sleep_hours
                cumulative_debt += daily_debt
                debt_trajectory.append({
                    "date": entry["entry_date"],
                    "sleep_hours": sleep_hours,
                    "daily_debt": daily_debt,
                    "cumulative_debt": cumulative_debt
                })
        
        # Current debt
        current_sleep = current_data.get("sleep_hours")
        if current_sleep:
            current_daily_debt = baseline_sleep - current_sleep
            cumulative_debt += current_daily_debt
        
        return {
            "debt_trajectory": debt_trajectory,
            "current_cumulative_debt": cumulative_debt,
            "recovery_sleep_needed": abs(cumulative_debt) if cumulative_debt < 0 else 0,
            "debt_severity": (
                "critical" if cumulative_debt < -10 else
                "high" if cumulative_debt < -5 else
                "moderate" if cumulative_debt < -3 else
                "low"
            )
        }
    
    def _analyze_activity_impacts(
        self,
        previous_entries: List[Dict],
        current_data: Dict
    ) -> List[Dict]:
        """
        Analyze activity impacts on next-day metrics
        
        Per architecture:
        - High Instagram day → Lower focus next day
        - Intense badminton → Better sleep that night
        - High stress work → Late sleep that night
        """
        impacts = []
        
        if not previous_entries:
            return impacts
        
        yesterday = previous_entries[0]
        yesterday_activities = yesterday.get("activities", [])
        
        for activity in yesterday_activities:
            activity_name = activity.get("name", "")
            
            # Detect impact on current metrics
            impact = self._detect_activity_impact(
                activity_name,
                yesterday,
                current_data
            )
            
            if impact:
                impacts.append(impact)
        
        return impacts
    
    def _detect_activity_impact(
        self,
        activity: str,
        yesterday: Dict,
        today: Dict
    ) -> Optional[Dict]:
        """Detect specific activity impact"""
        activity_lower = activity.lower()
        
        # Social media → Focus impact
        if "instagram" in activity_lower or "social media" in activity_lower:
            yesterday_duration = yesterday.get(f"{activity}_duration", 0)
            today_productivity = today.get("productivity")
            
            if yesterday_duration > 3 and today_productivity and today_productivity < 5:
                return {
                    "activity": activity,
                    "yesterday_duration": yesterday_duration,
                    "impact_type": "focus_reduction",
                    "today_metric": "productivity",
                    "today_value": today_productivity,
                    "confidence": 0.60
                }
        
        # Exercise → Sleep impact
        if "badminton" in activity_lower or "exercise" in activity_lower:
            yesterday_duration = yesterday.get("exercise_duration", 0)
            today_sleep_quality = today.get("sleep_quality")
            
            if yesterday_duration >= 30 and today_sleep_quality and today_sleep_quality >= 7:
                return {
                    "activity": activity,
                    "yesterday_duration": yesterday_duration,
                    "impact_type": "sleep_improvement",
                    "today_metric": "sleep_quality",
                    "today_value": today_sleep_quality,
                    "confidence": 0.70
                }
        
        return None
