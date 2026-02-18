"""
PLOS Centralized Logging Configuration
Structured logging with JSON output for all services
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = datetime.utcnow().isoformat()

        # Add log level
        log_record["level"] = record.levelname

        # Add service name (from environment or logger name)
        log_record["service"] = getattr(
            record, "service_name", record.name.split(".")[0]
        )

        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id

        # Add user ID if available
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id

        # Add request ID if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


def setup_logging(
    service_name: str, log_level: str = "INFO", json_logs: bool = True
) -> logging.Logger:
    """
    Setup centralized logging configuration

    Args:
        service_name: Name of the service (e.g., 'context-broker')
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to use JSON formatting (True for production)

    Returns:
        Configured logger instance
    """

    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Set formatter
    if json_logs:
        # JSON formatter for production
        formatter = CustomJsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s"
        )
    else:
        # Human-readable formatter for development
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# ============================================================================
# BUSINESS METRICS LOGGING
# ============================================================================


class MetricsLogger:
    """Logger for business metrics and events"""

    def __init__(self, service_name: str):
        self.logger = logging.getLogger(f"{service_name}.metrics")
        self.service_name = service_name

    def log_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None,
    ):
        """
        Log a business metric

        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Additional tags for filtering
            user_id: Associated user ID
        """
        extra = {
            "metric_name": metric_name,
            "metric_value": value,
            "metric_type": "gauge",
            "service_name": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if tags:
            extra["tags"] = tags
        if user_id:
            extra["user_id"] = user_id

        self.logger.info(f"METRIC: {metric_name}={value}", extra=extra)

    def log_event(
        self, event_name: str, event_data: Dict[str, Any], user_id: Optional[str] = None
    ):
        """
        Log a business event

        Args:
            event_name: Name of the event
            event_data: Event payload
            user_id: Associated user ID
        """
        extra = {
            "event_name": event_name,
            "event_data": event_data,
            "service_name": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if user_id:
            extra["user_id"] = user_id

        self.logger.info(f"EVENT: {event_name}", extra=extra)

    def log_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str] = None,
    ):
        """
        Log API call metrics

        Args:
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            user_id: Associated user ID
        """
        extra = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "service_name": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if user_id:
            extra["user_id"] = user_id

        self.logger.info(
            f"API_CALL: {method} {endpoint} {status_code} {duration_ms}ms", extra=extra
        )
