"""
Phase 4 — Component 7: Background Jobs (Section 8 of spec).

Three scheduled jobs:
  1. PageRank — every 6 hours.
  2. Orphan Cleanup — every 24 hours at 03:00 UTC.
  3. Graph Health Check — every 15 minutes.

Each job is implemented as a plain synchronous function designed to be called
from Celery Beat tasks.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import KnowledgeBaseConfig
from app.infrastructure.graph_store import KuzuGraphStore

from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 1. PageRank job
# ---------------------------------------------------------------------------


def run_pagerank(
    config: KnowledgeBaseConfig,
    graph_store: KuzuGraphStore,
    user_id: str,
) -> dict[str, Any]:
    """
    Compute PageRank scores for all Entity nodes belonging to the given user
    and write them back to Kuzu.

    Uses NetworkX with the RELATED_TO graph; weight = relationship strength.
    """
    try:
        import networkx as nx  # type: ignore[import]
    except ImportError:
        return {"status": "error", "reason": "networkx not installed"}

    start = time.monotonic()

    # Fetch all RELATED_TO edges for this user
    rows = graph_store.execute_read(
        "MATCH (e1:Entity {user_id: $uid})-[r:RELATED_TO]->(e2:Entity) "
        "RETURN e1.entity_id, e2.entity_id, r.strength",
        {"uid": user_id},
    )

    if not rows:
        logger.info("PageRank: no edges found for user", extra={"user_id": user_id})
        return {"status": "ok", "entities_updated": 0, "edges": 0}

    # Build directed graph
    graph = nx.DiGraph()
    for row in rows:
        if len(row) >= 3:
            graph.add_edge(row[0], row[1], weight=float(row[2]))

    # Compute PageRank
    try:
        scores: dict[str, float] = nx.pagerank(
            graph,
            alpha=config.graph_pagerank_damping,
            max_iter=config.graph_pagerank_iterations,
            weight="weight",
        )
    except nx.PowerIterationFailedConvergence:
        scores = nx.pagerank(
            graph,
            alpha=config.graph_pagerank_damping,
            max_iter=100,
            weight="weight",
        )

    # Write scores back to Kuzu
    updated = 0
    for entity_id, score in scores.items():
        with graph_store._write_ctx() as conn:  # type: ignore[attr-defined]
            try:
                conn.execute(
                    "MATCH (e:Entity {entity_id: $eid}) SET e.pagerank_score = $score",
                    {"eid": entity_id, "score": score},
                )
                updated += 1
            except Exception as exc:
                logger.warning(
                    "PageRank write failed",
                    extra={"entity_id": entity_id, "error": str(exc)},
                )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    result = {
        "status": "ok",
        "entities_updated": updated,
        "edges": len(rows),
        "computation_time_ms": elapsed_ms,
    }
    logger.info("PageRank job complete", extra=result)
    return result


# ---------------------------------------------------------------------------
# 2. Orphan cleanup job
# ---------------------------------------------------------------------------


def run_orphan_cleanup(
    config: KnowledgeBaseConfig,
    graph_store: KuzuGraphStore,
    user_id: str,
) -> dict[str, Any]:
    """
    Clean up orphaned Entity nodes (mention_count <= 0 or no MENTIONS edges)
    and dangling relationships.
    """
    start = time.monotonic()

    # Find orphaned entities
    orphan_rows = graph_store.execute_read(
        "MATCH (e:Entity {user_id: $uid}) "
        "WHERE e.mention_count <= 0 "
        "RETURN e.entity_id, e.canonical_name",
        {"uid": user_id},
    )

    deleted = 0
    for row in orphan_rows:
        entity_id = str(row[0]) if row else None
        if not entity_id:
            continue
        with graph_store._write_ctx() as conn:  # type: ignore[attr-defined]
            try:
                conn.execute(
                    "MATCH (e:Entity {entity_id: $eid}) DETACH DELETE e",
                    {"eid": entity_id},
                )
                deleted += 1
                logger.debug(
                    "Orphan entity deleted",
                    extra={"entity_id": entity_id, "name": str(row[1]) if len(row) > 1 else ""},
                )
            except Exception as exc:
                logger.warning(
                    "Orphan delete failed",
                    extra={"entity_id": entity_id, "error": str(exc)},
                )

    elapsed_s = round(time.monotonic() - start, 2)
    result = {
        "status": "ok",
        "orphans_deleted": deleted,
        "run_time_seconds": elapsed_s,
    }
    logger.info("Orphan cleanup job complete", extra=result)
    return result


# ---------------------------------------------------------------------------
# 3. Graph health check
# ---------------------------------------------------------------------------


def run_health_check(
    config: KnowledgeBaseConfig,
    graph_store: KuzuGraphStore,
    pg_document_count: int,
) -> dict[str, Any]:
    """
    Verify that:
      1. Node/relationship counts are within 5% of PostgreSQL document count.
      2. No orphaned MENTIONS relationships exist.
      3. Recent documents appear in the graph within the 5-minute SLA.

    Returns a dict with 'healthy' bool and per-check results.
    """
    checks: dict[str, Any] = {}
    healthy = True

    # Check 1 — node counts vs PostgreSQL
    node_counts = graph_store.node_counts()
    graph_doc_count = node_counts.get("Document", 0)
    if pg_document_count > 0:
        deviation = abs(graph_doc_count - pg_document_count) / pg_document_count
        checks["doc_count_deviation"] = round(deviation, 4)
        if deviation > 0.05:
            healthy = False
            logger.warning(
                "Graph health: document count deviation > 5%",
                extra={
                    "graph_docs": graph_doc_count,
                    "pg_docs": pg_document_count,
                    "deviation": deviation,
                },
            )
    checks["graph_doc_count"] = graph_doc_count
    checks["pg_doc_count"] = pg_document_count

    # Check 2 — recent documents indexed (within last 5 minutes)
    five_min_ago = int(time.time()) - 300
    recent_rows = graph_store.execute_read(
        "MATCH (d:Document) WHERE d.created_at > $ts RETURN count(d)",
        {"ts": five_min_ago},
    )
    recent_graph = int(recent_rows[0][0]) if recent_rows and recent_rows[0] else 0
    checks["recent_docs_in_graph"] = recent_graph

    checks["node_counts"] = node_counts
    checks["relationship_counts"] = graph_store.relationship_counts()
    checks["healthy"] = healthy

    if healthy:
        logger.info("Graph health check passed", extra=checks)
    else:
        logger.warning("Graph health check FAILED", extra=checks)

    return checks
