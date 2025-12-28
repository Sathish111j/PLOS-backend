"""
PLOS Shared Models - Journal Entry
Journal and parsing models
"""

from datetime import datetime, date
from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class JournalEntry(BaseModel):
    """Raw journal entry from user"""

    id: Optional[UUID] = None
    user_id: UUID
    entry_date: date
    raw_text: str = Field(..., min_length=1)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "entry_date": "2025-01-15",
                "raw_text": "Woke up feeling great today! Had 8 hours of sleep. Went for a 5km run in the morning. Feeling energized and focused. Working on the new project, made good progress. Had a healthy lunch - chicken salad. Feeling productive, around 8/10.",
            }
        }


class ParsedJournalEntry(BaseModel):
    """AI-parsed structured data from journal entry"""

    journal_entry_id: UUID
    user_id: UUID
    entry_date: date

    # Extracted structured data
    mood: Optional[Dict[str, Any]] = None
    health: Optional[Dict[str, Any]] = None
    nutrition: Optional[Dict[str, Any]] = None
    exercise: Optional[Dict[str, Any]] = None
    work: Optional[Dict[str, Any]] = None
    habits: Optional[List[Dict[str, Any]]] = None

    # Metadata
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    gaps_detected: List[str] = Field(default_factory=list)
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "journal_entry_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "entry_date": "2025-01-15",
                "mood": {"score": 8, "labels": ["energized", "focused", "productive"]},
                "health": {"sleep_hours": 8, "sleep_quality": 9, "energy_level": 8},
                "exercise": {
                    "type": "running",
                    "duration_minutes": 30,
                    "distance_km": 5.0,
                    "intensity": "moderate",
                },
                "nutrition": {
                    "meals": [
                        {
                            "type": "lunch",
                            "items": ["chicken salad"],
                            "notes": "healthy",
                        }
                    ]
                },
                "work": {"productivity_score": 8, "tasks": ["new project progress"]},
                "confidence_score": 0.95,
                "gaps_detected": [],
                "parsed_at": "2025-01-15T10:30:00Z",
            }
        }


class JournalParseRequest(BaseModel):
    """Request to parse a journal entry"""

    journal_entry_id: UUID
    user_id: UUID
    entry_date: date
    raw_text: str
    user_context: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "journal_entry_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "entry_date": "2025-01-15",
                "raw_text": "Woke up feeling great today...",
                "user_context": {
                    "timezone": "America/New_York",
                    "usual_wake_time": "07:00",
                },
            }
        }


class GapDetection(BaseModel):
    """Detected gaps in journal entry"""

    journal_entry_id: UUID
    gaps: List[str]
    suggestions: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "journal_entry_id": "123e4567-e89b-12d3-a456-426614174000",
                "gaps": ["nutrition", "water_intake"],
                "suggestions": [
                    "Did you track your meals today?",
                    "How much water did you drink?",
                ],
                "timestamp": "2025-01-15T10:30:00Z",
            }
        }
