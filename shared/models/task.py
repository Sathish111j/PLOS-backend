"""
PLOS Shared Models - Tasks and Goals
Task management and goal tracking models
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Goal(BaseModel):
    """Long-term goal"""

    id: Optional[UUID] = None
    user_id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    status: str = "active"  # active, completed, archived
    priority: int = Field(3, ge=1, le=5)
    target_date: Optional[datetime] = None
    progress_percentage: int = Field(0, ge=0, le=100)
    parent_goal_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Launch SaaS Product",
                "description": "Build and launch the MVP of my SaaS product",
                "category": "Business",
                "status": "active",
                "priority": 5,
                "target_date": "2025-06-30T00:00:00Z",
                "progress_percentage": 35,
            }
        }


class Task(BaseModel):
    """Individual task"""

    id: Optional[UUID] = None
    user_id: UUID
    goal_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    status: str = "todo"  # todo, in_progress, completed, blocked, cancelled
    priority: int = Field(3, ge=1, le=5)
    due_date: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    actual_duration_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "goal_id": "223e4567-e89b-12d3-a456-426614174000",
                "title": "Design database schema",
                "description": "Create PostgreSQL schema for user data",
                "status": "in_progress",
                "priority": 4,
                "due_date": "2025-01-20T17:00:00Z",
                "estimated_duration_minutes": 120,
                "tags": ["development", "database"],
            }
        }


class TaskCreate(BaseModel):
    """Create new task request"""

    goal_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: int = Field(3, ge=1, le=5)
    due_date: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    """Update task request"""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    due_date: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    actual_duration_minutes: Optional[int] = None
    tags: Optional[List[str]] = None


class GoalCreate(BaseModel):
    """Create new goal request"""

    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    priority: int = Field(3, ge=1, le=5)
    target_date: Optional[datetime] = None
    parent_goal_id: Optional[UUID] = None


class GoalUpdate(BaseModel):
    """Update goal request"""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    target_date: Optional[datetime] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
