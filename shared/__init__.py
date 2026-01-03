"""
PLOS Shared Library
Common models, utilities, and clients for all microservices
"""

__version__ = "0.1.0"

from . import models, utils

try:
    from . import kafka  # noqa: F401

    _kafka_available = True
except ImportError:
    _kafka_available = False

__all__ = ["models", "utils"]

if _kafka_available:
    __all__.append("kafka")
