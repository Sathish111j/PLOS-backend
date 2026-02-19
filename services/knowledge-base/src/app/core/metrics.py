from prometheus_client import Counter, Histogram

from shared.utils.logging_config import MetricsLogger

metrics = MetricsLogger("knowledge-base")

REQUEST_COUNT = Counter(
    "knowledge_base_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "knowledge_base_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)
