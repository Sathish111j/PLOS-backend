"""
PLOS v2.0 - Relationship State Machine
Tracks relationship states, transitions, and impact on mood/sleep/energy
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from shared.models import (
    ExtractionType,
    FieldMetadata,
    RelationshipState,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# STATE TRANSITION RULES
# ============================================================================

# State transition matrix (from_state -> to_state -> required conditions)
TRANSITION_RULES = {
    RelationshipState.HARMONY: {
        RelationshipState.TENSION: {
            "condition": "minor_disagreement",
            "required_signals": ["disagreement", "annoyed", "irritated"],
        },
        RelationshipState.CONFLICT: {
            "condition": "major_conflict",
            "required_signals": ["fight", "argument", "conflict", "mad", "angry"],
        },
    },
    RelationshipState.TENSION: {
        RelationshipState.HARMONY: {
            "condition": "resolved_quickly",
            "required_signals": ["resolved", "made up", "talked it out", "better"],
        },
        RelationshipState.CONFLICT: {
            "condition": "escalation",
            "required_signals": ["worse", "escalated", "fight", "argument"],
        },
    },
    RelationshipState.CONFLICT: {
        RelationshipState.COLD_WAR: {
            "condition": "avoidance_pattern",
            "required_signals": ["not talking", "avoiding", "silent", "ignoring"],
        },
        RelationshipState.RECOVERY: {
            "condition": "apology_or_discussion",
            "required_signals": ["apologized", "talked", "discussed", "sorry"],
        },
    },
    RelationshipState.COLD_WAR: {
        RelationshipState.RECOVERY: {
            "condition": "breakthrough",
            "required_signals": ["talked", "broke silence", "reached out"],
        },
        RelationshipState.CONFLICT: {
            "condition": "renewed_argument",
            "required_signals": ["fight again", "argument", "brought it up"],
        },
    },
    RelationshipState.RECOVERY: {
        RelationshipState.HARMONY: {
            "condition": "full_resolution",
            "required_signals": [
                "back to normal",
                "resolved",
                "good again",
                "fine now",
            ],
        },
        RelationshipState.CONFLICT: {
            "condition": "relapse",
            "required_signals": ["same issue", "again", "still upset"],
        },
    },
    RelationshipState.RESOLVED: {
        RelationshipState.HARMONY: {
            "condition": "stabilization",
            "required_signals": ["stable", "good", "happy"],
        },
    },
}

# Expected duration for each state (in days)
STATE_EXPECTED_DURATION = {
    RelationshipState.HARMONY: None,  # Indefinite
    RelationshipState.TENSION: 1,
    RelationshipState.CONFLICT: 2,
    RelationshipState.COLD_WAR: 5,
    RelationshipState.RECOVERY: 3,
    RelationshipState.RESOLVED: 7,
}

# Impact on mood/sleep/energy per state
STATE_IMPACT = {
    RelationshipState.HARMONY: {
        "mood_impact": 0.0,
        "sleep_impact": 0.0,
        "energy_impact": 0.0,
        "stress_impact": 0.0,
    },
    RelationshipState.TENSION: {
        "mood_impact": -1.0,
        "sleep_impact": -0.5,
        "energy_impact": -0.5,
        "stress_impact": 1.5,
    },
    RelationshipState.CONFLICT: {
        "mood_impact": -3.5,
        "sleep_impact": -2.0,
        "energy_impact": -2.0,
        "stress_impact": 4.0,
    },
    RelationshipState.COLD_WAR: {
        "mood_impact": -2.5,
        "sleep_impact": -1.5,
        "energy_impact": -1.5,
        "stress_impact": 3.5,
    },
    RelationshipState.RECOVERY: {
        "mood_impact": -1.0,
        "sleep_impact": -0.5,
        "energy_impact": 0.0,
        "stress_impact": 1.5,
    },
    RelationshipState.RESOLVED: {
        "mood_impact": 0.5,
        "sleep_impact": 0.0,
        "energy_impact": 0.5,
        "stress_impact": -0.5,
    },
}


# ============================================================================
# RELATIONSHIP STATE MACHINE
# ============================================================================


class RelationshipStateMachine:
    """
    Manages relationship state transitions and impact calculations
    """

    def __init__(self, current_state: Optional[Dict[str, Any]] = None):
        """
        Args:
            current_state: Dict with keys: state, days_in_state, started_at
        """
        if current_state:
            self.state = RelationshipState(current_state["state"])
            self.days_in_state = current_state["days_in_state"]
            self.started_at = current_state.get("started_at")
        else:
            # Default to HARMONY for new users
            self.state = RelationshipState.HARMONY
            self.days_in_state = 0
            self.started_at = None

    def detect_transition(
        self, entry_text: str, conflict_mentioned: bool = False
    ) -> Tuple[Optional[RelationshipState], Optional[str]]:
        """
        Detect if a state transition should occur based on journal entry

        Returns:
        (new_state, trigger_reason) or (None, None) if no transition
        """
        text_lower = entry_text.lower()

        # Get possible transitions from current state
        possible_transitions = TRANSITION_RULES.get(self.state, {})

        for new_state, rules in possible_transitions.items():
            required_signals = rules["required_signals"]

            # Check if any signal is present
            for signal in required_signals:
                if signal in text_lower:
                    logger.info(
                        f"State transition detected: {self.state.value} -> {new_state.value} "
                        f"(trigger: '{signal}')"
                    )
                    return new_state, f"Detected signal: '{signal}'"

        # Special case: conflict mentioned explicitly
        if conflict_mentioned and self.state == RelationshipState.HARMONY:
            return RelationshipState.CONFLICT, "Conflict explicitly mentioned"

        return None, None

    def transition_to(
        self, new_state: RelationshipState, trigger: str
    ) -> Dict[str, Any]:
        """
        Execute state transition

        Returns:
        Dict with transition event details
        """
        old_state = self.state
        old_days = self.days_in_state

        self.state = new_state
        self.days_in_state = 0
        self.started_at = datetime.utcnow()

        transition_event = {
            "from_state": old_state.value,
            "to_state": new_state.value,
            "trigger": trigger,
            "timestamp": self.started_at,
            "days_in_previous_state": old_days,
            "expected_duration_days": STATE_EXPECTED_DURATION.get(new_state),
        }

        logger.info(
            f"Relationship transition: {old_state.value} ({old_days} days) -> "
            f"{new_state.value} (trigger: {trigger})"
        )

        return transition_event

    def increment_day(self):
        """Increment days in current state (called daily)"""
        self.days_in_state += 1

    def get_impact(self) -> Dict[str, float]:
        """Get current state's impact on mood/sleep/energy"""
        return STATE_IMPACT[self.state]

    def get_expected_resolution_date(self) -> Optional[datetime]:
        """Estimate when state might resolve"""
        expected_duration = STATE_EXPECTED_DURATION.get(self.state)

        if expected_duration is None or not self.started_at:
            return None

        return self.started_at + timedelta(days=expected_duration)

    def is_overdue(self) -> bool:
        """Check if state has exceeded expected duration"""
        expected_duration = STATE_EXPECTED_DURATION.get(self.state)

        if expected_duration is None:
            return False

        return self.days_in_state > expected_duration * 1.5

    def get_status_summary(self) -> Dict[str, Any]:
        """Get current status summary"""
        impact = self.get_impact()
        expected_resolution = self.get_expected_resolution_date()

        return {
            "state": self.state.value,
            "days_in_state": self.days_in_state,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "impact": impact,
            "expected_resolution_date": (
                expected_resolution.isoformat() if expected_resolution else None
            ),
            "is_overdue": self.is_overdue(),
            "expected_duration_days": STATE_EXPECTED_DURATION.get(self.state),
        }


