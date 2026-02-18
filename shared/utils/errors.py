"""
PLOS Shared Errors & Response Models
Comprehensive error handling, codes, messages, and standardized responses
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# ERROR CODES
# ============================================================================


class ErrorCode(str, Enum):
    """Standardized error codes across all services"""

    # General Errors (1000-1099)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # Database Errors (1100-1199)
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    DB_QUERY_ERROR = "DB_QUERY_ERROR"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"
    DB_DUPLICATE_ENTRY = "DB_DUPLICATE_ENTRY"

    # Cache Errors (1200-1299)
    CACHE_CONNECTION_ERROR = "CACHE_CONNECTION_ERROR"
    CACHE_WRITE_ERROR = "CACHE_WRITE_ERROR"
    CACHE_READ_ERROR = "CACHE_READ_ERROR"

    # Kafka Errors (1300-1399)
    KAFKA_CONNECTION_ERROR = "KAFKA_CONNECTION_ERROR"
    KAFKA_PUBLISH_ERROR = "KAFKA_PUBLISH_ERROR"
    KAFKA_CONSUME_ERROR = "KAFKA_CONSUME_ERROR"

    # AI/Gemini Errors (1400-1499)
    GEMINI_API_ERROR = "GEMINI_API_ERROR"
    GEMINI_RATE_LIMIT = "GEMINI_RATE_LIMIT"
    GEMINI_INVALID_RESPONSE = "GEMINI_INVALID_RESPONSE"
    GEMINI_QUOTA_EXCEEDED = "GEMINI_QUOTA_EXCEEDED"

    # Vector DB Errors (1500-1599)
    VECTOR_DB_CONNECTION_ERROR = "VECTOR_DB_CONNECTION_ERROR"
    VECTOR_DB_SEARCH_ERROR = "VECTOR_DB_SEARCH_ERROR"

    # Business Logic Errors (2000-2999)
    USER_NOT_FOUND = "USER_NOT_FOUND"
    JOURNAL_NOT_FOUND = "JOURNAL_NOT_FOUND"
    CONTEXT_NOT_FOUND = "CONTEXT_NOT_FOUND"
    PARSING_FAILED = "PARSING_FAILED"


# ============================================================================
# ERROR MESSAGES
# ============================================================================

ERROR_MESSAGES = {
    ErrorCode.INTERNAL_ERROR: "An internal server error occurred. Please try again later.",
    ErrorCode.VALIDATION_ERROR: "The provided data is invalid. Please check your input.",
    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.UNAUTHORIZED: "Authentication required. Please provide valid credentials.",
    ErrorCode.FORBIDDEN: "You don't have permission to access this resource.",
    ErrorCode.RATE_LIMIT_EXCEEDED: "Too many requests. Please slow down.",
    ErrorCode.SERVICE_UNAVAILABLE: "Service temporarily unavailable. Please try again later.",
    ErrorCode.DB_CONNECTION_ERROR: "Database connection failed. Please try again.",
    ErrorCode.CACHE_CONNECTION_ERROR: "Cache service unavailable. Falling back to database.",
    ErrorCode.KAFKA_CONNECTION_ERROR: "Message broker unavailable. Request queued.",
    ErrorCode.GEMINI_API_ERROR: "AI service error. Please try again.",
    ErrorCode.GEMINI_RATE_LIMIT: "AI service rate limit reached. Please wait a moment.",
    ErrorCode.USER_NOT_FOUND: "User not found. Please check the user ID.",
    ErrorCode.JOURNAL_NOT_FOUND: "Journal entry not found.",
    ErrorCode.PARSING_FAILED: "Failed to parse journal entry. Please check the content.",
}


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information"""

    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response"""

    success: bool = False
    error_code: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standardized success response"""

    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# ERROR RESPONSE HELPERS
# ============================================================================


def normalize_error_details(details: Optional[Any]) -> Optional[List[ErrorDetail]]:
    """Normalize error details into a list of ErrorDetail items."""
    if details is None:
        return None
    if isinstance(details, list):
        return details
    if isinstance(details, ErrorDetail):
        return [details]
    if isinstance(details, dict):
        message = details.get("message") or str(details)
        field = details.get("field")
        return [ErrorDetail(field=field, message=message)]
    return [ErrorDetail(message=str(details))]


def build_error_response(exc: "PLOSException") -> ErrorResponse:
    """Create an ErrorResponse from a PLOSException."""
    return ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=normalize_error_details(exc.details),
    )


# ============================================================================
# EXCEPTION CLASSES
# ============================================================================


class PLOSException(Exception):
    """Base exception for PLOS application"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[ErrorCode] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code or ErrorCode.INTERNAL_ERROR
        super().__init__(self.message)


class ValidationError(PLOSException):
    """Validation error (400)"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(
            message,
            status_code=400,
            details=error_details,
            error_code=ErrorCode.VALIDATION_ERROR,
        )


class NotFoundError(PLOSException):
    """Resource not found error (404)"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message, status_code=404, details=details, error_code=ErrorCode.NOT_FOUND
        )


class AuthenticationError(PLOSException):
    """Authentication error (401)"""

    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message, status_code=401, details=details, error_code=ErrorCode.UNAUTHORIZED
        )


class AuthorizationError(PLOSException):
    """Authorization error (403)"""

    def __init__(
        self,
        message: str = "Permission denied",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message, status_code=403, details=details, error_code=ErrorCode.FORBIDDEN
        )


class ConflictError(PLOSException):
    """Resource conflict error (409)"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=409, details=details)


class RateLimitError(PLOSException):
    """Rate limit exceeded error (429)"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            status_code=429,
            details=details,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
        )


class ExternalServiceError(PLOSException):
    """External service error (502)"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=502, details=details)


class DatabaseError(PLOSException):
    """Database-related errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            status_code=500,
            details=details,
            error_code=ErrorCode.DB_QUERY_ERROR,
        )


class GeminiAPIError(PLOSException):
    """Gemini API errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            status_code=500,
            details=details,
            error_code=ErrorCode.GEMINI_API_ERROR,
        )


# ============================================================================
# RETRY STRATEGY
# ============================================================================


class RetryStrategy:
    """Retry strategy configuration"""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for retry attempt"""
        delay = min(
            self.initial_delay * (self.exponential_base**retry_count), self.max_delay
        )
        return delay
