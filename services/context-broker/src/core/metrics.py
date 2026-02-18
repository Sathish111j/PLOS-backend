"""Metrics helpers for context broker."""

from prometheus_client import Counter, Histogram

from shared.utils.logger import get_logger
from shared.utils.logging_config import MetricsLogger

logger = get_logger(__name__)
metrics = MetricsLogger("context-broker")

REQUEST_COUNT = Counter(
    "context_broker_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "context_broker_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)
