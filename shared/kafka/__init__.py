"""
PLOS Shared Kafka Module
Kafka producer and consumer wrappers
"""

from .consumer import KafkaConsumerClient, KafkaConsumerService
from .producer import KafkaProducerClient, KafkaProducerService
from .topics import KafkaTopic, KafkaTopics

__all__ = [
    "KafkaProducerClient",
    "KafkaProducerService",
    "KafkaConsumerClient",
    "KafkaConsumerService",
    "KafkaTopics",
    "KafkaTopic",
]
