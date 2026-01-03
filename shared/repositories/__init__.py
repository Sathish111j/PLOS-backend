"""
PLOS Repository Package
Centralized data access layer
"""

from shared.repositories.base import (
    ActivityRepository,
    BaseRepository,
    JournalRepository,
    MetricsRepository,
    RepositoryFactory,
)

__all__ = [
    "BaseRepository",
    "JournalRepository",
    "ActivityRepository",
    "MetricsRepository",
    "RepositoryFactory",
]
