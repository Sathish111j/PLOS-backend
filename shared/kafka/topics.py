"""
PLOS Kafka Topics
Centralized topic name definitions
"""


class KafkaTopics:
    """Kafka topic names"""

    # Journal & Parsing
    JOURNAL_ENTRIES = "journal_entries"
    PARSED_ENTRIES = "parsed_entries"

    # Data Extraction
    MOOD_EVENTS = "mood_events"
    HEALTH_EVENTS = "health_events"
    NUTRITION_EVENTS = "nutrition_events"
    EXERCISE_EVENTS = "exercise_events"
    WORK_EVENTS = "work_events"
    HABIT_EVENTS = "habit_events"

    # Context & State
    CONTEXT_UPDATES = "context_updates"

    # Tasks & Goals
    TASK_EVENTS = "task_events"
    GOAL_EVENTS = "goal_events"

    # Calendar
    CALENDAR_EVENTS = "calendar_events"

    # Notifications
    NOTIFICATION_EVENTS = "notification_events"

    # Knowledge
    KNOWLEDGE_EVENTS = "knowledge_events"

    # AI Agents
    INSIGHT_REQUESTS = "insight_requests"
    SCHEDULING_REQUESTS = "scheduling_requests"

    # General Event Stream
    EVENT_STREAM = "event_stream"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Get list of all topic names"""
        return [
            cls.JOURNAL_ENTRIES,
            cls.PARSED_ENTRIES,
            cls.MOOD_EVENTS,
            cls.HEALTH_EVENTS,
            cls.NUTRITION_EVENTS,
            cls.EXERCISE_EVENTS,
            cls.WORK_EVENTS,
            cls.HABIT_EVENTS,
            cls.CONTEXT_UPDATES,
            cls.TASK_EVENTS,
            cls.GOAL_EVENTS,
            cls.CALENDAR_EVENTS,
            cls.NOTIFICATION_EVENTS,
            cls.KNOWLEDGE_EVENTS,
            cls.INSIGHT_REQUESTS,
            cls.SCHEDULING_REQUESTS,
            cls.EVENT_STREAM,
        ]
