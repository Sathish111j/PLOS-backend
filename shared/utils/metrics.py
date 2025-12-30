"""
PLOS - Observability Metrics
Prometheus metrics for monitoring and observability.
"""

import time
from contextlib import contextmanager
from functools import wraps
from typing import Callable

# Try to import prometheus_client, provide stubs if not available
try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ============================================================================
# METRIC DEFINITIONS
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # Extraction metrics
    ENTRIES_PROCESSED = Counter(
        "journal_entries_processed_total",
        "Total journal entries processed",
        ["status"],  # success, failure
    )

    EXTRACTION_DURATION = Histogram(
        "extraction_duration_seconds",
        "Time spent in extraction pipeline",
        ["stage"],  # preprocessing, context, gemini, storage
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    ACTIVE_EXTRACTIONS = Gauge(
        "active_extractions",
        "Currently processing entries",
    )

    # Gemini API metrics
    GEMINI_REQUESTS = Counter(
        "gemini_api_requests_total",
        "Total Gemini API requests",
        ["model", "status"],
    )

    GEMINI_LATENCY = Histogram(
        "gemini_api_latency_seconds",
        "Gemini API latency",
        ["model"],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )

    GEMINI_TOKENS = Counter(
        "gemini_tokens_total",
        "Total Gemini tokens used",
        ["model", "type"],  # type: input, output
    )

    GEMINI_ERRORS = Counter(
        "gemini_api_errors_total",
        "Gemini API errors",
        ["model", "error_type"],
    )

    # Context retrieval metrics
    CONTEXT_RETRIEVAL_DURATION = Histogram(
        "context_retrieval_duration_seconds",
        "Time to retrieve user context",
        ["source"],  # cache, database
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    )

    CONTEXT_CACHE_HITS = Counter(
        "context_cache_hits_total",
        "Context cache hits",
        ["cache_type"],  # memory, redis
    )

    CONTEXT_CACHE_MISSES = Counter(
        "context_cache_misses_total",
        "Context cache misses",
        ["cache_type"],
    )

    # Database metrics
    DB_QUERY_DURATION = Histogram(
        "db_query_duration_seconds",
        "Database query duration",
        ["operation"],  # select, insert, update, upsert
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    )

    DB_CONNECTIONS_ACTIVE = Gauge(
        "db_connections_active",
        "Active database connections",
    )

    DB_POOL_SIZE = Gauge(
        "db_pool_size",
        "Database connection pool size",
    )

    # Quality metrics
    EXTRACTION_QUALITY = Histogram(
        "extraction_quality_score",
        "Quality score distribution",
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )

    GAPS_DETECTED = Counter(
        "extraction_gaps_detected_total",
        "Data gaps detected in extractions",
        ["category"],  # activity, meal, sleep, etc.
    )

    # Service info
    SERVICE_INFO = Info(
        "plos_service",
        "Service information",
    )

else:
    # Stub implementations when prometheus is not available
    class StubMetric:
        """Stub metric that does nothing"""

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def time(self):
            return _null_context()

        def info(self, *args, **kwargs):
            pass

    ENTRIES_PROCESSED = StubMetric()
    EXTRACTION_DURATION = StubMetric()
    ACTIVE_EXTRACTIONS = StubMetric()
    GEMINI_REQUESTS = StubMetric()
    GEMINI_LATENCY = StubMetric()
    GEMINI_TOKENS = StubMetric()
    GEMINI_ERRORS = StubMetric()
    CONTEXT_RETRIEVAL_DURATION = StubMetric()
    CONTEXT_CACHE_HITS = StubMetric()
    CONTEXT_CACHE_MISSES = StubMetric()
    DB_QUERY_DURATION = StubMetric()
    DB_CONNECTIONS_ACTIVE = StubMetric()
    DB_POOL_SIZE = StubMetric()
    EXTRACTION_QUALITY = StubMetric()
    GAPS_DETECTED = StubMetric()
    SERVICE_INFO = StubMetric()


@contextmanager
def _null_context():
    """Null context manager for stubs"""
    yield


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def track_extraction_time(stage: str):
    """Decorator to track extraction stage timing"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                EXTRACTION_DURATION.labels(stage=stage).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                EXTRACTION_DURATION.labels(stage=stage).observe(duration)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_db_query(operation: str):
    """Decorator to track database query timing"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(operation=operation).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(operation=operation).observe(duration)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def track_gemini_call(model: str = "gemini-2.5-flash"):
    """Context manager to track Gemini API calls"""
    start_time = time.time()
    status = "success"
    try:
        yield
    except Exception as e:
        status = "error"
        error_type = type(e).__name__
        GEMINI_ERRORS.labels(model=model, error_type=error_type).inc()
        raise
    finally:
        duration = time.time() - start_time
        GEMINI_REQUESTS.labels(model=model, status=status).inc()
        GEMINI_LATENCY.labels(model=model).observe(duration)


def record_gemini_tokens(model: str, input_tokens: int, output_tokens: int):
    """Record Gemini token usage"""
    GEMINI_TOKENS.labels(model=model, type="input").inc(input_tokens)
    GEMINI_TOKENS.labels(model=model, type="output").inc(output_tokens)


def record_cache_access(cache_type: str, hit: bool):
    """Record cache access"""
    if hit:
        CONTEXT_CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CONTEXT_CACHE_MISSES.labels(cache_type=cache_type).inc()


def record_extraction_quality(quality_score: float):
    """Record extraction quality score"""
    EXTRACTION_QUALITY.observe(quality_score)


def record_gap_detected(category: str):
    """Record a detected data gap"""
    GAPS_DETECTED.labels(category=category).inc()


def set_service_info(name: str, version: str, environment: str):
    """Set service information"""
    if PROMETHEUS_AVAILABLE:
        SERVICE_INFO.info(
            {
                "name": name,
                "version": version,
                "environment": environment,
            }
        )


# ============================================================================
# METRICS CONTEXT MANAGER
# ============================================================================


class ExtractionMetricsContext:
    """Context manager for tracking extraction metrics"""

    def __init__(self):
        self.start_time = None
        self.stage_times = {}

    def __enter__(self):
        ACTIVE_EXTRACTIONS.inc()
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ACTIVE_EXTRACTIONS.dec()
        if exc_type is None:
            ENTRIES_PROCESSED.labels(status="success").inc()
        else:
            ENTRIES_PROCESSED.labels(status="failure").inc()

    def start_stage(self, stage: str):
        """Mark start of a stage"""
        self.stage_times[stage] = {"start": time.time()}

    def end_stage(self, stage: str):
        """Mark end of a stage and record duration"""
        if stage in self.stage_times:
            duration = time.time() - self.stage_times[stage]["start"]
            EXTRACTION_DURATION.labels(stage=stage).observe(duration)
            self.stage_times[stage]["duration"] = duration
