"""
PLOS Shared Utilities
Common utility functions and classes used across services
"""

from .config import Settings, get_settings
from .errors import AuthenticationError, NotFoundError, PLOSException, ValidationError
from .logger import get_logger
from .unified_config import UnifiedSettings, get_unified_settings

__all__ = [
    # Config (unified - use this going forward)
    "get_unified_settings",
    "UnifiedSettings",
    # Config (legacy - for backward compatibility)
    "get_settings",
    "Settings",
    # Logging
    "get_logger",
    # Errors
    "PLOSException",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
]
