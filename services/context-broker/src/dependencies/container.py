"""Runtime container for context-broker dependencies."""

from contextlib import asynccontextmanager

from src.application.context_engine import ContextEngine
from src.infrastructure.cache_manager import CacheManager
from src.infrastructure.state_manager import StateManager

from shared.utils.logger import get_logger

logger = get_logger(__name__)

cache_manager = CacheManager()
state_manager = StateManager()
context_engine = ContextEngine(state_manager, cache_manager)


@asynccontextmanager
async def lifespan(app):
    """Initialize and shutdown core dependencies."""
    logger.info("Context Broker starting up...")
    await cache_manager.connect()
    await state_manager.connect()
    yield
    logger.info("Context Broker shutting down...")
    await cache_manager.close()
    await state_manager.close()
