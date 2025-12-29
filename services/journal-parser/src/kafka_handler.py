"""
Kafka Handler - Consumes journal entries from Kafka and processes them

Consumes from: journal_entries topic
Publishes to: parsed_entries topic
"""

import asyncio
import json
from typing import Any, Dict, Optional
from uuid import UUID

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.gemini.client import ResilientGeminiClient
from shared.kafka.producer import KafkaProducerService
from shared.kafka.topics import KafkaTopics
from shared.models.journal import JournalEntry
from shared.utils.config import get_settings
from shared.utils.logger import get_logger

from .orchestrator import JournalParserOrchestrator

logger = get_logger(__name__)
settings = get_settings()


class KafkaJournalConsumer:
    """
    Kafka consumer for journal entries

    Processes journal entries in real-time using the orchestrator
    """

    def __init__(
        self,
        db_session: AsyncSession,
        kafka_producer: Optional[KafkaProducerService] = None,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ):
        """
        Initialize Kafka consumer

        Args:
            db_session: Database session
            kafka_producer: Kafka producer for events
            gemini_client: Gemini client for extraction
        """
        self.db_session = db_session
        self.kafka_producer = kafka_producer
        self.gemini_client = gemini_client

        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None

        self.running = False
        self.messages_processed = 0
        self.errors = 0

        logger.info("Initialized KafkaJournalConsumer")

    async def start(self):
        """Start Kafka consumer and producer"""
        try:
            # Initialize consumer
            self.consumer = AIOKafkaConsumer(
                KafkaTopics.JOURNAL_ENTRIES,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="journal-parser-group",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )

            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )

            # Start both
            await self.consumer.start()
            await self.producer.start()

            self.running = True

            logger.info(
                f"Kafka consumer started - listening on topic: {KafkaTopics.JOURNAL_ENTRIES}"
            )

            # Start consuming in background
            asyncio.create_task(self._consume_loop())

        except Exception as e:
            logger.error(f"Error starting Kafka consumer: {str(e)}")
            raise

    async def stop(self):
        """Stop Kafka consumer and producer"""
        self.running = False

        if self.consumer:
            await self.consumer.stop()

        if self.producer:
            await self.producer.stop()

        logger.info("Kafka consumer stopped")

    async def _consume_loop(self):
        """Main consumption loop"""
        logger.info("Starting consumption loop...")

        try:
            async for message in self.consumer:
                try:
                    await self._process_message(message.value)
                    self.messages_processed += 1

                except Exception as e:
                    self.errors += 1
                    logger.error(f"Error processing message: {str(e)}")
                    # Continue processing other messages
                    continue

        except Exception as e:
            logger.error(f"Error in consumption loop: {str(e)}")
            self.running = False

    async def _process_message(self, message_data: dict) -> None:
        """
        Process a single journal entry message

        Args:
            message_data: Journal entry data from Kafka
        """
        try:
            # Parse message into JournalEntry
            entry = JournalEntry(**message_data)

            logger.info(f"Processing journal entry: {entry.id} (user: {entry.user_id})")

            # Create orchestrator and process
            orchestrator = JournalParserOrchestrator(
                db_session=self.db_session,
                kafka_producer=self.kafka_producer,
                gemini_client=self.gemini_client,
            )

            result = await orchestrator.process_journal_entry(
                user_id=(
                    UUID(entry.user_id)
                    if isinstance(entry.user_id, str)
                    else entry.user_id
                ),
                entry_text=entry.content,
                entry_date=(
                    entry.entry_date.date()
                    if hasattr(entry.entry_date, "date")
                    else entry.entry_date
                ),
            )

            # Prepare output message
            output_message = {
                "entry_id": result["entry_id"],
                "user_id": result["user_id"],
                "entry_date": result["entry_date"],
                "quality": result["quality"],
                "has_gaps": result["has_gaps"],
                "activity_count": len(result.get("activities", [])),
                "consumption_count": len(result.get("consumptions", [])),
                "processing_time_ms": result["metadata"]["processing_time_ms"],
            }

            # Publish to parsed_entries topic
            await self.producer.send(KafkaTopics.PARSED_ENTRIES, value=output_message)

            logger.info(
                f"Successfully processed entry {entry.id} - "
                f"quality: {result['quality']}, "
                f"has_gaps: {result['has_gaps']}"
            )

        except Exception as e:
            logger.error(f"Error processing journal entry: {str(e)}")
            raise

    async def process_single_entry(self, entry: JournalEntry) -> Dict[str, Any]:
        """
        Process a single entry (for testing/debugging)

        Args:
            entry: Journal entry to process

        Returns:
            Extraction result dict
        """
        orchestrator = JournalParserOrchestrator(
            db_session=self.db_session,
            kafka_producer=self.kafka_producer,
            gemini_client=self.gemini_client,
        )

        result = await orchestrator.process_journal_entry(
            user_id=(
                UUID(entry.user_id) if isinstance(entry.user_id, str) else entry.user_id
            ),
            entry_text=entry.content,
            entry_date=(
                entry.entry_date.date()
                if hasattr(entry.entry_date, "date")
                else entry.entry_date
            ),
        )

        return result
