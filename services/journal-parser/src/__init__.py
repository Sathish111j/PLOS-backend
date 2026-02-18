"""
PLOS - Journal Parser Service
Intelligent journal entry parsing with context-aware extraction
"""

__version__ = "2.0.0"

from api.journal.router import router
from application.orchestrator import JournalParserOrchestrator

__all__ = [
    "router",
    "JournalParserOrchestrator",
]