# ============================================================================
# RELATIONSHIP IMPACT CALCULATOR
# ============================================================================


class RelationshipImpactCalculator:
    """
    Calculates relationship state impact on other metrics
    """

    @staticmethod
    def apply_relationship_impact(
        base_values: Dict[str, FieldMetadata],
        relationship_state: RelationshipState,
        days_in_state: int,
    ) -> Dict[str, FieldMetadata]:
        """
        Adjust mood/sleep/energy based on relationship state

        Returns:
        Dict of adjusted values with updated metadata
        """
        adjusted = {}
        impact = STATE_IMPACT[relationship_state]

        # Calculate impact multiplier (increases with days in state)
        # Peak impact at 3 days, then plateaus
        impact_multiplier = min(1.0, days_in_state / 3.0)

        # Apply mood impact
        if "mood_score" in base_values or "mood_score_estimate" in base_values:
            mood_key = (
                "mood_score" if "mood_score" in base_values else "mood_score_estimate"
            )
            base_mood = base_values[mood_key].value

            mood_adjustment = impact["mood_impact"] * impact_multiplier
            adjusted_mood = max(1, min(10, round(base_mood + mood_adjustment, 1)))

            if abs(mood_adjustment) > 0.1:
                adjusted[mood_key] = FieldMetadata(
                    value=adjusted_mood,
                    type=base_values[mood_key].type,
                    confidence=base_values[mood_key].confidence,
                    source=f"relationship_adjusted ({relationship_state.value})",
                    reasoning=(
                        f"Base {base_mood} adjusted by {mood_adjustment:+.1f} "
                        f"for {relationship_state.value} state (day {days_in_state})"
                    ),
                )

        # Apply sleep impact
        if "sleep_quality" in base_values:
            base_quality = base_values["sleep_quality"].value
            quality_adjustment = impact["sleep_impact"] * impact_multiplier
            adjusted_quality = max(
                1, min(10, round(base_quality + quality_adjustment, 1))
            )

            if abs(quality_adjustment) > 0.1:
                adjusted["sleep_quality"] = FieldMetadata(
                    value=adjusted_quality,
                    type=base_values["sleep_quality"].type,
                    confidence=base_values["sleep_quality"].confidence,
                    source=f"relationship_adjusted ({relationship_state.value})",
                    reasoning=(
                        f"Base {base_quality} adjusted by {quality_adjustment:+.1f} "
                        f"for {relationship_state.value} state"
                    ),
                )

        # Apply energy impact
        if "energy_level" in base_values:
            base_energy = base_values["energy_level"].value
            energy_adjustment = impact["energy_impact"] * impact_multiplier
            adjusted_energy = max(1, min(10, round(base_energy + energy_adjustment, 1)))

            if abs(energy_adjustment) > 0.1:
                adjusted["energy_level"] = FieldMetadata(
                    value=adjusted_energy,
                    type=base_values["energy_level"].type,
                    confidence=base_values["energy_level"].confidence,
                    source=f"relationship_adjusted ({relationship_state.value})",
                    reasoning=(
                        f"Base {base_energy} adjusted by {energy_adjustment:+.1f} "
                        f"for {relationship_state.value} state"
                    ),
                )

        # Add stress if not present
        if "stress_level" not in base_values:
            stress_value = 5.0 + (impact["stress_impact"] * impact_multiplier)
            adjusted["stress_level"] = FieldMetadata(
                value=max(1, min(10, round(stress_value, 1))),
                type=ExtractionType.INFERRED,
                confidence=0.70,
                source=f"relationship_impact ({relationship_state.value})",
                reasoning=(
                    f"Inferred stress level from {relationship_state.value} state "
                    f"(day {days_in_state})"
                ),
            )

        return adjusted

    @staticmethod
    def predict_recovery_timeline(
        state: RelationshipState, days_in_state: int
    ) -> Dict[str, Any]:
        """
        Predict when metrics might return to baseline
        """
        expected_duration = STATE_EXPECTED_DURATION.get(state)

        if not expected_duration:
            return {
                "recovery_estimate_days": None,
                "confidence": 0.0,
                "note": f"State {state.value} has indefinite duration",
            }

        remaining_days = max(0, expected_duration - days_in_state)

        # Recovery timeline depends on state
        recovery_multiplier = {
            RelationshipState.TENSION: 0.5,  # Quick recovery
            RelationshipState.CONFLICT: 1.0,
            RelationshipState.COLD_WAR: 2.0,  # Slow recovery
            RelationshipState.RECOVERY: 0.5,
            RelationshipState.RESOLVED: 0.2,
        }.get(state, 1.0)

        recovery_days = remaining_days + (expected_duration * recovery_multiplier)

        confidence = 0.60 if days_in_state <= expected_duration else 0.40

        return {
            "recovery_estimate_days": int(recovery_days),
            "confidence": confidence,
            "current_state": state.value,
            "days_in_state": days_in_state,
            "expected_state_duration": expected_duration,
        }
