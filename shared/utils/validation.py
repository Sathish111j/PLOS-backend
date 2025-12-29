"""
PLOS Shared Validators
Common validation functions and schemas
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

# ============================================================================
# VALIDATION SCHEMAS
# ============================================================================


class UserIdValidation(BaseModel):
    """User ID validation"""

    user_id: UUID

    class Config:
        json_schema_extra = {
            "example": {"user_id": "123e4567-e89b-12d3-a456-426614174000"}
        }


class DateRangeValidation(BaseModel):
    """Date range validation"""

    start_date: date
    end_date: date

    @validator("end_date")
    def end_date_after_start_date(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    class Config:
        json_schema_extra = {
            "example": {"start_date": "2025-01-01", "end_date": "2025-01-31"}
        }


class PaginationValidation(BaseModel):
    """Pagination parameters validation"""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database queries"""
        return self.page_size

    class Config:
        json_schema_extra = {"example": {"page": 1, "page_size": 20}}


class EmailValidation(BaseModel):
    """Email validation"""

    email: str = Field(..., description="Email address")

    @validator("email")
    def valid_email(cls, v):
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    class Config:
        json_schema_extra = {"example": {"email": "user@example.com"}}


class ScoreValidation(BaseModel):
    """Score validation (1-10 scale)"""

    score: int = Field(..., ge=1, le=10, description="Score from 1 to 10")

    class Config:
        json_schema_extra = {"example": {"score": 7}}


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_uuid(value: str) -> UUID:
    """
    Validate and convert string to UUID

    Args:
        value: String to validate

    Returns:
        UUID object

    Raises:
        ValueError: If string is not a valid UUID
    """
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid UUID format: {value}")


def validate_date_string(value: str) -> date:
    """
    Validate and convert string to date

    Args:
        value: Date string (YYYY-MM-DD)

    Returns:
        date object

    Raises:
        ValueError: If string is not a valid date
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {value}. Expected YYYY-MM-DD")


def validate_datetime_string(value: str) -> datetime:
    """
    Validate and convert string to datetime

    Args:
        value: Datetime string (ISO 8601)

    Returns:
        datetime object

    Raises:
        ValueError: If string is not a valid datetime
    """
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Invalid datetime format: {value}. Expected ISO 8601")


def validate_score(value: int, min_score: int = 1, max_score: int = 10) -> int:
    """
    Validate score within range

    Args:
        value: Score value
        min_score: Minimum allowed score
        max_score: Maximum allowed score

    Returns:
        Validated score

    Raises:
        ValueError: If score is out of range
    """
    if not isinstance(value, int):
        raise ValueError(f"Score must be an integer, got {type(value)}")

    if value < min_score or value > max_score:
        raise ValueError(
            f"Score must be between {min_score} and {max_score}, got {value}"
        )

    return value


def validate_text_length(
    value: str, min_length: int = 1, max_length: int = 10000, field_name: str = "text"
) -> str:
    """
    Validate text length

    Args:
        value: Text to validate
        min_length: Minimum length
        max_length: Maximum length
        field_name: Field name for error messages

    Returns:
        Validated text

    Raises:
        ValueError: If text length is invalid
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    length = len(value)
    if length < min_length:
        raise ValueError(f"{field_name} must be at least {min_length} characters")
    if length > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")

    return value.strip()


def validate_tags(
    tags: List[str], max_tags: int = 10, max_tag_length: int = 50
) -> List[str]:
    """
    Validate tags list

    Args:
        tags: List of tags
        max_tags: Maximum number of tags
        max_tag_length: Maximum tag length

    Returns:
        Validated tags list

    Raises:
        ValueError: If tags are invalid
    """
    if not isinstance(tags, list):
        raise ValueError("Tags must be a list")

    if len(tags) > max_tags:
        raise ValueError(f"Maximum {max_tags} tags allowed, got {len(tags)}")

    validated_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("All tags must be strings")

        tag = tag.strip().lower()

        if len(tag) == 0:
            continue

        if len(tag) > max_tag_length:
            raise ValueError(f"Tag '{tag}' exceeds maximum length of {max_tag_length}")

        # Validate tag format (alphanumeric, hyphens, underscores)
        if not re.match(r"^[a-z0-9_-]+$", tag):
            raise ValueError(
                f"Tag '{tag}' contains invalid characters. Use only letters, numbers, hyphens, and underscores"
            )

        validated_tags.append(tag)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(validated_tags))


def validate_json_data(
    data: Any, required_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate JSON data structure

    Args:
        data: JSON data to validate
        required_fields: List of required field names

    Returns:
        Validated data dictionary

    Raises:
        ValueError: If data is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    return data


def validate_positive_number(value: float, field_name: str = "value") -> float:
    """
    Validate positive number

    Args:
        value: Number to validate
        field_name: Field name for error messages

    Returns:
        Validated number

    Raises:
        ValueError: If number is not positive
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a number")

    if value < 0:
        raise ValueError(f"{field_name} must be positive")

    return value


def validate_percentage(value: float, field_name: str = "percentage") -> float:
    """
    Validate percentage (0-100)

    Args:
        value: Percentage to validate
        field_name: Field name for error messages

    Returns:
        Validated percentage

    Raises:
        ValueError: If percentage is invalid
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a number")

    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")

    return value


# ============================================================================
# SANITIZATION FUNCTIONS
# ============================================================================


def sanitize_text(text: str, remove_html: bool = True) -> str:
    """
    Sanitize text input

    Args:
        text: Text to sanitize
        remove_html: Whether to remove HTML tags

    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return ""

    # Remove HTML tags
    if remove_html:
        text = re.sub(r"<[^>]+>", "", text)

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def sanitize_tags(tags: List[str]) -> List[str]:
    """
    Sanitize tags list

    Args:
        tags: Tags to sanitize

    Returns:
        Sanitized tags
    """
    if not isinstance(tags, list):
        return []

    sanitized = []
    for tag in tags:
        if isinstance(tag, str):
            tag = tag.strip().lower()
            # Remove special characters
            tag = re.sub(r"[^a-z0-9_-]", "", tag)
            if tag:
                sanitized.append(tag)

    return list(dict.fromkeys(sanitized))  # Remove duplicates


# ============================================================================
# DATE RANGE VALIDATION
# ============================================================================


def validate_date_range(
    start_date: Optional[date] = None, end_date: Optional[date] = None
) -> tuple[date, date]:
    """
    Validate date range

    Args:
        start_date: Start date (defaults to 30 days ago)
        end_date: End date (defaults to today)

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        ValueError: If end_date is before start_date
    """
    from datetime import timedelta

    today = date.today()

    if start_date is None:
        start_date = today - timedelta(days=30)

    if end_date is None:
        end_date = today

    if end_date < start_date:
        raise ValueError("end_date must be after start_date")

    return start_date, end_date


def validate_email(email: str) -> str:
    """
    Validate email format

    Args:
        email: Email address to validate

    Returns:
        Lowercase email

    Raises:
        ValueError: If invalid email format
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValueError(f"Invalid email format: {email}")
    return email.lower()


def validate_password(password: str) -> bool:
    """
    Validate password strength

    Args:
        password: Password to validate

    Returns:
        True if valid

    Raises:
        ValueError: If password doesn't meet requirements
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit")

    return True
