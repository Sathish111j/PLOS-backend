"""
PLOS v2.0 - Inference Rule Engine
4-Tier inference system for filling missing data intelligently
"""

from typing import Any, Dict, List, Optional

from shared.models import (
    ExtractionType,
    FieldMetadata,
    UserBaseline,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# INFERENCE ENGINE - 4 TIERS
# ============================================================================


class InferenceEngine:
    """
    4-Tier Inference System:

    TIER 1: Explicit extraction (already done in preprocessing)
    TIER 2: Inferential rules (calculate from available data)
    TIER 3: Contextual baseline comparison
    TIER 4: Default/population baseline (last resort)
    """

    def __init__(
        self,
        user_baseline: Optional[UserBaseline] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.user_baseline = user_baseline
        self.context = context or {}

    def infer_missing_fields(
        self, explicit_extractions: Dict[str, FieldMetadata], preprocessed_text: str
    ) -> Dict[str, FieldMetadata]:
        """
        Apply inference rules to fill missing fields

        Returns:
        Dict of additional inferred fields
        """
        inferred = {}

        # TIER 2: Inferential rules
        tier2_inferences = self._tier2_inference(
            explicit_extractions, preprocessed_text
        )
        inferred.update(tier2_inferences)

        # TIER 3: Contextual baseline
        tier3_inferences = self._tier3_contextual_inference(explicit_extractions)
        inferred.update(tier3_inferences)

        # TIER 4: Population defaults (only if nothing else worked)
        tier4_defaults = self._tier4_defaults(explicit_extractions, inferred)
        inferred.update(tier4_defaults)

        logger.info(f"Inference engine generated {len(inferred)} additional fields")
        return inferred

    # ========================================================================
    # TIER 2: INFERENTIAL RULES
    # ========================================================================

    def _tier2_inference(
        self, explicit: Dict[str, FieldMetadata], text: str
    ) -> Dict[str, FieldMetadata]:
        """
        Calculate from available data and apply correlation rules
        """
        inferred = {}

        # Infer sleep quality from disruptions
        if "sleep_hours" in explicit:
            sleep_hours = explicit["sleep_hours"].value

            # Infer quality from duration
            if sleep_hours >= 8:
                quality = 8
                confidence = 0.65
            elif sleep_hours >= 7:
                quality = 7
                confidence = 0.60
            elif sleep_hours >= 6:
                quality = 6
                confidence = 0.55
            elif sleep_hours >= 5:
                quality = 4
                confidence = 0.55
            else:
                quality = 3
                confidence = 0.60

            inferred["sleep_quality"] = FieldMetadata(
                value=quality,
                type=ExtractionType.INFERRED,
                confidence=confidence,
                source="correlation",
                reasoning=f"Inferred from sleep duration ({sleep_hours}hrs)",
            )

        # Infer energy from sleep and mood
        if "sleep_hours" in explicit or "mood_score_estimate" in explicit:
            energy = self._infer_energy_level(explicit)
            if energy:
                inferred["energy_level"] = energy

        # Infer stress from mood and conflict
        stress = self._infer_stress_level(explicit, text)
        if stress:
            inferred["stress_level"] = stress

        # Infer productivity from work hours and focus indicators
        productivity = self._infer_productivity(explicit, text)
        if productivity:
            inferred["productivity_score"] = productivity

        # Infer exercise intensity from duration and type
        if "exercise_duration_minutes" in explicit:
            intensity = self._infer_exercise_intensity(explicit)
            if intensity:
                inferred["exercise_intensity"] = intensity

        return inferred

    def _infer_energy_level(
        self, explicit: Dict[str, FieldMetadata]
    ) -> Optional[FieldMetadata]:
        """Infer energy from sleep and mood"""

        # Start with baseline or neutral
        base_energy = 6.0
        confidence = 0.50
        factors = []

        # Adjust based on sleep
        if "sleep_hours" in explicit:
            sleep_hours = explicit["sleep_hours"].value
            if sleep_hours >= 8:
                base_energy += 1.5
                factors.append(f"+1.5 from good sleep ({sleep_hours}hrs)")
                confidence += 0.10
            elif sleep_hours >= 7:
                base_energy += 0.5
                factors.append("+0.5 from adequate sleep")
                confidence += 0.05
            elif sleep_hours < 6:
                base_energy -= 2.0
                factors.append(f"-2.0 from poor sleep ({sleep_hours}hrs)")
                confidence += 0.15

        # Adjust based on mood
        if "mood_score_estimate" in explicit:
            mood = explicit["mood_score_estimate"].value
            if mood >= 8:
                base_energy += 1.0
                factors.append("+1.0 from positive mood")
                confidence += 0.10
            elif mood <= 4:
                base_energy -= 1.0
                factors.append("-1.0 from negative mood")
                confidence += 0.10

        # Clamp to 1-10 range
        energy = max(1, min(10, round(base_energy)))

        if factors:
            return FieldMetadata(
                value=energy,
                type=ExtractionType.INFERRED,
                confidence=min(confidence, 0.75),
                source="correlation",
                reasoning="; ".join(factors),
            )

        return None

    def _infer_stress_level(
        self, explicit: Dict[str, FieldMetadata], text: str
    ) -> Optional[FieldMetadata]:
        """Infer stress from mood, conflict, and work pressure"""

        base_stress = 4.0
        confidence = 0.50
        factors = []

        # Conflict increases stress
        if "conflict_mentioned" in explicit and explicit["conflict_mentioned"].value:
            base_stress += 3.0
            factors.append("+3.0 from conflict")
            confidence += 0.20

        # Negative mood correlates with stress
        if "mood_score_estimate" in explicit:
            mood = explicit["mood_score_estimate"].value
            if mood <= 4:
                base_stress += 2.0
                factors.append("+2.0 from low mood")
                confidence += 0.15
            elif mood >= 8:
                base_stress -= 1.5
                factors.append("-1.5 from positive mood")
                confidence += 0.10

        # Work pressure indicators
        if "work_hours" in explicit and explicit["work_hours"].value > 8:
            base_stress += 1.5
            factors.append("+1.5 from long work hours")
            confidence += 0.10

        # Deadline/pressure keywords
        stress_keywords = ["deadline", "pressure", "stressed", "overwhelmed", "anxious"]
        if any(keyword in text.lower() for keyword in stress_keywords):
            base_stress += 1.0
            factors.append("+1.0 from stress keywords")
            confidence += 0.10

        stress = max(1, min(10, round(base_stress)))

        if factors:
            return FieldMetadata(
                value=stress,
                type=ExtractionType.INFERRED,
                confidence=min(confidence, 0.75),
                source="correlation",
                reasoning="; ".join(factors),
            )

        return None

    def _infer_productivity(
        self, explicit: Dict[str, FieldMetadata], text: str
    ) -> Optional[FieldMetadata]:
        """Infer productivity from work hours and focus indicators"""

        if "work_hours" not in explicit:
            return None

        work_hours = explicit["work_hours"].value
        base_productivity = 6.0
        confidence = 0.55
        factors = []

        # More hours usually = more productivity (to a point)
        if work_hours >= 6:
            base_productivity += 1.0
            factors.append("+1.0 from substantial work time")
        elif work_hours >= 4:
            base_productivity += 0.5
            factors.append("+0.5 from moderate work time")

        # Focus/productivity keywords
        positive_keywords = [
            "productive",
            "focused",
            "accomplished",
            "completed",
            "finished",
        ]
        negative_keywords = ["distracted", "unfocused", "procrastinated", "wasted"]

        positive_count = sum(1 for kw in positive_keywords if kw in text.lower())
        negative_count = sum(1 for kw in negative_keywords if kw in text.lower())

        if positive_count > 0:
            base_productivity += min(positive_count, 2)
            factors.append(f"+{min(positive_count, 2)} from productivity indicators")
            confidence += 0.10

        if negative_count > 0:
            base_productivity -= min(negative_count, 2)
            factors.append(f"-{min(negative_count, 2)} from distraction indicators")
            confidence += 0.10

        productivity = max(1, min(10, round(base_productivity)))

        return FieldMetadata(
            value=productivity,
            type=ExtractionType.INFERRED,
            confidence=min(confidence, 0.70),
            source="correlation",
            reasoning="; ".join(factors) if factors else "Inferred from work hours",
        )

    def _infer_exercise_intensity(
        self, explicit: Dict[str, FieldMetadata]
    ) -> Optional[FieldMetadata]:
        """Infer exercise intensity from duration and type"""

        duration = explicit["exercise_duration_minutes"].value
        exercise_type = (
            explicit.get("exercise_type", {}).value
            if "exercise_type" in explicit
            else "unknown"
        )

        # Duration-based intensity
        if duration >= 60:
            intensity = "high"
            confidence = 0.65
        elif duration >= 30:
            intensity = "moderate"
            confidence = 0.70
        else:
            intensity = "low"
            confidence = 0.60

        # Adjust based on type
        high_intensity_activities = ["running", "sprinting", "hiit", "cardio"]
        moderate_activities = ["badminton", "cycling", "swimming"]

        if any(
            activity in exercise_type.lower() for activity in high_intensity_activities
        ):
            intensity = "high"
            confidence += 0.10
        elif any(activity in exercise_type.lower() for activity in moderate_activities):
            if intensity == "low":
                intensity = "moderate"
                confidence += 0.05

        return FieldMetadata(
            value=intensity,
            type=ExtractionType.INFERRED,
            confidence=min(confidence, 0.75),
            source="correlation",
            reasoning=f"Inferred from {duration}min duration and activity type",
        )

    # ========================================================================
    # TIER 3: CONTEXTUAL BASELINE COMPARISON
    # ========================================================================

    def _tier3_contextual_inference(
        self, explicit: Dict[str, FieldMetadata]
    ) -> Dict[str, FieldMetadata]:
        """
        Use user baseline and context for inference
        """
        inferred = {}

        if not self.user_baseline:
            logger.debug("No user baseline available for Tier 3 inference")
            return inferred

        # Infer sleep from user baseline if missing
        if "sleep_hours" not in explicit:
            # Check if it's a weekend/weekday pattern
            day_of_week_pattern = self.context.get("day_of_week_pattern", {})
            if "sleep_baseline" in day_of_week_pattern:
                sleep_hours = day_of_week_pattern["sleep_baseline"]["value"]
                confidence = day_of_week_pattern["sleep_baseline"]["confidence"]

                inferred["sleep_hours"] = FieldMetadata(
                    value=sleep_hours,
                    type=ExtractionType.ESTIMATED,
                    confidence=max(confidence * 0.7, 0.40),
                    source="day_of_week_pattern",
                    reasoning=f"Estimated from day-of-week pattern ({confidence:.0%} confidence)",
                )
            else:
                # Use overall baseline
                inferred["sleep_hours"] = FieldMetadata(
                    value=self.user_baseline.sleep_hours,
                    type=ExtractionType.ESTIMATED,
                    confidence=0.45,
                    source="user_baseline",
                    reasoning="Estimated from 30-day baseline (no specific data)",
                )

        # Infer mood from baseline if missing
        if "mood_score_estimate" not in explicit and "mood_score" not in explicit:
            # Adjust baseline based on context
            base_mood = self.user_baseline.mood_score
            confidence = 0.40
            factors = []

            # Adjust for relationship state
            rel_state = self.context.get("relationship_state", {})
            if rel_state.get("state") == "CONFLICT":
                base_mood -= 3.5
                factors.append("-3.5 for conflict state")
                confidence += 0.15
            elif rel_state.get("state") == "RECOVERY":
                base_mood -= 1.5
                factors.append("-1.5 for recovery state")
                confidence += 0.10

            # Adjust for sleep debt
            sleep_debt = self.context.get("sleep_debt", 0)
            if sleep_debt > 5:
                base_mood -= 1.5
                factors.append(f"-1.5 for high sleep debt ({sleep_debt:.1f}hrs)")
                confidence += 0.10

            mood = max(1, min(10, round(base_mood)))

            inferred["mood_score"] = FieldMetadata(
                value=mood,
                type=ExtractionType.ESTIMATED,
                confidence=min(confidence, 0.65),
                source="contextual_baseline",
                reasoning=(
                    f"Baseline {self.user_baseline.mood_score:.1f}; "
                    + "; ".join(factors)
                    if factors
                    else "From baseline"
                ),
            )

        # Detect anomalies by comparing to baseline
        anomalies = self._detect_baseline_anomalies(explicit)
        if anomalies:
            inferred["_anomalies"] = FieldMetadata(
                value=anomalies,
                type=ExtractionType.INFERRED,
                confidence=0.80,
                source="baseline_comparison",
                reasoning="Significant deviations from user baseline detected",
            )

        return inferred

    def _detect_baseline_anomalies(
        self, explicit: Dict[str, FieldMetadata]
    ) -> List[str]:
        """Detect anomalies by comparing to baseline"""

        if not self.user_baseline:
            return []

        anomalies = []

        # Sleep anomaly
        if "sleep_hours" in explicit:
            sleep = explicit["sleep_hours"].value
            baseline = self.user_baseline.sleep_hours
            stddev = self.user_baseline.sleep_stddev

            z_score = abs((sleep - baseline) / stddev) if stddev > 0 else 0

            if z_score > 2:
                percentage = ((sleep - baseline) / baseline) * 100
                anomalies.append(
                    f"Sleep: {sleep}hrs vs baseline {baseline:.1f}hrs "
                    f"({percentage:+.0f}%, {z_score:.1f} std deviations)"
                )

        # Mood anomaly
        mood_field = "mood_score" if "mood_score" in explicit else "mood_score_estimate"
        if mood_field in explicit:
            mood = explicit[mood_field].value
            baseline = self.user_baseline.mood_score
            stddev = self.user_baseline.mood_stddev

            z_score = abs((mood - baseline) / stddev) if stddev > 0 else 0

            if z_score > 2:
                anomalies.append(
                    f"Mood: {mood}/10 vs baseline {baseline:.1f}/10 "
                    f"({z_score:.1f} std deviations)"
                )

        return anomalies

    # ========================================================================
    # TIER 4: POPULATION DEFAULTS
    # ========================================================================

    def _tier4_defaults(
        self, explicit: Dict[str, FieldMetadata], inferred: Dict[str, FieldMetadata]
    ) -> Dict[str, FieldMetadata]:
        """
        Last resort: use population averages
        Only used when no other data available
        """
        defaults = {}

        # Only apply defaults if field is completely missing
        all_fields = {**explicit, **inferred}

        if "sleep_hours" not in all_fields:
            defaults["sleep_hours"] = FieldMetadata(
                value=7.0,
                type=ExtractionType.DEFAULT,
                confidence=0.20,
                source="population_average",
                reasoning="No sleep data available, using population average",
            )

        if "mood_score" not in all_fields and "mood_score_estimate" not in all_fields:
            defaults["mood_score"] = FieldMetadata(
                value=6.5,
                type=ExtractionType.DEFAULT,
                confidence=0.15,
                source="population_average",
                reasoning="No mood data available, using population average",
            )

        if "energy_level" not in all_fields:
            defaults["energy_level"] = FieldMetadata(
                value=6.0,
                type=ExtractionType.DEFAULT,
                confidence=0.15,
                source="population_average",
                reasoning="No energy data available, using population average",
            )

        if "stress_level" not in all_fields:
            defaults["stress_level"] = FieldMetadata(
                value=4.0,
                type=ExtractionType.DEFAULT,
                confidence=0.15,
                source="population_average",
                reasoning="No stress data available, using population average",
            )

        if defaults:
            logger.warning(
                f"Applied {len(defaults)} population defaults (low confidence)"
            )

        return defaults


# ============================================================================
# ACTIVITY CORRELATION
# ============================================================================


class ActivityCorrelationEngine:
    """
    Analyzes correlation between activities and mood/energy/sleep
    """

    def __init__(self, activity_patterns: List[Any]):
        self.activity_patterns = {
            pattern.activity_type: pattern for pattern in activity_patterns
        }

    def predict_impact(self, activities: List[str]) -> Dict[str, FieldMetadata]:
        """
        Predict mood/energy/sleep impact from activities
        """
        predictions = {}

        if not activities:
            return predictions

        total_mood_impact = 0
        total_energy_impact = 0
        total_sleep_impact = 0
        count = 0

        for activity in activities:
            if activity in self.activity_patterns:
                pattern = self.activity_patterns[activity]

                if pattern.avg_mood_impact is not None:
                    total_mood_impact += pattern.avg_mood_impact
                    count += 1

                if pattern.avg_energy_impact is not None:
                    total_energy_impact += pattern.avg_energy_impact

                if pattern.avg_sleep_impact is not None:
                    total_sleep_impact += pattern.avg_sleep_impact

        if count > 0:
            predictions["predicted_mood_impact"] = FieldMetadata(
                value=total_mood_impact,
                type=ExtractionType.INFERRED,
                confidence=0.70,
                source="activity_correlation",
                reasoning=f"Based on {count} known activity patterns",
            )

        return predictions
