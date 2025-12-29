"""
PLOS v2.0 - Pattern & Analysis Models
Models for user patterns, baselines, predictions, and analytics
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .extraction import AlertLevel, RelationshipState, Trajectory


# ============================================================================
# USER PATTERNS
# ============================================================================

class UserPattern(BaseModel):
    """User pattern/baseline"""
    id: Optional[UUID] = None
    user_id: UUID
    
    pattern_type: str  # "sleep_baseline", "mood_baseline", etc.
    value: Optional[float] = None
    std_dev: Optional[float] = None
    
    day_of_week: Optional[int] = Field(None, ge=0, le=6)  # 0=Monday, 6=Sunday
    
    sample_count: int = 0
    last_updated: datetime
    confidence: float = Field(ge=0, le=1)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserPatternCreate(BaseModel):
    """Create user pattern"""
    user_id: UUID
    pattern_type: str
    value: Optional[float] = None
    std_dev: Optional[float] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    sample_count: int = 0
    confidence: float = Field(default=0.5, ge=0, le=1)


# ============================================================================
# RELATIONSHIP HISTORY
# ============================================================================

class RelationshipEvent(BaseModel):
    """Relationship state change event"""
    id: Optional[UUID] = None
    user_id: UUID
    
    event_date: date
    state_before: Optional[RelationshipState] = None
    state_after: RelationshipState
    trigger: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=10)
    
    resolution_date: Optional[date] = None
    resolution_days: Optional[int] = None
    what_worked: Optional[str] = None
    
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RelationshipEventCreate(BaseModel):
    """Create relationship event"""
    user_id: UUID
    event_date: date
    state_before: Optional[RelationshipState] = None
    state_after: RelationshipState
    trigger: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=10)


# ============================================================================
# ACTIVITY IMPACT
# ============================================================================

class ActivityImpact(BaseModel):
    """Activity impact correlation"""
    id: Optional[UUID] = None
    user_id: UUID
    
    activity_type: str
    occurrence_count: int = 0
    
    # Average impacts
    avg_mood_impact: Optional[float] = None
    avg_energy_impact: Optional[float] = None
    avg_sleep_impact: Optional[float] = None
    avg_focus_impact: Optional[float] = None
    
    avg_duration_minutes: Optional[float] = None
    avg_satisfaction: Optional[float] = Field(None, ge=0, le=10)
    
    confidence: float = Field(ge=0, le=1)
    last_occurred: Optional[date] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ActivityImpactCreate(BaseModel):
    """Create activity impact"""
    user_id: UUID
    activity_type: str
    occurrence_count: int = 1


# ============================================================================
# SLEEP DEBT
# ============================================================================

class SleepDebtLog(BaseModel):
    """Sleep debt log entry"""
    id: Optional[UUID] = None
    user_id: UUID
    
    entry_date: date
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    baseline_hours: Optional[float] = None
    
    debt_this_day: Optional[float] = None
    debt_cumulative: Optional[float] = None
    recovery_sleep_needed: Optional[float] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SleepDebtLogCreate(BaseModel):
    """Create sleep debt log"""
    user_id: UUID
    entry_date: date
    sleep_hours: float = Field(ge=0, le=24)
    baseline_hours: float


# ============================================================================
# HEALTH ALERTS
# ============================================================================

class HealthAlert(BaseModel):
    """Health alert"""
    id: Optional[UUID] = None
    user_id: UUID
    
    alert_date: date
    alert_level: AlertLevel
    alert_type: str
    alert_text: str
    
    recommendations: List[str] = Field(default_factory=list)
    severity_score: Optional[float] = Field(None, ge=0, le=10)
    requires_immediate_action: bool = False
    
    user_acknowledged: bool = False
    user_response: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    
    resolved: bool = False
    resolved_date: Optional[date] = None
    resolution_notes: Optional[str] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class HealthAlertCreate(BaseModel):
    """Create health alert"""
    user_id: UUID
    alert_date: date
    alert_level: AlertLevel
    alert_type: str
    alert_text: str
    recommendations: List[str] = Field(default_factory=list)
    severity_score: float = Field(ge=0, le=10)
    requires_immediate_action: bool = False


# ============================================================================
# PREDICTIONS
# ============================================================================

class Prediction(BaseModel):
    """Prediction model"""
    id: Optional[UUID] = None
    user_id: UUID
    prediction_date: date
    
    # Next day predictions
    predicted_sleep: Optional[float] = None
    predicted_sleep_confidence: Optional[float] = Field(None, ge=0, le=1)
    predicted_mood: Optional[float] = None
    predicted_mood_confidence: Optional[float] = Field(None, ge=0, le=1)
    predicted_energy: Optional[float] = None
    predicted_energy_confidence: Optional[float] = Field(None, ge=0, le=1)
    
    # Week forecast
    week_forecast: Optional[Dict[str, Any]] = None
    
    # Activity recommendations
    activity_recommendations: Optional[Dict[str, Any]] = None
    
    # Metadata
    factors: Optional[Dict[str, Any]] = None
    model_version: str = "v2.0"
    
    created_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PredictionCreate(BaseModel):
    """Create prediction"""
    user_id: UUID
    prediction_date: date
    predicted_sleep: Optional[float] = None
    predicted_mood: Optional[float] = None
    predicted_energy: Optional[float] = None


# ============================================================================
# CONTEXT SUMMARY
# ============================================================================

class ContextSummary(BaseModel):
    """Complete user context summary"""
    user_id: UUID
    
    # Current state
    current_mood: Optional[float] = None
    current_energy: Optional[int] = None
    current_stress: Optional[int] = None
    
    # Sleep
    sleep_debt: float = 0
    sleep_debt_status: str = "normal"  # "normal", "moderate", "high", "critical"
    
    # Relationship
    relationship_state: Optional[RelationshipState] = None
    relationship_state_days: int = 0
    expected_resolution_date: Optional[date] = None
    
    # Trends (7-day)
    mood_trend: Trajectory = Trajectory.STABLE
    energy_trend: Trajectory = Trajectory.STABLE
    sleep_trend: Trajectory = Trajectory.STABLE
    
    avg_mood_7d: Optional[float] = None
    avg_energy_7d: Optional[float] = None
    avg_sleep_7d: Optional[float] = None
    
    # Baselines (30-day)
    baseline_mood: Optional[float] = None
    baseline_energy: Optional[float] = None
    baseline_sleep: Optional[float] = None
    
    # Health
    active_health_alerts: List[HealthAlert] = Field(default_factory=list)
    health_alert_count: int = 0
    
    # Activities
    top_mood_boosters: List[str] = Field(default_factory=list)
    top_energy_drainers: List[str] = Field(default_factory=list)
    
    # Predictions
    next_day_forecast: Optional[Prediction] = None
    week_forecast: Optional[Dict[str, Any]] = None
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    
    # Metadata
    last_updated: datetime
    data_quality: str = "good"  # "excellent", "good", "fair", "poor"


# ============================================================================
# PATTERN ANALYSIS
# ============================================================================

class PatternAnalysis(BaseModel):
    """Pattern analysis response"""
    user_id: UUID
    
    # Sleep patterns
    sleep_baseline: Optional[float] = None
    sleep_stddev: Optional[float] = None
    sleep_quality_pattern: Optional[Dict[str, Any]] = None
    
    # Mood patterns
    mood_baseline: Optional[float] = None
    mood_stddev: Optional[float] = None
    mood_volatility: Optional[float] = None
    
    # Day-of-week patterns
    day_of_week_patterns: Dict[str, Any] = Field(default_factory=dict)
    
    # Activity correlations
    activity_impacts: List[ActivityImpact] = Field(default_factory=list)
    
    # Relationship patterns
    conflict_frequency: Optional[float] = None  # per week
    avg_conflict_resolution_days: Optional[float] = None
    conflict_triggers: List[str] = Field(default_factory=list)
    
    # Health patterns
    sleep_debt_pattern: Optional[Dict[str, Any]] = None
    energy_pattern: Optional[Dict[str, Any]] = None
    
    # Metadata
    analyzed_at: datetime
    sample_size: int
    confidence: float = Field(ge=0, le=1)
