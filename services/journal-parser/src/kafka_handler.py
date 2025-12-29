"""
Kafka Handler - Consumes journal entries from Kafka and processes them

Consumes from: journal_entries topic
Publishes to: parsed_entries topic
"""

import asyncio
import json
from typing import Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from shared.kafka.topics import KafkaTopics
from shared.models.journal import JournalEntry, ParsedJournalEntry
from shared.utils.config import get_settings
from shared.utils.logger import get_logger

from .gap_detector import GapDetector
from .parser_engine import JournalParserEngine

logger = get_logger(__name__)
settings = get_settings()


class KafkaJournalConsumer:
    """
    Kafka consumer for journal entries

    Processes journal entries in real-time using Gemini parser
    """

    def __init__(self, parser_engine: JournalParserEngine, gap_detector: GapDetector):
        """
        Initialize Kafka consumer

        Args:
            parser_engine: Parser engine instance
            gap_detector: Gap detector instance
        """
        self.parser_engine = parser_engine
        self.gap_detector = gap_detector

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

    async def _process_message(self, message_data: dict):
        """
        Process a single journal entry message

        Args:
            message_data: Journal entry data from Kafka
        """
        try:
            # Parse message into JournalEntry
            entry = JournalEntry(**message_data)

            logger.info(f"Processing journal entry: {entry.id} (user: {entry.user_id})")

            # Parse entry using Gemini
            parsed_entry = await self.parser_engine.parse_entry(
                entry_text=entry.content, user_id=entry.user_id
            )

            # Detect gaps
            missing_metrics = await self.gap_detector.detect_gaps(entry.content)
            completeness_score = self.gap_detector.calculate_completeness_score(
                missing_metrics
            )

            # Add metadata
            parsed_entry.id = entry.id
            parsed_entry.entry_date = entry.entry_date

            # Prepare output message
            output_message = {
                "entry_id": str(entry.id),
                "user_id": entry.user_id,
                "parsed_data": parsed_entry.model_dump(exclude_none=True),
                "metadata": {
                    "missing_metrics": missing_metrics,
                    "completeness_score": completeness_score,
                    "parsed_at": parsed_entry.parsed_at.isoformat(),
                },
            }

            # Publish to parsed_entries topic
            await self.producer.send(KafkaTopics.PARSED_ENTRIES, value=output_message)

            logger.info(
                f"Successfully processed entry {entry.id} - "
                f"completeness: {completeness_score:.2f}, "
                f"missing: {len(missing_metrics)} metrics"
            )

        except Exception as e:
            logger.error(f"Error processing journal entry: {str(e)}")
            raise

    async def process_single_entry(self, entry: JournalEntry) -> ParsedJournalEntry:
        """
        Process a single entry (for testing/debugging)

        Args:
            entry: Journal entry to process

        Returns:
            Parsed journal entry
        """
        parsed_entry = await self.parser_engine.parse_entry(
            entry_text=entry.content, user_id=entry.user_id
        )

        parsed_entry.id = entry.id
        parsed_entry.entry_date = entry.entry_date

        return parsed_entry
