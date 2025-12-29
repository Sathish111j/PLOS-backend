"""
PLOS v2.0 - Complete Integration Example
Shows how to wire all components together for production deployment
"""

import asyncio
import os
from datetime import datetime
from uuid import UUID

# Core components
from services.journal_parser.src.cache_manager import MultiLayerCacheManager
from services.journal_parser.src.db_pool import (
    DatabaseConnectionPool,
    initialize_global_pool,
    get_global_pool
)
from services.journal_parser.src.orchestrator import JournalParserOrchestrator
from services.journal_parser.src.worker import JournalProcessingWorker
from shared.kafka.producer import KafkaProducerService
from shared.kafka.consumer import KafkaConsumerService
from shared.gemini.client import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# APPLICATION SETUP
# ============================================================================

class PLOSApplication:
    """
    Complete PLOS v2.0 application setup
    Wires together all components per architecture
    """
    
    def __init__(self):
        # Core infrastructure
        self.db_pool: DatabaseConnectionPool | None = None
        self.cache_manager: MultiLayerCacheManager | None = None
        self.kafka_producer: KafkaProducerService | None = None
        self.kafka_consumer: KafkaConsumerService | None = None
        self.gemini_client: ResilientGeminiClient | None = None
        
        # Services
        self.orchestrator: JournalParserOrchestrator | None = None
        self.worker: JournalProcessingWorker | None = None
        
        # Configuration from environment
        self.config = {
            "database_url": os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/plos"),
            "redis_host": os.getenv("REDIS_HOST", "localhost"),
            "redis_port": int(os.getenv("REDIS_PORT", "6379")),
            "kafka_brokers": os.getenv("KAFKA_BROKERS", "localhost:9092"),
            "gemini_api_keys": os.getenv("GEMINI_API_KEYS", "").split(","),
            "pool_min": int(os.getenv("DB_POOL_MIN", "5")),
            "pool_max": int(os.getenv("DB_POOL_MAX", "20")),
        }
    
    async def initialize(self) -> None:
        """
        Initialize all components
        Call this at application startup
        """
        logger.info("Initializing PLOS v2.0 application")
        
        # 1. Initialize database connection pool
        logger.info("Initializing database pool")
        await initialize_global_pool(
            self.config["database_url"]
        )
        self.db_pool = get_global_pool()
        
        # 2. Initialize Redis for caching
        logger.info("Initializing cache manager")
        import redis.asyncio as redis
        redis_client = await redis.from_url(
            f"redis://{self.config['redis_host']}:{self.config['redis_port']}"
        )
        
        self.cache_manager = MultiLayerCacheManager(
            redis_client=redis_client,
            db_session=None  # Will use pool directly
        )
        
        # 3. Initialize Kafka
        logger.info("Initializing Kafka producer")
        self.kafka_producer = KafkaProducerService(
            bootstrap_servers=self.config["kafka_brokers"]
        )
        await self.kafka_producer.start()
        
        logger.info("Initializing Kafka consumer")
        self.kafka_consumer = KafkaConsumerService(
            bootstrap_servers=self.config["kafka_brokers"],
            group_id="journal-parser-workers"
        )
        await self.kafka_consumer.start()
        
        # 4. Initialize Gemini client
        logger.info("Initializing Gemini client")
        self.gemini_client = ResilientGeminiClient()
        # Keys are loaded from environment by the client
        
        # 5. Initialize orchestrator
        logger.info("Initializing orchestrator")
        async with self.db_pool.get_session() as session:
            self.orchestrator = JournalParserOrchestrator(
                db_session=session,
                cache_manager=self.cache_manager,
                gemini_client=self.gemini_client,
                kafka_producer=self.kafka_producer
            )
        
        # 6. Initialize worker
        logger.info("Initializing background worker")
        self.worker = JournalProcessingWorker(
            kafka_consumer=self.kafka_consumer,
            orchestrator=self.orchestrator,
            redis_client=redis_client
        )
        
        logger.info("✅ PLOS v2.0 initialization complete")
    
    async def start_worker(self) -> None:
        """
        Start background worker
        Runs indefinitely, processing from Kafka queue
        """
        logger.info("Starting background worker")
        await self.worker.start()
    
    async def shutdown(self) -> None:
        """
        Graceful shutdown
        Call this on application exit
        """
        logger.info("Shutting down PLOS v2.0")
        
        # Stop Kafka
        if self.kafka_producer:
            await self.kafka_producer.stop()
        if self.kafka_consumer:
            await self.kafka_consumer.stop()
        
        # Close database pool
        if self.db_pool:
            await self.db_pool.close()
        
        logger.info("✅ Shutdown complete")
    
    def get_metrics(self) -> dict:
        """Get comprehensive system metrics"""
        return {
            "database": self.db_pool.get_pool_status() if self.db_pool else {},
            "cache": self.cache_manager.get_cache_stats() if self.cache_manager else {},
            "worker": self.worker.get_metrics() if self.worker else {}
        }


# ============================================================================
# EXAMPLE USAGE: SYNC API
# ============================================================================

