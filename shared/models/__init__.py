"""
PLOS Shared Library - Models Module
Pydantic models used across all microservices
"""

from .context import ContextUpdate, UserContext
from .extraction import (
    ExtractionType,
    FieldMetadata,
    UserBaseline,
)

__all__ = [
    # Context models (used by context-broker)
    "UserContext",
    "ContextUpdate",
    # Extraction models (used by journal-parser)
    "ExtractionType",
    "FieldMetadata",
    "UserBaseline",
]
