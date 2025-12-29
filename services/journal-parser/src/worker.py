"""
Background Kafka worker for asynchronous journal entry processing.

This module implements a Kafka consumer that processes journal entries in the background,
providing status updates via Redis and webhook notifications upon completion.

Part of PLOS v2.0 async-first architecture for <200ms API response times.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import aiohttp
from redis.asyncio import Redis

from shared.kafka.consumer import KafkaConsumerService
from shared.kafka.topics import KafkaTopic
from shared.utils.logger import get_logger

from .orchestrator import JournalParserOrchestrator

logger = get_logger(__name__)


class JournalProcessingWorker:
    """
    Background worker that consumes journal entries from Kafka queue and processes them.

    Features:
    - Async processing with status tracking in Redis
    - Progress updates (10% -> 30% -> 90% -> 100%)
    - Webhook notifications on completion/failure
    - Metrics tracking (processed count, success rate, avg time)
    - Graceful error handling and retry logic
    """

    def __init__(
        self,
        orchestrator: JournalParserOrchestrator,
        kafka_consumer: KafkaConsumerService,
        redis_client: Redis,
        max_concurrent: int = 10,
        batch_timeout: float = 5.0,
    ):
        """
        Initialize the worker.

        Args:
            orchestrator: Journal parser orchestrator for processing
            kafka_consumer: Kafka consumer service
            redis_client: Redis client for status tracking
            max_concurrent: Maximum concurrent messages to process
            batch_timeout: Timeout for batch processing in seconds
        """
        self.orchestrator = orchestrator
        self.kafka_consumer = kafka_consumer
        self.redis_client = redis_client
        self.max_concurrent = max_concurrent
        self.batch_timeout = batch_timeout

        # Metrics tracking
        self.processed_count = 0
        self.failed_count = 0
        self.total_processing_time = 0.0
        self.start_time = datetime.utcnow()

        self._running = False

    async def start(self):
        """
        Start the worker and begin consuming messages from Kafka.

        This runs indefinitely until stopped. Processes messages in batches
        for better throughput while maintaining individual status tracking.
        """
        self._running = True
        logger.info("Starting journal processing worker")

        # Subscribe to the raw journal entries topic
        await self.kafka_consumer.subscribe([KafkaTopic.JOURNAL_ENTRIES_RAW])

        batch = []

        try:
            while self._running:
                # Consume messages with timeout
                message = await self.kafka_consumer.consume(timeout=1.0)

                if message is None:
                    # Process accumulated batch if we have any
                    if batch:
                        await self._process_batch(batch)
                        batch = []
                    continue

                batch.append(message)

                # Process batch if we've reached max concurrent or timeout
                if len(batch) >= self.max_concurrent:
                    await self._process_batch(batch)
                    batch = []

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
        finally:
            # Process any remaining messages
            if batch:
                await self._process_batch(batch)

            logger.info("Worker stopped")

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker...")
        self._running = False

    async def _process_batch(self, messages: list):
        """
        Process a batch of messages in parallel.

        Args:
            messages: List of Kafka messages to process
        """
        tasks = [self._process_message(msg) for msg in messages]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_message(self, message: Dict[str, Any]):
        """
        Process a single journal entry message.

        Args:
            message: Kafka message containing journal entry data
        """
        start_time = datetime.utcnow()
        task_id = None

        try:
            # Parse message
            data = json.loads(message.get("value", "{}"))
            task_id = data.get("task_id")
            user_id = data.get("user_id")
            entry_text = data.get("entry_text")
            webhook_url = data.get("webhook_url")
            priority = data.get("priority", 5)

            if not all([task_id, user_id, entry_text]):
                logger.error(f"Invalid message data: {data}")
                return

            logger.info(
                f"Processing task {task_id} for user {user_id} (priority: {priority})"
            )

            # Update status: processing (10% complete)
            await self._update_status(
                task_id=task_id,
                status="processing",
                progress=10,
                message="Entry received, starting preprocessing",
            )

            # Stage 1: Preprocessing (10% -> 30%)
            await self._update_status(task_id, "processing", 30, "Preprocessing entry")

            # Stage 2-6: Main processing (30% -> 90%)
            result = await self.orchestrator.process_entry(
                user_id=UUID(user_id), entry_text=entry_text
            )

            await self._update_status(task_id, "processing", 90, "Finalizing results")

            # Stage 7: Complete (90% -> 100%)
            await self._update_status(
                task_id=task_id,
                status="completed",
                progress=100,
                message="Processing completed successfully",
                result=result,
            )

            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.processed_count += 1
            self.total_processing_time += processing_time

            logger.info(f"Task {task_id} completed in {processing_time:.2f}s")

            # Send webhook notification if provided
            if webhook_url:
                await self._call_webhook(
                    url=webhook_url, task_id=task_id, status="completed", result=result
                )

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)

            # Update status: failed
            if task_id:
                await self._update_status(
                    task_id=task_id,
                    status="failed",
                    progress=0,
                    message=f"Processing failed: {str(e)}",
                )

                # Send failure webhook
                webhook_url = json.loads(message.get("value", "{}")).get("webhook_url")
                if webhook_url:
                    await self._call_webhook(
                        url=webhook_url, task_id=task_id, status="failed", error=str(e)
                    )

            self.failed_count += 1

    async def _update_status(
        self,
        task_id: str,
        status: str,
        progress: int,
        message: str,
        result: Optional[Dict[str, Any]] = None,
    ):
        """
        Update task status in Redis.

        Args:
            task_id: Unique task identifier
            status: Status string (queued, processing, completed, failed)
            progress: Progress percentage (0-100)
            message: Status message
            result: Processing result (for completed status)
        """
        try:
            status_data = {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "message": message,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if result:
                status_data["result"] = result

            # Store in Redis with 1 hour TTL
            key = f"task_status:{task_id}"
            await self.redis_client.setex(key, 3600, json.dumps(status_data))  # 1 hour

        except Exception as e:
            logger.error(f"Error updating status for task {task_id}: {e}")

    async def _call_webhook(
        self,
        url: str,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """
        Call webhook URL to notify about task completion/failure.

        Args:
            url: Webhook URL to call
            task_id: Task identifier
            status: Task status
            result: Processing result (for success)
            error: Error message (for failure)
        """
        try:
            payload = {
                "task_id": task_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if result:
                payload["result"] = result
            if error:
                payload["error"] = error

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status >= 400:
                        logger.warning(
                            f"Webhook call failed for task {task_id}: "
                            f"HTTP {response.status}"
                        )
                    else:
                        logger.info(f"Webhook called successfully for task {task_id}")

        except Exception as e:
            logger.error(f"Error calling webhook for task {task_id}: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get worker performance metrics.

        Returns:
            Dictionary containing:
            - processed_count: Total successfully processed entries
            - failed_count: Total failed entries
            - success_rate: Success percentage
            - avg_processing_time: Average time per entry in seconds
            - uptime_seconds: Worker uptime
        """
        total = self.processed_count + self.failed_count
        success_rate = (self.processed_count / total * 100) if total > 0 else 0.0
        avg_time = (
            self.total_processing_time / self.processed_count
            if self.processed_count > 0
            else 0.0
        )
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        return {
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "total_count": total,
            "success_rate": round(success_rate, 2),
            "avg_processing_time": round(avg_time, 2),
            "uptime_seconds": round(uptime, 2),
        }


