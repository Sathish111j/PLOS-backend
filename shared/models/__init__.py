"""
PLOS Shared Library - Models Module
Pydantic models used across all microservices
"""

from .context import ContextUpdate, UserContext
from .extraction import (
    ActivityData,
    AlertLevel,
    ExerciseData,
    ExtractedData,
    ExtractionMetadata,
    ExtractionType,
    FieldMetadata,
    HealthData,
    JournalExtraction,
    JournalExtractionCreate,
    JournalExtractionResponse,
    MoodData,
    NutritionData,
    QualityLevel,
    RelationshipData,
    RelationshipState,
    Trajectory,
    UserBaseline,
    WorkData,
    calculate_quality_level,
)
from .journal import JournalEntry, ParsedJournalEntry
from .knowledge import KnowledgeBucket, KnowledgeItem
from .patterns import (
    ActivityImpact,
    ActivityImpactCreate,
    ContextSummary,
    HealthAlert,
    HealthAlertCreate,
    PatternAnalysis,
    Prediction,
    PredictionCreate,
    RelationshipEvent,
    RelationshipEventCreate,
    SleepDebtLog,
    SleepDebtLogCreate,
    UserPattern,
    UserPatternCreate,
)
from .task import Goal, Task
from .user import User, UserCreate, UserUpdate

__all__ = [
    # Original models
    "UserContext",
    "ContextUpdate",
    "JournalEntry",
    "ParsedJournalEntry",
    "KnowledgeItem",
    "KnowledgeBucket",
    "Task",
    "Goal",
    "User",
    "UserCreate",
    "UserUpdate",
    # Extraction models
    "JournalExtraction",
    "JournalExtractionCreate",
    "JournalExtractionResponse",
    "ExtractedData",
    "ExtractionMetadata",
    "FieldMetadata",
    "MoodData",
    "HealthData",
    "NutritionData",
    "ExerciseData",
    "WorkData",
    "ActivityData",
    "RelationshipData",
    "UserBaseline",
    "calculate_quality_level",
    # Enums
    "RelationshipState",
    "AlertLevel",
    "ExtractionType",
    "QualityLevel",
    "Trajectory",
    # Pattern models
    "UserPattern",
    "UserPatternCreate",
    "RelationshipEvent",
    "RelationshipEventCreate",
    "ActivityImpact",
    "ActivityImpactCreate",
    "SleepDebtLog",
    "SleepDebtLogCreate",
    "HealthAlert",
    "HealthAlertCreate",
    "Prediction",
    "PredictionCreate",
    "ContextSummary",
    "PatternAnalysis",
]
