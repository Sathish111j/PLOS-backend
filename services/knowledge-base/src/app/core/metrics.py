from shared.utils.logging_config import MetricsLogger
from shared.utils.metrics import REQUEST_COUNT, REQUEST_LATENCY

metrics = MetricsLogger("knowledge-base")

__all__ = ["metrics", "REQUEST_COUNT", "REQUEST_LATENCY"]
