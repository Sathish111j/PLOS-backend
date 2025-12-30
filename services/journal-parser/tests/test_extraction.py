"""
PLOS - Test Suite for Journal Parser Service
Tests for the actual extraction pipeline components.
"""

from uuid import uuid4

import pytest

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


def test_explicit_exercise_extraction():
    """Test explicit exercise extraction"""
    from ..src.preprocessing import ExplicitExtractor

    extractor = ExplicitExtractor()

    text = "Ran for 45 minutes this morning"
    extractions = extractor.extract_all(text)

    assert "exercise_done" in extractions
    assert extractions["exercise_done"].value is True


def test_conflict_detection():
    """Test conflict detection in text"""
    from ..src.preprocessing import ExplicitExtractor

    extractor = ExplicitExtractor()

    # Text with conflict
    text = "Had a big fight with my partner today. Really upset."
    extractions = extractor.extract_all(text)

    assert "conflict_mentioned" in extractions
    assert extractions["conflict_mentioned"].value is True

    # Text without conflict
    text2 = "Had a great day with family. Went for a walk."
    extractions2 = extractor.extract_all(text2)

    # conflict_mentioned should be False or not present
    if "conflict_mentioned" in extractions2:
        assert extractions2["conflict_mentioned"].value is False


# ============================================================================
# GENERALIZED EXTRACTION TESTS
# ============================================================================


def test_extraction_result_structure():
    """Test ExtractionResult data structure"""
    from ..src.generalized_extraction import (
        ExtractionResult,
        NormalizedActivity,
        TimeOfDay,
    )

    # Test basic structure
    result = ExtractionResult(
        activities=[],
        consumptions=[],
        sleep={},
        metrics={},
        social={},
        notes={},
        gaps=[],
    )

    assert result.quality == "medium"
    assert result.has_gaps is False
    assert len(result.activities) == 0

    # Test with activity
    activity = NormalizedActivity(
        raw_name="running",
        canonical_name="run",
        category="physical",
        duration_minutes=30,
        time_of_day=TimeOfDay.MORNING,
    )

    result2 = ExtractionResult(
        activities=[activity],
        consumptions=[],
        sleep={},
        metrics={},
        social={},
        notes={},
        gaps=[],
    )

    assert len(result2.activities) == 1
    assert result2.activities[0].canonical_name == "run"


def test_time_of_day_enum():
    """Test TimeOfDay enum values"""
    from ..src.generalized_extraction import TimeOfDay

    assert TimeOfDay.MORNING.value == "morning"
    assert TimeOfDay.AFTERNOON.value == "afternoon"
    assert TimeOfDay.EVENING.value == "evening"
    assert TimeOfDay.NIGHT.value == "night"


def test_gap_priority_enum():
    """Test GapPriority enum"""
    from ..src.generalized_extraction import GapPriority

    assert GapPriority.HIGH.value == 1
    assert GapPriority.MEDIUM.value == 2
    assert GapPriority.LOW.value == 3


# ============================================================================
# INTEGRATION TESTS (Mock-based)
# ============================================================================


@pytest.mark.asyncio
async def test_preprocessing_pipeline():
    """Test preprocessing stage of pipeline"""
    from ..src.preprocessing import Preprocessor

    preprocessor = Preprocessor()

    # Sample journal entry
    entry_text = """
    Slept for 6 hours last night. Woke up feeling tired.
    Had a disagreement with my partner in the morning.
    Worked for 8 hours but wasn't very productive.
    Played badminton for 45 minutes in the evening.
    Overall mood: 5/10
    """

    # Preprocessing
    preprocessed, metadata, explicit = preprocessor.process(entry_text)

    # Should extract explicit values
    assert "sleep_hours" in explicit
    assert explicit["sleep_hours"].value == 6.0

    # Should detect conflict
    assert "conflict_mentioned" in explicit
    assert explicit["conflict_mentioned"].value is True

    # Should detect exercise
    assert "exercise_done" in explicit


# ============================================================================
# FIXTURE HELPERS
# ============================================================================


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


@pytest.fixture
def sample_short_entry():
    """Short journal entry for gap detection testing"""
    return "Had coffee and went for a run."


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
