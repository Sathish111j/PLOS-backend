import uuid as _uuid

from app.api.graph_router import graph_router
from app.api.router import router as api_router
from app.core.config import get_kb_config
from app.dependencies.container import lifespan
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.logger import get_logger
from shared.utils.logging_config import setup_logging

config = get_kb_config()
setup_logging("knowledge-base", log_level=config.log_level, json_logs=True)
logger = get_logger(__name__)

app = FastAPI(
    title="PLOS Knowledge Base",
    description="Knowledge Base service skeleton for ingestion, retrieval, and chat.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Attach a correlation ID to every request for distributed tracing."""
    correlation_id = request.headers.get("X-Correlation-ID", str(_uuid.uuid4()))
    request.state.correlation_id = correlation_id
    logger.info(
        "[REQUEST] %s %s correlation_id=%s",
        request.method,
        request.url.path,
        correlation_id,
    )
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


app.include_router(api_router)
app.include_router(graph_router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "knowledge-base",
        "status": "operational",
        "docs": "/docs",
    }
