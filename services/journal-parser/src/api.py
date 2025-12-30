"""
PLOS - API Endpoints for Journal Parser Service
FastAPI endpoints for journal processing with gap detection and clarification.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
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
    entry_text: str = Field(
        ..., min_length=1, max_length=10000, description="Journal entry text"
    )
    entry_date: Optional[date] = Field(
        default=None, description="Entry date (defaults to today)"
    )


class ActivityResponse(BaseModel):
    """Activity in extraction response"""

    name: str
    category: str
    duration_minutes: Optional[int] = None
    time_of_day: Optional[str] = None
    intensity: Optional[str] = None
    calories: Optional[int] = None


class ConsumptionResponse(BaseModel):
    """Consumption in extraction response"""

    name: str
    type: str
    meal_type: Optional[str] = None
    time_of_day: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None


class ClarificationQuestion(BaseModel):
    """A question for the user to clarify ambiguous data"""

    question: str
    context: Optional[str] = None
    category: str
    priority: str
    suggestions: Optional[List[str]] = None


class ExtractionResponse(BaseModel):
    """Response model for extraction results"""

    entry_id: str
    user_id: str
    entry_date: str
    quality: str

    # Extracted data
    sleep: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    activities: List[ActivityResponse] = []
    consumptions: List[ConsumptionResponse] = []
    social: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None

    # Gaps requiring clarification
    has_gaps: bool = False
    clarification_questions: List[ClarificationQuestion] = []

    # Metadata
    processing_time_ms: int


class ResolveGapRequest(BaseModel):
    """Request to resolve a clarification gap"""

    gap_id: UUID = Field(..., description="Gap UUID to resolve")
    user_response: str = Field(..., description="User's answer to the question")


class ResolveParagraphRequest(BaseModel):
    """Request to resolve multiple gaps with a paragraph response"""

    user_id: UUID = Field(..., description="User UUID")
    entry_id: UUID = Field(..., description="Entry UUID with gaps to resolve")
    user_paragraph: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's natural language response answering clarification questions",
    )


class ResolveParagraphResponse(BaseModel):
    """Response after resolving gaps with paragraph"""

    entry_id: str
    resolved_count: int
    remaining_count: int
    remaining_questions: List[ClarificationQuestion] = []
    updated_activities: List[ActivityResponse] = []
    updated_consumptions: List[ConsumptionResponse] = []
    prompt_for_remaining: Optional[str] = None


class ResolveGapResponse(BaseModel):
    """Response after resolving a gap"""

    status: str
    gap_id: str
    response: str


class PendingGap(BaseModel):
    """A pending gap that needs user clarification"""

    gap_id: str
    field: str
    question: str
    context: Optional[str] = None
    priority: str
    raw_value: Optional[str] = None
    created_at: str
    entry_date: Optional[str] = None


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
    Process a journal entry through the PLOS extraction pipeline:
    - Preprocessing (spell correction, normalization)
    - Context retrieval (user baseline, patterns)
    - Gemini AI extraction with normalization
    - Gap detection for ambiguous entries
    - Controlled vocabulary resolution
    - Storage with alias learning

    Returns extracted data plus any clarification questions for ambiguous entries.
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
        safe_user_id = str(request.user_id).replace("\n", "")
        logger.info(f"Processing journal for user {safe_user_id}")

        # Create orchestrator
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        # Process entry
        result = await orchestrator.process_journal_entry(
            user_id=request.user_id,
            entry_text=request.entry_text,
            entry_date=request.entry_date,
        )

        # Build response
        return ExtractionResponse(
            entry_id=result["entry_id"],
            user_id=result["user_id"],
            entry_date=result["entry_date"],
            quality=result["quality"],
            sleep=result.get("sleep"),
            metrics=result.get("metrics"),
            activities=[ActivityResponse(**a) for a in result.get("activities", [])],
            consumptions=[
                ConsumptionResponse(**c) for c in result.get("consumptions", [])
            ],
            social=result.get("social"),
            notes=result.get("notes"),
            has_gaps=result.get("has_gaps", False),
            clarification_questions=[
                ClarificationQuestion(**q)
                for q in result.get("clarification_questions", [])
            ],
            processing_time_ms=result["metadata"]["processing_time_ms"],
        )

    except Exception as e:
        logger.error(f"Error processing journal entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process journal entry: {str(e)}",
        )


@router.post(
    "/resolve-gap",
    response_model=ResolveGapResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a clarification gap",
    description="Provide an answer to a clarification question from extraction.",
)
async def resolve_gap(
    request: ResolveGapRequest,
    user_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> ResolveGapResponse:
    """
    Resolve a clarification gap with user's response
    """
    try:
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        result = await orchestrator.resolve_gap(
            user_id=user_id,
            gap_id=request.gap_id,
            user_response=request.user_response,
        )

        return ResolveGapResponse(
            status=result["status"],
            gap_id=result["gap_id"],
            response=result["response"],
        )

    except Exception as e:
        logger.error(f"Error resolving gap: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve gap: {str(e)}",
        )


@router.post(
    "/resolve-paragraph",
    response_model=ResolveParagraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve gaps with a paragraph response",
    description="""
    Resolve multiple clarification gaps using a natural language paragraph.

    Instead of answering each question individually, the user can respond naturally:
    "I played badminton for about 45 minutes in the morning. Had idli and coffee
    for breakfast around 9am. The meeting was with my colleague Rahul."

    Gemini will parse the response and extract answers to all pending questions.
    Returns remaining gaps if some questions are still unanswered.
    """,
)
async def resolve_gaps_with_paragraph(
    request: ResolveParagraphRequest,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> ResolveParagraphResponse:
    """
    Resolve multiple gaps with a paragraph response using Gemini
    """
    try:
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        result = await orchestrator.resolve_gaps_with_paragraph(
            user_id=request.user_id,
            entry_id=request.entry_id,
            user_paragraph=request.user_paragraph,
        )

        return ResolveParagraphResponse(
            entry_id=result["entry_id"],
            resolved_count=result["resolved_count"],
            remaining_count=result["remaining_count"],
            remaining_questions=[
                ClarificationQuestion(**q)
                for q in result.get("remaining_questions", [])
            ],
            updated_activities=[
                ActivityResponse(**a) for a in result.get("updated_activities", [])
            ],
            updated_consumptions=[
                ConsumptionResponse(**c) for c in result.get("updated_consumptions", [])
            ],
            prompt_for_remaining=result.get("prompt_for_remaining"),
        )

    except Exception as e:
        logger.error(f"Error resolving gaps with paragraph: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve gaps: {str(e)}",
        )


@router.get(
    "/pending-gaps/{user_id}",
    response_model=List[PendingGap],
    status_code=status.HTTP_200_OK,
    summary="Get pending clarification gaps",
    description="Get all pending gaps that need user clarification.",
)
async def get_pending_gaps(
    user_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> List[PendingGap]:
    """
    Get all pending clarification gaps for a user
    """
    try:
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        gaps = await orchestrator.get_pending_gaps(user_id)

        return [
            PendingGap(
                gap_id=str(g["gap_id"]),
                field=g["field"],
                question=g["question"],
                context=g.get("context"),
                priority=g["priority"],
                raw_value=g.get("raw_value"),
                created_at=g["created_at"],
                entry_date=g.get("entry_date"),
            )
            for g in gaps
        ]

    except Exception as e:
        logger.error(f"Error getting pending gaps: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending gaps: {str(e)}",
        )


@router.get(
    "/activities/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Get user activities",
    description="Get activities for a user with optional filters.",
)
async def get_user_activities(
    user_id: UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> List[Dict[str, Any]]:
    """
    Get user activities with optional filters
    """
    try:
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        return await orchestrator.get_user_activities(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            category=category,
        )

    except Exception as e:
        logger.error(f"Error getting activities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activities: {str(e)}",
        )


@router.get(
    "/activity-summary/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Get activity summary",
    description="Get activity summary by category for a user.",
)
async def get_activity_summary(
    user_id: UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> Dict[str, Any]:
    """
    Get activity summary for a user
    """
    try:
        orchestrator = JournalParserOrchestrator(
            db_session=db, kafka_producer=kafka, gemini_client=gemini
        )

        return await orchestrator.get_activity_summary(user_id, days)

    except Exception as e:
        logger.error(f"Error getting activity summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity summary: {str(e)}",
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
        version="1.0.0",
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
