"""
PLOS Shared Models - User Context
Real-time user state and context models
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """Complete user context - single source of truth"""

    user_id: UUID

    # Current State
    current_mood_score: Optional[int] = Field(None, ge=1, le=10)
    current_energy_level: Optional[int] = Field(None, ge=1, le=10)
    current_stress_level: Optional[int] = Field(None, ge=1, le=10)

    # Recent Averages (7-day rolling)
    sleep_quality_avg_7d: Optional[float] = None
    productivity_score_avg_7d: Optional[float] = None

    # Task & Goal Counts
    active_goals_count: int = 0
    pending_tasks_count: int = 0
    completed_tasks_today: int = 0

    # Extended Context (JSON)
    context_data: Dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "current_mood_score": 7,
                "current_energy_level": 6,
                "current_stress_level": 4,
                "sleep_quality_avg_7d": 7.2,
                "productivity_score_avg_7d": 6.8,
                "active_goals_count": 5,
                "pending_tasks_count": 12,
                "completed_tasks_today": 3,
                "context_data": {
                    "last_journal_entry": "2025-01-15",
                    "current_habits_streak": 7,
                },
                "updated_at": "2025-01-15T10:30:00Z",
            }
        }


class ContextUpdate(BaseModel):
    """Update event for user context"""

    user_id: UUID
    update_type: str  # mood, health, task, goal, etc.
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "update_type": "mood",
                "data": {"mood_score": 7, "mood_labels": ["happy", "energetic"]},
                "timestamp": "2025-01-15T10:30:00Z",
            }
        }
