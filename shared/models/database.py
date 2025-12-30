"""
PLOS - Shared Database Models
SQLAlchemy ORM models used across services.
These models are in shared to avoid circular imports.
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# ============================================================================
# JOURNAL EXTRACTIONS
# ============================================================================


class JournalExtractionDB(Base):
    """Journal extraction database model"""

    __tablename__ = "journal_extractions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)

    # Raw input
    raw_entry = Column(Text, nullable=False)
    preprocessed_entry = Column(Text)

    # Quality
    overall_quality = Column(String(10))  # 'high', 'medium', 'low'
    extraction_time_ms = Column(Integer)
    gemini_model = Column(String(50))

    # Gaps
    has_gaps = Column(Boolean, default=False)
    gaps_resolved = Column(Boolean, default=False)

    # Extracted data (JSONB for flexible schema)
    extracted_data = Column(JSONB, default=dict)

    # State tracking
    relationship_state = Column(String(20))
    mood_trajectory = Column(String(20))
    sleep_debt_cumulative = Column(Float, default=0)

    created_at = Column(Date, server_default=func.now())
    updated_at = Column(Date, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "entry_date", name="uq_user_entry_date"),
    )


# ============================================================================
# USER PATTERNS
# ============================================================================


class UserPatternDB(Base):
    """User pattern/baseline cache"""

    __tablename__ = "user_patterns"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    pattern_type = Column(String(50), nullable=False, index=True)
    day_of_week = Column(Integer)  # 0=Monday, 6=Sunday, NULL for overall

    value = Column(Float)
    std_dev = Column(Float)

    sample_count = Column(Integer, default=0)
    confidence = Column(Float, default=0.5)

    extra_data = Column(JSONB, default=dict)

    last_updated = Column(Date, server_default=func.now())
    created_at = Column(Date, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id", "pattern_type", "day_of_week", name="uq_user_pattern_dow"
        ),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="valid_dow"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="valid_confidence"),
    )


# ============================================================================
# RELATIONSHIP HISTORY
# ============================================================================


class RelationshipHistoryDB(Base):
    """Relationship state change history"""

    __tablename__ = "relationship_history"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    event_date = Column(Date, nullable=False, index=True)
    state_before = Column(String(20))
    state_after = Column(String(20), nullable=False)

    trigger = Column(Text)
    severity = Column(Integer)

    resolution_date = Column(Date)
    resolution_days = Column(Integer)
    what_worked = Column(Text)

    notes = Column(Text)
    extra_data = Column(JSONB, default=dict)

    created_at = Column(Date, server_default=func.now())

    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 10", name="valid_severity"),
    )


# ============================================================================
# SLEEP DEBT LOG
# ============================================================================


class SleepDebtLogDB(Base):
    """Daily sleep debt tracking"""

    __tablename__ = "sleep_debt_log"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    entry_date = Column(Date, nullable=False, index=True)
    sleep_hours = Column(Float)
    baseline_hours = Column(Float)

    debt_this_day = Column(Float)
    debt_cumulative = Column(Float)
    recovery_sleep_needed = Column(Float)

    extra_data = Column(JSONB, default=dict)
    created_at = Column(Date, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "entry_date", name="uq_user_sleep_date"),
        CheckConstraint(
            "sleep_hours >= 0 AND sleep_hours <= 24", name="valid_sleep_hours"
        ),
    )


# ============================================================================
# ACTIVITY IMPACT
# ============================================================================


class ActivityImpactDB(Base):
    """Learned activity impact correlations"""

    __tablename__ = "activity_impact"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    activity_type = Column(String(100), nullable=False, index=True)
    occurrence_count = Column(Integer, default=0)

    avg_mood_impact = Column(Float)
    avg_energy_impact = Column(Float)
    avg_sleep_impact = Column(Float)
    avg_focus_impact = Column(Float)

    avg_duration_minutes = Column(Float)
    avg_satisfaction = Column(Float)

    confidence = Column(Float, default=0.5)
    last_occurred = Column(Date)

    extra_data = Column(JSONB, default=dict)
    last_updated = Column(Date, server_default=func.now())
    created_at = Column(Date, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "activity_type", name="uq_user_activity"),
        CheckConstraint(
            "avg_satisfaction >= 0 AND avg_satisfaction <= 10",
            name="valid_satisfaction",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="valid_impact_confidence"
        ),
    )


# ============================================================================
# HEALTH ALERTS
# ============================================================================


class HealthAlertDB(Base):
    """Health alerts from pattern analysis"""

    __tablename__ = "health_alerts"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    alert_date = Column(Date, nullable=False, index=True)
    alert_level = Column(String(20), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    alert_text = Column(Text, nullable=False)

    severity_score = Column(Float)
    requires_immediate_action = Column(Boolean, default=False)
    recommendations = Column(JSONB, default=list)

    user_acknowledged = Column(Boolean, default=False)
    user_response = Column(Text)
    acknowledged_at = Column(Date)

    resolved = Column(Boolean, default=False, index=True)
    resolved_date = Column(Date)
    resolution_notes = Column(Text)

    extra_data = Column(JSONB, default=dict)
    created_at = Column(Date, server_default=func.now())


# ============================================================================
# PREDICTIONS
# ============================================================================


class PredictionDB(Base):
    """AI-generated predictions"""

    __tablename__ = "predictions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    prediction_date = Column(Date, nullable=False, index=True)

    predicted_sleep = Column(Float)
    predicted_sleep_confidence = Column(Float)
    predicted_mood = Column(Float)
    predicted_mood_confidence = Column(Float)
    predicted_energy = Column(Float)
    predicted_energy_confidence = Column(Float)

    week_forecast = Column(JSONB)
    activity_recommendations = Column(JSONB)
    factors = Column(JSONB)

    model_version = Column(String(20), default="v2.0")
    valid_until = Column(Date)
    created_at = Column(Date, server_default=func.now())


# ============================================================================
# USER CONTEXT STATE
# ============================================================================


class UserContextStateDB(Base):
    """Real-time user context for fast retrieval"""

    __tablename__ = "user_context_state"

    user_id = Column(PGUUID(as_uuid=True), primary_key=True)

    current_mood_score = Column(Float)
    current_energy_level = Column(Integer)
    current_stress_level = Column(Integer)

    sleep_quality_avg_7d = Column(Float)
    productivity_score_avg_7d = Column(Float)

    active_goals_count = Column(Integer, default=0)
    pending_tasks_count = Column(Integer, default=0)
    completed_tasks_today = Column(Integer, default=0)

    context_data = Column(JSONB, default=dict)
    updated_at = Column(Date, server_default=func.now())
