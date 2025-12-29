"""
PLOS - Journal Parser Service
Intelligent journal entry processing with comprehensive extraction and gap detection.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.config import get_settings
from shared.utils.logger import get_logger
from shared.utils.logging_config import setup_logging

from .api import router as journal_router
from .db_pool import close_global_pool, initialize_global_pool
from .dependencies import initialize_dependencies, shutdown_dependencies

# Setup structured logging
setup_logging("journal-parser", log_level="INFO", json_logs=True)
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    logger.info("Starting PLOS Journal Parser Service...")

    # Initialize database connection pool
    logger.info("Initializing database connection pool...")
    await initialize_global_pool(settings.postgres_url)

    # Initialize dependencies (Gemini, Kafka producer)
    logger.info("Initializing service dependencies...")
    await initialize_dependencies()

    logger.info("Journal Parser Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Journal Parser Service...")
    await shutdown_dependencies()
    await close_global_pool()
    logger.info("Journal Parser Service stopped")


# Create FastAPI app
app = FastAPI(
    title="PLOS Journal Parser Service",
    description="""
    # PLOS Journal Parser

    **Intelligent Context-Aware Journal Entry Processing**

    ## Processing Pipeline

    1. **Preprocessing** - Text normalization, spell correction
    2. **Context Retrieval** - Load user baseline, patterns
    3. **Gemini AI Extraction** - Comprehensive multi-field extraction
    4. **Normalization** - Controlled vocabulary resolution
    5. **Gap Detection** - Identify ambiguous entries for clarification
    6. **Storage** - Normalized data with alias learning
    7. **Response Assembly** - Rich extraction results with gaps

    ## Key Features

    * **Controlled Vocabulary** - Canonical names for activities, foods
    * **Gap Detection** - LLM asks clarifying questions for ambiguity
    * **Time of Day Tracking** - When activities happened
    * **Alias Learning** - Auto-learns synonyms from user responses
    * **Fuzzy Matching** - Handles typos and variations
    * **Quality Scoring** - Confidence ratings for extractions

    ## Extracted Data

    - **Sleep**: hours, quality, bedtime/waketime
    - **Metrics**: mood, energy, stress scores
    - **Activities**: normalized name, category, duration, time of day
    - **Consumptions**: food/drink, meal type, quantity
    - **Social**: interactions, people mentioned
    - **Notes**: goals, gratitude, free-form

    ## API Endpoints

    - `POST /journal/process` - Process journal entry
    - `POST /journal/resolve-gap` - Resolve clarification gap
    - `GET /journal/pending-gaps/{user_id}` - Get pending gaps
    - `GET /journal/activities/{user_id}` - Get user activities
    - `GET /journal/activity-summary/{user_id}` - Activity summary
    - `GET /journal/health` - Service health check
    - `GET /journal/metrics` - Service metrics
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "journal-parser",
            "description": "Intelligent journal entry processing",
        },
        {"name": "health", "description": "Service health and monitoring"},
    ],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include journal router
app.include_router(journal_router)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint"""
    return {
        "service": "PLOS Journal Parser",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.journal_parser_port,
        reload=settings.debug,
    )
