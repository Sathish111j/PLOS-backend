"""
PLOS - API Endpoints for Journal Parser Service
FastAPI endpoints for journal processing with gap detection and clarification.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from application.orchestrator import JournalParserOrchestrator
from dependencies.providers import (
    get_db_session,
    get_gemini_client,
    get_kafka_producer,
)
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.dependencies import get_current_user
from shared.auth.models import TokenData
from shared.gemini.client import ResilientGeminiClient
from shared.kafka.producer import KafkaProducerService
from shared.utils.logger import get_logger

from .schemas import (
    ActivityResponse,
    ClarificationQuestion,
    ConsumptionResponse,
    ExtractionResponse,
    HealthCheckResponse,
    PendingGap,
    ProcessJournalRequest,
    ResolveGapRequest,
    ResolveGapResponse,
    ResolveParagraphRequest,
    ResolveParagraphResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/journal", tags=["journal-parser"])

# Prometheus metrics
JOURNAL_PROCESS_COUNT = Counter(
    "journal_parser_entries_processed_total",
    "Total number of journal entries processed",
    ["status"],
)
JOURNAL_PROCESS_LATENCY = Histogram(
    "journal_parser_process_latency_seconds", "Journal processing latency in seconds"
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def verify_user_access(current_user: TokenData, target_user_id: UUID) -> None:
    """
    Verify that the authenticated user can access the target user's data.
    For now, users can only access their own data.

    Raises:
        HTTPException 403 if access denied
    """
    if current_user.user_id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data",
        )


def get_orchestrator(
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
) -> JournalParserOrchestrator:
    """Provide an orchestrator with per-request dependencies."""
    return JournalParserOrchestrator(
        db_session=db, kafka_producer=kafka, gemini_client=gemini
    )


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

    **Authentication required**: Uses the authenticated user's ID automatically.
    """,
)
async def process_journal_entry(
    request: ProcessJournalRequest,
    current_user: TokenData = Depends(get_current_user),
    orchestrator: JournalParserOrchestrator = Depends(get_orchestrator),
) -> ExtractionResponse:
    """
    Process a journal entry with intelligent extraction.
    Uses the authenticated user's ID from the JWT token.
    """
    try:
        user_id = current_user.user_id
        safe_user_id = str(user_id).replace("\n", "")
        logger.info(f"API /journal/process - START for user {safe_user_id}")
        logger.info(
            f"Request details: entry_text_length={len(request.entry_text)}, entry_date={request.entry_date}, detect_gaps={request.detect_gaps}, require_complete={request.require_complete}"
        )
        logger.info(f"Entry preview: {request.entry_text[:150]}...")

        # Process entry
        logger.info("Starting orchestrator.process_journal_entry()")
        result = await orchestrator.process_journal_entry(
            user_id=user_id,
            entry_text=request.entry_text,
            entry_date=request.entry_date,
            detect_gaps=request.detect_gaps,
            require_complete=request.require_complete,
        )
        logger.info(
            f"Orchestrator completed: entry_id={result.get('entry_id')}, stored={result.get('stored')}, has_gaps={result.get('has_gaps')}"
        )

        # Build response
        logger.info("Building ExtractionResponse")
        response = ExtractionResponse(
            entry_id=result["entry_id"],
            user_id=result["user_id"],
            entry_date=result["entry_date"],
            quality=result["quality"],
            stored=result.get("stored", True),
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

        logger.info(
            f"API /journal/process - SUCCESS: processed in {result['metadata']['processing_time_ms']}ms"
        )
        logger.info(
            f"Response summary: activities={len(response.activities)}, consumptions={len(response.consumptions)}, gaps={len(response.clarification_questions)}"
        )
        JOURNAL_PROCESS_COUNT.labels(status="success").inc()
        return response

    except HTTPException:
        logger.error("HTTP exception during journal processing")
        JOURNAL_PROCESS_COUNT.labels(status="error").inc()
        raise
    except Exception as e:
        logger.error(f"API /journal/process - FAILED: {e}", exc_info=True)
        JOURNAL_PROCESS_COUNT.labels(status="error").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process journal entry: {str(e)}",
        )


