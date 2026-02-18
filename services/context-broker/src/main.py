"""
PLOS Context Broker - Main Application
FastAPI service for managing user context (single source of truth)
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.api.router import router as api_router
from src.core.metrics import metrics
from src.dependencies.container import lifespan

from shared.utils.errors import (
    ErrorResponse,
    PLOSException,
    build_error_response,
)
from shared.utils.logger import get_logger
from shared.utils.logging_config import setup_logging
from shared.utils.unified_config import get_unified_settings

settings = get_unified_settings()

# Setup structured logging
setup_logging("context-broker", log_level=settings.log_level, json_logs=True)
logger = get_logger(__name__)

# FastAPI app with comprehensive documentation
app = FastAPI(
    title="PLOS Context Broker",
    description="""
    # PLOS Context Broker API

    Single source of truth for real-time user context and state management.

    ## Features

    * **Real-time Context** - Get aggregated user state in <100ms
    * **Cache-First Strategy** - Redis cache for ultra-fast retrieval
    * **Event-Driven Updates** - Kafka integration for async updates
    * **Rolling Metrics** - 7-day averages for health/productivity

    ## Authentication

    All endpoints (except /health) require JWT authentication.
    Pass token in `Authorization: Bearer <token>` header.

    ## Error Codes

    - `CONTEXT_NOT_FOUND` (404) - User context doesn't exist
    - `VALIDATION_ERROR` (400) - Invalid request data
    - `CACHE_CONNECTION_ERROR` (500) - Redis unavailable
    - `DB_QUERY_ERROR` (500) - Database query failed

    ## Rate Limits

    - Anonymous: 100 requests/minute
    - Authenticated: 1000 requests/minute
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Health", "description": "Service health and status endpoints"},
        {"name": "Context", "description": "User context management operations"},
        {"name": "Admin", "description": "Administrative and monitoring endpoints"},
    ],
    responses={
        400: {"model": ErrorResponse, "description": "Validation Error"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PLOSException)
async def plos_exception_handler(request: Request, exc: PLOSException):
    """Handle custom PLOS exceptions"""
    metrics.log_event(
        "exception_occurred",
        {"error_code": exc.error_code, "status_code": exc.status_code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(exc).model_dump(),
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request timing and logging"""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000  # Convert to ms

    # Log API call metrics
    metrics.log_api_call(
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration_ms=process_time,
    )

    response.headers["X-Process-Time-Ms"] = str(round(process_time, 2))
    return response


app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
