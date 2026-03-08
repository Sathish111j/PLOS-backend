"""Metrics helpers for context broker."""

from shared.utils.logger import get_logger
from shared.utils.logging_config import MetricsLogger
from shared.utils.metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = get_logger(__name__)
metrics = MetricsLogger("context-broker")

__all__ = ["metrics", "REQUEST_COUNT", "REQUEST_LATENCY"]
