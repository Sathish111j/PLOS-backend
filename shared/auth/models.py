"""
PLOS Authentication Models
Pydantic models for authentication requests and responses
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """User registration request"""

    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(
        ..., min_length=3, max_length=100, description="Unique username"
    )
    password: str = Field(
        ..., min_length=8, max_length=128, description="Password (min 8 characters)"
    )
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    timezone: str = Field(default="UTC", description="User timezone")


class UserLogin(BaseModel):
    """User login request"""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class TokenData(BaseModel):
    """JWT token payload data"""

    user_id: UUID
    email: str
    username: str


class TokenResponse(BaseModel):
    """Authentication token response"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: "UserResponse" = Field(..., description="Authenticated user details")


class UserResponse(BaseModel):
    """User details response (no sensitive data)"""

    id: UUID = Field(..., description="User UUID")
    email: str = Field(..., description="User email")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="Full name")
    timezone: str = Field(..., description="User timezone")
    is_active: bool = Field(..., description="Is user active")
    is_verified: bool = Field(..., description="Is email verified")
    created_at: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    class Config:
        from_attributes = True


# Rebuild TokenResponse model now that UserResponse is defined
TokenResponse.model_rebuild()


class UserUpdate(BaseModel):
    """User profile update request"""

    full_name: Optional[str] = Field(None, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)


class PasswordChange(BaseModel):
    """Password change request"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password (min 8 chars)"
    )
