"""
PLOS Shared Utilities
Common utility functions and classes used across services
"""

from .config import Settings, get_settings
from .errors import AuthenticationError, NotFoundError, PLOSException, ValidationError
from .logger import get_logger
from .validation import (
    DateRangeValidation,
    EmailValidation,
    PaginationValidation,
    ScoreValidation,
    UserIdValidation,
    sanitize_tags,
    sanitize_text,
    validate_date_range,
    validate_date_string,
    validate_datetime_string,
    validate_email,
    validate_json_data,
    validate_password,
    validate_percentage,
    validate_positive_number,
    validate_score,
    validate_tags,
    validate_text_length,
    validate_uuid,
)

__all__ = [
    # Config
    "get_settings",
    "Settings",
    # Logging
    "get_logger",
    # Errors
    "PLOSException",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    # Validation Functions
    "validate_uuid",
    "validate_date_range",
    "validate_date_string",
    "validate_datetime_string",
    "validate_score",
    "validate_text_length",
    "validate_tags",
    "validate_json_data",
    "validate_positive_number",
    "validate_percentage",
    "validate_email",
    "validate_password",
    # Validation Schemas (Pydantic)
    "UserIdValidation",
    "DateRangeValidation",
    "PaginationValidation",
    "EmailValidation",
    "ScoreValidation",
    # Sanitization
    "sanitize_text",
    "sanitize_tags",
]
