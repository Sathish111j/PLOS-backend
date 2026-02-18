"""Pydantic models for journal reporting endpoints."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DailyOverview(BaseModel):
    """Daily metrics for reporting."""

    date: date
    calories_in: Optional[float] = None
    water_ml: Optional[float] = None
    steps: Optional[int] = None
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[float] = None
    mood_score: Optional[float] = None
    activity_minutes: Optional[int] = None
    activity_calories: Optional[int] = None


class OverviewSummary(BaseModel):
    """Aggregated summary for a date range."""

    total_calories_in: Optional[float] = None
    avg_sleep_hours: Optional[float] = None
    avg_sleep_quality: Optional[float] = None
    avg_mood_score: Optional[float] = None
    total_water_ml: Optional[float] = None
    total_steps: Optional[int] = None
    avg_steps: Optional[float] = None
    total_activity_minutes: Optional[int] = None
    total_activity_calories: Optional[int] = None


class ContextSnapshot(BaseModel):
    """Latest context snapshot from context-broker state."""

    current_mood_score: Optional[int] = None
    current_energy_level: Optional[int] = None
    current_stress_level: Optional[int] = None
    sleep_quality_avg_7d: Optional[float] = None
    productivity_score_avg_7d: Optional[float] = None
    active_goals_count: Optional[int] = None
    pending_tasks_count: Optional[int] = None
    completed_tasks_today: Optional[int] = None
    context_data: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class WeeklyOverviewResponse(BaseModel):
    """Combined weekly overview response."""

    user_id: str
    start_date: date
    end_date: date
    daily: List[DailyOverview]
    summary: OverviewSummary
    context_snapshot: Optional[ContextSnapshot] = None


class MetricSeriesPoint(BaseModel):
    """Single metric value per day."""

    date: date
    value: Optional[float] = None


class MetricSummary(BaseModel):
    """Summary for a single metric series."""

    total: Optional[float] = None
    average: Optional[float] = None
    unit: Optional[str] = None


class WeeklyMetricResponse(BaseModel):
    """Weekly metric response for single-metric endpoints."""

    user_id: str
    metric: str
    unit: str
    start_date: date
    end_date: date
    series: List[MetricSeriesPoint]
    summary: MetricSummary


class ActivityDaily(BaseModel):
    """Daily activity metrics."""

    date: date
    minutes: Optional[int] = None
    calories: Optional[int] = None


class WeeklyActivityResponse(BaseModel):
    """Weekly activity response."""

    user_id: str
    start_date: date
    end_date: date
    daily: List[ActivityDaily]
    total_minutes: Optional[int] = None
    total_calories: Optional[int] = None


class NutritionDaily(BaseModel):
    """Daily nutrition totals."""

    date: date
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class NutritionSummary(BaseModel):
    """Aggregate nutrition totals."""

    total_calories: Optional[float] = None
    total_protein_g: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    avg_calories: Optional[float] = None
    avg_protein_g: Optional[float] = None
    avg_carbs_g: Optional[float] = None
    avg_fat_g: Optional[float] = None


class WeeklyNutritionResponse(BaseModel):
    """Weekly nutrition response."""

    user_id: str
    start_date: date
    end_date: date
    daily: List[NutritionDaily]
    summary: NutritionSummary


class SocialDaily(BaseModel):
    """Daily social interactions count."""

    date: date
    interactions: Optional[int] = None


class SocialTopPerson(BaseModel):
    """Top interaction person summary."""

    person: str
    interactions: int


class SocialSummary(BaseModel):
    """Aggregate social summary."""

    total_interactions: int
    by_relationship_category: Dict[str, int]
    top_people: List[SocialTopPerson]


class WeeklySocialResponse(BaseModel):
    """Weekly social response."""

    user_id: str
    start_date: date
    end_date: date
    daily: List[SocialDaily]
    summary: SocialSummary


class HealthDaily(BaseModel):
    """Daily health symptom count."""

    date: date
    symptoms: Optional[int] = None


class HealthTopSymptom(BaseModel):
    """Top symptom summary."""

    symptom: str
    count: int


class HealthSummary(BaseModel):
    """Aggregate health summary."""

    total_symptoms: int
    top_symptoms: List[HealthTopSymptom]


class WeeklyHealthResponse(BaseModel):
    """Weekly health response."""

    user_id: str
    start_date: date
    end_date: date
    daily: List[HealthDaily]
    summary: HealthSummary


class WorkDaily(BaseModel):
    """Daily work summary."""

    date: date
    minutes: Optional[int] = None
    productivity_avg: Optional[float] = None


class WorkSummary(BaseModel):
    """Aggregate work summary."""

    total_minutes: Optional[int] = None
    avg_productivity: Optional[float] = None


class WeeklyWorkResponse(BaseModel):
    """Weekly work response."""

    user_id: str
    start_date: date
    end_date: date
    daily: List[WorkDaily]
    summary: WorkSummary


class TimeSeriesBucketPoint(BaseModel):
    """Bucketed time-series analytics point."""

    bucket_time: datetime
    calories_in: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[float] = None
    mood_score: Optional[float] = None
    water_ml: Optional[float] = None
    steps: Optional[int] = None
    activity_minutes: Optional[int] = None
    activity_calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class TimeSeriesOverviewResponse(BaseModel):
    """Bucketed time-series overview response."""

    user_id: str
    start_date: date
    end_date: date
    bucket: str
    points: List[TimeSeriesBucketPoint]
