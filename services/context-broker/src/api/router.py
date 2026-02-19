"""API endpoints for context broker."""

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from src.core.metrics import metrics
from src.dependencies.container import cache_manager, context_engine

from shared.models.context import ContextUpdate, UserContext
from shared.utils.errors import ErrorResponse, NotFoundError, SuccessResponse
from shared.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
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


@router.get(
    "/metrics",
    tags=["Health"],
    summary="Prometheus metrics endpoint",
    description="Returns Prometheus-compatible metrics for monitoring",
)
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get(
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

    Performance: Typically <100ms (cached) or <500ms (database)

    Cache Strategy: Cache-first with automatic invalidation
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


@router.post(
    "/context/update",
    response_model=SuccessResponse,
    tags=["Context"],
    summary="Update user context",
    description="""
    Processes context updates from various services (journal parser, task manager, etc.)

    Updates are applied asynchronously and cached immediately.

    Update Types:
    - mood - Mood score and labels
    - health - Sleep, energy, stress metrics
    - task - Task completion/creation
    - goal - Goal progress updates
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


@router.get(
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


@router.post(
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


@router.get(
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
