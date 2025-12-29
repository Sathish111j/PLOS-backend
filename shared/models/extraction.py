"""
PLOS - Extraction Data Models
Comprehensive models for intelligent journal extraction with context
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================================
# ENUMS
# ============================================================================


class RelationshipState(str, Enum):
    HARMONY = "HARMONY"
    TENSION = "TENSION"
    CONFLICT = "CONFLICT"
    COLD_WAR = "COLD_WAR"
    RECOVERY = "RECOVERY"
    RESOLVED = "RESOLVED"


class AlertLevel(str, Enum):
    INFO = "INFO"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExtractionType(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    ESTIMATED = "estimated"
    DEFAULT = "default"
    AI_EXTRACTED = "ai_extracted"


class QualityLevel(str, Enum):
    EXCELLENT = "EXCELLENT"  # 0.90+
    VERY_GOOD = "VERY_GOOD"  # 0.80-0.89
    GOOD = "GOOD"  # 0.70-0.79
    ACCEPTABLE = "ACCEPTABLE"  # 0.60-0.69
    POOR = "POOR"  # 0.50-0.59
    UNRELIABLE = "UNRELIABLE"  # <0.50
    HIGH = "HIGH"  # Alias for EXCELLENT/VERY_GOOD
    MEDIUM = "MEDIUM"  # Alias for GOOD/ACCEPTABLE
    LOW = "LOW"  # Alias for POOR/UNRELIABLE


class Trajectory(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"


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
# EXTRACTED DATA STRUCTURES
# ============================================================================


class MoodData(BaseModel):
    """Mood extraction"""

    score: Optional[float] = Field(None, ge=1, le=10)
    labels: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    type: ExtractionType


class HealthData(BaseModel):
    """Health metrics extraction"""

    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    sleep_quality: Optional[int] = Field(None, ge=1, le=10)
    energy_level: Optional[int] = Field(None, ge=1, le=10)
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    symptoms: List[str] = Field(default_factory=list)
    bedtime: Optional[str] = None
    waketime: Optional[str] = None
    disruptions: int = 0


class NutritionData(BaseModel):
    """Nutrition extraction"""

    meals: List[Dict[str, Any]] = Field(default_factory=list)
    meals_count: int = 0
    water_intake: Optional[float] = None  # liters
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class ExerciseData(BaseModel):
    """Exercise extraction"""

    activities: List[Dict[str, Any]] = Field(default_factory=list)
    total_duration_minutes: int = 0
    exercise_type: Optional[str] = None
    intensity: Optional[str] = None  # low, moderate, high
    calories_burned: Optional[int] = None
    distance_km: Optional[float] = None


class WorkData(BaseModel):
    """Work/productivity extraction"""

    work_hours: Optional[float] = None
    productivity_score: Optional[int] = Field(None, ge=1, le=10)
    focus_level: Optional[int] = Field(None, ge=1, le=10)
    tasks_completed: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)


class ActivityData(BaseModel):
    """General activities"""

    type: str
    duration_minutes: Optional[int] = None
    satisfaction: Optional[int] = Field(None, ge=1, le=10)
    notes: Optional[str] = None


class RelationshipData(BaseModel):
    """Relationship mentions"""

    conflict_mentioned: bool = False
    positive_interaction: bool = False
    trigger: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=10)
    resolution_status: Optional[str] = None


# ============================================================================
# EXTRACTION METADATA
# ============================================================================


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process"""

    quality_score: float = Field(ge=0, le=1)
    quality_level: QualityLevel
    overall_confidence: float = Field(ge=0, le=1)

    # What was used
    sources_used: List[str] = Field(default_factory=list)
    gemini_used: bool = False
    inference_used: bool = False
    baseline_used: bool = False

    # Processing time
    extraction_time_ms: Optional[int] = None
    gemini_time_ms: Optional[int] = None

    # Field statistics
    explicit_fields: int = 0
    inferred_fields: int = 0
    missing_fields: int = 0

    # Model version
    model_version: str = "v2.0"
    gemini_model: Optional[str] = None


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
# COMPLETE EXTRACTION
# ============================================================================


class ExtractedData(BaseModel):
    """Complete extracted data structure"""

    # Core metrics
    mood: Optional[MoodData] = None
    health: Optional[HealthData] = None
    nutrition: Optional[NutritionData] = None
    exercise: Optional[ExerciseData] = None
    work: Optional[WorkData] = None

    # Activities and relationships
    activities: List[ActivityData] = Field(default_factory=list)
    relationship: Optional[RelationshipData] = None

    # Habits tracking
    habits: List[Dict[str, Any]] = Field(default_factory=list)

    # Screen time
    screen_time: Optional[Dict[str, int]] = None  # app: minutes

    # Field-level metadata
    field_metadata: Dict[str, FieldMetadata] = Field(default_factory=dict)


# ============================================================================
# JOURNAL EXTRACTION (Main Model)
# ============================================================================


class JournalExtraction(BaseModel):
    """Complete journal extraction with intelligence"""

    id: Optional[UUID] = None
    user_id: UUID
    entry_date: date

    # Raw input
    raw_entry: str

    # Extracted data
    extracted_data: ExtractedData

    # Metadata
    extraction_metadata: ExtractionMetadata

    # Context at extraction time
    user_baseline: Optional[UserBaseline] = None
    day_of_week_pattern: Optional[Dict[str, Any]] = None

    # State tracking
    relationship_state: Optional[RelationshipState] = None
    relationship_state_day: int = 0
    sleep_debt_cumulative: float = 0
    fatigue_trajectory: Optional[Trajectory] = None
    mood_trajectory: Optional[Trajectory] = None

    # Detected issues
    anomalies_detected: List[str] = Field(default_factory=list)
    health_alerts: List[str] = Field(default_factory=list)
    clarification_needed: List[str] = Field(default_factory=list)

    # Temporal linkage
    previous_entry_id: Optional[UUID] = None
    conflict_resolution_status: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# CREATE/UPDATE MODELS
# ============================================================================


class JournalExtractionCreate(BaseModel):
    """Model for creating a new extraction"""

    user_id: UUID
    entry_date: date
    raw_entry: str = Field(min_length=1)


class JournalExtractionResponse(BaseModel):
    """API response model"""

    extraction: JournalExtraction
    recommendations: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    predictions: Optional[Dict[str, Any]] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def calculate_quality_level(score: float) -> QualityLevel:
    """Calculate quality level from score"""
    if score >= 0.90:
        return QualityLevel.EXCELLENT
    elif score >= 0.80:
        return QualityLevel.VERY_GOOD
    elif score >= 0.70:
        return QualityLevel.GOOD
    elif score >= 0.60:
        return QualityLevel.ACCEPTABLE
    elif score >= 0.50:
        return QualityLevel.POOR
    else:
        return QualityLevel.UNRELIABLE
