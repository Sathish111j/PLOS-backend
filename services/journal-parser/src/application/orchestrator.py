"""
PLOS - Journal Parser Orchestrator
Simplified pipeline using comprehensive Gemini extraction with normalized storage.
"""

import time
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from application.context_retrieval import ContextRetrievalEngine
from application.extraction.generalized_extraction import (
    ExtractionResult,
    GapResolver,
    GeminiExtractor,
)
from application.preprocessing import Preprocessor
from infrastructure.storage.service import StorageService
from sqlalchemy.ext.asyncio import AsyncSession

from shared.gemini.client import ResilientGeminiClient
from shared.kafka.producer import KafkaProducerService
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class JournalParserOrchestrator:
    """
    Journal parsing orchestrator that:
    1. Preprocesses text
    2. Retrieves user context
    3. Uses Gemini for comprehensive extraction
    4. Normalizes to controlled vocabulary
    5. Detects gaps for clarification
    6. Stores in normalized tables
    7. Generates insights

    Pipeline stages:
    1. Preprocessing
    2. Context Retrieval
    3. Gemini Extraction
    4. Normalization + Gap Detection
    5. Storage
    6. Response Assembly
    """

    def __init__(
        self,
        db_session: AsyncSession,
        kafka_producer: Optional[KafkaProducerService] = None,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ):
        self.db = db_session
        self.kafka = kafka_producer
        self.gemini_client = gemini_client or ResilientGeminiClient()

        # Initialize components
        self.preprocessor = Preprocessor()
        self.context_engine = ContextRetrievalEngine(db_session)
        self.extractor = GeminiExtractor(self.gemini_client)
        self.gap_resolver = GapResolver(self.gemini_client)
        self.storage = StorageService(db_session, kafka_producer)

    def _log_stage(self, title: str) -> None:
        logger.info("=" * 60)
        logger.info(title)
        logger.info("=" * 60)

    async def _preprocess_entry(self, entry_text: str) -> tuple[str, Dict[str, Any]]:
        self._log_stage("STAGE 1: PREPROCESSING")
        logger.info(f"Input text ({len(entry_text)} chars): {entry_text[:200]}...")

        preprocessed_text, preprocessing_data, _ = self.preprocessor.process(entry_text)
        logger.info(f"Preprocessed text: {preprocessed_text[:200]}...")
        logger.info(f"Preprocessing stats: {preprocessing_data}")

        return preprocessed_text, preprocessing_data

    async def _retrieve_context(
        self, user_id: UUID, entry_date: date
    ) -> Dict[str, Any]:
        self._log_stage("STAGE 2: CONTEXT RETRIEVAL")
        user_context = await self.context_engine.get_full_context(
            user_id=user_id,
            entry_date=entry_date,
        )

        baseline = user_context.get("baseline")
        logger.info(
            "Context retrieved: "
            f"baseline={'yes' if baseline else 'no'}, "
            f"recent_entries={len(user_context.get('recent_entries', []))}, "
            f"known_aliases={len(user_context.get('known_aliases', {}))}"
        )

        return user_context

    async def _extract_with_gemini(
        self,
        *,
        preprocessed_text: str,
        user_context: Dict[str, Any],
        entry_date: date,
        detect_gaps: bool,
    ) -> ExtractionResult:
        self._log_stage("STAGE 3: GEMINI EXTRACTION + NORMALIZATION")
        logger.info("Calling Gemini AI for extraction...")
        logger.info(f"Gap detection: {'ENABLED' if detect_gaps else 'DISABLED'}")

        extraction = await self.extractor.extract_all(
            journal_text=preprocessed_text,
            user_context=user_context,
            entry_date=entry_date,
            detect_gaps=detect_gaps,
        )

        logger.info("Extraction complete!")
        logger.info(f"  - Quality: {extraction.quality}")
        logger.info(f"  - Sleep: {extraction.sleep}")
        logger.info(f"  - Metrics: {extraction.metrics}")
        logger.info(f"  - Activities ({len(extraction.activities)}):")
        for i, activity in enumerate(extraction.activities):
            logger.info(
                f"      [{i+1}] {activity.raw_name} -> {activity.canonical_name} "
                f"({activity.category}, {activity.duration_minutes}min)"
            )
        logger.info(f"  - Consumptions ({len(extraction.consumptions)}):")
        for i, consumption in enumerate(extraction.consumptions):
            logger.info(
                f"      [{i+1}] {consumption.raw_name} -> {consumption.canonical_name} "
                f"({consumption.consumption_type}, {consumption.meal_type})"
            )
        logger.info(f"  - Gaps requiring clarification: {len(extraction.gaps)}")
        for i, gap in enumerate(extraction.gaps):
            logger.info(f"      [{i+1}] {gap.field_category}: {gap.question}")

        return extraction

    async def _store_extraction(
        self,
        *,
        user_id: UUID,
        entry_date: date,
        preprocessed_text: str,
        extraction: ExtractionResult,
        require_complete: bool,
        processing_time_ms: int,
    ) -> tuple[Optional[UUID], bool]:
        self._log_stage("STAGE 4: STORAGE")

        if require_complete and extraction.has_gaps:
            logger.info("SKIPPING STORAGE: require_complete=True and gaps exist")
            logger.info(
                "User must answer clarification questions before data is stored"
            )
            return None, False

        entry_id = await self.storage.store_extraction(
            user_id=user_id,
            entry_date=entry_date,
            raw_entry=preprocessed_text,
            extraction=extraction,
            extraction_time_ms=processing_time_ms,
        )
        logger.info(f"Stored extraction with entry_id: {entry_id}")
        logger.info(
            "Data saved to database tables: journal_entries, activities, consumptions"
        )

        return entry_id, True

    def _build_response(
        self,
        *,
        user_id: UUID,
        entry_date: date,
        extraction: ExtractionResult,
        entry_id: Optional[UUID],
        stored: bool,
        clarification_questions: List[Dict[str, Any]],
        processing_time_ms: int,
        preprocessing_data: Dict[str, Any],
        detect_gaps: bool,
        require_complete: bool,
    ) -> Dict[str, Any]:
        self._log_stage("STAGE 5: RESPONSE ASSEMBLY")

        return {
            "entry_id": str(entry_id) if entry_id else None,
            "user_id": str(user_id),
            "entry_date": entry_date.isoformat(),
            "quality": extraction.quality,
            "stored": stored,
            "sleep": extraction.sleep,
            "metrics": extraction.metrics,
            "activities": [
                {
                    "name": a.canonical_name or a.raw_name,
                    "category": a.category,
                    "duration_minutes": a.duration_minutes,
                    "time_of_day": a.time_of_day.value if a.time_of_day else None,
                    "intensity": a.intensity,
                    "calories": a.calories_burned,
                }
                for a in extraction.activities
            ],
            "consumptions": [
                {
                    "name": c.canonical_name or c.raw_name,
                    "type": c.consumption_type,
                    "meal_type": c.meal_type,
                    "food_category": c.food_category,
                    "time_of_day": c.time_of_day.value if c.time_of_day else None,
                    "quantity": c.quantity,
                    "unit": c.unit,
                    "calories": c.calories,
                    "protein_g": c.protein_g,
                    "carbs_g": c.carbs_g,
                    "fat_g": c.fat_g,
                }
                for c in extraction.consumptions
            ],
            "social": (
                {"interactions": extraction.social} if extraction.social else None
            ),
            "notes": {"items": extraction.notes} if extraction.notes else None,
            "locations": (
                [
                    {
                        "location_name": loc.get("location_name"),
                        "location_type": loc.get("location_type"),
                        "time_of_day": loc.get("time_of_day"),
                        "duration_minutes": loc.get("duration_minutes"),
                        "activity_context": loc.get("activity_context"),
                    }
                    for loc in extraction.locations
                ]
                if extraction.locations
                else []
            ),
            "health": (
                [
                    {
                        "symptom_type": h.get("symptom_type"),
                        "body_part": h.get("body_part"),
                        "severity": h.get("severity"),
                        "duration_minutes": h.get("duration_minutes"),
                        "time_of_day": h.get("time_of_day"),
                        "possible_cause": h.get("possible_cause"),
                        "medication_taken": h.get("medication_taken"),
                    }
                    for h in extraction.health
                ]
                if extraction.health
                else []
            ),
            "has_gaps": extraction.has_gaps,
            "clarification_questions": clarification_questions,
            "metadata": {
                "processing_time_ms": processing_time_ms,
                "preprocessing": preprocessing_data,
                "detect_gaps": detect_gaps,
                "require_complete": require_complete,
            },
        }

    async def process_journal_entry(
        self,
        user_id: UUID,
        entry_text: str,
        entry_date: Optional[date] = None,
        detect_gaps: bool = True,
        require_complete: bool = False,
    ) -> Dict[str, Any]:
        """
        Process a journal entry through the extraction pipeline.

        Args:
            user_id: User UUID
            entry_text: Raw journal text
            entry_date: Date of the entry (defaults to today)
            detect_gaps: If True, detects ambiguous data and generates clarification questions
            require_complete: If True, do not store data until all gaps are resolved

        Returns:
            Complete extraction results with gaps and metadata
        """
        start_time = time.time()
        entry_date = entry_date or date.today()

        safe_user_id = str(user_id).replace("\n", "")
        logger.info(f"Processing journal for user {safe_user_id} on {entry_date}")
        logger.info(
            f"Options: detect_gaps={detect_gaps}, require_complete={require_complete}"
        )

        try:
            preprocessed_text, preprocessing_data = await self._preprocess_entry(
                entry_text
            )

            user_context = await self._retrieve_context(user_id, entry_date)

            extraction = await self._extract_with_gemini(
                preprocessed_text=preprocessed_text,
                user_context=user_context,
                entry_date=entry_date,
                detect_gaps=detect_gaps,
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            entry_id, stored = await self._store_extraction(
                user_id=user_id,
                entry_date=entry_date,
                preprocessed_text=preprocessed_text,
                extraction=extraction,
                require_complete=require_complete,
                processing_time_ms=processing_time_ms,
            )

            clarification_questions = []
            if extraction.gaps:
                if stored and entry_id:
                    stored_gaps = await self.storage.get_entry_gaps(entry_id)
                    clarification_questions = [
                        {
                            "gap_id": str(gap["gap_id"]),
                            "question": gap["question"],
                            "context": gap["context"],
                            "category": gap["field_category"],
                            "priority": (
                                "high"
                                if gap.get("priority") == 1
                                else "medium" if gap.get("priority") == 2 else "low"
                            ),
                        }
                        for gap in stored_gaps
                    ]
                else:
                    clarification_questions = self.gap_resolver.format_gaps_for_user(
                        extraction.gaps
                    )
                logger.info(
                    f"Generated {len(clarification_questions)} clarification questions"
                )

            result = self._build_response(
                user_id=user_id,
                entry_date=entry_date,
                extraction=extraction,
                entry_id=entry_id,
                stored=stored,
                clarification_questions=clarification_questions,
                processing_time_ms=processing_time_ms,
                preprocessing_data=preprocessing_data,
                detect_gaps=detect_gaps,
                require_complete=require_complete,
            )

            logger.info("=" * 60)
            logger.info("PROCESSING COMPLETE")
            logger.info("=" * 60)
            logger.info(
                f"Total processing time: {processing_time_ms}ms, "
                f"Quality: {extraction.quality}, "
                f"Has gaps: {extraction.has_gaps}"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing journal: {e}", exc_info=True)
            raise

    async def resolve_gap(
        self,
        user_id: UUID,
        gap_id: UUID,
        user_response: str,
    ) -> Dict[str, Any]:
        """
        Resolve a clarification gap with user's response.

        Args:
            user_id: User UUID
            gap_id: Gap UUID to resolve
            user_response: User's answer to the clarification question

        Returns:
            Updated extraction data
        """
        logger.info(f"ORCHESTRATOR: Starting gap resolution for {gap_id}")
        try:
            # Update the gap in storage
            await self.storage.resolve_gap(gap_id, user_response)
            logger.info(f"Resolved gap {gap_id} for user {user_id}")

            return {
                "status": "resolved",
                "gap_id": str(gap_id),
                "response": user_response,
            }

        except Exception as e:
            logger.error(f"Error resolving gap {gap_id}: {e}", exc_info=True)
            raise

    async def resolve_gaps_with_paragraph(
        self,
        user_id: UUID,
        entry_id: UUID,
        user_paragraph: str,
    ) -> Dict[str, Any]:
        """
        Resolve multiple gaps with a natural language paragraph response.

        Gemini parses the paragraph to extract answers to pending questions.
        This allows users to respond naturally instead of one question at a time.

        Args:
            user_id: User UUID
            entry_id: Entry UUID with gaps to resolve
            user_paragraph: User's natural language response

        Returns:
            Resolution results with remaining gaps if any
        """
        try:
            # Get pending gaps for this entry
            pending_gaps = await self.storage.get_entry_gaps(entry_id)

            if not pending_gaps:
                return {
                    "entry_id": str(entry_id),
                    "resolved_count": 0,
                    "remaining_count": 0,
                    "remaining_questions": [],
                    "updated_activities": [],
                    "updated_consumptions": [],
                    "prompt_for_remaining": None,
                }

            # Convert to DataGap objects
            from application.extraction.generalized_extraction import (
                DataGap,
                GapPriority,
            )

            gaps = []
            for g in pending_gaps:
                priority = GapPriority.MEDIUM
                if g.get("priority") == 1:
                    priority = GapPriority.HIGH
                elif g.get("priority") == 3:
                    priority = GapPriority.LOW

                gaps.append(
                    DataGap(
                        field_category=g.get("field_category", "other"),
                        question=g.get("question", ""),
                        context=g.get("context", ""),
                        original_mention=g.get("original_mention", ""),
                        priority=priority,
                        suggested_options=g.get("suggested_options", []),
                    )
                )

            # Get current extraction state
            current_extraction = await self.storage.get_extraction_result(entry_id)

            # Use Gemini to resolve gaps from paragraph
            original_gap_count = len(gaps)
            updated_extraction, remaining_gaps = (
                await self.gap_resolver.resolve_gaps_from_paragraph(
                    gaps=gaps,
                    user_paragraph=user_paragraph,
                    original_extraction=current_extraction,
                )
            )

            resolved_count = original_gap_count - len(remaining_gaps)

            # Update storage with resolved gaps and new data
            await self.storage.update_extraction_from_resolution(
                entry_id=entry_id,
                extraction=updated_extraction,
                resolved_gap_count=resolved_count,
            )

            # Format remaining questions
            remaining_questions = self.gap_resolver.format_gaps_for_user(remaining_gaps)

            # Generate prompt for remaining questions
            prompt_for_remaining = None
            if remaining_gaps:
                prompt_for_remaining = self.gap_resolver.format_gaps_as_prompt(
                    remaining_gaps
                )

            logger.info(
                f"Paragraph resolution for entry {entry_id}: "
                f"{resolved_count} resolved, {len(remaining_gaps)} remaining"
            )

            return {
                "entry_id": str(entry_id),
                "resolved_count": resolved_count,
                "remaining_count": len(remaining_gaps),
                "remaining_questions": remaining_questions,
                "updated_activities": [
                    {
                        "name": a.canonical_name or a.raw_name,
                        "category": a.category,
                        "duration_minutes": a.duration_minutes,
                        "time_of_day": a.time_of_day.value if a.time_of_day else None,
                        "intensity": a.intensity,
                        "calories": a.calories_burned,
                    }
                    for a in updated_extraction.activities
                ],
                "updated_consumptions": [
                    {
                        "name": c.canonical_name or c.raw_name,
                        "type": c.consumption_type,
                        "meal_type": c.meal_type,
                        "food_category": c.food_category,
                        "time_of_day": c.time_of_day.value if c.time_of_day else None,
                        "quantity": c.quantity,
                        "unit": c.unit,
                    }
                    for c in updated_extraction.consumptions
                ],
                "prompt_for_remaining": prompt_for_remaining,
            }

        except Exception as e:
            logger.error(f"Error resolving gaps with paragraph: {e}")
            raise

    async def get_pending_gaps(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all pending clarification gaps for a user.

        Args:
            user_id: User UUID

        Returns:
            List of pending gaps with questions
        """
        return await self.storage.get_pending_gaps(user_id)

    async def get_activity_summary(
        self,
        user_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get activity summary for a user.

        Args:
            user_id: User UUID
            days: Number of days to look back

        Returns:
            Activity summary by category
        """
        return await self.storage.get_activity_summary(user_id, days)

    async def get_user_activities(
        self,
        user_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get user activities with optional filters.

        Args:
            user_id: User UUID
            start_date: Start date filter
            end_date: End date filter
            category: Category filter (physical, mental, etc.)

        Returns:
            List of activities
        """
        return await self.storage.get_user_activities(
            user_id, start_date, end_date, category
        )


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================


async def process_journal(
    db_session: AsyncSession,
    user_id: UUID,
    entry_text: str,
    entry_date: Optional[date] = None,
    kafka_producer: Optional[KafkaProducerService] = None,
    gemini_client: Optional[ResilientGeminiClient] = None,
) -> Dict[str, Any]:
    """
    Convenience function to process a journal entry.

    Args:
        db_session: Database session
        user_id: User UUID
        entry_text: Raw journal text
        entry_date: Date of the entry
        kafka_producer: Optional Kafka producer
        gemini_client: Optional Gemini client

    Returns:
        Extraction results
    """
    orchestrator = JournalParserOrchestrator(
        db_session=db_session,
        kafka_producer=kafka_producer,
        gemini_client=gemini_client,
    )
    return await orchestrator.process_journal_entry(user_id, entry_text, entry_date)
