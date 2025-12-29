"""
PLOS v2.0 - Health Monitoring & Anomaly Detection
Detects health concerns, tracks patterns, generates alerts
"""

from typing import Any, Dict, List, Optional

from shared.models import (
    AlertLevel,
    FieldMetadata,
    UserBaseline,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# HEALTH THRESHOLDS
# ============================================================================

# Sleep health thresholds
SLEEP_THRESHOLDS = {
    "severe_insomnia": {"max_hours": 4.0, "alert_level": AlertLevel.CRITICAL},
    "insomnia": {"max_hours": 5.0, "alert_level": AlertLevel.HIGH},
    "poor_sleep": {"max_hours": 6.0, "alert_level": AlertLevel.MEDIUM},
    "hypersomnia": {"min_hours": 10.0, "alert_level": AlertLevel.MEDIUM},
    "severe_hypersomnia": {"min_hours": 12.0, "alert_level": AlertLevel.HIGH},
}

# Sleep debt thresholds
SLEEP_DEBT_THRESHOLDS = {
    "moderate_debt": {"min_debt": 3.0, "alert_level": AlertLevel.LOW},
    "high_debt": {"min_debt": 5.0, "alert_level": AlertLevel.MEDIUM},
    "critical_debt": {"min_debt": 8.0, "alert_level": AlertLevel.HIGH},
}

# Mental health thresholds
MOOD_THRESHOLDS = {
    "severe_low_mood": {"max_score": 3, "alert_level": AlertLevel.HIGH},
    "low_mood": {"max_score": 4, "alert_level": AlertLevel.MEDIUM},
    "mood_volatility": {"max_stddev": 2.5, "alert_level": AlertLevel.MEDIUM},
}

# Stress thresholds
STRESS_THRESHOLDS = {
    "high_stress": {"min_score": 7, "alert_level": AlertLevel.MEDIUM},
    "severe_stress": {"min_score": 9, "alert_level": AlertLevel.HIGH},
}

# Conflict pattern thresholds
CONFLICT_THRESHOLDS = {
    "frequent_conflicts": {"max_days_between": 3, "alert_level": AlertLevel.MEDIUM},
    "chronic_conflict": {"min_days_in_conflict": 7, "alert_level": AlertLevel.HIGH},
    "cold_war_extended": {"min_days_in_coldwar": 10, "alert_level": AlertLevel.HIGH},
}


# ============================================================================
# HEALTH MONITOR
# ============================================================================


class HealthMonitor:
    """
    Monitors health patterns and generates alerts
    """

    def __init__(
        self,
        user_baseline: Optional[UserBaseline] = None,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ):
        self.user_baseline = user_baseline
        self.recent_history = recent_history or []

    def analyze_health(
        self,
        extracted_data: Dict[str, FieldMetadata],
        sleep_debt: float = 0.0,
        relationship_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Comprehensive health analysis

        Returns:
        List of health alerts
        """
        alerts = []

        # Sleep health monitoring
        sleep_alerts = self._check_sleep_health(extracted_data, sleep_debt)
        alerts.extend(sleep_alerts)

        # Mental health monitoring
        mental_alerts = self._check_mental_health(extracted_data)
        alerts.extend(mental_alerts)

        # Stress monitoring
        stress_alerts = self._check_stress_levels(extracted_data)
        alerts.extend(stress_alerts)

        # Relationship health monitoring
        if relationship_state:
            relationship_alerts = self._check_relationship_health(relationship_state)
            alerts.extend(relationship_alerts)

        # Pattern-based anomalies
        pattern_alerts = self._check_pattern_anomalies(extracted_data)
        alerts.extend(pattern_alerts)

        # Sort by severity
        alerts.sort(key=lambda x: self._alert_priority(x["level"]), reverse=True)

        logger.info(f"Health monitoring generated {len(alerts)} alerts")
        return alerts

    @staticmethod
    def _alert_priority(level: str) -> int:
        """Convert alert level to priority for sorting"""
        priority = {
            "CRITICAL": 4,
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1,
            "INFO": 0,
        }
        return priority.get(level, 0)

    # ========================================================================
    # SLEEP HEALTH
    # ========================================================================

    def _check_sleep_health(
        self, data: Dict[str, FieldMetadata], sleep_debt: float
    ) -> List[Dict[str, Any]]:
        """Monitor sleep patterns"""
        alerts = []

        # Check sleep duration
        if "sleep_hours" in data:
            sleep_hours = data["sleep_hours"].value

            # Severe insomnia
            if sleep_hours <= SLEEP_THRESHOLDS["severe_insomnia"]["max_hours"]:
                alerts.append(
                    {
                        "type": "severe_insomnia",
                        "level": AlertLevel.CRITICAL.value,
                        "message": f"Severe insomnia detected: only {sleep_hours}hrs sleep",
                        "value": sleep_hours,
                        "threshold": SLEEP_THRESHOLDS["severe_insomnia"]["max_hours"],
                        "recommendation": "Consider consulting a healthcare provider if this persists",
                    }
                )

            # Regular insomnia
            elif sleep_hours <= SLEEP_THRESHOLDS["insomnia"]["max_hours"]:
                alerts.append(
                    {
                        "type": "insomnia",
                        "level": AlertLevel.HIGH.value,
                        "message": f"Insomnia pattern: {sleep_hours}hrs sleep",
                        "value": sleep_hours,
                        "threshold": SLEEP_THRESHOLDS["insomnia"]["max_hours"],
                        "recommendation": "Try to maintain consistent sleep schedule, avoid screens before bed",
                    }
                )

            # Poor sleep
            elif sleep_hours <= SLEEP_THRESHOLDS["poor_sleep"]["max_hours"]:
                alerts.append(
                    {
                        "type": "poor_sleep",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"Insufficient sleep: {sleep_hours}hrs",
                        "value": sleep_hours,
                        "threshold": SLEEP_THRESHOLDS["poor_sleep"]["max_hours"],
                        "recommendation": "Aim for 7-9 hours of sleep",
                    }
                )

            # Hypersomnia
            elif sleep_hours >= SLEEP_THRESHOLDS["severe_hypersomnia"]["min_hours"]:
                alerts.append(
                    {
                        "type": "severe_hypersomnia",
                        "level": AlertLevel.HIGH.value,
                        "message": f"Excessive sleep: {sleep_hours}hrs",
                        "value": sleep_hours,
                        "threshold": SLEEP_THRESHOLDS["severe_hypersomnia"][
                            "min_hours"
                        ],
                        "recommendation": "Excessive sleep may indicate depression or other health issues",
                    }
                )

            elif sleep_hours >= SLEEP_THRESHOLDS["hypersomnia"]["min_hours"]:
                alerts.append(
                    {
                        "type": "hypersomnia",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"High sleep duration: {sleep_hours}hrs",
                        "value": sleep_hours,
                        "threshold": SLEEP_THRESHOLDS["hypersomnia"]["min_hours"],
                        "recommendation": "Monitor for signs of fatigue or low energy",
                    }
                )

        # Check sleep debt
        if sleep_debt >= SLEEP_DEBT_THRESHOLDS["critical_debt"]["min_debt"]:
            alerts.append(
                {
                    "type": "critical_sleep_debt",
                    "level": AlertLevel.HIGH.value,
                    "message": f"Critical sleep debt: {sleep_debt:.1f}hrs accumulated",
                    "value": sleep_debt,
                    "threshold": SLEEP_DEBT_THRESHOLDS["critical_debt"]["min_debt"],
                    "recommendation": "Prioritize catch-up sleep over the next few days",
                }
            )

        elif sleep_debt >= SLEEP_DEBT_THRESHOLDS["high_debt"]["min_debt"]:
            alerts.append(
                {
                    "type": "high_sleep_debt",
                    "level": AlertLevel.MEDIUM.value,
                    "message": f"High sleep debt: {sleep_debt:.1f}hrs accumulated",
                    "value": sleep_debt,
                    "threshold": SLEEP_DEBT_THRESHOLDS["high_debt"]["min_debt"],
                    "recommendation": "Try to get extra sleep this weekend",
                }
            )

        elif sleep_debt >= SLEEP_DEBT_THRESHOLDS["moderate_debt"]["min_debt"]:
            alerts.append(
                {
                    "type": "moderate_sleep_debt",
                    "level": AlertLevel.LOW.value,
                    "message": f"Moderate sleep debt: {sleep_debt:.1f}hrs",
                    "value": sleep_debt,
                    "threshold": SLEEP_DEBT_THRESHOLDS["moderate_debt"]["min_debt"],
                    "recommendation": "Monitor sleep duration",
                }
            )

        # Check sleep quality
        if "sleep_quality" in data:
            quality = data["sleep_quality"].value
            if quality <= 4:
                alerts.append(
                    {
                        "type": "poor_sleep_quality",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"Poor sleep quality: {quality}/10",
                        "value": quality,
                        "threshold": 4,
                        "recommendation": "Consider sleep hygiene improvements",
                    }
                )

        return alerts

    # ========================================================================
    # MENTAL HEALTH
    # ========================================================================

    def _check_mental_health(
        self, data: Dict[str, FieldMetadata]
    ) -> List[Dict[str, Any]]:
        """Monitor mental health indicators"""
        alerts = []

        # Check mood
        mood_key = "mood_score" if "mood_score" in data else "mood_score_estimate"
        if mood_key in data:
            mood = data[mood_key].value

            if mood <= MOOD_THRESHOLDS["severe_low_mood"]["max_score"]:
                alerts.append(
                    {
                        "type": "severe_low_mood",
                        "level": AlertLevel.HIGH.value,
                        "message": f"Severe low mood detected: {mood}/10",
                        "value": mood,
                        "threshold": MOOD_THRESHOLDS["severe_low_mood"]["max_score"],
                        "recommendation": "Consider reaching out to friends, family, or a mental health professional",
                    }
                )

            elif mood <= MOOD_THRESHOLDS["low_mood"]["max_score"]:
                alerts.append(
                    {
                        "type": "low_mood",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"Low mood: {mood}/10",
                        "value": mood,
                        "threshold": MOOD_THRESHOLDS["low_mood"]["max_score"],
                        "recommendation": "Engage in activities you enjoy, maintain social connections",
                    }
                )

        # Check mood volatility from baseline
        if self.user_baseline and mood_key in data:
            mood = data[mood_key].value
            baseline_mood = self.user_baseline.mood_score
            baseline_stddev = self.user_baseline.mood_stddev

            deviation = abs(mood - baseline_mood)
            if baseline_stddev > 0:
                z_score = deviation / baseline_stddev

                if z_score > 3:
                    alerts.append(
                        {
                            "type": "mood_volatility",
                            "level": AlertLevel.MEDIUM.value,
                            "message": f"Unusual mood swing: {mood}/10 (baseline {baseline_mood:.1f})",
                            "value": mood,
                            "baseline": baseline_mood,
                            "deviation": f"{z_score:.1f} standard deviations",
                            "recommendation": "Monitor for pattern of mood volatility",
                        }
                    )

        # Check for sustained low mood pattern (last 3+ days)
        if len(self.recent_history) >= 3:
            recent_moods = [
                entry.get("mood_score", entry.get("mood_score_estimate"))
                for entry in self.recent_history[-3:]
                if entry.get("mood_score") or entry.get("mood_score_estimate")
            ]

            if len(recent_moods) >= 3 and all(m <= 4 for m in recent_moods):
                avg_mood = sum(recent_moods) / len(recent_moods)
                alerts.append(
                    {
                        "type": "sustained_low_mood",
                        "level": AlertLevel.HIGH.value,
                        "message": f"Low mood persisting for {len(recent_moods)} days (avg {avg_mood:.1f}/10)",
                        "value": avg_mood,
                        "duration_days": len(recent_moods),
                        "recommendation": "Sustained low mood may indicate depression - consider professional support",
                    }
                )

        return alerts

    # ========================================================================
    # STRESS MONITORING
    # ========================================================================

    def _check_stress_levels(
        self, data: Dict[str, FieldMetadata]
    ) -> List[Dict[str, Any]]:
        """Monitor stress levels"""
        alerts = []

        if "stress_level" in data:
            stress = data["stress_level"].value

            if stress >= STRESS_THRESHOLDS["severe_stress"]["min_score"]:
                alerts.append(
                    {
                        "type": "severe_stress",
                        "level": AlertLevel.HIGH.value,
                        "message": f"Severe stress detected: {stress}/10",
                        "value": stress,
                        "threshold": STRESS_THRESHOLDS["severe_stress"]["min_score"],
                        "recommendation": "Practice stress management techniques, consider taking breaks",
                    }
                )

            elif stress >= STRESS_THRESHOLDS["high_stress"]["min_score"]:
                alerts.append(
                    {
                        "type": "high_stress",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"High stress level: {stress}/10",
                        "value": stress,
                        "threshold": STRESS_THRESHOLDS["high_stress"]["min_score"],
                        "recommendation": "Engage in relaxation activities, ensure adequate rest",
                    }
                )

        # Check for sustained high stress
        if len(self.recent_history) >= 5:
            recent_stress = [
                entry.get("stress_level")
                for entry in self.recent_history[-5:]
                if entry.get("stress_level")
            ]

            if len(recent_stress) >= 3 and all(s >= 7 for s in recent_stress):
                avg_stress = sum(recent_stress) / len(recent_stress)
                alerts.append(
                    {
                        "type": "chronic_stress",
                        "level": AlertLevel.HIGH.value,
                        "message": f"Chronic stress pattern: {len(recent_stress)} days at {avg_stress:.1f}/10",
                        "value": avg_stress,
                        "duration_days": len(recent_stress),
                        "recommendation": "Chronic stress can impact health - consider stress management strategies",
                    }
                )

        return alerts

    # ========================================================================
    # RELATIONSHIP HEALTH
    # ========================================================================

    def _check_relationship_health(
        self, relationship_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Monitor relationship health patterns"""
        alerts = []

        state = relationship_state.get("state")
        days_in_state = relationship_state.get("days_in_state", 0)

        # Extended conflict
        if (
            state == "CONFLICT"
            and days_in_state
            >= CONFLICT_THRESHOLDS["chronic_conflict"]["min_days_in_conflict"]
        ):
            alerts.append(
                {
                    "type": "chronic_conflict",
                    "level": AlertLevel.HIGH.value,
                    "message": f"Conflict state for {days_in_state} days",
                    "value": days_in_state,
                    "threshold": CONFLICT_THRESHOLDS["chronic_conflict"][
                        "min_days_in_conflict"
                    ],
                    "recommendation": "Consider relationship counseling or mediation",
                }
            )

        # Extended cold war
        elif (
            state == "COLD_WAR"
            and days_in_state
            >= CONFLICT_THRESHOLDS["cold_war_extended"]["min_days_in_coldwar"]
        ):
            alerts.append(
                {
                    "type": "extended_cold_war",
                    "level": AlertLevel.HIGH.value,
                    "message": f"Cold War state for {days_in_state} days",
                    "value": days_in_state,
                    "threshold": CONFLICT_THRESHOLDS["cold_war_extended"][
                        "min_days_in_coldwar"
                    ],
                    "recommendation": "Extended avoidance may damage relationship - consider reaching out",
                }
            )

        # Frequent conflicts (check history)
        if len(self.recent_history) >= 7:
            conflict_days = sum(
                1
                for entry in self.recent_history[-7:]
                if entry.get("conflict_mentioned") is True
            )

            if conflict_days >= 3:
                alerts.append(
                    {
                        "type": "frequent_conflicts",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"{conflict_days} conflicts in last 7 days",
                        "value": conflict_days,
                        "threshold": 3,
                        "recommendation": "Frequent conflicts may indicate underlying issues - consider communication strategies",
                    }
                )

        return alerts

    # ========================================================================
    # PATTERN ANOMALIES
    # ========================================================================

    def _check_pattern_anomalies(
        self, data: Dict[str, FieldMetadata]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in patterns"""
        alerts = []

        if not self.user_baseline:
            return alerts

        # Significant sleep deviation
        if "sleep_hours" in data:
            sleep = data["sleep_hours"].value
            baseline = self.user_baseline.sleep_hours
            stddev = self.user_baseline.sleep_stddev

            if stddev > 0:
                z_score = abs((sleep - baseline) / stddev)

                if z_score > 2.5:
                    percentage = ((sleep - baseline) / baseline) * 100
                    alerts.append(
                        {
                            "type": "sleep_anomaly",
                            "level": AlertLevel.LOW.value,
                            "message": f"Unusual sleep pattern: {sleep}hrs vs baseline {baseline:.1f}hrs ({percentage:+.0f}%)",
                            "value": sleep,
                            "baseline": baseline,
                            "z_score": round(z_score, 1),
                            "recommendation": "Monitor for pattern continuation",
                        }
                    )

        # Energy crash
        if "energy_level" in data:
            energy = data["energy_level"].value
            baseline = self.user_baseline.energy_level

            if energy <= 3 and baseline >= 6:
                alerts.append(
                    {
                        "type": "energy_crash",
                        "level": AlertLevel.MEDIUM.value,
                        "message": f"Significant energy drop: {energy}/10 (baseline {baseline:.1f}/10)",
                        "value": energy,
                        "baseline": baseline,
                        "recommendation": "May be related to poor sleep, stress, or health issues",
                    }
                )

        return alerts


# ============================================================================
# TREND DETECTOR
# ============================================================================


class TrendDetector:
    """
    Detects trends in health metrics over time
    """

    @staticmethod
    def detect_trends(
        history: List[Dict[str, Any]], metric: str, window_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Detect trends in a specific metric

        Returns:
        Dict with trend info: direction, magnitude, confidence
        """
        if len(history) < window_days:
            return None

        # Extract metric values
        values = [
            entry.get(metric)
            for entry in history[-window_days:]
            if entry.get(metric) is not None
        ]

        if len(values) < window_days // 2:
            return None

        # Calculate trend (simple linear regression)
        n = len(values)
        x = list(range(n))
        y = values

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return None

        slope = numerator / denominator

        # Determine direction
        if abs(slope) < 0.1:
            direction = "stable"
        elif slope > 0:
            direction = (
                "improving"
                if metric in ["mood_score", "energy_level", "sleep_hours"]
                else "worsening"
            )
        else:
            direction = (
                "worsening"
                if metric in ["mood_score", "energy_level", "sleep_hours"]
                else "improving"
            )

        # Calculate confidence (R-squared)
        y_pred = [slope * i + (y_mean - slope * x_mean) for i in x]
        ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "metric": metric,
            "direction": direction,
            "slope": round(slope, 3),
            "confidence": round(r_squared, 2),
            "current_value": values[-1],
            "change_over_period": round(values[-1] - values[0], 2),
            "window_days": window_days,
        }
