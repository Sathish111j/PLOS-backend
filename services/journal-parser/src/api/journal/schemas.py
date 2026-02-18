"""
PLOS - API Models for Journal Parser Service
Request and response models for journal endpoints.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProcessJournalRequest(BaseModel):
    """Request model for processing a journal entry"""

    entry_text: str = Field(
        ..., min_length=1, max_length=10000, description="Journal entry text"
    )
    entry_date: Optional[date] = Field(
        default=None, description="Entry date (defaults to today)"
    )
    detect_gaps: bool = Field(
        default=True,
        description="If True, detects ambiguous data and generates clarification questions. "
        "Set to False to skip gap detection and process as-is.",
    )
    require_complete: bool = Field(
        default=False,
        description="If True, requires all clarification questions to be answered before storing. "
        "Returns gaps without storing data until resolved.",
    )


class ActivityResponse(BaseModel):
    """Activity in extraction response"""

    name: str
    category: str
    duration_minutes: Optional[int] = None
    time_of_day: Optional[str] = None
    intensity: Optional[str] = None
    calories: Optional[int] = None


class ConsumptionResponse(BaseModel):
    """Consumption in extraction response"""

    name: str
    type: str
    meal_type: Optional[str] = None
    food_category: Optional[str] = None
    time_of_day: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class ClarificationQuestion(BaseModel):
    """A question for the user to clarify ambiguous data"""

    gap_id: Optional[str] = Field(
        default=None,
        description="Unique gap identifier for resolution (present when the entry is stored)",
    )
    question: str
    context: Optional[str] = None
    category: str
    priority: str | int
    suggestions: Optional[List[str]] = None


class LocationResponse(BaseModel):
    """Location in extraction response"""

    location_name: str
    location_type: Optional[str] = None
    time_of_day: Optional[str] = None
    duration_minutes: Optional[int] = None
    activity_context: Optional[str] = None


class HealthResponse(BaseModel):
    """Health symptom in extraction response"""

    symptom_type: str
    body_part: Optional[str] = None
    severity: Optional[int] = None
    duration_minutes: Optional[int] = None
    time_of_day: Optional[str] = None
    possible_cause: Optional[str] = None
    medication_taken: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Response model for extraction results"""

    entry_id: Optional[str] = None
    user_id: str
    entry_date: str
    quality: str
    stored: bool = True

    sleep: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    activities: List[ActivityResponse] = Field(default_factory=list)
    consumptions: List[ConsumptionResponse] = Field(default_factory=list)
    social: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None
    locations: List[LocationResponse] = Field(default_factory=list)
    health: List[HealthResponse] = Field(default_factory=list)

    has_gaps: bool = False
    clarification_questions: List[ClarificationQuestion] = Field(default_factory=list)

    processing_time_ms: int


class ResolveGapRequest(BaseModel):
    """Request to resolve a clarification gap"""

    gap_id: UUID = Field(..., description="Gap UUID to resolve")
    user_response: str = Field(..., description="User's answer to the question")


class ResolveParagraphRequest(BaseModel):
    """Request to resolve multiple gaps with a paragraph response"""

    entry_id: UUID = Field(..., description="Entry UUID with gaps to resolve")
    user_paragraph: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's natural language response answering clarification questions",
    )


class ResolveParagraphResponse(BaseModel):
    """Response after resolving gaps with paragraph"""

    entry_id: str
    resolved_count: int
    remaining_count: int
    remaining_questions: List[ClarificationQuestion] = Field(default_factory=list)
    updated_activities: List[ActivityResponse] = Field(default_factory=list)
    updated_consumptions: List[ConsumptionResponse] = Field(default_factory=list)
    prompt_for_remaining: Optional[str] = None


class ResolveGapResponse(BaseModel):
    """Response after resolving a gap"""

    status: str
    gap_id: str
    response: str


class PendingGap(BaseModel):
    """A pending gap that needs user clarification"""

    gap_id: str
    field: str
    question: str
    context: Optional[str] = None
    priority: str
    raw_value: Optional[str] = None
    created_at: str
    entry_date: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str
    service: str
    version: str
    timestamp: datetime
