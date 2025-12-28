"""
PLOS Kafka Producer
Wrapper for Kafka producer with JSON serialization
"""

import json
from typing import Any, Dict, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from ..utils.config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class KafkaProducerClient:
    """Kafka producer wrapper for easy message publishing"""

    def __init__(self, bootstrap_servers: Optional[str] = None):
        """
        Initialize Kafka producer

        Args:
            bootstrap_servers: Kafka broker addresses (defaults to settings)
        """
        settings = get_settings()
        self.bootstrap_servers = bootstrap_servers or settings.kafka_brokers

        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=5,
            compression_type="gzip",
        )

        logger.info(f"Kafka producer initialized: {self.bootstrap_servers}")

    def send(
        self, topic: str, value: Dict[str, Any], key: Optional[str] = None
    ) -> bool:
        """
        Send message to Kafka topic

        Args:
            topic: Topic name
            value: Message value (will be JSON serialized)
            key: Optional message key for partitioning

        Returns:
            True if successful, False otherwise
        """
        try:
            future = self.producer.send(topic, value=value, key=key)
            record_metadata = future.get(timeout=10)

            logger.debug(
                f"Message sent to {topic} "
                f"(partition: {record_metadata.partition}, "
                f"offset: {record_metadata.offset})"
            )
            return True

        except KafkaError as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            return False

    def send_batch(self, topic: str, messages: list[Dict[str, Any]]) -> int:
        """
        Send batch of messages

        Args:
            topic: Topic name
            messages: List of messages

        Returns:
            Number of successfully sent messages
        """
        success_count = 0

        for message in messages:
            if self.send(topic, message):
                success_count += 1

        self.flush()
        logger.info(f"Sent {success_count}/{len(messages)} messages to {topic}")

        return success_count

    def flush(self) -> None:
        """Flush pending messages"""
        self.producer.flush()

    def close(self) -> None:
        """Close producer connection"""
        self.producer.close()
        logger.info("Kafka producer closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