async def example_sync_processing():
    """
    Example: Synchronous processing (user waits)
    Use for: Testing, admin tools, debugging
    """
    app = PLOSApplication()
    await app.initialize()
    
    try:
        # Process entry synchronously
        async with app.db_pool.get_session() as session:
            result = await app.orchestrator.process_journal_entry(
                user_id=UUID("12345678-1234-1234-1234-123456789abc"),
                journal_entry_id=UUID("87654321-4321-4321-4321-cba987654321"),
                entry_text="Slept 7 hours. Played badminton for 1 hour. Feeling great!",
                entry_date=datetime.utcnow()
            )
        
        logger.info(f"Processing complete: {result['extraction_id']}")
        logger.info(f"Quality: {result['quality_level']}")
        logger.info(f"Health alerts: {len(result.get('health_alerts', []))}")
        logger.info(f"Predictions: {result.get('predictions', {})}")
    
    finally:
        await app.shutdown()


# ============================================================================
# EXAMPLE USAGE: ASYNC API
# ============================================================================

async def example_async_processing():
    """
    Example: Asynchronous processing (fire-and-forget)
    Use for: Production API, user-facing endpoints
    """
    app = PLOSApplication()
    await app.initialize()
    
    try:
        # Queue entry for async processing
        from uuid import uuid4
        task_id = str(uuid4())
        
        await app.kafka_producer.publish(
            topic="journal_entries_raw",
            key=str("user-123"),
            value={
                "task_id": task_id,
                "user_id": "12345678-1234-1234-1234-123456789abc",
                "journal_entry_id": "87654321-4321-4321-4321-cba987654321",
                "entry_text": "Slept 7 hours. Played badminton for 1 hour. Feeling great!",
                "entry_date": datetime.utcnow().isoformat(),
                "priority": 5,
                "queued_at": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Queued task: {task_id}")
        logger.info("User can check status at /v2/async/status/{task_id}")
        
        # Start worker in background
        # In production, run this in separate process/container
        await app.start_worker()
    
    finally:
        await app.shutdown()


# ============================================================================
# FASTAPI INTEGRATION
# ============================================================================

async def create_fastapi_app():
    """
    Example: Integrate with FastAPI
    """
    from fastapi import FastAPI, Depends
    
    app_instance = FastAPI(title="PLOS v2.0 API")
    plos = PLOSApplication()
    
    @app_instance.on_event("startup")
    async def startup():
        await plos.initialize()
    
    @app_instance.on_event("shutdown")
    async def shutdown():
        await plos.shutdown()
    
    @app_instance.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "plos-v2",
            "metrics": plos.get_metrics()
        }
    
    # Include routers
    from services.journal_parser.src.api import router as sync_router
    from services.journal_parser.src.api_async import router as async_router
    
    app_instance.include_router(sync_router)
    app_instance.include_router(async_router)
    
    return app_instance


# ============================================================================
# WORKER PROCESS ENTRYPOINT
# ============================================================================

async def run_worker_process():
    """
    Standalone worker process
    Run with: python -m services.journal-parser.src.integration_example
    """
    logger.info("Starting PLOS v2.0 background worker")
    
    app = PLOSApplication()
    await app.initialize()
    
    try:
        # Run worker indefinitely
        await app.start_worker()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    finally:
        await app.shutdown()


# ============================================================================
# DOCKER COMPOSE EXAMPLE
# ============================================================================

DOCKER_COMPOSE_EXAMPLE = """
# docker-compose.yml for PLOS v2.0

version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: plos
      POSTGRES_USER: plos_user
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - ./infrastructure/database/migrations/v2_schema.sql:/docker-entrypoint-initdb.d/schema.sql
      - postgres_data:/var/lib/postgresql/data
  
  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  # Kafka
  kafka:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    ports:
      - "9092:9092"
  
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  # PLOS API (FastAPI)
  api:
    build: .
    command: uvicorn integration_example:create_fastapi_app --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql+asyncpg://plos_user:secure_password@postgres:5432/plos
      REDIS_HOST: redis
      KAFKA_BROKERS: kafka:9092
      GEMINI_API_KEYS: ${GEMINI_API_KEYS}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - kafka
  
  # PLOS Background Worker
  worker:
    build: .
    command: python -m services.journal-parser.src.integration_example
    environment:
      DATABASE_URL: postgresql+asyncpg://plos_user:secure_password@postgres:5432/plos
      REDIS_HOST: redis
      KAFKA_BROKERS: kafka:9092
      GEMINI_API_KEYS: ${GEMINI_API_KEYS}
    depends_on:
      - postgres
      - redis
      - kafka
    deploy:
      replicas: 2  # Run 2 workers for redundancy

volumes:
  postgres_data:
  redis_data:
"""


# ============================================================================
# ENVIRONMENT VARIABLES TEMPLATE
# ============================================================================

ENV_TEMPLATE = """
# .env file for PLOS v2.0

# Database
DATABASE_URL=postgresql+asyncpg://plos_user:secure_password@localhost:5432/plos
DB_POOL_MIN=5
DB_POOL_MAX=20

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Kafka
KAFKA_BROKERS=localhost:9092

# Gemini API
GEMINI_API_KEYS=key1,key2,key3

# Logging
LOG_LEVEL=INFO
"""


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        # Run as worker
        asyncio.run(run_worker_process())
    else:
        # Run sync example
        asyncio.run(example_sync_processing())
