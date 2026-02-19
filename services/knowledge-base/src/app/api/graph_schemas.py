"""
Phase 4 — Graph API Schemas (Pydantic response models).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class EntitySummary(BaseModel):
    entity_id: str
    canonical_name: str
    type: str
    mention_count: int | None = None
    pagerank_score: float | None = None


class DocumentSummary(BaseModel):
    document_id: str
    title: str | None = None
    created_at: int | None = None
    confidence: float | None = None
    context: str | None = None


# ---------------------------------------------------------------------------
# Endpoint-specific responses
# ---------------------------------------------------------------------------


class EntityDetailResponse(BaseModel):
    entity_id: str
    canonical_name: str
    type: str
    description: str | None = None
    wikipedia_url: str | None = None
    mention_count: int | None = None
    pagerank_score: float | None = None
    aliases: str | None = None
    documents: list[DocumentSummary] = Field(default_factory=list)


class EntitySearchResponse(BaseModel):
    results: list[EntitySummary]
    total: int


class DocumentEntitiesResponse(BaseModel):
    document_id: str
    entities: list[dict[str, Any]]


class RelatedEntitiesResponse(BaseModel):
    entity_id: str
    related: list[dict[str, Any]]


class ShortestPathResponse(BaseModel):
    path: list[str]
    hops: int
    found: bool


class CoOccurringResponse(BaseModel):
    entity_id: str
    co_occurring: list[dict[str, Any]]


class CentralityResponse(BaseModel):
    entities: list[dict[str, Any]]


class TimelineResponse(BaseModel):
    entity_id: str
    timeline: list[dict[str, Any]]


class GraphStatsResponse(BaseModel):
    node_counts: dict[str, int]
    relationship_counts: dict[str, int]


class GraphDeleteResponse(BaseModel):
    status: str
    document_id: str
    affected_entities: list[str] = Field(default_factory=list)


class GraphMoveResponse(BaseModel):
    status: str
    document_id: str
    new_bucket_id: str
