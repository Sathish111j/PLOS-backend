"""
PLOS Kafka Topics
Centralized topic name definitions using dot notation (standard Kafka practice).

With generalized extraction, we use a minimal set of topics.
The JOURNAL_EXTRACTION_COMPLETE topic publishes the complete extraction result
which downstream services can consume.

Simplified from 12 topics to 3 active topics (others reserved for future use).
"""


class KafkaTopics:
    """
    Kafka topic names - using dot notation for consistency.

    Active Topics (currently in use):
    - JOURNAL_ENTRIES: Input from API
    - PARSED_ENTRIES: Legacy output (for compatibility)
    - JOURNAL_EXTRACTION_COMPLETE: Main output with full extraction
    """

    # ========================================================================
    # ACTIVE TOPICS - Currently Used in Code
    # ========================================================================

    # Input: Raw journal entries from API (consumed by workers)
    JOURNAL_ENTRIES = "plos.journal.entries"

    # Output: Parsed entries (legacy, kept for backward compatibility)
    PARSED_ENTRIES = "plos.journal.parsed"

    # Output: Complete extraction with all data (main output topic)
    JOURNAL_EXTRACTION_COMPLETE = "plos.journal.extraction.complete"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Get list of all active topic names for initialization"""
        return [
            cls.JOURNAL_ENTRIES,
            cls.PARSED_ENTRIES,
            cls.JOURNAL_EXTRACTION_COMPLETE,
        ]


KafkaTopic = KafkaTopics
