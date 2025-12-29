"""
PLOS Kafka Topics
Centralized topic name definitions using dot notation (standard Kafka practice)
"""


class KafkaTopics:
    """Kafka topic names - using dot notation for consistency"""

    # Journal and Parsing
    JOURNAL_ENTRIES = "plos.journal.entries"
    JOURNAL_ENTRIES_RAW = "plos.journal.entries.raw"
    PARSED_ENTRIES = "plos.journal.parsed"
    JOURNAL_EXTRACTION_COMPLETE = "plos.journal.extraction.complete"

    # Data Extraction
    MOOD_EVENTS = "plos.mood.events"
    HEALTH_EVENTS = "plos.health.events"
    NUTRITION_EVENTS = "plos.nutrition.events"
    EXERCISE_EVENTS = "plos.exercise.events"
    WORK_EVENTS = "plos.work.events"
    HABIT_EVENTS = "plos.habit.events"
    SLEEP_DATA_EXTRACTED = "plos.sleep.data.extracted"
    MOOD_DATA_EXTRACTED = "plos.mood.data.extracted"

    # Context and State
    CONTEXT_UPDATES = "plos.context.updates"

    # Relationship State
    RELATIONSHIP_EVENTS = "plos.relationship.events"
    RELATIONSHIP_STATE_CHANGED = "plos.relationship.state.changed"

    # Health Alerts
    HEALTH_ALERTS = "plos.health.alerts"
    HEALTH_ALERTS_TRIGGERED = "plos.health.alerts.triggered"

    # Predictions
    PREDICTIONS = "plos.predictions"
    PREDICTIONS_GENERATED = "plos.predictions.generated"

    # Tasks and Goals
    TASK_EVENTS = "plos.task.events"
    GOAL_EVENTS = "plos.goal.events"

    # Calendar
    CALENDAR_EVENTS = "plos.calendar.events"

    # Notifications
    NOTIFICATION_EVENTS = "plos.notification.events"

    # Knowledge
    KNOWLEDGE_EVENTS = "plos.knowledge.events"

    # AI Agents
    INSIGHT_REQUESTS = "plos.insight.requests"
    SCHEDULING_REQUESTS = "plos.scheduling.requests"

    # General Event Stream
    EVENT_STREAM = "plos.event.stream"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Get list of all topic names"""
        return [
            cls.JOURNAL_ENTRIES,
            cls.JOURNAL_ENTRIES_RAW,
            cls.PARSED_ENTRIES,
            cls.JOURNAL_EXTRACTION_COMPLETE,
            cls.MOOD_EVENTS,
            cls.HEALTH_EVENTS,
            cls.NUTRITION_EVENTS,
            cls.EXERCISE_EVENTS,
            cls.WORK_EVENTS,
            cls.HABIT_EVENTS,
            cls.SLEEP_DATA_EXTRACTED,
            cls.MOOD_DATA_EXTRACTED,
            cls.CONTEXT_UPDATES,
            cls.RELATIONSHIP_EVENTS,
            cls.RELATIONSHIP_STATE_CHANGED,
            cls.HEALTH_ALERTS,
            cls.HEALTH_ALERTS_TRIGGERED,
            cls.PREDICTIONS,
            cls.PREDICTIONS_GENERATED,
            cls.TASK_EVENTS,
            cls.GOAL_EVENTS,
            cls.CALENDAR_EVENTS,
            cls.NOTIFICATION_EVENTS,
            cls.KNOWLEDGE_EVENTS,
            cls.INSIGHT_REQUESTS,
            cls.SCHEDULING_REQUESTS,
            cls.EVENT_STREAM,
        ]


# Alias for backwards compatibility and consistent naming
KafkaTopic = KafkaTopics
