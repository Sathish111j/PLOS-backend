"""
PLOS Shared Logger
Centralized logging configuration
"""

import logging
import sys
from typing import Optional

from .config import get_settings


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

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Set log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger
