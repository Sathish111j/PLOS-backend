"""
PLOS Shared Config
Backward-compatible access to unified configuration.
"""

from .unified_config import UnifiedSettings, get_unified_settings


class Settings(UnifiedSettings):
    """Legacy alias for unified settings."""


def get_settings() -> Settings:
    """Get cached settings instance (legacy alias)."""
    return get_unified_settings()
