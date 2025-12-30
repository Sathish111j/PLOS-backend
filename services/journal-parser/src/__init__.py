"""
PLOS - Journal Parser Service
Intelligent journal entry parsing with context-aware extraction
"""

__version__ = "2.0.0"

from .api import router
from .orchestrator import JournalParserOrchestrator

__all__ = [
    "router",
    "JournalParserOrchestrator",
]
