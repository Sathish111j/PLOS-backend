"""
PLOS Shared Models - User
User account models
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User account model"""

    id: UUID
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = None
    timezone: str = "UTC"
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_verified: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "username": "johndoe",
                "full_name": "John Doe",
                "timezone": "America/New_York",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-15T10:30:00Z",
                "last_login": "2025-01-15T09:00:00Z",
                "is_active": True,
                "is_verified": True,
            }
        }


class UserCreate(BaseModel):
    """Create new user request"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    timezone: str = "UTC"

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "securepassword123",
                "full_name": "New User",
                "timezone": "America/Los_Angeles",
            }
        }


class UserUpdate(BaseModel):
    """Update user request"""

    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = None
    timezone: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {"full_name": "John Updated Doe", "timezone": "Europe/London"}
        }


class UserLogin(BaseModel):
    """User login request"""

    username: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {"username": "johndoe", "password": "securepassword123"}
        }


class Token(BaseModel):
    """JWT token response"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        }


class TokenData(BaseModel):
    """Token payload data"""

    user_id: UUID
    username: str
    exp: Optional[datetime] = None
