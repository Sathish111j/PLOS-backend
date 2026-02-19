"""
Phase 4 — Graph Query API Router (Section 7 of spec).

Endpoints:
  GET  /graph/entity/{entity_id}                  — entity detail
  GET  /graph/entity/search                        — entity name search
  GET  /graph/document/{doc_id}/entities           — entities in a document
  GET  /graph/related/{entity_id}                  — related entities
  GET  /graph/path                                 — shortest path
  GET  /graph/cooccurring                          — co-occurring entities
  GET  /graph/centrality                           — top-N central entities
  GET  /graph/timeline                             — entity time series
  GET  /graph/stats                                — graph node/rel counts
  DELETE /graph/document/{doc_id}                  — delete document from graph
  POST   /graph/document/{doc_id}/move             — move document to new bucket

All endpoints enforce user_id isolation.
"""

from __future__ import annotations

from app.api.graph_schemas import (
    CentralityResponse,
    CoOccurringResponse,
    DocumentEntitiesResponse,
    EntityDetailResponse,
    EntitySearchResponse,
    EntitySummary,
    GraphDeleteResponse,
    GraphMoveResponse,
    GraphStatsResponse,
    RelatedEntitiesResponse,
    ShortestPathResponse,
    TimelineResponse,
)
from app.dependencies.container import graph_query_service, graph_update_service
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shared.auth.dependencies import get_current_user_optional
from shared.auth.models import TokenData
from shared.utils.logger import get_logger

logger = get_logger(__name__)
graph_router = APIRouter(prefix="/graph", tags=["graph"])


def _user_id(user: TokenData | None) -> str:
    if user:
        return str(user.user_id)
    return "anonymous"


def _not_found(msg: str = "Not found"):
    raise HTTPException(status_code=404, detail=msg)


# ---------------------------------------------------------------------------
# Entity endpoints
# ---------------------------------------------------------------------------


@graph_router.get("/entity/search", response_model=EntitySearchResponse)
async def search_entities(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> EntitySearchResponse:
    """Search entities by name or alias."""
    uid = _user_id(current_user)
    results = graph_query_service.entity_search(q, uid, limit=limit)
    summaries = [
        EntitySummary(
            entity_id=r["entity_id"],
            canonical_name=r["canonical_name"],
            type=r["type"],
            mention_count=r.get("mention_count"),
            pagerank_score=r.get("pagerank_score"),
        )
        for r in results
    ]
    return EntitySearchResponse(results=summaries, total=len(summaries))


@graph_router.get("/entity/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(
    entity_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> EntityDetailResponse:
    """Get an entity with all documents that mention it."""
    uid = _user_id(current_user)
    data = graph_query_service.entity_detail(entity_id, uid, limit=limit)
    if not data:
        _not_found(f"Entity {entity_id} not found")
    return EntityDetailResponse(**data)


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------


@graph_router.get(
    "/document/{doc_id}/entities", response_model=DocumentEntitiesResponse
)
async def document_entities(
    doc_id: str,
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> DocumentEntitiesResponse:
    """Return all entities mentioned in a document."""
    uid = _user_id(current_user)
    entities = graph_query_service.document_entities(doc_id, uid)
    return DocumentEntitiesResponse(document_id=doc_id, entities=entities)


@graph_router.delete("/document/{doc_id}", response_model=GraphDeleteResponse)
async def delete_document_from_graph(
    doc_id: str,
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> GraphDeleteResponse:
    """Remove a document and its relationships from the graph."""
    uid = _user_id(current_user)
    result = graph_update_service.delete_document(doc_id, uid)
    return GraphDeleteResponse(**result)


class BucketMoveBody(BaseModel):
    new_bucket_id: str
    new_bucket_name: str = ""
    new_bucket_path: str = ""


@graph_router.post("/document/{doc_id}/move", response_model=GraphMoveResponse)
async def move_document_bucket(
    doc_id: str,
    body: BucketMoveBody,
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> GraphMoveResponse:
    """Propagate a document bucket move to the graph."""
    uid = _user_id(current_user)
    result = graph_update_service.move_document_bucket(
        document_id=doc_id,
        new_bucket_id=body.new_bucket_id,
        new_bucket_name=body.new_bucket_name or body.new_bucket_id,
        new_bucket_path=body.new_bucket_path or body.new_bucket_id,
        user_id=uid,
    )
    return GraphMoveResponse(**result)


# ---------------------------------------------------------------------------
# Relationship / traversal endpoints
# ---------------------------------------------------------------------------


@graph_router.get("/related/{entity_id}", response_model=RelatedEntitiesResponse)
async def related_entities(
    entity_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> RelatedEntitiesResponse:
    """Return entities directly connected to the given entity."""
    uid = _user_id(current_user)
    related = graph_query_service.related_entities(entity_id, uid, limit=limit)
    return RelatedEntitiesResponse(entity_id=entity_id, related=related)


@graph_router.get("/path", response_model=ShortestPathResponse)
async def shortest_path(
    from_entity: str = Query(alias="from"),
    to_entity: str = Query(alias="to"),
    max_hops: int = Query(default=5, ge=1, le=10),
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> ShortestPathResponse:
    """Find the shortest path between two entities."""
    uid = _user_id(current_user)
    result = graph_query_service.shortest_path(from_entity, to_entity, uid, max_hops)
    return ShortestPathResponse(**result)


@graph_router.get("/cooccurring", response_model=CoOccurringResponse)
async def co_occurring_entities(
    entity: str,
    bucket: str | None = Query(default=None),
    min_docs: int = Query(default=2, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> CoOccurringResponse:
    """Return entities that co-occur with the given entity."""
    uid = _user_id(current_user)
    co = graph_query_service.co_occurring_entities(
        entity, uid, bucket_id=bucket, min_shared_docs=min_docs, limit=limit
    )
    return CoOccurringResponse(entity_id=entity, co_occurring=co)


@graph_router.get("/centrality", response_model=CentralityResponse)
async def centrality_ranked(
    bucket: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> CentralityResponse:
    """Return top-N most central entities, optionally filtered by bucket."""
    uid = _user_id(current_user)
    entities = graph_query_service.centrality_ranked(uid, bucket_id=bucket, limit=limit)
    return CentralityResponse(entities=entities)


@graph_router.get("/timeline", response_model=TimelineResponse)
async def entity_timeline(
    entity: str,
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> TimelineResponse:
    """Return monthly mention frequency for an entity."""
    uid = _user_id(current_user)
    timeline = graph_query_service.entity_timeline(entity, uid)
    return TimelineResponse(entity_id=entity, timeline=timeline)


# ---------------------------------------------------------------------------
# Health / stats
# ---------------------------------------------------------------------------


@graph_router.get("/stats", response_model=GraphStatsResponse)
async def graph_stats(
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> GraphStatsResponse:
    """Return node and relationship counts across the graph."""
    uid = _user_id(current_user)
    stats = graph_query_service.graph_stats(uid)
    return GraphStatsResponse(**stats)
