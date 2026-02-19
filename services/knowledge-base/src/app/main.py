from app.api.router import router as api_router
from app.core.config import get_kb_config
from app.dependencies.container import lifespan
from fastapi import FastAPI
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "knowledge-base",
        "status": "operational",
        "docs": "/docs",
    }
