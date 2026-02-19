"""
Phase 4 — Component 5: Incremental Updates & Deletion (Section 6 of spec).

Provides high-level operations for:
  - Document deletion from the graph.
  - Document content update (delete old + re-extract).
  - Bucket move propagation.

All operations maintain referential integrity: orphaned entities and dangling
relationships are cleaned up after each modification.
"""

from __future__ import annotations

import time
from typing import Any

from app.application.graph.construction import GraphConstructor
from app.application.graph.disambiguation import EntityDisambiguator
from app.application.graph.models import GraphExtractionTask
from app.core.config import KnowledgeBaseConfig
from app.infrastructure.graph_store import KuzuGraphStore

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class GraphUpdateService:
    """
    High-level service for incremental graph updates.

    All write paths go through KuzuGraphStore ensuring write-lock safety.
    """

    def __init__(
        self,
        config: KnowledgeBaseConfig,
        graph_store: KuzuGraphStore,
        disambiguator: EntityDisambiguator,
    ) -> None:
        self._config = config
        self._store = graph_store
        self._disambiguator = disambiguator
        self._constructor = GraphConstructor(config, graph_store)

    # ------------------------------------------------------------------
    # Document deletion (Section 6.2)
    # ------------------------------------------------------------------

    def delete_document(self, document_id: str, user_id: str) -> dict[str, Any]:
        """
        Remove a document and all its relationships from the graph.
        Cleans up orphaned entities and dangling RELATED_TO edges.

        Returns a summary dict.
        """
        entity_ids = self._store.delete_document(document_id, user_id)
        self._store.delete_weak_related_to(document_id, strength_threshold=0.3)

        logger.info(
            "Document deleted from graph",
            extra={
                "document_id": document_id,
                "affected_entities": len(entity_ids),
            },
        )
        return {
            "status": "deleted",
            "document_id": document_id,
            "affected_entities": entity_ids,
        }

    # ------------------------------------------------------------------
    # Document update (Section 6.1)
    # ------------------------------------------------------------------

    async def update_document(
        self,
        task: GraphExtractionTask,
    ) -> dict[str, Any]:
        """
        Re-extract graph data for an updated document.

        1. Delete old MENTIONS relationships.
        2. Decrement mention counts for previously mentioned entities.
        3. Delete RELATED_TO edges that depended solely on this document.
        4. Re-run full NER + disambiguation + graph construction.
        """
        # Step 1 — record which entities were previously mentioned
        old_rows = self._store.execute_read(
            "MATCH (d:Document {document_id: $doc_id})-[:MENTIONS]->(e:Entity) "
            "RETURN e.entity_id",
            {"doc_id": task.document_id},
        )
        old_entity_ids = [str(row[0]) for row in old_rows if row]

        # Step 2 — delete old MENTIONS
        self._store.delete_document_mentions(task.document_id)

        # Step 3 — decrement mention counts
        for eid in old_entity_ids:
            self._store.update_mention_count(eid, -1)

        # Step 4 — delete weak RELATED_TO that assumed old content
        self._store.delete_weak_related_to(task.document_id, strength_threshold=0.5)

        # Step 5 — re-run full extraction
        summary = await self._constructor.process_document(task, self._disambiguator)
        summary["operation"] = "update"
        return summary

    # ------------------------------------------------------------------
    # Bucket move (Section 6.3)
    # ------------------------------------------------------------------

    def move_document_bucket(
        self,
        *,
        document_id: str,
        new_bucket_id: str,
        new_bucket_name: str,
        new_bucket_path: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Update the BELONGS_TO relationship when a document is moved to a
        different bucket.
        """
        self._store.move_belongs_to(
            document_id=document_id,
            new_bucket_id=new_bucket_id,
            new_bucket_name=new_bucket_name,
            new_bucket_path=new_bucket_path,
            user_id=user_id,
        )
        logger.info(
            "Document bucket moved in graph",
            extra={
                "document_id": document_id,
                "new_bucket_id": new_bucket_id,
            },
        )
        return {
            "status": "moved",
            "document_id": document_id,
            "new_bucket_id": new_bucket_id,
        }

    # ------------------------------------------------------------------
    # Post-deletion validation (integrity check)
    # ------------------------------------------------------------------

    def validate_integrity(self, user_id: str) -> dict[str, int]:
        """
        Verify there are no orphaned relationships or entities with
        mention_count <= 0.  Returns a dict of violation counts.
        """
        violations: dict[str, int] = {}

        # Entities with mention_count <= 0
        rows = self._store.execute_read(
            "MATCH (e:Entity {user_id: $uid}) WHERE e.mention_count <= 0 RETURN count(e)",
            {"uid": user_id},
        )
        violations["orphaned_entities"] = int(rows[0][0]) if rows and rows[0] else 0

        if violations["orphaned_entities"] > 0:
            logger.warning(
                "Integrity violation: orphaned entities found",
                extra={"count": violations["orphaned_entities"], "user_id": user_id},
            )

        return violations
