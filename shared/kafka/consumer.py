"""
PLOS Kafka Consumer
Wrapper for Kafka consumer with JSON deserialization
"""

import json
from typing import Any, Callable, Dict, List, Optional

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from ..utils.config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class KafkaConsumerClient:
    """Kafka consumer wrapper for easy message consumption"""

    def __init__(
        self,
        topics: List[str],
        group_id: Optional[str] = None,
        bootstrap_servers: Optional[str] = None,
        auto_offset_reset: str = "earliest",
    ):
        """
        Initialize Kafka consumer

        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID (defaults to settings)
            bootstrap_servers: Kafka broker addresses (defaults to settings)
            auto_offset_reset: Where to start consuming ('earliest' or 'latest')
        """
        settings = get_settings()
        self.topics = topics
        self.group_id = (
            group_id or settings.kafka_consumer_group or settings.service_name
        )
        self.bootstrap_servers = bootstrap_servers or settings.kafka_brokers

        self.consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers.split(","),
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            max_poll_records=500,
        )

        logger.info(
            f"Kafka consumer initialized: {self.topics} " f"(group: {self.group_id})"
        )

    def consume(
        self,
        callback: Callable[[Dict[str, Any]], None],
        error_callback: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Start consuming messages (blocking)

        Args:
            callback: Function to call for each message
            error_callback: Optional error handler
        """
        logger.info(f"Starting to consume from {self.topics}")

        try:
            for message in self.consumer:
                try:
                    logger.debug(
                        f"Received message from {message.topic} "
                        f"(partition: {message.partition}, offset: {message.offset})"
                    )

                    callback(message.value)

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    if error_callback:
                        error_callback(e)

        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
            if error_callback:
                error_callback(e)
        finally:
            self.close()

    def consume_batch(
        self, batch_size: int = 100, timeout_ms: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Consume a batch of messages

        Args:
            batch_size: Maximum messages to consume
            timeout_ms: Timeout for polling

        Returns:
            List of messages
        """
        messages = []

        try:
            msg_batch = self.consumer.poll(
                timeout_ms=timeout_ms, max_records=batch_size
            )

            for topic_partition, records in msg_batch.items():
                for record in records:
                    messages.append(record.value)

            logger.debug(f"Consumed batch of {len(messages)} messages")

        except KafkaError as e:
            logger.error(f"Error consuming batch: {e}")

        return messages

    def close(self) -> None:
        """Close consumer connection"""
        self.consumer.close()
        logger.info("Kafka consumer closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class KafkaConsumerService:
    """
    Async Kafka consumer service for PLOS
    Wraps aiokafka for async message consumption
    """

    def __init__(
        self,
        topics: List[str],
        group_id: str,
        bootstrap_servers: str,
    ):
        """
        Initialize async Kafka consumer

        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID
            bootstrap_servers: Kafka broker addresses
        """
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers
        self._consumer = None
        self._started = False

    async def start(self):
        """Start the async consumer"""
        if self._started:
            return

        import json

        from aiokafka import AIOKafkaConsumer

        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self._consumer.start()
        self._started = True
        logger.info(
            f"Async Kafka consumer started: {self.topics} (group: {self.group_id})"
        )

    async def stop(self):
        """Stop the async consumer"""
        if self._consumer and self._started:
            await self._consumer.stop()
            self._started = False
            logger.info("Async Kafka consumer stopped")

    async def consume(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """
        Start consuming messages asynchronously

        Args:
            callback: Async function to call for each message
        """
        if not self._started:
            await self.start()

        try:
            async for message in self._consumer:
                try:
                    logger.debug(
                        f"Received message from {message.topic} "
                        f"(partition: {message.partition}, offset: {message.offset})"
                    )
                    # Support both sync and async callbacks
                    import asyncio

                    if asyncio.iscoroutinefunction(callback):
                        await callback(message.value)
                    else:
                        callback(message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            raise

    async def get_messages(self, timeout_ms: int = 1000) -> List[Dict[str, Any]]:
        """
        Get available messages (non-blocking)

        Args:
            timeout_ms: Timeout for polling

        Returns:
            List of message values
        """
        if not self._started:
            await self.start()

        messages = []
        data = await self._consumer.getmany(timeout_ms=timeout_ms)
        for tp, records in data.items():
            for record in records:
                messages.append(record.value)

        return messages
