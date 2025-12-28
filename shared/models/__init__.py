"""
PLOS Shared Library - Models Module
Pydantic models used across all microservices
"""

from .context import UserContext, ContextUpdate
from .journal import JournalEntry, ParsedJournalEntry
from .knowledge import KnowledgeItem, KnowledgeBucket
from .task import Task, Goal
from .user import User, UserCreate, UserUpdate

__all__ = [
    'UserContext',
    'ContextUpdate',
    'JournalEntry',
    'ParsedJournalEntry',
    'KnowledgeItem',
    'KnowledgeBucket',
    'Task',
    'Goal',
    'User',
    'UserCreate',
    'UserUpdate',
]
