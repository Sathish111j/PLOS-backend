"""
PLOS Shared Validators
Common validation functions
"""

import re
from datetime import date, datetime
from typing import Optional, Tuple
from uuid import UUID

from .errors import ValidationError


def validate_uuid(value: str) -> UUID:
    """
    Validate and convert string to UUID

    Args:
        value: String to validate

    Returns:
        UUID object

    Raises:
        ValidationError: If invalid UUID format
    """
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise ValidationError(f"Invalid UUID format: {value}")


def validate_email(email: str) -> bool:
    """
    Validate email format

    Args:
        email: Email address to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If invalid email format
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    return True


def validate_date_range(
    start_date: Optional[date] = None, end_date: Optional[date] = None
) -> Tuple[date, date]:
    """
    Validate date range

    Args:
        start_date: Start date (defaults to 30 days ago)
        end_date: End date (defaults to today)

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        ValidationError: If end_date is before start_date
    """
    today = date.today()

    if start_date is None:
        from datetime import timedelta

        start_date = today - timedelta(days=30)

    if end_date is None:
        end_date = today

    if end_date < start_date:
        raise ValidationError("end_date must be after start_date")

    return start_date, end_date


def validate_score(
    score: int, min_val: int = 1, max_val: int = 10, field_name: str = "score"
) -> int:
    """
    Validate score is within range

    Args:
        score: Score value
        min_val: Minimum value
        max_val: Maximum value
        field_name: Field name for error message

    Returns:
        Validated score

    Raises:
        ValidationError: If score out of range
    """
    if not isinstance(score, int):
        raise ValidationError(f"{field_name} must be an integer")

    if score < min_val or score > max_val:
        raise ValidationError(f"{field_name} must be between {min_val} and {max_val}")

    return score


def validate_password(password: str) -> bool:
    """
    Validate password strength

    Args:
        password: Password to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If password doesn't meet requirements
    """
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter")

    if not re.search(r"[0-9]", password):
        raise ValidationError("Password must contain at least one digit")

    return True
