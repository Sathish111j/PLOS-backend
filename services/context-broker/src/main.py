"""
PLOS Context Broker - Main Application
FastAPI service for managing user context (single source of truth)
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from uuid import UUID
from typing import Optional
import sys
sys.path.append('/app')

from shared.models.context import UserContext, ContextUpdate
from shared.utils.logger import get_logger
from shared.utils.config import get_settings
from .context_engine import ContextEngine
from .state_manager import StateManager
from .cache_manager import CacheManager

logger = get_logger(__name__)
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


# FastAPI app
app = FastAPI(
    title="PLOS Context Broker",
    description="Single source of truth for user context and state",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "context-broker",
        "version": "0.1.0"
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # TODO: Implement Prometheus metrics
    return {"message": "Metrics endpoint - implement Prometheus"}


# ============================================================================
# CONTEXT ENDPOINTS
# ============================================================================

@app.get("/context/{user_id}", response_model=UserContext)
async def get_user_context(user_id: UUID):
    """
    Get complete user context
    
    Returns real-time aggregated state from cache + database
    """
    try:
        context = await context_engine.get_context(user_id)
        if not context:
            raise HTTPException(status_code=404, detail="User context not found")
        return context
    except Exception as e:
        logger.error(f"Error fetching context for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/context/update")
async def update_context(update: ContextUpdate):
    """
    Update user context
    
    Processes context updates from various services
    """
    try:
        await context_engine.update_context(update)
        return {"status": "success", "user_id": str(update.user_id)}
    except Exception as e:
        logger.error(f"Error updating context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/context/{user_id}/summary")
async def get_context_summary(user_id: UUID):
    """Get lightweight context summary"""
    try:
        summary = await context_engine.get_summary(user_id)
        return summary
    except Exception as e:
        logger.error(f"Error fetching summary for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/context/{user_id}/invalidate")
async def invalidate_cache(user_id: UUID):
    """Invalidate cache for user (force refresh)"""
    try:
        await cache_manager.invalidate(user_id)
        return {"status": "success", "message": "Cache invalidated"}
    except Exception as e:
        logger.error(f"Error invalidating cache for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.get("/admin/stats")
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