async def run_worker():
    """
    Entry point for running the worker as a standalone process.

    This function initializes all dependencies and starts the worker.
    Intended to be run in a separate container/process from the API.

    Example:
        python -m services.journal-parser.src.worker
    """
    import os

    from redis.asyncio import Redis

    from shared.gemini.client import GeminiClient
    from shared.kafka.consumer import KafkaConsumerService
    from shared.kafka.producer import KafkaProducerService
    from shared.utils.db_pool import get_global_pool, initialize_global_pool

    logger.info("Initializing worker...")

    # Load configuration from environment
    database_url = os.getenv("DATABASE_URL")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    kafka_brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    gemini_api_keys = os.getenv("GEMINI_API_KEYS", "").split(",")

    # Initialize database connection pool
    await initialize_global_pool(database_url)
    pool = get_global_pool()

    # Initialize Redis
    redis_client = Redis(host=redis_host, port=redis_port, decode_responses=False)

    # Initialize Kafka
    kafka_consumer = KafkaConsumerService(
        bootstrap_servers=kafka_brokers, group_id="journal-processor-workers"
    )
    kafka_producer = KafkaProducerService(bootstrap_servers=kafka_brokers)

    # Initialize Gemini client
    gemini_client = GeminiClient(api_keys=gemini_api_keys)

    # Initialize orchestrator
    async with pool.get_session() as session:
        orchestrator = JournalParserOrchestrator(
            db_session=session,
            gemini_client=gemini_client,
            kafka_producer=kafka_producer,
        )

        # Initialize and start worker
        worker = JournalProcessingWorker(
            orchestrator=orchestrator,
            kafka_consumer=kafka_consumer,
            redis_client=redis_client,
        )

        try:
            await worker.start()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await worker.stop()
            await kafka_consumer.close()
            await kafka_producer.close()
            await redis_client.close()
            await pool.close()

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(run_worker())
