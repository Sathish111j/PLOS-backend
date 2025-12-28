"""
PLOS Shared Models - Knowledge Management
Knowledge items and buckets
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """A single knowledge item/note"""

    id: Optional[UUID] = None
    user_id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    content_type: str = "text"  # text, markdown, pdf, image
    bucket_id: Optional[UUID] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Python FastAPI Best Practices",
                "content": "Always use async/await for I/O operations...",
                "content_type": "markdown",
                "bucket_id": "223e4567-e89b-12d3-a456-426614174000",
                "tags": ["programming", "python", "fastapi"],
                "metadata": {"source": "documentation", "importance": "high"},
            }
        }


class KnowledgeBucket(BaseModel):
    """Organizational bucket for knowledge items"""

    id: Optional[UUID] = None
    user_id: UUID
    bucket_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    created_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "bucket_name": "Programming",
                "description": "All programming-related notes and resources",
                "color": "#3498db",
            }
        }


class KnowledgeSearch(BaseModel):
    """Semantic search request for knowledge base"""

    user_id: UUID
    query: str = Field(..., min_length=1)
    bucket_ids: Optional[List[UUID]] = None
    tags: Optional[List[str]] = None
    limit: int = Field(10, ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "query": "how to optimize database queries",
                "tags": ["programming", "database"],
                "limit": 10,
            }
        }


class KnowledgeSearchResult(BaseModel):
    """Search result with relevance score"""

    knowledge_item: KnowledgeItem
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    highlights: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "knowledge_item": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "title": "Database Query Optimization",
                    "content": "Use indexes for frequently queried columns...",
                    "tags": ["database", "performance"],
                },
                "relevance_score": 0.92,
                "highlights": [
                    "Use indexes for frequently queried columns",
                    "Avoid SELECT * in production",
                ],
            }
        }
