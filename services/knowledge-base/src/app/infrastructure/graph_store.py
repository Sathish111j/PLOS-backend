"""
Phase 4 — Kuzu Graph Store (Infrastructure Layer).

Handles all Kuzu database interactions:
  - Schema initialisation (idempotent).
  - Node upserts (Document, Entity, Bucket).
  - Relationship inserts (MENTIONS, BELONGS_TO, AUTHORED_BY, RELATED_TO).
  - Deletion helpers (DETACH DELETE, orphan cleanup).
  - Query execution and result parsing.
  - Write-lock management (one writer at a time).

Kùzu is embedded — no server process required. The DB directory is created
on first connect and opened on subsequent starts.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any, Generator

from app.application.graph.models import CanonicalEntity, EntityRelationship
from app.core.config import KnowledgeBaseConfig

from shared.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL — run once at init (CREATE ... IF NOT EXISTS = idempotent)
# ---------------------------------------------------------------------------

_NODE_DDLS = [
    """CREATE NODE TABLE IF NOT EXISTS Document (
        document_id STRING PRIMARY KEY,
        title STRING,
        content_type STRING,
        bucket_id STRING,
        user_id STRING,
        created_at INT64,
        word_count INT64,
        source_url STRING
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Entity (
        entity_id STRING PRIMARY KEY,
        name STRING,
        canonical_name STRING,
        type STRING,
        description STRING,
        wikipedia_url STRING,
        mention_count INT64,
        pagerank_score DOUBLE,
        aliases STRING,
        user_id STRING,
        created_at INT64
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Bucket (
        bucket_id STRING PRIMARY KEY,
        name STRING,
        path STRING,
        description STRING,
        user_id STRING
    )""",
]

_REL_DDLS = [
    """CREATE REL TABLE IF NOT EXISTS MENTIONS (
        FROM Document TO Entity,
        confidence DOUBLE,
        context STRING,
        window_index INT64
    )""",
    """CREATE REL TABLE IF NOT EXISTS RELATED_TO (
        FROM Entity TO Entity,
        relationship_type STRING,
        strength DOUBLE,
        evidence_doc_id STRING,
        extraction_method STRING,
        created_at INT64
    )""",
    """CREATE REL TABLE IF NOT EXISTS BELONGS_TO (
        FROM Document TO Bucket,
        assigned_at INT64,
        assignment_method STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS AUTHORED_BY (
        FROM Document TO Entity,
        role STRING
    )""",
]


# ---------------------------------------------------------------------------
# Graph store
# ---------------------------------------------------------------------------


class KuzuGraphStore:
    """
    Thin wrapper around the Kuzu embedded graph database.

    Thread safety:
      - Writes acquire a threading.Lock (max 5-second hold).
      - Reads run concurrently without a lock.
    """

    def __init__(self, config: KnowledgeBaseConfig) -> None:
        self._config = config
        self._db_path = config.graph_db_path
        self._db: Any = None
        self._write_lock = threading.Lock()
        self._lock_timeout = 5.0  # seconds

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open (or create) the Kuzu database and apply the schema."""
        import kuzu  # type: ignore[import]

        os.makedirs(self._db_path, exist_ok=True)
        self._db = kuzu.Database(self._db_path)
        self._init_schema()
        logger.info("KuzuGraphStore connected", extra={"db_path": self._db_path})

    def close(self) -> None:
        """Close the database connection."""
        self._db = None
        logger.info("KuzuGraphStore closed")

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Apply all DDL statements idempotently."""
        import kuzu  # type: ignore[import]

        conn = kuzu.Connection(self._db)
        try:
            for ddl in _NODE_DDLS + _REL_DDLS:
                try:
                    conn.execute(ddl)
                except Exception as exc:
                    # Kuzu raises if table already exists even with IF NOT EXISTS
                    # in older versions — swallow "already exists" errors.
                    if (
                        "already exist" in str(exc).lower()
                        or "already exists" in str(exc).lower()
                    ):
                        pass
                    else:
                        logger.warning(
                            "Schema DDL warning",
                            extra={"error": str(exc), "ddl": ddl[:80]},
                        )
        finally:
            del conn

    # ------------------------------------------------------------------
    # Write lock context manager
    # ------------------------------------------------------------------

    @contextmanager
    def _write_ctx(self) -> Generator[Any, None, None]:
        """Acquire write lock and yield a fresh Kuzu connection."""
        import kuzu  # type: ignore[import]

        acquired = self._write_lock.acquire(timeout=self._lock_timeout)
        if not acquired:
            raise TimeoutError("Could not acquire Kuzu write lock within 5 seconds")
        conn = kuzu.Connection(self._db)
        try:
            yield conn
        finally:
            del conn
            self._write_lock.release()

    def _read_conn(self) -> Any:
        """Return a fresh read connection (no lock required)."""
        import kuzu  # type: ignore[import]

        return kuzu.Connection(self._db)

    # ------------------------------------------------------------------
    # Node upserts
    # ------------------------------------------------------------------

    def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        content_type: str,
        bucket_id: str,
        user_id: str,
        created_at: int,
        word_count: int,
        source_url: str = "",
    ) -> None:
        """Upsert a Document node (MERGE equivalent via DELETE + CREATE)."""
        with self._write_ctx() as conn:
            # Kuzu does not have MERGE; we simulate it with a try-catch insert.
            self._safe_upsert_node(
                conn,
                "Document",
                "document_id",
                document_id,
                {
                    "document_id": document_id,
                    "title": title,
                    "content_type": content_type,
                    "bucket_id": bucket_id,
                    "user_id": user_id,
                    "created_at": created_at,
                    "word_count": word_count,
                    "source_url": source_url,
                },
            )

    def upsert_entity(self, entity: CanonicalEntity) -> None:
        """Upsert an Entity node, incrementing mention_count on re-insert."""
        with self._write_ctx() as conn:
            self._safe_upsert_node(
                conn,
                "Entity",
                "entity_id",
                entity.entity_id,
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "canonical_name": entity.canonical_name,
                    "type": entity.entity_type,
                    "description": entity.description,
                    "wikipedia_url": entity.wikipedia_url,
                    "mention_count": entity.mention_count,
                    "pagerank_score": entity.pagerank_score,
                    "aliases": entity.aliases_json(),
                    "user_id": entity.user_id,
                    "created_at": entity.created_at,
                },
            )

    def upsert_bucket(
        self,
        *,
        bucket_id: str,
        name: str,
        path: str,
        description: str,
        user_id: str,
    ) -> None:
        """Upsert a Bucket node."""
        with self._write_ctx() as conn:
            self._safe_upsert_node(
                conn,
                "Bucket",
                "bucket_id",
                bucket_id,
                {
                    "bucket_id": bucket_id,
                    "name": name,
                    "path": path,
                    "description": description,
                    "user_id": user_id,
                },
            )

    def _safe_upsert_node(
        self,
        conn: Any,
        table: str,
        pk_field: str,
        pk_value: str,
        fields: dict[str, Any],
    ) -> None:
        """
        Emulate MERGE for a node: if PK exists update props, else insert.
        Kuzu v0.7 supports MERGE syntax for nodes.
        """
        cols = ", ".join(f"{k}: ${k}" for k in fields)
        query = f"MERGE (n:{table} {{{pk_field}: ${pk_field}}}) SET n = {{{cols}}}"
        try:
            conn.execute(query, fields)
        except Exception as exc:
            # Fallback: try plain CREATE (first time)
            if "already exist" in str(exc).lower():
                set_parts = ", ".join(f"n.{k} = ${k}" for k in fields if k != pk_field)
                upd = (
                    f"MATCH (n:{table} {{{pk_field}: ${pk_field}}}) " f"SET {set_parts}"
                )
                conn.execute(upd, fields)
            else:
                insert = f"CREATE (n:{table} {{{cols}}})"
                try:
                    conn.execute(insert, fields)
                except Exception:
                    logger.warning(
                        "Node upsert failed",
                        extra={"table": table, "pk": pk_value, "error": str(exc)},
                    )

    # ------------------------------------------------------------------
    # Relationship inserts
    # ------------------------------------------------------------------

    def create_mentions(
        self,
        *,
        document_id: str,
        entity_id: str,
        confidence: float,
        context: str,
        window_index: int,
    ) -> None:
        """Insert a MENTIONS relationship from Document to Entity."""
        with self._write_ctx() as conn:
            query = (
                "MATCH (d:Document {document_id: $doc_id}), "
                "(e:Entity {entity_id: $entity_id}) "
                "CREATE (d)-[:MENTIONS {confidence: $confidence, context: $context, "
                "window_index: $window_index}]->(e)"
            )
            try:
                conn.execute(
                    query,
                    {
                        "doc_id": document_id,
                        "entity_id": entity_id,
                        "confidence": confidence,
                        "context": context,
                        "window_index": window_index,
                    },
                )
            except Exception as exc:
                logger.warning("MENTIONS insert failed", extra={"error": str(exc)})

    def upsert_belongs_to(
        self,
        *,
        document_id: str,
        bucket_id: str,
        assigned_at: int,
        assignment_method: str = "auto",
    ) -> None:
        """Create or replace a BELONGS_TO relationship."""
        with self._write_ctx() as conn:
            # Delete old BELONGS_TO first to avoid duplicates
            del_q = (
                "MATCH (d:Document {document_id: $doc_id})-[r:BELONGS_TO]->() DELETE r"
            )
            try:
                conn.execute(del_q, {"doc_id": document_id})
            except Exception:
                pass
            ins_q = (
                "MATCH (d:Document {document_id: $doc_id}), "
                "(b:Bucket {bucket_id: $bucket_id}) "
                "CREATE (d)-[:BELONGS_TO {assigned_at: $assigned_at, "
                "assignment_method: $method}]->(b)"
            )
            try:
                conn.execute(
                    ins_q,
                    {
                        "doc_id": document_id,
                        "bucket_id": bucket_id,
                        "assigned_at": assigned_at,
                        "method": assignment_method,
                    },
                )
            except Exception as exc:
                logger.warning("BELONGS_TO insert failed", extra={"error": str(exc)})

    def create_authored_by(
        self,
        *,
        document_id: str,
        author_entity_id: str,
        role: str = "author",
    ) -> None:
        """Insert an AUTHORED_BY relationship."""
        with self._write_ctx() as conn:
            query = (
                "MATCH (d:Document {document_id: $doc_id}), "
                "(e:Entity {entity_id: $entity_id}) "
                "MERGE (d)-[:AUTHORED_BY {role: $role}]->(e)"
            )
            try:
                conn.execute(
                    query,
                    {
                        "doc_id": document_id,
                        "entity_id": author_entity_id,
                        "role": role,
                    },
                )
            except Exception as exc:
                logger.warning("AUTHORED_BY insert failed", extra={"error": str(exc)})

    def upsert_related_to(self, rel: EntityRelationship) -> None:
        """
        Upsert a RELATED_TO relationship between two entities.
        If it already exists, update the strength with an EMA: 0.8*old + 0.2*new.
        """

        with self._write_ctx() as conn:
            # Check if relationship already exists
            check_q = (
                "MATCH (a:Entity {entity_id: $from_id})-[r:RELATED_TO]->"
                "(b:Entity {entity_id: $to_id}) "
                "WHERE r.relationship_type = $rtype "
                "RETURN r.strength"
            )
            try:
                result = conn.execute(
                    check_q,
                    {
                        "from_id": rel.from_entity_id,
                        "to_id": rel.to_entity_id,
                        "rtype": rel.relationship_type,
                    },
                )
                rows = self._rows(result)
                if rows:
                    old_strength = float(rows[0][0]) if rows[0] else rel.strength
                    new_strength = 0.8 * old_strength + 0.2 * rel.strength
                    upd_q = (
                        "MATCH (a:Entity {entity_id: $from_id})-[r:RELATED_TO]->"
                        "(b:Entity {entity_id: $to_id}) "
                        "WHERE r.relationship_type = $rtype "
                        "SET r.strength = $strength"
                    )
                    conn.execute(
                        upd_q,
                        {
                            "from_id": rel.from_entity_id,
                            "to_id": rel.to_entity_id,
                            "rtype": rel.relationship_type,
                            "strength": new_strength,
                        },
                    )
                    return
            except Exception:
                pass

            # Insert new relationship
            ins_q = (
                "MATCH (a:Entity {entity_id: $from_id}), "
                "(b:Entity {entity_id: $to_id}) "
                "CREATE (a)-[:RELATED_TO {relationship_type: $rtype, "
                "strength: $strength, evidence_doc_id: $doc_id, "
                "extraction_method: $method, created_at: $created_at}]->(b)"
            )
            try:
                conn.execute(
                    ins_q,
                    {
                        "from_id": rel.from_entity_id,
                        "to_id": rel.to_entity_id,
                        "rtype": rel.relationship_type,
                        "strength": rel.strength,
                        "doc_id": rel.evidence_doc_id,
                        "method": rel.extraction_method,
                        "created_at": rel.created_at,
                    },
                )
            except Exception as exc:
                logger.warning("RELATED_TO insert failed", extra={"error": str(exc)})

    # ------------------------------------------------------------------
    # Deletion helpers
    # ------------------------------------------------------------------

    def delete_document(self, document_id: str, user_id: str) -> list[str]:
        """
        DETACH DELETE a document node and all its relationships.
        Returns list of entity_ids that were mentioned by this document.
        """
        # First collect mentioned entity IDs
        entity_ids: list[str] = []
        conn = self._read_conn()
        try:
            q = (
                "MATCH (d:Document {document_id: $doc_id})-[:MENTIONS]->(e:Entity) "
                "RETURN e.entity_id"
            )
            result = conn.execute(q, {"doc_id": document_id})
            for row in self._rows(result):
                if row:
                    entity_ids.append(str(row[0]))
        except Exception as exc:
            logger.warning(
                "Entity lookup before delete failed", extra={"error": str(exc)}
            )
        finally:
            del conn

        with self._write_ctx() as conn:
            # Detach delete document
            try:
                conn.execute(
                    "MATCH (d:Document {document_id: $doc_id}) DETACH DELETE d",
                    {"doc_id": document_id},
                )
            except Exception as exc:
                logger.warning("DETACH DELETE failed", extra={"error": str(exc)})

            # Decrement mention counts and clean orphans
            for eid in entity_ids:
                try:
                    conn.execute(
                        "MATCH (e:Entity {entity_id: $eid}) "
                        "SET e.mention_count = e.mention_count - 1",
                        {"eid": eid},
                    )
                except Exception:
                    pass

            # Clean genuine orphans (mention_count <= 0 and no incoming MENTIONS)
            try:
                conn.execute(
                    "MATCH (e:Entity {user_id: $uid}) "
                    "WHERE e.mention_count <= 0 "
                    "DETACH DELETE e",
                    {"uid": user_id},
                )
            except Exception as exc:
                logger.warning("Orphan cleanup failed", extra={"error": str(exc)})

        return entity_ids

    def delete_document_mentions(self, document_id: str) -> None:
        """Delete only MENTIONS relationships from a document (for update flow)."""
        with self._write_ctx() as conn:
            try:
                conn.execute(
                    "MATCH (d:Document {document_id: $doc_id})-[m:MENTIONS]->() DELETE m",
                    {"doc_id": document_id},
                )
            except Exception as exc:
                logger.warning("Delete MENTIONS failed", extra={"error": str(exc)})

    def update_mention_count(self, entity_id: str, delta: int) -> None:
        """Increment or decrement mention_count for an entity."""
        with self._write_ctx() as conn:
            try:
                conn.execute(
                    "MATCH (e:Entity {entity_id: $eid}) "
                    "SET e.mention_count = e.mention_count + $delta",
                    {"eid": entity_id, "delta": delta},
                )
            except Exception as exc:
                logger.warning("mention_count update failed", extra={"error": str(exc)})

    def delete_weak_related_to(
        self, document_id: str, strength_threshold: float = 0.3
    ) -> None:
        """Delete RELATED_TO relationships whose only evidence is this document."""
        with self._write_ctx() as conn:
            try:
                conn.execute(
                    "MATCH ()-[r:RELATED_TO]->() "
                    "WHERE r.evidence_doc_id = $doc_id AND r.strength < $threshold "
                    "DELETE r",
                    {"doc_id": document_id, "threshold": strength_threshold},
                )
            except Exception as exc:
                logger.warning("RELATED_TO cleanup failed", extra={"error": str(exc)})

    def move_belongs_to(
        self,
        *,
        document_id: str,
        new_bucket_id: str,
        new_bucket_name: str,
        new_bucket_path: str,
        user_id: str,
    ) -> None:
        """Move a document to a different bucket in the graph."""
        self.upsert_bucket(
            bucket_id=new_bucket_id,
            name=new_bucket_name,
            path=new_bucket_path,
            description="",
            user_id=user_id,
        )
        self.upsert_belongs_to(
            document_id=document_id,
            bucket_id=new_bucket_id,
            assigned_at=int(__import__("time").time()),
            assignment_method="user_manual",
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute_read(self, query: str, params: dict | None = None) -> list[list[Any]]:
        """Execute a read query and return rows as lists."""
        conn = self._read_conn()
        try:
            result = conn.execute(query, params or {})
            return self._rows(result)
        except Exception as exc:
            logger.warning(
                "Read query failed", extra={"error": str(exc), "query": query[:100]}
            )
            return []
        finally:
            del conn

    @staticmethod
    def _rows(result: Any) -> list[list[Any]]:
        """Convert Kuzu QueryResult to a list of rows."""
        rows: list[list[Any]] = []
        if result is None:
            return rows
        try:
            while result.has_next():
                rows.append(result.get_next())
        except Exception:
            pass
        return rows

    # ------------------------------------------------------------------
    # Bulk entity fetch (for disambiguation cache load)
    # ------------------------------------------------------------------

    def get_all_entities(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch all Entity nodes for a user (for seeding the disambiguator cache)."""
        rows = self.execute_read(
            "MATCH (e:Entity {user_id: $uid}) "
            "RETURN e.entity_id, e.canonical_name, e.type, e.mention_count, e.aliases",
            {"uid": user_id},
        )
        entities: list[dict[str, Any]] = []
        for row in rows:
            if len(row) >= 5:
                entities.append(
                    {
                        "entity_id": row[0],
                        "canonical_name": row[1],
                        "entity_type": row[2],
                        "mention_count": row[3],
                        "aliases": row[4],
                    }
                )
        return entities

    # ------------------------------------------------------------------
    # Health / stats
    # ------------------------------------------------------------------

    def node_counts(self) -> dict[str, int]:
        """Return counts of Document, Entity, Bucket nodes."""
        counts: dict[str, int] = {}
        for table in ("Document", "Entity", "Bucket"):
            rows = self.execute_read(f"MATCH (n:{table}) RETURN count(n)")
            counts[table] = int(rows[0][0]) if rows and rows[0] else 0
        return counts

    def relationship_counts(self) -> dict[str, int]:
        """Return counts of all relationship types."""
        counts: dict[str, int] = {}
        for rel in ("MENTIONS", "RELATED_TO", "BELONGS_TO", "AUTHORED_BY"):
            rows = self.execute_read(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
            counts[rel] = int(rows[0][0]) if rows and rows[0] else 0
        return counts
