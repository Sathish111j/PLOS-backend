"""
PLOS v2.0 - API Endpoints for Journal Parser Service
FastAPI endpoints for journal processing
"""

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shared.gemini.client import ResilientGeminiClient
from shared.kafka.producer import KafkaProducerService
from shared.utils.logger import get_logger

from .dependencies import get_db_session, get_gemini_client, get_kafka_producer
from .orchestrator import JournalParserOrchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/journal", tags=["journal-parser"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class ProcessJournalRequest(BaseModel):
    """Request model for processing a journal entry"""

    user_id: UUID = Field(..., description="User UUID")
    journal_entry_id: UUID = Field(..., description="Journal entry UUID")
    entry_text: str = Field(
        ..., min_length=1, max_length=10000, description="Journal entry text"
    )
    entry_date: datetime = Field(
        default_factory=datetime.utcnow, description="Entry date"
    )


class ExtractionResponse(BaseModel):
    """Response model for extraction results"""

    extraction_id: str
    user_id: str
    journal_entry_id: str
    quality_level: str
    processing_time_ms: int
    extraction_counts: Dict[str, int]
    health_alerts_count: int
    predictions_available: bool
    insights_available: bool


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str
    service: str
    version: str
    timestamp: datetime


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post(
    "/process",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Process journal entry with intelligent extraction",
    description="""
    Process a journal entry through the complete PLOS v2.0 pipeline:
    - Preprocessing (spell correction, time normalization)
    - Multi-tier extraction (explicit, inferred, AI)
    - Context-aware analysis
    - Relationship state tracking
    - Health monitoring
    - Predictive analytics
    - Insights generation
    """,
)
async def process_journal_entry(
    request: ProcessJournalRequest,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> ExtractionResponse:
    """
    Process a journal entry with intelligent extraction
    """
    try:
        logger.info(
            f"Processing journal entry {request.journal_entry_id} for user {request.user_id}"
        )

        # Create orchestrator
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        # Process entry
        result = await orchestrator.process_journal_entry(
            user_id=request.user_id,
            journal_entry_id=request.journal_entry_id,
            entry_text=request.entry_text,
            entry_date=request.entry_date,
        )

        # Build response
        return ExtractionResponse(
            extraction_id=result["extraction_id"],
            user_id=result["user_id"],
            journal_entry_id=result["journal_entry_id"],
            quality_level=result["quality_level"],
            processing_time_ms=result["metadata"]["processing_time_ms"],
            extraction_counts=result["metadata"]["extraction_counts"],
            health_alerts_count=len(result["health_alerts"]),
            predictions_available=bool(result["predictions"]),
            insights_available=bool(result["insights"]),
        )

    except Exception as e:
        logger.error(f"Error processing journal entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process journal entry: {str(e)}",
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint for service monitoring
    """
    return HealthCheckResponse(
        status="healthy",
        service="journal-parser",
        version="2.0.0",
        timestamp=datetime.utcnow(),
    )


@router.get(
    "/metrics",
    summary="Get service metrics",
    description="Get processing metrics and statistics",
)
async def get_metrics(
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> Dict[str, Any]:
    """
    Get service metrics including Gemini API usage
    """
    try:
        metrics = gemini.get_key_metrics()

        return {
            "service": "journal-parser",
            "timestamp": datetime.utcnow().isoformat(),
            "gemini_metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}",
        )
