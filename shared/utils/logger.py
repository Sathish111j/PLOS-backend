"""
PLOS Shared Logger
Centralized logging configuration
"""

import logging
from typing import Optional

from .config import get_settings
from .logging_config import setup_logging


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get configured logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger
    """
    settings = get_settings()
    logger_name = name or settings.service_name

    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    return setup_logging(
        service_name=logger_name,
        log_level=settings.log_level,
        json_logs=False,
    )
