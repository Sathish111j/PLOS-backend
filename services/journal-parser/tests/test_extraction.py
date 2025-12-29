"""
PLOS - Test Suite for Journal Parser Service
Comprehensive tests for all components
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from shared.models import (
    ExtractionType,
    FieldMetadata,
    RelationshipState,
    UserBaseline,
)

# ============================================================================
# PREPROCESSING TESTS
# ============================================================================


def test_spell_correction():
    """Test spell correction in preprocessing"""
    from ..src.preprocessing import Preprocessor

    preprocessor = Preprocessor()

    # Test common typos
    text = "I slept for 7 hurs and woked up at 8am. Fealing good today."
    corrected, _, _ = preprocessor.process(text)

    assert "hours" in corrected
    assert "woke" in corrected
    assert "feeling" in corrected or "Feeling" in corrected


def test_time_normalization():
    """Test time normalization"""
    from ..src.preprocessing import Preprocessor

    preprocessor = Preprocessor()

    text = "Went to bed at 11 pm and woke at 7 am"
    corrected, _, _ = preprocessor.process(text)

    assert "23:00" in corrected or "11:00 PM" in corrected
    assert "07:00" in corrected or "7:00 AM" in corrected


def test_explicit_sleep_extraction():
    """Test explicit sleep extraction"""
    from ..src.preprocessing import ExplicitExtractor

    extractor = ExplicitExtractor()

    # Direct mention
    text = "I slept for 7.5 hours last night"
    extractions = extractor.extract_all(text)

    assert "sleep_hours" in extractions
    assert extractions["sleep_hours"].value == 7.5
    assert extractions["sleep_hours"].confidence >= 0.90

    # Calculated from bedtime/waketime
    text2 = "Went to bed at 23:00 and woke up at 07:00"
    extractions2 = extractor.extract_all(text2)

    assert "sleep_hours" in extractions2
    assert extractions2["sleep_hours"].value == 8.0


# ============================================================================
# INFERENCE ENGINE TESTS
# ============================================================================


def test_energy_inference():
    """Test energy level inference from sleep and mood"""
    from ..src.inference_engine import InferenceEngine

    baseline = UserBaseline(
        sleep_hours=7.5,
        sleep_stddev=0.8,
        mood_score=7.0,
        mood_stddev=1.2,
        energy_level=6.5,
        stress_level=4.0,
    )

    engine = InferenceEngine(user_baseline=baseline)

    # Good sleep should increase energy
    explicit = {
        "sleep_hours": FieldMetadata(
            value=8.5,
            type=ExtractionType.EXPLICIT,
            confidence=0.95,
            source="explicit",
            reasoning="Direct mention",
        )
    }

    inferred = engine._tier2_inference(explicit, "")

    assert "energy_level" in inferred
    assert inferred["energy_level"].value >= 7  # Should be above baseline


def test_stress_inference():
    """Test stress inference from conflict and mood"""
    from services.journal_parser.src.inference_engine import InferenceEngine

    engine = InferenceEngine()

    explicit = {
        "conflict_mentioned": FieldMetadata(
            value=True,
            type=ExtractionType.EXPLICIT,
            confidence=0.95,
            source="explicit",
            reasoning="Conflict detected",
        ),
        "mood_score_estimate": FieldMetadata(
            value=3,
            type=ExtractionType.INFERRED,
            confidence=0.70,
            source="mood_indicators",
            reasoning="Negative mood",
        ),
    }

    inferred = engine._tier2_inference(explicit, "had a big fight, feeling stressed")

    assert "stress_level" in inferred
    assert inferred["stress_level"].value >= 7  # High stress


# ============================================================================
# RELATIONSHIP STATE MACHINE TESTS
# ============================================================================


def test_relationship_transition_harmony_to_conflict():
    """Test state transition from HARMONY to CONFLICT"""
    from ..src.relationship_state_machine import RelationshipStateMachine

    current_state = {
        "state": "HARMONY",
        "days_in_state": 10,
        "started_at": datetime.utcnow() - timedelta(days=10),
    }

    state_machine = RelationshipStateMachine(current_state)

    # Detect conflict
    text = "Had a big fight with my partner today. Really upset."
    new_state, trigger = state_machine.detect_transition(text, conflict_mentioned=True)

    assert new_state == RelationshipState.CONFLICT
    assert trigger is not None


def test_relationship_impact_on_mood():
    """Test relationship state impact on mood"""
    from ..src.relationship_state_machine import RelationshipImpactCalculator

    base_values = {
        "mood_score": FieldMetadata(
            value=7,
            type=ExtractionType.AI_EXTRACTED,
            confidence=0.70,
            source="gemini",
            reasoning="Inferred from text",
        )
    }

    calculator = RelationshipImpactCalculator()

    # Conflict should decrease mood
    adjusted = calculator.apply_relationship_impact(
        base_values=base_values,
        relationship_state=RelationshipState.CONFLICT,
        days_in_state=2,
    )

    assert "mood_score" in adjusted
    assert adjusted["mood_score"].value < 7  # Should be lower than base


# ============================================================================
# HEALTH MONITOR TESTS
# ============================================================================


def test_sleep_debt_alert():
    """Test sleep debt alert generation"""
    from ..src.health_monitor import HealthMonitor

    monitor = HealthMonitor()

    data = {
        "sleep_hours": FieldMetadata(
            value=4.5,
            type=ExtractionType.EXPLICIT,
            confidence=0.95,
            source="explicit",
            reasoning="Direct mention",
        )
    }

    alerts = monitor._check_sleep_health(data, sleep_debt=6.5)

    # Should have insomnia and high debt alerts
    alert_types = [a["type"] for a in alerts]
    assert "insomnia" in alert_types or "severe_insomnia" in alert_types
    assert "high_sleep_debt" in alert_types or "critical_sleep_debt" in alert_types


def test_mood_volatility_detection():
    """Test mood volatility detection"""
    from ..src.health_monitor import HealthMonitor

    baseline = UserBaseline(
        sleep_hours=7.5,
        sleep_stddev=0.8,
        mood_score=7.0,
        mood_stddev=1.0,
        energy_level=6.5,
        stress_level=4.0,
    )

    monitor = HealthMonitor(user_baseline=baseline)

    # Very low mood compared to baseline
    data = {
        "mood_score": FieldMetadata(
            value=2,
            type=ExtractionType.AI_EXTRACTED,
            confidence=0.75,
            source="gemini",
            reasoning="Low mood",
        )
    }

    alerts = monitor._check_mental_health(data)

    alert_types = [a["type"] for a in alerts]
    assert "severe_low_mood" in alert_types or "low_mood" in alert_types


# ============================================================================
# PREDICTION ENGINE TESTS
# ============================================================================


def test_sleep_prediction_with_debt():
    """Test sleep prediction accounts for sleep debt"""
    from ..src.prediction_engine import PredictionEngine

    baseline = UserBaseline(
        sleep_hours=7.5,
        sleep_stddev=0.8,
        mood_score=7.0,
        mood_stddev=1.2,
        energy_level=6.5,
        stress_level=4.0,
    )

    engine = PredictionEngine(user_baseline=baseline)

    # High sleep debt should predict catch-up sleep
    prediction = engine._predict_sleep(sleep_debt=6.0, relationship_state=None)

    assert (
        prediction["predicted_value"] > baseline.sleep_hours
    )  # Should predict more sleep
    assert "sleep_debt_adjustment" in prediction["factors"]
    assert prediction["factors"]["sleep_debt_adjustment"] > 0


def test_mood_prediction_with_conflict():
    """Test mood prediction with relationship conflict"""
    from ..src.prediction_engine import PredictionEngine

    baseline = UserBaseline(
        sleep_hours=7.5,
        sleep_stddev=0.8,
        mood_score=7.0,
        mood_stddev=1.2,
        energy_level=6.5,
        stress_level=4.0,
    )

    engine = PredictionEngine(user_baseline=baseline)

    relationship_state = {"state": "CONFLICT", "days_in_state": 2}

    prediction = engine._predict_mood(
        sleep_debt=0, relationship_state=relationship_state
    )

    assert (
        prediction["predicted_value"] < baseline.mood_score
    )  # Should predict lower mood
    assert prediction["factors"]["relationship_impact"] < 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_pipeline_mock():
    """Test full pipeline with mocked dependencies"""
    # This would require proper mocking of database and Kafka
    # Simplified test showing the flow

    from ..src.inference_engine import InferenceEngine
    from ..src.preprocessing import Preprocessor

    # Sample journal entry
    entry_text = """
    Slept for 6 hours last night. Woke up feeling tired.
    Had a disagreement with my partner in the morning.
    Worked for 8 hours but wasn't very productive.
    Played badminton for 45 minutes in the evening.
    Overall mood: 5/10
    """

    # Preprocessing
    preprocessor = Preprocessor()
    preprocessed, _, explicit = preprocessor.process(entry_text)

    # Should extract sleep and conflict
    assert "sleep_hours" in explicit
    assert explicit["sleep_hours"].value == 6.0

    # Inference
    engine = InferenceEngine()
    inferred = engine._tier2_inference(explicit, preprocessed)

    # Should infer energy and other fields
    assert len(inferred) > 0


# ============================================================================
# FIXTURE HELPERS
# ============================================================================


@pytest.fixture
def sample_baseline():
    """Sample user baseline"""
    return UserBaseline(
        sleep_hours=7.5,
        sleep_stddev=0.8,
        mood_score=7.0,
        mood_stddev=1.2,
        energy_level=6.5,
        stress_level=4.0,
    )


@pytest.fixture
def sample_user_id():
    """Sample user UUID"""
    return uuid4()


@pytest.fixture
def sample_journal_entry():
    """Sample journal entry text"""
    return """
    Went to bed at 11pm and woke up at 7am. Slept well, no interruptions.
    Felt energized in the morning. Had a productive work session for 6 hours.
    Played badminton for 1 hour in the evening - felt great!
    Overall good day, mood around 8/10.
    """


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
