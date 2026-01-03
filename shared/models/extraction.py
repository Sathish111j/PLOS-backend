"""
PLOS - Extraction Data Models
Comprehensive models for intelligent journal extraction with context
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

# ============================================================================
# ENUMS
# ============================================================================


class ExtractionType(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    ESTIMATED = "estimated"
    DEFAULT = "default"
    AI_EXTRACTED = "ai_extracted"


# ============================================================================
# FIELD METADATA
# ============================================================================


class FieldMetadata(BaseModel):
    """Metadata for each extracted field"""

    value: Optional[Any] = None
    type: ExtractionType
    confidence: float = Field(ge=0, le=1)
    source: str  # "direct mention", "calculation", "pattern_match", "baseline"
    user_said: Optional[str] = None  # Exact quote if explicit
    reasoning: Optional[str] = None  # Why inferred/estimated
    comparison_to_baseline: Optional[str] = None
    anomaly: bool = False
    health_concern: bool = False


# ============================================================================
# USER BASELINE
# ============================================================================


class UserBaseline(BaseModel):
    """User's baseline metrics (30-day)"""

    sleep_hours: float
    sleep_stddev: float
    mood_score: float
    mood_stddev: float
    energy_level: float
    energy_stddev: float
    stress_level: float
    stress_stddev: float

    sample_count: int
    last_updated: datetime

    # Day-of-week patterns
    day_of_week_patterns: Optional[Dict[str, Any]] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def calculate_quality_level(score: float) -> float:
    """Calculate quality level from score (simplified to just return the score)"""
    return score