@router.post(
    "/resolve-gap",
    response_model=ResolveGapResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a clarification gap",
    description="Provide an answer to a clarification question from extraction. **Authentication required**.",
)
async def resolve_gap(
    request: ResolveGapRequest,
    current_user: TokenData = Depends(get_current_user),
    orchestrator: JournalParserOrchestrator = Depends(get_orchestrator),
) -> ResolveGapResponse:
    """
    Resolve a clarification gap with user's response.
    Uses the authenticated user's ID from the JWT token.
    """
    try:
        result = await orchestrator.resolve_gap(
            user_id=current_user.user_id,
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

    **Authentication required**.
    """,
)
async def resolve_gaps_with_paragraph(
    request: ResolveParagraphRequest,
    current_user: TokenData = Depends(get_current_user),
    orchestrator: JournalParserOrchestrator = Depends(get_orchestrator),
) -> ResolveParagraphResponse:
    """
    Resolve multiple gaps with a paragraph response using Gemini.
    Uses the authenticated user's ID from the JWT token.
    """
    try:
        result = await orchestrator.resolve_gaps_with_paragraph(
            user_id=current_user.user_id,
            entry_id=request.entry_id,
            user_paragraph=request.user_paragraph,
        )

        def _normalize_text(value: Any, fallback: str) -> str:
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value if item)
            if value is None:
                return fallback
            normalized = str(value).strip()
            return normalized if normalized else fallback

        normalized_activities = []
        for activity in result.get("updated_activities", []):
            normalized = dict(activity)
            normalized["name"] = _normalize_text(normalized.get("name"), "unknown")
            normalized["category"] = _normalize_text(
                normalized.get("category"), "other"
            )
            normalized_activities.append(normalized)

        normalized_consumptions = []
        for consumption in result.get("updated_consumptions", []):
            normalized = dict(consumption)
            normalized["name"] = _normalize_text(normalized.get("name"), "unknown")
            normalized["type"] = _normalize_text(normalized.get("type"), "meal")
            normalized_consumptions.append(normalized)

        return ResolveParagraphResponse(
            entry_id=result["entry_id"],
            resolved_count=result["resolved_count"],
            remaining_count=result["remaining_count"],
            remaining_questions=[
                ClarificationQuestion(**q)
                for q in result.get("remaining_questions", [])
            ],
            updated_activities=[ActivityResponse(**a) for a in normalized_activities],
            updated_consumptions=[
                ConsumptionResponse(**c) for c in normalized_consumptions
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
    "/pending-gaps",
    response_model=List[PendingGap],
    status_code=status.HTTP_200_OK,
    summary="Get pending clarification gaps",
    description="Get all pending gaps that need user clarification. **Authentication required**.",
)
async def get_pending_gaps(
    current_user: TokenData = Depends(get_current_user),
    orchestrator: JournalParserOrchestrator = Depends(get_orchestrator),
) -> List[PendingGap]:
    """
    Get all pending clarification gaps for the authenticated user.
    """
    try:
        gaps = await orchestrator.get_pending_gaps(current_user.user_id)

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
    "/activities",
    status_code=status.HTTP_200_OK,
    summary="Get user activities",
    description="Get activities for the authenticated user with optional filters. **Authentication required**.",
)
async def get_user_activities(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    orchestrator: JournalParserOrchestrator = Depends(get_orchestrator),
) -> List[Dict[str, Any]]:
    """
    Get user activities with optional filters.
    Uses the authenticated user's ID from the JWT token.
    """
    try:
        return await orchestrator.get_user_activities(
            user_id=current_user.user_id,
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
    "/activity-summary",
    status_code=status.HTTP_200_OK,
    summary="Get activity summary",
    description="Get activity summary by category for the authenticated user. **Authentication required**.",
)
async def get_activity_summary(
    days: int = 30,
    current_user: TokenData = Depends(get_current_user),
    orchestrator: JournalParserOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """
    Get activity summary for the authenticated user.
    """
    try:
        return await orchestrator.get_activity_summary(current_user.user_id, days)

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
    description="Get Prometheus-compatible metrics for monitoring",
)
async def get_metrics() -> PlainTextResponse:
    """
    Returns Prometheus-compatible metrics
    """
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
