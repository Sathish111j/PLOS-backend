"""
PLOS - Journal Parser Orchestrator
Simplified pipeline using comprehensive Gemini extraction with normalized storage.
"""

import time
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from context_retrieval import ContextRetrievalEngine
from generalized_extraction import (
    ExtractionResult,
    GapResolver,
    GeminiExtractor,
)
from preprocessing import Preprocessor
from sqlalchemy.ext.asyncio import AsyncSession
from storage_service import StorageService

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

    async def process_journal_entry(
        self,
        user_id: UUID,
        entry_text: str,
        entry_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Process a journal entry through the extraction pipeline.

        Args:
            user_id: User UUID
            entry_text: Raw journal text
            entry_date: Date of the entry (defaults to today)

        Returns:
            Complete extraction results with gaps and metadata
        """
        start_time = time.time()
        entry_date = entry_date or date.today()

        safe_user_id = str(user_id).replace("\n", "")
        logger.info(f"Processing journal for user {safe_user_id} on {entry_date}")

        try:
            # ================================================================
            # STAGE 1: PREPROCESSING
            # ================================================================
            logger.debug("Stage 1: Preprocessing")
            preprocessed_text, preprocessing_data, _ = self.preprocessor.process(
                entry_text
            )

            # ================================================================
            # STAGE 2: CONTEXT RETRIEVAL
            # ================================================================
            logger.debug("Stage 2: Context retrieval")
            # Pass date directly - context_retrieval.py now handles date type consistently
            user_context = await self.context_engine.get_full_context(
                user_id=user_id,
                entry_date=entry_date,  # Pass date directly, not datetime
            )

            baseline = user_context.get("baseline")
            logger.info(
                f"Context: baseline={'yes' if baseline else 'no'}, "
                f"recent_entries={len(user_context.get('recent_entries', []))}"
            )

            # ================================================================
            # STAGE 3: GEMINI EXTRACTION + NORMALIZATION
            # ================================================================
            logger.debug("Stage 3: Gemini extraction")
            extraction: ExtractionResult = await self.extractor.extract_all(
                journal_text=preprocessed_text,
                user_context=user_context,
                entry_date=entry_date,
            )

            logger.info(
                f"Extraction: {len(extraction.activities)} activities, "
                f"{len(extraction.consumptions)} consumptions, "
                f"{len(extraction.gaps)} gaps, quality={extraction.quality}"
            )

            # ================================================================
            # STAGE 4: STORAGE
            # ================================================================
            logger.debug("Stage 4: Storage")
            processing_time_ms = int((time.time() - start_time) * 1000)

            entry_id = await self.storage.store_extraction(
                user_id=user_id,
                entry_date=entry_date,
                raw_entry=preprocessed_text,
                extraction=extraction,
                extraction_time_ms=processing_time_ms,
            )

            logger.info(f"Stored extraction {entry_id}")

            # ================================================================
            # STAGE 5: RESPONSE ASSEMBLY
            # ================================================================
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Format gaps as questions for user
            clarification_questions = []
            if extraction.gaps:
                clarification_questions = self.gap_resolver.format_gaps_for_user(
                    extraction.gaps
                )

            result = {
                "entry_id": str(entry_id),
                "user_id": str(user_id),
                "entry_date": entry_date.isoformat(),
                "quality": extraction.quality,
                # Extraction data
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
                        "time_of_day": c.time_of_day.value if c.time_of_day else None,
                        "quantity": c.quantity,
                        "unit": c.unit,
                    }
                    for c in extraction.consumptions
                ],
                "social": extraction.social,
                "notes": extraction.notes,
                # Gaps requiring user clarification
                "has_gaps": extraction.has_gaps,
                "clarification_questions": clarification_questions,
                # Metadata
                "metadata": {
                    "processing_time_ms": processing_time_ms,
                    "preprocessing": preprocessing_data,
                },
            }

            logger.info(
                f"Processing complete in {processing_time_ms}ms "
                f"(quality: {extraction.quality})"
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
            logger.error(f"Error resolving gap: {e}")
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
            from generalized_extraction import DataGap, GapPriority

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
