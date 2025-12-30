"""
PLOS - Dependency Injection for Journal Parser Service
Production-ready FastAPI dependencies
"""

from typing import AsyncGenerator

from db_pool import get_global_pool
from sqlalchemy.ext.asyncio import AsyncSession

from shared.gemini.client import ResilientGeminiClient
from shared.kafka.producer import KafkaProducerService
from shared.utils.config import get_settings
from shared.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ============================================================================
# GLOBAL INSTANCES (initialized at startup)
# ============================================================================

_gemini_client: ResilientGeminiClient = None
_kafka_producer: KafkaProducerService = None


async def initialize_dependencies() -> None:
    """Initialize global dependencies at startup"""
    global _gemini_client, _kafka_producer

    logger.info("Initializing global dependencies...")

    # Initialize Gemini client
    _gemini_client = ResilientGeminiClient()

    # Initialize Kafka producer
    _kafka_producer = KafkaProducerService(
        bootstrap_servers=settings.kafka_bootstrap_servers
    )
    await _kafka_producer.start()

    logger.info("Dependencies initialized successfully")


async def shutdown_dependencies() -> None:
    """Shutdown global dependencies"""
    global _kafka_producer

    logger.info("Shutting down dependencies...")

    if _kafka_producer:
        await _kafka_producer.stop()

    logger.info("Dependencies shutdown complete")


# ============================================================================
# FASTAPI DEPENDENCY FUNCTIONS
# ============================================================================


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session from connection pool

    Usage:
    ```python
    @app.get("/endpoint")
    async def endpoint(db: AsyncSession = Depends(get_db_session)):
        result = await db.execute(query)
    ```
    """
    pool = get_global_pool()

    async with pool.get_session() as session:
        yield session


async def get_kafka_producer() -> KafkaProducerService:
    """
    Get Kafka producer instance

    Returns: Singleton KafkaProducerService instance
    """
    if _kafka_producer is None:
        raise RuntimeError(
            "Kafka producer not initialized. Call initialize_dependencies() first."
        )

    return _kafka_producer


async def get_gemini_client() -> ResilientGeminiClient:
    """
    Get Gemini AI client instance

    Returns: Singleton ResilientGeminiClient instance
    """
    if _gemini_client is None:
        raise RuntimeError(
            "Gemini client not initialized. Call initialize_dependencies() first."
        )

    return _gemini_client
