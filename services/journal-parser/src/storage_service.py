"""
PLOS v2.0 - Storage Layer
Handles database persistence and event publishing for journal extractions
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.kafka.producer import KafkaProducerService
from shared.kafka.topics import KafkaTopic
from shared.models import (
    AlertLevel,
    ExtractionType,
    FieldMetadata,
    RelationshipState,
    Trajectory,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# Import database models (assuming they exist in shared)
# from shared.database.models import (
#     JournalExtraction,
#     UserPattern,
#     RelationshipHistory,
#     ActivityImpact,
#     SleepDebtLog,
#     HealthAlert,
#     Prediction,
# )


# ============================================================================
# STORAGE SERVICE
# ============================================================================

class JournalStorageService:
    """
    Handles persistence of journal extractions and related data
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        kafka_producer: Optional[KafkaProducerService] = None
    ):
        self.db = db_session
        self.kafka = kafka_producer
    
    async def store_extraction(
        self,
        user_id: UUID,
        journal_entry_id: UUID,
        entry_text: str,
        extracted_data: Dict[str, FieldMetadata],
        metadata: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Store complete journal extraction
        
        Args:
            user_id: User UUID
            journal_entry_id: Original journal entry UUID
            entry_text: Preprocessed entry text
            extracted_data: All extracted fields with metadata
            metadata: Extraction metadata (quality, processing time, etc.)
            baseline: User baseline used for context
        
        Returns:
            extraction_id: UUID of created extraction record
        """
        # Convert extracted_data to storage format
        extraction_dict = {}
        for field, field_meta in extracted_data.items():
            extraction_dict[field] = {
                "value": field_meta.value,
                "type": field_meta.type.value if hasattr(field_meta.type, 'value') else field_meta.type,
                "confidence": field_meta.confidence,
                "source": field_meta.source,
                "reasoning": field_meta.reasoning,
            }
        
        # Prepare INSERT statement
        extraction_record = {
            "user_id": user_id,
            "journal_entry_id": journal_entry_id,
            "entry_text": entry_text,
            "extracted_data": extraction_dict,
            "extraction_metadata": metadata,
            "user_baseline_snapshot": baseline,
            "created_at": datetime.utcnow(),
        }
        
        # Execute INSERT (pseudo-code - adapt to actual ORM)
        # result = await self.db.execute(
        #     insert(JournalExtraction).values(extraction_record).returning(JournalExtraction.id)
        # )
        # extraction_id = result.scalar_one()
        
        # For now, mock the UUID
        from uuid import uuid4
        extraction_id = uuid4()
        
        logger.info(f"Stored extraction {extraction_id} for user {user_id}")
        
        # Publish event
        if self.kafka:
            await self._publish_extraction_event(
                extraction_id=extraction_id,
                user_id=user_id,
                extracted_data=extraction_dict,
                metadata=metadata
            )
        
        return extraction_id
    
    async def update_user_patterns(
        self,
        user_id: UUID,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        day_of_week: Optional[int] = None
    ) -> None:
        """
        Update or insert user pattern
        
        Args:
            user_id: User UUID
            pattern_type: Type of pattern (baseline, day_of_week, activity, etc.)
            pattern_data: Pattern statistics
            day_of_week: Optional day of week (0=Monday, 6=Sunday)
        """
        # Upsert pattern
        pattern_record = {
            "user_id": user_id,
            "pattern_type": pattern_type,
            "day_of_week": day_of_week,
            "pattern_data": pattern_data,
            "sample_size": pattern_data.get("sample_size", 0),
            "last_updated": datetime.utcnow(),
        }
        
        # Execute UPSERT (pseudo-code)
        # await self.db.execute(
        #     insert(UserPattern)
        #     .values(pattern_record)
        #     .on_conflict_do_update(
        #         index_elements=["user_id", "pattern_type", "day_of_week"],
        #         set_={"pattern_data": pattern_data, "last_updated": datetime.utcnow()}
        #     )
        # )
        
        logger.debug(f"Updated {pattern_type} pattern for user {user_id}")
    
    async def store_relationship_event(
        self,
        user_id: UUID,
        from_state: RelationshipState,
        to_state: RelationshipState,
        trigger: str,
        duration_in_previous_state: int
    ) -> None:
        """
        Store relationship state transition
        """
        event_record = {
            "user_id": user_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "transition_trigger": trigger,
            "duration_in_previous_state": duration_in_previous_state,
            "occurred_at": datetime.utcnow(),
        }
        
        # Execute INSERT
        # await self.db.execute(
        #     insert(RelationshipHistory).values(event_record)
        # )
        
        logger.info(f"Stored relationship transition: {from_state.value} -> {to_state.value}")
        
        # Publish event
        if self.kafka:
            await self.kafka.publish(
                topic=KafkaTopic.RELATIONSHIP_EVENTS,
                message={
                    "user_id": str(user_id),
                    "from_state": from_state.value,
                    "to_state": to_state.value,
                    "trigger": trigger,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
    
    async def update_activity_impact(
        self,
        user_id: UUID,
        activity_type: str,
        mood_impact: Optional[float],
        energy_impact: Optional[float],
        sleep_impact: Optional[float],
        occurrence_count: int
    ) -> None:
        """
        Update activity impact correlation matrix
        """
        impact_record = {
            "user_id": user_id,
            "activity_type": activity_type,
            "avg_mood_impact": mood_impact,
            "avg_energy_impact": energy_impact,
            "avg_sleep_impact": sleep_impact,
            "occurrence_count": occurrence_count,
            "last_updated": datetime.utcnow(),
        }
        
        # Upsert
        # await self.db.execute(
        #     insert(ActivityImpact)
        #     .values(impact_record)
        #     .on_conflict_do_update(
        #         index_elements=["user_id", "activity_type"],
        #         set_={
        #             "avg_mood_impact": mood_impact,
        #             "avg_energy_impact": energy_impact,
        #             "avg_sleep_impact": sleep_impact,
        #             "occurrence_count": occurrence_count,
        #             "last_updated": datetime.utcnow(),
        #         }
        #     )
        # )
        
        logger.debug(f"Updated activity impact for {activity_type}")
    
    async def log_sleep_debt(
        self,
        user_id: UUID,
        date: datetime,
        daily_debt: float,
        cumulative_debt: float
    ) -> None:
        """
        Log daily sleep debt
        """
        debt_record = {
            "user_id": user_id,
            "date": date.date(),
            "daily_debt_hours": daily_debt,
            "cumulative_debt_hours": cumulative_debt,
            "logged_at": datetime.utcnow(),
        }
        
        # Insert
        # await self.db.execute(
        #     insert(SleepDebtLog).values(debt_record)
        # )
        
        logger.debug(f"Logged sleep debt: daily={daily_debt:.1f}, cumulative={cumulative_debt:.1f}")
    
    async def store_health_alerts(
        self,
        user_id: UUID,
        alerts: List[Dict[str, Any]]
    ) -> None:
        """
        Store health alerts
        """
        if not alerts:
            return
        
        for alert in alerts:
            alert_record = {
                "user_id": user_id,
                "alert_type": alert["type"],
                "level": alert["level"],
                "message": alert["message"],
                "data": {
                    "value": alert.get("value"),
                    "threshold": alert.get("threshold"),
                    "recommendation": alert.get("recommendation"),
                },
                "created_at": datetime.utcnow(),
            }
            
            # Insert
            # await self.db.execute(
            #     insert(HealthAlert).values(alert_record)
            # )
        
        logger.info(f"Stored {len(alerts)} health alerts")
        
        # Publish high-priority alerts
        if self.kafka:
            critical_alerts = [a for a in alerts if a["level"] in ["CRITICAL", "HIGH"]]
            for alert in critical_alerts:
                await self.kafka.publish(
                    topic=KafkaTopic.HEALTH_ALERTS,
                    message={
                        "user_id": str(user_id),
                        "alert_type": alert["type"],
                        "level": alert["level"],
                        "message": alert["message"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
    
    async def store_predictions(
        self,
        user_id: UUID,
        target_date: datetime,
        predictions: Dict[str, Any]
    ) -> None:
        """
        Store predictions for target date
        """
        prediction_record = {
            "user_id": user_id,
            "target_date": target_date.date(),
            "prediction_type": "daily_forecast",
            "predicted_values": predictions,
            "confidence": predictions.get("mood", {}).get("confidence", 0.5),
            "created_at": datetime.utcnow(),
        }
        
        # Insert
        # await self.db.execute(
        #     insert(Prediction).values(prediction_record)
        # )
        
        logger.debug(f"Stored predictions for {target_date.date()}")
    
    async def _publish_extraction_event(
        self,
        extraction_id: UUID,
        user_id: UUID,
        extracted_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> None:
        """
        Publish extraction event to Kafka
        """
        event = {
            "extraction_id": str(extraction_id),
            "user_id": str(user_id),
            "extracted_fields": list(extracted_data.keys()),
            "quality_level": metadata.get("quality_level"),
            "processing_time_ms": metadata.get("processing_time_ms"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.kafka.publish(
            topic=KafkaTopic.PARSED_ENTRIES,
            message=event
        )
        
        logger.debug(f"Published extraction event for {extraction_id}")
    
    async def commit(self):
        """Commit database transaction"""
        await self.db.commit()
    
    async def rollback(self):
        """Rollback database transaction"""
        await self.db.rollback()


# ============================================================================
# EVENT PUBLISHER (standalone)
# ============================================================================

class JournalEventPublisher:
    """
    Publishes various journal-related events to Kafka
    """
    
    def __init__(self, kafka_producer: KafkaProducerService):
        self.kafka = kafka_producer
    
    async def publish_mood_event(
        self,
        user_id: UUID,
        mood_score: int,
        mood_trajectory: Trajectory,
        context: Dict[str, Any]
    ) -> None:
        """
        Publish mood event for real-time tracking
        """
        event = {
            "user_id": str(user_id),
            "mood_score": mood_score,
            "trajectory": mood_trajectory.value,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.kafka.publish(
            topic=KafkaTopic.MOOD_EVENTS,
            message=event
        )
    
    async def publish_context_update(
        self,
        user_id: UUID,
        context_summary: Dict[str, Any]
    ) -> None:
        """
        Publish context update event
        """
        event = {
            "user_id": str(user_id),
            "context_summary": context_summary,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.kafka.publish(
            topic=KafkaTopic.CONTEXT_UPDATES,
            message=event
        )
    
    async def publish_prediction_event(
        self,
        user_id: UUID,
        predictions: Dict[str, Any]
    ) -> None:
        """
        Publish predictions for downstream services
        """
        event = {
            "user_id": str(user_id),
            "predictions": predictions,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.kafka.publish(
            topic=KafkaTopic.PREDICTIONS,
            message=event
        )
