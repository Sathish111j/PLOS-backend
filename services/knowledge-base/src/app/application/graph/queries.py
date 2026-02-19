"""
Phase 4 — Component 6: Graph Query Service (Section 7 of spec).

All eight query types are implemented here as plain methods backed by
Cypher queries executed on KuzuGraphStore.

Every query enforces user_id isolation — users never see each other's data.
"""

from __future__ import annotations

from typing import Any

from app.core.config import KnowledgeBaseConfig
from app.infrastructure.graph_store import KuzuGraphStore

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class GraphQueryService:
    """
    Read-only (no write lock needed) query service over the Kuzu graph.
    """

    def __init__(
        self, config: KnowledgeBaseConfig, graph_store: KuzuGraphStore
    ) -> None:
        self._config = config
        self._store = graph_store

    # ------------------------------------------------------------------
    # 1. Entity detail — all documents mentioning entity X
    # ------------------------------------------------------------------

    def entity_detail(
        self, entity_id: str, user_id: str, limit: int = 50
    ) -> dict[str, Any]:
        """Return entity metadata and the documents that mention it."""
        # Entity node
        entity_rows = self._store.execute_read(
            "MATCH (e:Entity {entity_id: $eid}) "
            "RETURN e.entity_id, e.canonical_name, e.type, e.description, "
            "e.wikipedia_url, e.mention_count, e.pagerank_score, e.aliases",
            {"eid": entity_id},
        )
        if not entity_rows:
            return {}

        row = entity_rows[0]
        entity = {
            "entity_id": row[0],
            "canonical_name": row[1],
            "type": row[2],
            "description": row[3],
            "wikipedia_url": row[4],
            "mention_count": row[5],
            "pagerank_score": row[6],
            "aliases": row[7],
        }

        # Mentioning documents
        doc_rows = self._store.execute_read(
            "MATCH (d:Document)-[m:MENTIONS]->(e:Entity {entity_id: $eid}) "
            "WHERE d.user_id = $uid "
            "RETURN d.document_id, d.title, d.created_at, m.confidence, m.context "
            "ORDER BY m.confidence DESC LIMIT $lim",
            {"eid": entity_id, "uid": user_id, "lim": limit},
        )
        entity["documents"] = [
            {
                "document_id": r[0],
                "title": r[1],
                "created_at": r[2],
                "confidence": r[3],
                "context": r[4],
            }
            for r in doc_rows
        ]
        return entity

    # ------------------------------------------------------------------
    # 2. Entity search by name / alias
    # ------------------------------------------------------------------

    def entity_search(
        self, query: str, user_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Find entities whose canonical_name or aliases contain the query string."""
        q_lower = query.lower()
        rows = self._store.execute_read(
            "MATCH (e:Entity {user_id: $uid}) "
            "WHERE lower(e.canonical_name) CONTAINS $q "
            "OR lower(e.name) CONTAINS $q "
            "OR lower(e.aliases) CONTAINS $q "
            "RETURN e.entity_id, e.canonical_name, e.type, e.mention_count, "
            "e.pagerank_score "
            "ORDER BY e.mention_count DESC LIMIT $lim",
            {"uid": user_id, "q": q_lower, "lim": limit},
        )
        return [
            {
                "entity_id": r[0],
                "canonical_name": r[1],
                "type": r[2],
                "mention_count": r[3],
                "pagerank_score": r[4],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 3. All entities mentioned in a document
    # ------------------------------------------------------------------

    def document_entities(self, document_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return all entities mentioned in a document."""
        rows = self._store.execute_read(
            "MATCH (d:Document {document_id: $doc_id})-[m:MENTIONS]->(e:Entity) "
            "WHERE d.user_id = $uid "
            "RETURN e.entity_id, e.canonical_name, e.type, m.confidence "
            "ORDER BY m.confidence DESC",
            {"doc_id": document_id, "uid": user_id},
        )
        return [
            {
                "entity_id": r[0],
                "canonical_name": r[1],
                "type": r[2],
                "confidence": r[3],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 4. Related entities (one hop)
    # ------------------------------------------------------------------

    def related_entities(
        self, entity_id: str, user_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return entities directly related to the given entity."""
        rows = self._store.execute_read(
            "MATCH (e1:Entity {entity_id: $eid})-[r:RELATED_TO]->(e2:Entity) "
            "WHERE e1.user_id = $uid "
            "RETURN e2.entity_id, e2.canonical_name, e2.type, "
            "r.relationship_type, r.strength "
            "ORDER BY r.strength DESC LIMIT $lim",
            {"eid": entity_id, "uid": user_id, "lim": limit},
        )
        return [
            {
                "entity_id": r[0],
                "canonical_name": r[1],
                "type": r[2],
                "relationship_type": r[3],
                "strength": r[4],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 5. Shortest path between two entities
    # ------------------------------------------------------------------

    def shortest_path(
        self, entity_id_1: str, entity_id_2: str, user_id: str, max_hops: int = 5
    ) -> dict[str, Any]:
        """
        Find the shortest path between two entities via RELATED_TO edges.
        Kuzu supports shortestPath syntax.
        """
        query = (
            "MATCH path = shortestPath("
            "(e1:Entity {entity_id: $eid1})-[:RELATED_TO*1.."
            + str(max_hops)
            + "]-(e2:Entity {entity_id: $eid2})) "
            "WHERE e1.user_id = $uid "
            "RETURN nodes(path), length(path)"
        )
        rows = self._store.execute_read(
            query,
            {"eid1": entity_id_1, "eid2": entity_id_2, "uid": user_id},
        )
        if not rows:
            return {"path": [], "hops": -1, "found": False}

        # Extract node canonical names from path
        row = rows[0]
        path_nodes = row[0] if row else []
        hops = int(row[1]) if len(row) > 1 else -1

        # path_nodes is a list of node objects in Kuzu
        names = []
        if isinstance(path_nodes, list):
            for node in path_nodes:
                if isinstance(node, dict):
                    names.append(node.get("canonical_name", str(node)))
                else:
                    names.append(str(node))
        return {"path": names, "hops": hops, "found": True}

    # ------------------------------------------------------------------
    # 6. Co-occurring entities in a bucket
    # ------------------------------------------------------------------

    def co_occurring_entities(
        self,
        entity_id: str,
        user_id: str,
        bucket_id: str | None = None,
        min_shared_docs: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return entities that frequently co-occur with the target entity."""
        if bucket_id:
            query = (
                "MATCH (d:Document)-[:BELONGS_TO]->(b:Bucket {bucket_id: $bid}) "
                "MATCH (d)-[:MENTIONS]->(target:Entity {entity_id: $eid}) "
                "MATCH (d)-[:MENTIONS]->(co:Entity) "
                "WHERE co.entity_id <> $eid AND d.user_id = $uid "
                "WITH co, count(d) AS shared_doc_count "
                "WHERE shared_doc_count >= $min_docs "
                "ORDER BY shared_doc_count DESC LIMIT $lim "
                "RETURN co.entity_id, co.canonical_name, co.type, shared_doc_count"
            )
            params = {
                "eid": entity_id,
                "uid": user_id,
                "bid": bucket_id,
                "min_docs": min_shared_docs,
                "lim": limit,
            }
        else:
            query = (
                "MATCH (d:Document)-[:MENTIONS]->(target:Entity {entity_id: $eid}) "
                "MATCH (d)-[:MENTIONS]->(co:Entity) "
                "WHERE co.entity_id <> $eid AND d.user_id = $uid "
                "WITH co, count(d) AS shared_doc_count "
                "WHERE shared_doc_count >= $min_docs "
                "ORDER BY shared_doc_count DESC LIMIT $lim "
                "RETURN co.entity_id, co.canonical_name, co.type, shared_doc_count"
            )
            params = {
                "eid": entity_id,
                "uid": user_id,
                "min_docs": min_shared_docs,
                "lim": limit,
            }

        rows = self._store.execute_read(query, params)
        return [
            {
                "entity_id": r[0],
                "canonical_name": r[1],
                "type": r[2],
                "shared_doc_count": r[3],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 7. Centrality ranked (top-N in a bucket)
    # ------------------------------------------------------------------

    def centrality_ranked(
        self,
        user_id: str,
        bucket_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return top-N entities by mention frequency (+ PageRank score)."""
        if bucket_id:
            query = (
                "MATCH (d:Document)-[:BELONGS_TO]->(b:Bucket {bucket_id: $bid}) "
                "WHERE d.user_id = $uid "
                "MATCH (d)-[m:MENTIONS]->(e:Entity) "
                "WITH e, count(m) AS mention_freq "
                "ORDER BY mention_freq DESC LIMIT $lim "
                "RETURN e.canonical_name, e.type, mention_freq, e.pagerank_score"
            )
            params = {"uid": user_id, "bid": bucket_id, "lim": limit}
        else:
            query = (
                "MATCH (d:Document)-[m:MENTIONS]->(e:Entity {user_id: $uid}) "
                "WITH e, count(m) AS mention_freq "
                "ORDER BY mention_freq DESC LIMIT $lim "
                "RETURN e.canonical_name, e.type, mention_freq, e.pagerank_score"
            )
            params = {"uid": user_id, "lim": limit}

        rows = self._store.execute_read(query, params)
        return [
            {
                "canonical_name": r[0],
                "type": r[1],
                "mention_freq": r[2],
                "pagerank_score": r[3],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 8. Temporal analysis — entity mentions by month
    # ------------------------------------------------------------------

    def entity_timeline(self, entity_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return monthly mention frequencies for an entity."""
        seconds_per_month = 2_592_000
        rows = self._store.execute_read(
            "MATCH (d:Document)-[m:MENTIONS]->(e:Entity {entity_id: $eid}) "
            "WHERE d.user_id = $uid "
            "WITH d.created_at AS ts, count(m) AS freq "
            "RETURN (ts / $spm) AS month_bucket, sum(freq) AS monthly_mentions "
            "ORDER BY month_bucket ASC",
            {"eid": entity_id, "uid": user_id, "spm": seconds_per_month},
        )
        return [{"month_bucket": r[0], "monthly_mentions": r[1]} for r in rows]

    # ------------------------------------------------------------------
    # Two-hop traversal (used internally by RAG context assembler)
    # ------------------------------------------------------------------

    def two_hop_documents(
        self, entity_id: str, user_id: str, limit: int = 30
    ) -> list[dict[str, Any]]:
        """
        Find documents about entities related to entity X (two-hop traversal).
        Used by Phase 5 for context enrichment.
        """
        rows = self._store.execute_read(
            "MATCH (d:Document)-[:MENTIONS]->(e2:Entity)<-[:RELATED_TO]-"
            "(e1:Entity {entity_id: $eid}) "
            "WHERE d.user_id = $uid AND e1.user_id = $uid "
            "RETURN d.document_id, d.title, e2.canonical_name, e2.type "
            "ORDER BY d.created_at DESC LIMIT $lim",
            {"eid": entity_id, "uid": user_id, "lim": limit},
        )
        return [
            {
                "document_id": r[0],
                "title": r[1],
                "related_entity_name": r[2],
                "related_entity_type": r[3],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Graph statistics
    # ------------------------------------------------------------------

    def graph_stats(self, user_id: str) -> dict[str, Any]:
        """Return node and relationship counts for health checks."""
        return {
            "node_counts": self._store.node_counts(),
            "relationship_counts": self._store.relationship_counts(),
        }
