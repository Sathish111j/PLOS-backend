"""
PLOS v2.0 - Journal Parser Service Orchestrator
Main service that coordinates all extraction, inference, and analytics
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.gemini.client import ResilientGeminiClient
from shared.kafka.producer import KafkaProducerService
from shared.models import (
    ExtractionType,
    FieldMetadata,
    QualityLevel,
)
from shared.utils.logger import get_logger

# Import all our components
from .context_retrieval import ContextRetrievalEngine
from .gemini_extractor import ContextAwareGeminiExtractor
from .health_monitor import HealthMonitor
from .inference_engine import InferenceEngine
from .prediction_engine import PredictionEngine
from .preprocessing import Preprocessor
from .relationship_state_machine import (
    RelationshipImpactCalculator,
    RelationshipStateMachine,
)
from .storage_service import JournalEventPublisher, JournalStorageService

logger = get_logger(__name__)


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================


class JournalParserOrchestrator:
    """
    Main orchestrator that coordinates the complete journal processing pipeline

    Pipeline:
    1. Preprocessing (spell correction, time normalization)
    2. Tier 1: Explicit extraction (regex patterns)
    3. Context retrieval (baseline, patterns, relationship state, etc.)
    4. Tier 2: Inferential rules
    5. Tier 3: Contextual baseline inference
    6. Tier 4: Gemini AI extraction (fills remaining gaps)
    7. Relationship state machine
    8. Health monitoring & anomaly detection
    9. Predictive analytics
    10. Storage & event publishing
    11. Insights generation
    """

    def __init__(
        self,
        db_session: AsyncSession,
        kafka_producer: Optional[KafkaProducerService] = None,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ):
        self.db = db_session
        self.kafka = kafka_producer

        # Initialize components
        self.context_engine = ContextRetrievalEngine(db_session)
        self.preprocessor = Preprocessor()
        self.gemini_extractor = ContextAwareGeminiExtractor(gemini_client)
        self.storage = JournalStorageService(db_session, kafka_producer)
        self.event_publisher = (
            JournalEventPublisher(kafka_producer) if kafka_producer else None
        )

    async def process_journal_entry(
        self,
        user_id: UUID,
        journal_entry_id: UUID,
        entry_text: str,
        entry_date: datetime,
    ) -> Dict[str, Any]:
        """
        Process a complete journal entry through the intelligent extraction pipeline

        Args:
            user_id: User UUID
            journal_entry_id: Journal entry UUID
            entry_text: Raw journal text
            entry_date: Date of the entry

        Returns:
            Complete extraction results with all metadata
        """
        start_time = time.time()
        safe_entry_id = str(journal_entry_id).replace("\n", "")
        safe_user_id = str(user_id).replace("\n", "")
        logger.info(f"Processing journal entry {safe_entry_id} for user {safe_user_id}")

        try:
            # ================================================================
            # PHASE 1: PREPROCESSING
            # ================================================================
            logger.debug("Phase 1: Preprocessing")
            preprocessed_text, preprocessing_data, explicit_extractions = (
                self.preprocessor.process(entry_text)
            )

            logger.info(
                f"Preprocessing complete: {len(explicit_extractions)} explicit extractions, "
                f"{preprocessing_data['spell_corrections']} spelling corrections"
            )

            # ================================================================
            # PHASE 2: CONTEXT RETRIEVAL
            # ================================================================
            logger.debug("Phase 2: Context retrieval")
            user_context = await self.context_engine.get_full_context(
                user_id=user_id, entry_date=entry_date
            )

            baseline = user_context.get("baseline")
            relationship_state = user_context.get("relationship_state")
            sleep_debt = user_context.get("sleep_debt", 0)
            activity_patterns = user_context.get("activity_patterns", [])

            logger.info(
                f"Context retrieved: baseline={baseline is not None}, sleep_debt={sleep_debt:.1f}hrs"
            )

            # ================================================================
            # PHASE 3: INFERENCE ENGINE (TIER 2 & 3)
            # ================================================================
            logger.debug("Phase 3: Inference engine")
            inference_engine = InferenceEngine(
                user_baseline=baseline, context=user_context
            )

            inferred_extractions = inference_engine.infer_missing_fields(
                explicit_extractions=explicit_extractions,
                preprocessed_text=preprocessed_text,
            )

            logger.info(
                f"Inference complete: {len(inferred_extractions)} inferred fields"
            )

            # ================================================================
            # PHASE 4: GEMINI AI EXTRACTION (fills remaining gaps)
            # ================================================================
            logger.debug("Phase 4: Gemini AI extraction")
            gemini_extractions = await self.gemini_extractor.extract_with_context(
                journal_text=preprocessed_text,
                user_context=user_context,
                explicit_extractions=explicit_extractions,
                inferred_extractions=inferred_extractions,
            )

            logger.info(
                f"Gemini extraction complete: {len(gemini_extractions)} AI-extracted fields"
            )

            # ================================================================
            # PHASE 5: MERGE ALL EXTRACTIONS (priority: explicit > inferred > gemini)
            # ================================================================
            all_extractions = {
                **gemini_extractions,  # Lowest priority
                **inferred_extractions,  # Medium priority
                **explicit_extractions,  # Highest priority
            }

            logger.info(f"Total extractions: {len(all_extractions)} fields")

            # ================================================================
            # PHASE 6: RELATIONSHIP STATE MACHINE
            # ================================================================
            logger.debug("Phase 6: Relationship state machine")
            relationship_transition = None

            if relationship_state:
                state_machine = RelationshipStateMachine(relationship_state)

                # Check for state transition
                conflict_mentioned = explicit_extractions.get(
                    "conflict_mentioned",
                    FieldMetadata(
                        value=False,
                        type=ExtractionType.EXPLICIT,
                        confidence=1.0,
                        source="explicit",
                        reasoning="",
                    ),
                ).value

                new_state, trigger = state_machine.detect_transition(
                    entry_text=preprocessed_text, conflict_mentioned=conflict_mentioned
                )

                if new_state:
                    relationship_transition = state_machine.transition_to(
                        new_state, trigger
                    )
                    logger.info(
                        f"Relationship transition: {relationship_transition['from_state']} -> {relationship_transition['to_state']}"
                    )

                    # Store transition
                    await self.storage.store_relationship_event(
                        user_id=user_id,
                        from_state=state_machine.state,
                        to_state=new_state,
                        trigger=trigger,
                        duration_in_previous_state=relationship_transition[
                            "days_in_previous_state"
                        ],
                    )
                else:
                    state_machine.increment_day()

                # Apply relationship impact adjustments
                impact_calculator = RelationshipImpactCalculator()
                adjusted_values = impact_calculator.apply_relationship_impact(
                    base_values=all_extractions,
                    relationship_state=state_machine.state,
                    days_in_state=state_machine.days_in_state,
                )

                all_extractions.update(adjusted_values)
                logger.debug(
                    f"Applied relationship impact: {len(adjusted_values)} fields adjusted"
                )

            # ================================================================
            # PHASE 7: HEALTH MONITORING
            # ================================================================
            logger.debug("Phase 7: Health monitoring")
            health_monitor = HealthMonitor(
                user_baseline=baseline,
                recent_history=user_context.get("recent_entries", []),
            )

            health_alerts = health_monitor.analyze_health(
                extracted_data=all_extractions,
                sleep_debt=sleep_debt,
                relationship_state=relationship_state,
            )

            logger.info(f"Health monitoring: {len(health_alerts)} alerts generated")

            # Store alerts
            if health_alerts:
                await self.storage.store_health_alerts(user_id, health_alerts)

            # ================================================================
            # PHASE 8: PREDICTIVE ANALYTICS
            # ================================================================
            logger.debug("Phase 8: Predictive analytics")
            prediction_engine = PredictionEngine(
                user_baseline=baseline,
                recent_history=user_context.get("recent_entries", []),
                activity_patterns=activity_patterns,
            )

            predictions = prediction_engine.generate_predictions(
                sleep_debt=sleep_debt,
                relationship_state=relationship_state,
                forecast_days=1,
            )

            logger.info("Predictions generated for next day")

            # Store predictions
            await self.storage.store_predictions(
                user_id=user_id,
                target_date=entry_date + timedelta(days=1),
                predictions=predictions,
            )

            # ================================================================
            # PHASE 9: QUALITY SCORING
            # ================================================================
            quality_level = self._calculate_quality_level(all_extractions)

            # ================================================================
            # PHASE 10: STORAGE
            # ================================================================
            logger.debug("Phase 10: Storage")
            processing_time_ms = int((time.time() - start_time) * 1000)

            metadata = {
                "quality_level": quality_level.value,
                "processing_time_ms": processing_time_ms,
                "extraction_counts": {
                    "explicit": len(explicit_extractions),
                    "inferred": len(inferred_extractions),
                    "ai_extracted": len(gemini_extractions),
                    "total": len(all_extractions),
                },
                "preprocessing_stats": preprocessing_data,
                "relationship_transition": relationship_transition,
            }

            extraction_id = await self.storage.store_extraction(
                user_id=user_id,
                journal_entry_id=journal_entry_id,
                entry_text=preprocessed_text,
                extracted_data=all_extractions,
                metadata=metadata,
                baseline=baseline.__dict__ if baseline else None,
            )

            # Commit transaction
            await self.storage.commit()

            logger.info(f"Extraction {extraction_id} stored successfully")

            # ================================================================
            # PHASE 11: EVENT PUBLISHING
            # ================================================================
            if self.event_publisher:
                logger.debug("Phase 11: Event publishing")

                # Mood event
                if (
                    "mood_score" in all_extractions
                    or "mood_score_estimate" in all_extractions
                ):
                    mood_key = (
                        "mood_score"
                        if "mood_score" in all_extractions
                        else "mood_score_estimate"
                    )
                    await self.event_publisher.publish_mood_event(
                        user_id=user_id,
                        mood_score=all_extractions[mood_key].value,
                        mood_trajectory=predictions.get("mood", {}).get(
                            "trajectory", "STABLE"
                        ),
                        context={"relationship_state": relationship_state},
                    )

                # Context update
                await self.event_publisher.publish_context_update(
                    user_id=user_id,
                    context_summary={
                        "sleep_debt": sleep_debt,
                        "relationship_state": relationship_state,
                        "quality_level": quality_level.value,
                    },
                )

                # Predictions
                await self.event_publisher.publish_prediction_event(
                    user_id=user_id, predictions=predictions
                )

            # ================================================================
            # PHASE 12: INSIGHTS GENERATION
            # ================================================================
            logger.debug("Phase 12: Insights generation")
            insights = await self.gemini_extractor.generate_insights(
                all_extractions=all_extractions,
                user_context=user_context,
                predictions=predictions,
                health_alerts=health_alerts,
            )

            # ================================================================
            # RETURN COMPLETE RESULTS
            # ================================================================
            result = {
                "extraction_id": str(extraction_id),
                "user_id": str(user_id),
                "journal_entry_id": str(journal_entry_id),
                "extracted_data": {k: v.__dict__ for k, v in all_extractions.items()},
                "metadata": metadata,
                "health_alerts": health_alerts,
                "predictions": predictions,
                "insights": insights,
                "relationship_transition": relationship_transition,
                "quality_level": quality_level.value,
            }

            logger.info(
                f"Journal entry processed successfully in {processing_time_ms}ms "
                f"(quality: {quality_level.value})"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing journal entry: {e}", exc_info=True)
            await self.storage.rollback()
            raise

    def _calculate_quality_level(
        self, extractions: Dict[str, FieldMetadata]
    ) -> QualityLevel:
        """
        Calculate extraction quality based on field count and confidence
        """
        if not extractions:
            return QualityLevel.LOW

        # Count by type
        explicit_count = sum(
            1 for v in extractions.values() if v.type == ExtractionType.EXPLICIT
        )

        # Average confidence
        avg_confidence = sum(v.confidence for v in extractions.values()) / len(
            extractions
        )

        # Key fields present
        key_fields = ["sleep_hours", "mood_score", "energy_level"]
        key_field_count = sum(
            1 for f in key_fields if f in extractions or f"{f}_estimate" in extractions
        )

        # Scoring
        score = 0

        # Field coverage (max 40 points)
        score += min(len(extractions), 10) * 4

        # Explicit extractions (max 20 points)
        score += min(explicit_count, 5) * 4

        # Confidence (max 20 points)
        score += int(avg_confidence * 20)

        # Key fields (max 20 points)
        score += key_field_count * 7

        # Determine quality
        if score >= 80:
            return QualityLevel.HIGH
        elif score >= 60:
            return QualityLevel.MEDIUM
        else:
            return QualityLevel.LOW
