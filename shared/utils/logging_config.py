"""
PLOS Centralized Logging Configuration
Structured logging with JSON output for all services
"""

import logging
import sys
import json
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
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            rename_fields={
                "levelname": "level",
                "name": "logger",
                "pathname": "file",
                "lineno": "line",
            },
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


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter with context"""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add extra context to log messages"""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger_with_context(
    service_name: str,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> LoggerAdapter:
    """
    Get logger with contextual information

    Args:
        service_name: Name of the service
        user_id: User ID for tracking
        request_id: Request ID for tracing
        correlation_id: Correlation ID across services

    Returns:
        Logger adapter with context
    """
    logger = logging.getLogger(service_name)

    extra = {}
    if user_id:
        extra["user_id"] = user_id
    if request_id:
        extra["request_id"] = request_id
    if correlation_id:
        extra["correlation_id"] = correlation_id

    return LoggerAdapter(logger, extra)


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


# ============================================================================
# STRUCTURED LOGGING HELPERS
# ============================================================================


def log_error_with_context(
    logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None
):
    """
    Log error with full context and stack trace

    Args:
        logger: Logger instance
        error: Exception to log
        context: Additional context information
    """
    extra = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
    }

    if context:
        extra.update(context)

    logger.error(
        f"Error occurred: {type(error).__name__}: {str(error)}",
        exc_info=True,
        extra=extra,
    )


def log_performance(
    logger: logging.Logger,
    operation: str,
    duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Log performance metrics

    Args:
        logger: Logger instance
        operation: Operation name
        duration_ms: Duration in milliseconds
        metadata: Additional metadata
    """
    extra = {
        "operation": operation,
        "duration_ms": duration_ms,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if metadata:
        extra.update(metadata)

    logger.info(f"Performance: {operation} took {duration_ms}ms", extra=extra)


# ============================================================================
# LOG AGGREGATION HELPERS
# ============================================================================


def format_for_elk(log_record: Dict[str, Any]) -> str:
    """
    Format log record for ELK Stack (Elasticsearch, Logstash, Kibana)

    Args:
        log_record: Log record dictionary

    Returns:
        JSON string formatted for ELK
    """
    return json.dumps(log_record)


def format_for_datadog(log_record: Dict[str, Any]) -> str:
    """
    Format log record for Datadog

    Args:
        log_record: Log record dictionary

    Returns:
        JSON string formatted for Datadog
    """
    # Datadog expects specific field names
    datadog_record = {
        "ddsource": log_record.get("service", "plos"),
        "ddtags": f"service:{log_record.get('service', 'plos')},env:development",
        "hostname": log_record.get("hostname", "localhost"),
        "message": log_record.get("message", ""),
        "status": log_record.get("level", "INFO").lower(),
        "timestamp": log_record.get("timestamp", datetime.utcnow().isoformat()),
    }

    # Add custom attributes
    for key, value in log_record.items():
        if key not in ["service", "level", "message", "timestamp"]:
            datadog_record[key] = value

    return json.dumps(datadog_record)
