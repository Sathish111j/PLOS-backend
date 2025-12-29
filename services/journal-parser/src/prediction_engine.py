"""
PLOS v2.0 - Predictive Analytics Engine
Next-day and weekly forecasts for sleep, mood, energy, activities
"""

from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

from shared.models import (
    Trajectory,
    UserBaseline,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# PREDICTION ENGINE
# ============================================================================


class PredictionEngine:
    """
    Generates predictions for health metrics and activities
    """

    def __init__(
        self,
        user_baseline: Optional[UserBaseline] = None,
        recent_history: Optional[List[Dict[str, Any]]] = None,
        activity_patterns: Optional[List[Dict[str, Any]]] = None,
    ):
        self.user_baseline = user_baseline
        self.recent_history = recent_history or []
        self.activity_patterns = {
            p["activity_type"]: p for p in (activity_patterns or [])
        }

    def generate_predictions(
        self,
        sleep_debt: float = 0.0,
        relationship_state: Optional[Dict[str, Any]] = None,
        forecast_days: int = 1,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive predictions

        Args:
            sleep_debt: Current cumulative sleep debt
            relationship_state: Current relationship state info
            forecast_days: Number of days to forecast (1 or 7)

        Returns:
            Dict with predictions for each metric
        """
        predictions = {}

        # Next-day predictions
        if forecast_days == 1:
            predictions["sleep"] = self._predict_sleep(sleep_debt, relationship_state)
            predictions["mood"] = self._predict_mood(sleep_debt, relationship_state)
            predictions["energy"] = self._predict_energy(sleep_debt, relationship_state)
            predictions["stress"] = self._predict_stress(relationship_state)

        # Weekly forecast
        elif forecast_days == 7:
            predictions["week_forecast"] = self._predict_week(
                sleep_debt, relationship_state
            )

        # Activity feasibility
        predictions["activity_recommendations"] = self._predict_activity_feasibility(
            predictions.get("energy", {}).get("predicted_value", 6)
        )

        # Conflict resolution forecast
        if relationship_state and relationship_state.get("state") in [
            "CONFLICT",
            "COLD_WAR",
            "RECOVERY",
        ]:
            predictions["conflict_resolution"] = self._predict_conflict_resolution(
                relationship_state
            )

        logger.info(f"Generated {len(predictions)} prediction categories")
        return predictions

    # ========================================================================
    # SLEEP PREDICTION
    # ========================================================================

    def _predict_sleep(
        self, sleep_debt: float, relationship_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Predict next-day sleep duration and quality"""

        # Start with baseline
        if self.user_baseline:
            base_sleep = self.user_baseline.sleep_hours
            sleep_stddev = self.user_baseline.sleep_stddev
        else:
            base_sleep = 7.0
            sleep_stddev = 0.8

        # Adjust for sleep debt (catch-up sleep tendency)
        debt_adjustment = 0
        if sleep_debt > 5:
            debt_adjustment = min(2.0, sleep_debt * 0.3)
        elif sleep_debt > 3:
            debt_adjustment = 0.5

        # Adjust for relationship state
        relationship_adjustment = 0
        if relationship_state:
            state = relationship_state.get("state")
            if state == "CONFLICT":
                relationship_adjustment = -1.5
            elif state == "COLD_WAR":
                relationship_adjustment = -1.0
            elif state == "RECOVERY":
                relationship_adjustment = -0.5

        # Recent trend
        trend_adjustment = 0
        if len(self.recent_history) >= 3:
            recent_sleep = [
                entry.get("sleep_hours")
                for entry in self.recent_history[-3:]
                if entry.get("sleep_hours")
            ]
            if len(recent_sleep) >= 2:
                trend_slope = (recent_sleep[-1] - recent_sleep[0]) / len(recent_sleep)
                trend_adjustment = trend_slope * 0.5

        # Calculate prediction
        predicted_sleep = (
            base_sleep + debt_adjustment + relationship_adjustment + trend_adjustment
        )
        predicted_sleep = max(4.0, min(11.0, predicted_sleep))

        # Confidence calculation
        base_confidence = 0.60
        if len(self.recent_history) >= 7:
            base_confidence += 0.15
        if self.user_baseline:
            base_confidence += 0.10

        # Confidence interval
        confidence_interval = sleep_stddev * 1.96  # 95% CI
        lower_bound = max(4.0, predicted_sleep - confidence_interval)
        upper_bound = min(11.0, predicted_sleep + confidence_interval)

        # Determine trajectory
        if debt_adjustment > 0.5:
            trajectory = Trajectory.IMPROVING
        elif relationship_adjustment < -0.5:
            trajectory = Trajectory.DECLINING
        else:
            trajectory = Trajectory.STABLE

        return {
            "predicted_value": round(predicted_sleep, 1),
            "confidence": round(base_confidence, 2),
            "confidence_interval": {
                "lower": round(lower_bound, 1),
                "upper": round(upper_bound, 1),
            },
            "trajectory": trajectory.value,
            "factors": {
                "baseline": base_sleep,
                "sleep_debt_adjustment": round(debt_adjustment, 1),
                "relationship_adjustment": round(relationship_adjustment, 1),
                "trend_adjustment": round(trend_adjustment, 1),
            },
            "reasoning": self._build_sleep_reasoning(
                debt_adjustment, relationship_adjustment, trend_adjustment
            ),
        }

    @staticmethod
    def _build_sleep_reasoning(debt: float, rel: float, trend: float) -> str:
        """Build human-readable reasoning"""
        reasons = []

        if debt > 0.5:
            reasons.append(f"catch-up sleep likely (+{debt:.1f}hrs)")
        if rel < -0.5:
            reasons.append(f"relationship stress impact ({rel:.1f}hrs)")
        if abs(trend) > 0.3:
            direction = "increasing" if trend > 0 else "decreasing"
            reasons.append(f"{direction} trend")

        if not reasons:
            return "Based on baseline patterns"

        return "; ".join(reasons)

    # ========================================================================
    # MOOD PREDICTION
    # ========================================================================

    def _predict_mood(
        self, sleep_debt: float, relationship_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Predict next-day mood"""

        # Start with baseline
        if self.user_baseline:
            base_mood = self.user_baseline.mood_score
            mood_stddev = self.user_baseline.mood_stddev
        else:
            base_mood = 6.5
            mood_stddev = 1.5

        # Adjust for sleep debt
        debt_adjustment = 0
        if sleep_debt > 5:
            debt_adjustment = -2.0
        elif sleep_debt > 3:
            debt_adjustment = -1.0

        # Adjust for relationship state
        relationship_adjustment = 0
        if relationship_state:
            state = relationship_state.get("state")
            days_in_state = relationship_state.get("days_in_state", 0)

            if state == "CONFLICT":
                relationship_adjustment = -3.5 * min(1.0, days_in_state / 3.0)
            elif state == "COLD_WAR":
                relationship_adjustment = -2.5 * min(1.0, days_in_state / 3.0)
            elif state == "RECOVERY":
                # Recovery shows improvement over time
                relationship_adjustment = -1.0 + (days_in_state * 0.3)
            elif state == "RESOLVED":
                relationship_adjustment = 0.5

        # Recent trend
        trend_adjustment = 0
        if len(self.recent_history) >= 3:
            recent_moods = [
                entry.get("mood_score", entry.get("mood_score_estimate"))
                for entry in self.recent_history[-3:]
                if entry.get("mood_score") or entry.get("mood_score_estimate")
            ]
            if len(recent_moods) >= 2:
                trend_slope = (recent_moods[-1] - recent_moods[0]) / len(recent_moods)
                trend_adjustment = trend_slope * 0.5

        # Calculate prediction
        predicted_mood = (
            base_mood + debt_adjustment + relationship_adjustment + trend_adjustment
        )
        predicted_mood = max(1, min(10, predicted_mood))

        # Confidence
        base_confidence = 0.55
        if len(self.recent_history) >= 5:
            base_confidence += 0.15

        # Confidence interval
        confidence_interval = mood_stddev * 1.96
        lower_bound = max(1, predicted_mood - confidence_interval)
        upper_bound = min(10, predicted_mood + confidence_interval)

        # Trajectory
        total_adjustment = debt_adjustment + relationship_adjustment + trend_adjustment
        if total_adjustment > 0.5:
            trajectory = Trajectory.IMPROVING
        elif total_adjustment < -0.5:
            trajectory = Trajectory.DECLINING
        else:
            trajectory = Trajectory.STABLE

        return {
            "predicted_value": round(predicted_mood, 1),
            "confidence": round(base_confidence, 2),
            "confidence_interval": {
                "lower": round(lower_bound, 1),
                "upper": round(upper_bound, 1),
            },
            "trajectory": trajectory.value,
            "factors": {
                "baseline": base_mood,
                "sleep_debt_impact": round(debt_adjustment, 1),
                "relationship_impact": round(relationship_adjustment, 1),
                "trend_adjustment": round(trend_adjustment, 1),
            },
        }

    # ========================================================================
    # ENERGY PREDICTION
    # ========================================================================

    def _predict_energy(
        self, sleep_debt: float, relationship_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Predict next-day energy level"""

        # Start with baseline
        if self.user_baseline:
            base_energy = self.user_baseline.energy_level
        else:
            base_energy = 6.0

        # Adjust for sleep debt (stronger impact than mood)
        debt_adjustment = 0
        if sleep_debt > 5:
            debt_adjustment = -3.0
        elif sleep_debt > 3:
            debt_adjustment = -1.5

        # Adjust for relationship state
        relationship_adjustment = 0
        if relationship_state:
            state = relationship_state.get("state")
            if state in ["CONFLICT", "COLD_WAR"]:
                relationship_adjustment = -2.0
            elif state == "RECOVERY":
                relationship_adjustment = -0.5

        # Recent trend
        trend_adjustment = 0
        if len(self.recent_history) >= 3:
            recent_energy = [
                entry.get("energy_level")
                for entry in self.recent_history[-3:]
                if entry.get("energy_level")
            ]
            if len(recent_energy) >= 2:
                trend_slope = (recent_energy[-1] - recent_energy[0]) / len(
                    recent_energy
                )
                trend_adjustment = trend_slope * 0.5

        # Calculate prediction
        predicted_energy = (
            base_energy + debt_adjustment + relationship_adjustment + trend_adjustment
        )
        predicted_energy = max(1, min(10, predicted_energy))

        # Confidence
        confidence = 0.60 if len(self.recent_history) >= 5 else 0.45

        # Trajectory
        total_adjustment = debt_adjustment + relationship_adjustment + trend_adjustment
        if total_adjustment > 0.5:
            trajectory = Trajectory.IMPROVING
        elif total_adjustment < -0.5:
            trajectory = Trajectory.DECLINING
        else:
            trajectory = Trajectory.STABLE

        return {
            "predicted_value": round(predicted_energy, 1),
            "confidence": round(confidence, 2),
            "trajectory": trajectory.value,
            "factors": {
                "baseline": base_energy,
                "sleep_debt_impact": round(debt_adjustment, 1),
                "relationship_impact": round(relationship_adjustment, 1),
            },
        }

    # ========================================================================
    # STRESS PREDICTION
    # ========================================================================

    def _predict_stress(
        self, relationship_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Predict next-day stress level"""

        base_stress = 4.0

        # Relationship state impact
        if relationship_state:
            state = relationship_state.get("state")
            days_in_state = relationship_state.get("days_in_state", 0)

            if state == "CONFLICT":
                base_stress += 4.0 * min(1.0, days_in_state / 3.0)
            elif state == "COLD_WAR":
                base_stress += 3.5 * min(1.0, days_in_state / 3.0)
            elif state == "RECOVERY":
                base_stress += max(0, 2.0 - (days_in_state * 0.4))

        # Recent trend
        if len(self.recent_history) >= 3:
            recent_stress = [
                entry.get("stress_level")
                for entry in self.recent_history[-3:]
                if entry.get("stress_level")
            ]
            if len(recent_stress) >= 2:
                # Use recent average
                base_stress = mean(recent_stress)

        predicted_stress = max(1, min(10, base_stress))

        return {
            "predicted_value": round(predicted_stress, 1),
            "confidence": 0.50,
            "trajectory": Trajectory.STABLE.value,
        }

    # ========================================================================
    # WEEKLY FORECAST
    # ========================================================================

    def _predict_week(
        self, sleep_debt: float, relationship_state: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate 7-day forecast"""

        forecast = []
        current_debt = sleep_debt
        current_rel_state = relationship_state

        for day in range(1, 8):
            # Predict for this day
            day_pred = {
                "day": day,
                "date": (datetime.utcnow() + timedelta(days=day)).strftime("%Y-%m-%d"),
                "sleep": self._predict_sleep(current_debt, current_rel_state),
                "mood": self._predict_mood(current_debt, current_rel_state),
                "energy": self._predict_energy(current_debt, current_rel_state),
            }

            forecast.append(day_pred)

            # Update debt for next day (simple projection)
            predicted_sleep = day_pred["sleep"]["predicted_value"]
            optimal_sleep = (
                self.user_baseline.sleep_hours if self.user_baseline else 7.5
            )
            current_debt += optimal_sleep - predicted_sleep
            current_debt = max(0, current_debt)  # Can't go negative

            # Project relationship state progression
            if current_rel_state and current_rel_state.get("state") == "RECOVERY":
                # Recovery progresses
                days_in_recovery = current_rel_state.get("days_in_state", 0) + day
                if days_in_recovery >= 3:
                    # Transition to RESOLVED
                    current_rel_state = {"state": "RESOLVED", "days_in_state": 0}

        return forecast

    # ========================================================================
    # ACTIVITY FEASIBILITY
    # ========================================================================

    def _predict_activity_feasibility(
        self, predicted_energy: float
    ) -> List[Dict[str, Any]]:
        """Predict which activities are feasible based on energy"""

        recommendations = []

        # Energy-based recommendations
        if predicted_energy >= 7:
            recommendations.append(
                {
                    "category": "high_energy",
                    "feasibility": "high",
                    "suggested_activities": ["badminton", "running", "gym", "sports"],
                    "reasoning": "High predicted energy suitable for intense activities",
                }
            )
        elif predicted_energy >= 5:
            recommendations.append(
                {
                    "category": "moderate_energy",
                    "feasibility": "moderate",
                    "suggested_activities": ["walking", "light exercise", "yoga"],
                    "reasoning": "Moderate energy - focus on light to moderate activities",
                }
            )
        else:
            recommendations.append(
                {
                    "category": "low_energy",
                    "feasibility": "low",
                    "suggested_activities": ["rest", "reading", "meditation"],
                    "reasoning": "Low predicted energy - prioritize rest and recovery",
                }
            )

        # Activity pattern-based recommendations
        for activity_type, pattern in self.activity_patterns.items():
            if pattern.get("avg_energy_impact", 0) > 0:
                recommendations.append(
                    {
                        "activity": activity_type,
                        "expected_energy_boost": round(pattern["avg_energy_impact"], 1),
                        "expected_mood_boost": round(
                            pattern.get("avg_mood_impact", 0), 1
                        ),
                        "typical_duration": pattern.get(
                            "avg_duration_minutes", "unknown"
                        ),
                    }
                )

        return recommendations

    # ========================================================================
    # CONFLICT RESOLUTION FORECAST
    # ========================================================================

    def _predict_conflict_resolution(
        self, relationship_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict when conflict might resolve"""

        state = relationship_state.get("state")
        days_in_state = relationship_state.get("days_in_state", 0)

        # Expected durations (from state machine)
        state_durations = {
            "TENSION": 1,
            "CONFLICT": 2,
            "COLD_WAR": 5,
            "RECOVERY": 3,
            "RESOLVED": 7,
        }

        expected_duration = state_durations.get(state, 3)
        remaining_days = max(0, expected_duration - days_in_state)

        # Factor in recovery timeline
        if state == "CONFLICT":
            # Conflict -> COLD_WAR or RECOVERY
            recovery_timeline = remaining_days + 3  # Additional recovery time
        elif state == "COLD_WAR":
            # Longer recovery needed
            recovery_timeline = remaining_days + 5
        elif state == "RECOVERY":
            # Already recovering
            recovery_timeline = remaining_days
        else:
            recovery_timeline = 0

        # Confidence decreases the longer state persists
        confidence = max(0.3, 0.7 - (days_in_state * 0.05))

        # Predicted mood/energy at resolution
        post_resolution_mood = (
            self.user_baseline.mood_score if self.user_baseline else 7.0
        ) - 0.5
        post_resolution_energy = (
            self.user_baseline.energy_level if self.user_baseline else 6.5
        ) - 0.5

        return {
            "current_state": state,
            "days_in_state": days_in_state,
            "estimated_resolution_days": recovery_timeline,
            "confidence": round(confidence, 2),
            "estimated_resolution_date": (
                datetime.utcnow() + timedelta(days=recovery_timeline)
            ).strftime("%Y-%m-%d"),
            "post_resolution_predictions": {
                "mood": round(post_resolution_mood, 1),
                "energy": round(post_resolution_energy, 1),
            },
            "recommendation": self._build_conflict_recommendation(state, days_in_state),
        }

    @staticmethod
    def _build_conflict_recommendation(state: str, days: int) -> str:
        """Build recommendation for conflict resolution"""

        if state == "CONFLICT":
            if days >= 3:
                return "Consider proactive communication or mediation - conflict persisting"
            else:
                return "Allow time for emotions to settle, then discuss calmly"

        elif state == "COLD_WAR":
            if days >= 7:
                return "Extended silence harmful - consider reaching out with neutral topic"
            else:
                return "Avoid prolonged avoidance - gradual re-engagement recommended"

        elif state == "RECOVERY":
            return "Continue positive interactions - relationship healing"

        else:
            return "Maintain healthy communication patterns"
