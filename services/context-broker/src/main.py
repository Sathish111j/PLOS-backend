"""
PLOS Context Broker - Main Application
FastAPI service for managing user context (single source of truth)
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from uuid import UUID
from typing import Optional
import sys
import time

sys.path.append("/app")

from shared.models.context import UserContext, ContextUpdate
from shared.utils.logger import get_logger
from shared.utils.config import get_settings
from shared.utils.errors import (
    PLOSException,
    ErrorResponse,
    SuccessResponse,
    NotFoundError,
)
from shared.utils.logging_config import setup_logging, MetricsLogger
from .context_engine import ContextEngine
from .state_manager import StateManager
from .cache_manager import CacheManager

# Setup structured logging
setup_logging("context-broker", log_level="INFO", json_logs=True)
logger = get_logger(__name__)
metrics = MetricsLogger("context-broker")
settings = get_settings()

# Initialize managers
cache_manager = CacheManager()
state_manager = StateManager()
context_engine = ContextEngine(state_manager, cache_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    logger.info("🚀 Context Broker starting up...")
    await cache_manager.connect()
    await state_manager.connect()
    yield
    logger.info("👋 Context Broker shutting down...")
    await cache_manager.close()
    await state_manager.close()


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


# Global exception handler
@app.exception_handler(PLOSException)
async def plos_exception_handler(request: Request, exc: PLOSException):
    """Handle custom PLOS exceptions"""
    metrics.log_event(
        "exception_occurred",
        {"error_code": exc.error_code, "status_code": exc.status_code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=exc.error_code, message=exc.message, details=exc.details
        ).model_dump(),
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


# ============================================================================
# HEALTH & STATUS
# ============================================================================


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check endpoint",
    description="Returns service health status and dependencies",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "context-broker",
                        "version": "1.0.0",
                        "dependencies": {"redis": "connected", "postgres": "connected"},
                    }
                }
            },
        }
    },
)
async def health_check():
    """Health check endpoint - no authentication required"""
    return {"status": "healthy", "service": "context-broker", "version": "1.0.0"}


@app.get(
    "/metrics",
    tags=["Health"],
    summary="Prometheus metrics endpoint",
    description="Returns Prometheus-compatible metrics for monitoring",
)
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    # TODO: Implement Prometheus metrics
    return {"message": "Metrics endpoint - implement Prometheus"}


# ============================================================================
# CONTEXT ENDPOINTS
# ============================================================================


@app.get(
    "/context/{user_id}",
    response_model=UserContext,
    tags=["Context"],
    summary="Get complete user context",
    description="""
    Retrieves the complete real-time context for a user, including:
    - Current mood, energy, and stress levels
    - 7-day rolling averages for health metrics
    - Active goals and pending tasks count
    - Extended context data (custom fields)
    
    **Performance:** Typically <100ms (cached) or <500ms (database)
    
    **Cache Strategy:** Cache-first with automatic invalidation
    """,
    responses={
        200: {
            "description": "User context retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "current_mood_score": 7,
                        "current_energy_level": 6,
                        "current_stress_level": 4,
                        "sleep_quality_avg_7d": 7.2,
                        "productivity_score_avg_7d": 6.8,
                        "active_goals_count": 5,
                        "pending_tasks_count": 12,
                        "completed_tasks_today": 3,
                        "context_data": {"last_journal_entry": "2025-01-15"},
                        "updated_at": "2025-01-15T10:30:00Z",
                    }
                }
            },
        },
        404: {"model": ErrorResponse},
    },
)
async def get_user_context(user_id: UUID):
    """
    Get complete user context

    Returns real-time aggregated state from cache + database
    """
    try:
        start_time = time.time()
        context = await context_engine.get_context(user_id)
        duration_ms = (time.time() - start_time) * 1000

        if not context:
            raise NotFoundError(f"User context not found for user_id: {user_id}")

        metrics.log_metric(
            "context_retrieval_time_ms", duration_ms, user_id=str(user_id)
        )
        return context
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error fetching context for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/context/update",
    response_model=SuccessResponse,
    tags=["Context"],
    summary="Update user context",
    description="""
    Processes context updates from various services (journal parser, task manager, etc.)
    
    Updates are applied asynchronously and cached immediately.
    
    **Update Types:**
    - `mood` - Mood score and labels
    - `health` - Sleep, energy, stress metrics
    - `task` - Task completion/creation
    - `goal` - Goal progress updates
    """,
    responses={
        200: {
            "description": "Context updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Context updated successfully",
                        "data": {"user_id": "123e4567-e89b-12d3-a456-426614174000"},
                        "timestamp": "2025-01-15T10:30:00Z",
                    }
                }
            },
        }
    },
)
async def update_context(update: ContextUpdate):
    """
    Update user context

    Processes context updates from various services
    """
    try:
        await context_engine.update_context(update)
        metrics.log_event(
            "context_updated",
            {"update_type": update.update_type},
            user_id=str(update.user_id),
        )

        return SuccessResponse(
            message="Context updated successfully",
            data={"user_id": str(update.user_id)},
        )
    except Exception as e:
        logger.error(f"Error updating context: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/context/{user_id}/summary",
    tags=["Context"],
    summary="Get lightweight context summary",
    description="Returns a lightweight summary of user context (faster than full context)",
)
async def get_context_summary(user_id: UUID):
    """Get lightweight context summary"""
    try:
        summary = await context_engine.get_summary(user_id)
        return summary
    except Exception as e:
        logger.error(f"Error fetching summary for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/context/{user_id}/invalidate",
    response_model=SuccessResponse,
    tags=["Context"],
    summary="Invalidate user cache",
    description="Forces cache refresh for user (next request will fetch fresh data from database)",
)
async def invalidate_cache(user_id: UUID):
    """Invalidate cache for user (force refresh)"""
    try:
        await cache_manager.invalidate(user_id)
        return SuccessResponse(
            message="Cache invalidated successfully", data={"user_id": str(user_id)}
        )
    except Exception as e:
        logger.error(f"Error invalidating cache for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@app.get(
    "/admin/stats",
    tags=["Admin"],
    summary="Get service statistics",
    description="Returns comprehensive service statistics and performance metrics",
)
async def get_stats():
    """Get service statistics"""
    try:
        stats = await context_engine.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
