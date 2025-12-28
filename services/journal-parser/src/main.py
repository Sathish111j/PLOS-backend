"""
Journal Parser Service - AI-powered journal entry extraction using Gemini API

This service:
1. Consumes journal_entries from Kafka
2. Uses Gemini to extract structured data (mood, health, nutrition, exercise, work, habits)
3. Publishes parsed entries to parsed_entries topic
4. Detects missing information (gap detection)
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from gap_detector import GapDetector
from kafka_handler import KafkaJournalConsumer
from parser_engine import JournalParserEngine

from shared.models.journal import JournalEntry, ParsedJournalEntry
from shared.utils.config import get_settings
from shared.utils.errors import ErrorResponse
from shared.utils.logger import get_logger
from shared.utils.logging_config import MetricsLogger, setup_logging

# Setup structured logging
setup_logging("journal-parser", log_level="INFO", json_logs=True)
logger = get_logger(__name__)
metrics = MetricsLogger("journal-parser")
settings = get_settings()

# Global instances
parser_engine: JournalParserEngine = None
gap_detector: GapDetector = None
kafka_consumer: KafkaJournalConsumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global parser_engine, gap_detector, kafka_consumer

    logger.info("Starting Journal Parser Service...")

    # Initialize components
    parser_engine = JournalParserEngine(
        api_key=settings.gemini_api_key, model=settings.gemini_default_model
    )
    gap_detector = GapDetector(
        api_key=settings.gemini_api_key, model=settings.gemini_default_model
    )

    # Initialize and start Kafka consumer
    kafka_consumer = KafkaJournalConsumer(
        parser_engine=parser_engine, gap_detector=gap_detector
    )
    await kafka_consumer.start()

    logger.info("Journal Parser Service started successfully")

    yield

    # Cleanup
    logger.info("Shutting down Journal Parser Service...")
    if kafka_consumer:
        await kafka_consumer.stop()
    logger.info("Journal Parser Service stopped")


# Create FastAPI app with comprehensive documentation
app = FastAPI(
    title="PLOS Journal Parser Service",
    description="""
    # PLOS Journal Parser API

    AI-powered extraction of structured data from free-form journal entries.

    ## Features

    * **Gemini AI Extraction** - Extract mood, health, nutrition, exercise, work, habits
    * **Gap Detection** - Identify missing information in journal entries
    * **Confidence Scoring** - AI confidence levels for extracted data
    * **Kafka Integration** - Async event processing

    ## AI Models

    - **Default:** gemini-2.5-flash (balanced performance)
    - **Caching:** Enabled (reduces API costs)

    ## Extracted Data

    - Mood (score, labels)
    - Health (sleep, energy, stress)
    - Nutrition (meals, calories, macros)
    - Exercise (type, duration, intensity)
    - Work (productivity, focus, tasks)
    - Habits (tracked habits completion)

    ## Error Codes

    - `PARSING_FAILED` (500) - AI extraction failed
    - `GEMINI_API_ERROR` (500) - Gemini API error
    - `GEMINI_RATE_LIMIT` (429) - Rate limit exceeded
    - `VALIDATION_ERROR` (400) - Invalid journal entry
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Health", "description": "Service health and status"},
        {"name": "Parsing", "description": "Journal parsing operations"},
        {"name": "Gap Detection", "description": "Missing information detection"},
        {"name": "Monitoring", "description": "Service statistics and metrics"},
    ],
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "journal-parser",
        "gemini_model": settings.gemini_default_model,
    }


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    # TODO: Implement Prometheus metrics
    return {"total_parsed": 0, "total_errors": 0, "avg_parse_time": 0}


@app.post("/parse", response_model=ParsedJournalEntry)
async def parse_entry(entry: JournalEntry):
    """
    Parse a single journal entry (for testing/manual parsing)

    Args:
        entry: Journal entry to parse

    Returns:
        ParsedJournalEntry: Extracted structured data
    """
    try:
        logger.info(f"Parsing journal entry: {entry.id}")

        parsed = await parser_engine.parse_entry(entry.content)

        logger.info(f"Successfully parsed entry: {entry.id}")
        return parsed

    except Exception as e:
        logger.error(f"Error parsing entry {entry.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect-gaps")
async def detect_gaps(entry: JournalEntry):
    """
    Detect missing information in a journal entry

    Args:
        entry: Journal entry to analyze

    Returns:
        List of missing metrics/information
    """
    try:
        logger.info(f"Detecting gaps in entry: {entry.id}")

        gaps = await gap_detector.detect_gaps(entry.content)

        return {
            "entry_id": entry.id,
            "missing_metrics": gaps,
            "completeness_score": 1.0 - (len(gaps) / 10.0),  # Rough estimate
        }

    except Exception as e:
        logger.error(f"Error detecting gaps in entry {entry.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    if not kafka_consumer:
        return {"status": "initializing"}

    return {
        "service": "journal-parser",
        "kafka_consumer": {
            "running": kafka_consumer.running,
            "messages_processed": kafka_consumer.messages_processed,
            "errors": kafka_consumer.errors,
        },
        "parser_engine": {
            "model": settings.gemini_default_model,
            "cache_enabled": settings.use_gemini_caching,
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=8002, reload=False  # Journal Parser port
    )
