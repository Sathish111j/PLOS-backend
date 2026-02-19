"""
Phase 4 — Knowledge Graph Models.

Defines the canonical data contracts for entities and relationships as
described in the Phase 4 specification (Sections 1.3 and 1.4).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Allowed entity types
# ---------------------------------------------------------------------------

ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "PERSON",
        "ORGANIZATION",
        "LOCATION",
        "CONCEPT",
        "PRODUCT",
        "EVENT",
        "TECHNOLOGY",
        "DATE_TIME",
        "METRIC_QUANTITY",
    }
)

# ---------------------------------------------------------------------------
# Allowed relationship types (controlled vocabulary)
# ---------------------------------------------------------------------------

RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "works_at",
        "founded",
        "acquired",
        "part_of",
        "cited_by",
        "competitor_of",
        "located_in",
        "created_by",
        "funded_by",
        "partner_of",
        "reports_to",
        "member_of",
        "successor_of",
        "predecessor_of",
        "co_occurs_with",  # produced by co-occurrence method
    }
)


# ---------------------------------------------------------------------------
# Raw entity straight out of the NER call
# ---------------------------------------------------------------------------


@dataclass
class RawEntity:
    """Unresolved entity as returned by the Gemini NER prompt."""

    name: str
    entity_type: str
    canonical_form: str
    confidence: float
    context: str  # sentence the entity was found in
    window_index: int = 0

    def is_valid(self) -> bool:
        return (
            bool(self.name)
            and self.entity_type in ENTITY_TYPES
            and 0.0 <= self.confidence <= 1.0
        )


# ---------------------------------------------------------------------------
# Resolved / canonical entity (stored in graph)
# ---------------------------------------------------------------------------


@dataclass
class CanonicalEntity:
    """Fully resolved entity ready to be upserted into Kuzu."""

    entity_id: str
    name: str
    canonical_name: str
    entity_type: str
    description: str = ""
    wikipedia_url: str = ""
    mention_count: int = 0
    pagerank_score: float = 0.0
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0
    embedding: list[float] = field(default_factory=list)
    first_seen_document_id: str = ""
    user_id: str = ""
    created_at: int = field(default_factory=lambda: int(time.time()))
    is_new: bool = True  # False when merged with an existing entity

    def aliases_json(self) -> str:
        import json

        return json.dumps(self.aliases)


# ---------------------------------------------------------------------------
# Relationship between two canonical entities
# ---------------------------------------------------------------------------


@dataclass
class EntityRelationship:
    """A directed edge between two entities in the graph."""

    from_entity_id: str
    to_entity_id: str
    relationship_type: str
    strength: float
    evidence_doc_id: str
    evidence_context: str = ""
    extraction_method: str = "co_occurrence"
    created_at: int = field(default_factory=lambda: int(time.time()))

    def is_valid(self) -> bool:
        return (
            self.relationship_type in RELATIONSHIP_TYPES and 0.0 <= self.strength <= 1.0
        )


# ---------------------------------------------------------------------------
# Task payload passed to the Celery graph worker
# ---------------------------------------------------------------------------


@dataclass
class GraphExtractionTask:
    """Payload for a graph_extraction Celery task."""

    document_id: str
    user_id: str
    bucket_id: str
    title: str
    chunks: list[dict[str, Any]]  # {"chunk_index": int, "text": str, ...}
    word_count: int = 0
    source_url: str = ""
