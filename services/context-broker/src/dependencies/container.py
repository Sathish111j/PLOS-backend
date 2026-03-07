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
    logger.info("[STARTUP] Context Broker starting up...")
    logger.info("[STARTUP] Connecting to Redis cache...")
    await cache_manager.connect()
    logger.info("[STARTUP] Redis cache connected")
    logger.info("[STARTUP] Connecting to PostgreSQL state manager...")
    await state_manager.connect()
    logger.info("[STARTUP] PostgreSQL state manager connected")
    logger.info("[STARTUP] Context Broker fully initialized and ready")
    yield
    logger.info("[SHUTDOWN] Context Broker shutting down...")
    await cache_manager.close()
    await state_manager.close()
    logger.info("[SHUTDOWN] Context Broker shutdown complete")
