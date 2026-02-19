import asyncio
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import meilisearch
from app.application.deduplication import (
    IntegrityCheckpoint,
    hamming_distance_64,
    minhash_similarity,
    to_unsigned_bigint,
)
from app.application.embeddings import GeminiEmbeddingProvider
from app.application.entity_extraction import ExtractedEntity
from app.application.ingestion.models import DocumentChunk, StructuredDocument
from app.core.config import KnowledgeBaseConfig
from minio import Minio
from minio.error import S3Error
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from redis.asyncio import Redis

from shared.gemini.client import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgePersistence:
    EMBEDDING_DLQ_KEY = "kb:embedding:dlq"
    EMBEDDING_DLQ_UNREPLAYABLE_KEY = "kb:embedding:dlq:unreplayable"
    EMBEDDING_DLQ_FAILED_KEY = "kb:embedding:dlq:failed"
    EMBEDDING_DLQ_REPLAYED_KEY = "kb:embedding:dlq:replayed"
    ROUTING_AUTO_CONFIDENCE_THRESHOLD = 0.85
    ROUTING_CONFIRMATION_THRESHOLD = 0.60

    def __init__(self, config: KnowledgeBaseConfig):
        self.config = config
        self._pool: asyncpg.Pool | None = None
        self._redis: Redis | None = None
        self._qdrant: QdrantClient | None = None
        self._table_exists_cache: dict[str, bool] = {}
        self._semantic_chunk_dedup_queue: (
            asyncio.Queue[
                tuple[
                    list[int], list[int], float, asyncio.Future[dict[str, Any] | None]
                ]
            ]
            | None
        ) = None
        self._semantic_chunk_dedup_worker_task: asyncio.Task[None] | None = None
        self._embedding_dlq_replay_task: asyncio.Task[None] | None = None
        self._embedding_provider = GeminiEmbeddingProvider(config)
        self._minio_client = Minio(
            config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure,
        )
        self._meili: meilisearch.Client | None = None

    async def connect(self) -> None:
        dsn = self.config.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
        self._qdrant = QdrantClient(url=self.config.qdrant_url, timeout=10)
        try:
            redis_client = Redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await redis_client.ping()
            self._redis = redis_client
        except Exception:
            self._redis = None

        self._start_semantic_chunk_dedup_worker()
        self._start_embedding_dlq_replay_worker()
        await self.ensure_qdrant_collection()
        try:
            meili_client = meilisearch.Client(
                self.config.meilisearch_url,
                self.config.meilisearch_master_key or None,
            )
            await asyncio.to_thread(meili_client.health)
            self._meili = meili_client
            await self._ensure_meili_index()
        except Exception as exc:
            logger.warning(
                "Meilisearch unavailable, typo-tolerant search will use pg_trgm fallback: %s",
                exc,
            )
            self._meili = None

    async def close(self) -> None:
        if self._semantic_chunk_dedup_worker_task:
            self._semantic_chunk_dedup_worker_task.cancel()
            try:
                await self._semantic_chunk_dedup_worker_task
            except asyncio.CancelledError:
                pass
            self._semantic_chunk_dedup_worker_task = None
            self._semantic_chunk_dedup_queue = None

        if self._embedding_dlq_replay_task:
            self._embedding_dlq_replay_task.cancel()
            try:
                await self._embedding_dlq_replay_task
            except asyncio.CancelledError:
                pass
            self._embedding_dlq_replay_task = None

        if self._redis:
            await self._redis.aclose()
            self._redis = None
        if self._qdrant:
            self._qdrant.close()
            self._qdrant = None
        self._meili = None
        if self._pool:
            await self._pool.close()

    async def check_postgres(self) -> str:
        try:
            if not self._pool:
                return "uninitialized"
            async with self._pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
            return "healthy"
        except Exception:
            return "unreachable"

    async def _ensure_storage_bucket_record(
        self, user_uuid: UUID | None
    ) -> UUID | None:
        if not self._pool:
            return None

        minio_storage_bucket_name = self.config.minio_bucket
        bucket_path = f"/root/{self._bucket_slug(minio_storage_bucket_name)}"

        if user_uuid:
            select_query = """
                SELECT id
                FROM buckets
                WHERE user_id = $1
                  AND parent_bucket_id IS NULL
                  AND is_deleted = FALSE
                  AND lower(name) = lower($2)
                LIMIT 1
            """
            select_params = (user_uuid, minio_storage_bucket_name)
        else:
            select_query = """
                SELECT id
                FROM buckets
                WHERE user_id IS NULL
                  AND parent_bucket_id IS NULL
                  AND is_deleted = FALSE
                  AND lower(name) = lower($1)
                LIMIT 1
            """
            select_params = (minio_storage_bucket_name,)

        update_query = """
            UPDATE buckets
            SET storage_backend = 'minio',
                storage_bucket = $2,
                is_active = TRUE,
                updated_at = NOW(),
                updated_by = $3
            WHERE id = $1
            RETURNING id
        """

        insert_query = """
            INSERT INTO buckets (
                user_id,
                parent_bucket_id,
                depth,
                path,
                name,
                description,
                storage_backend,
                storage_bucket,
                is_active,
                is_default,
                is_deleted,
                created_by,
                updated_by
            )
            VALUES (
                $1,
                NULL,
                0,
                $2,
                $3,
                'Auto-created storage bucket record',
                'minio',
                $4,
                TRUE,
                FALSE,
                FALSE,
                $1,
                $1
            )
            RETURNING id
        """

        async with self._pool.acquire() as connection:
            existing = await connection.fetchrow(select_query, *select_params)
            if existing:
                row = await connection.fetchrow(
                    update_query,
                    existing["id"],
                    minio_storage_bucket_name,
                    user_uuid,
                )
                return row["id"] if row else existing["id"]

            row = await connection.fetchrow(
                insert_query,
                user_uuid,
                bucket_path,
                minio_storage_bucket_name,
                minio_storage_bucket_name,
            )
            return row["id"] if row else None

    async def _resolve_existing_user_uuid(self, owner_id: str) -> UUID | None:
        try:
            parsed = UUID(owner_id)
        except Exception:
            return None

        if not self._pool:
            return None

        query = "SELECT id FROM users WHERE id = $1"
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, parsed)
        return row["id"] if row else None

    @staticmethod
    def _bucket_slug(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
        slug = slug.strip("-")
        return slug or "bucket"

    async def _get_bucket_row(
        self,
        *,
        user_uuid: UUID,
        bucket_id: UUID,
        include_deleted: bool = False,
    ) -> asyncpg.Record | None:
        if not self._pool:
            return None

        where_deleted = "" if include_deleted else "AND is_deleted = FALSE"
        query = f"""
            SELECT id, user_id, parent_bucket_id, depth, name, description,
                   icon_emoji, color_hex, document_count, is_default, is_deleted,
                   path, created_at, updated_at
            FROM buckets
            WHERE user_id = $1
              AND id = $2
              {where_deleted}
            LIMIT 1
        """
        async with self._pool.acquire() as connection:
            return await connection.fetchrow(query, user_uuid, bucket_id)

    async def _ensure_user_default_buckets(self, user_uuid: UUID) -> None:
        if not self._pool:
            return

        async with self._pool.acquire() as connection:
            existing = await connection.fetchval(
                "SELECT COUNT(*) FROM buckets WHERE user_id = $1 AND is_deleted = FALSE",
                user_uuid,
            )
            if int(existing or 0) > 0:
                return

            default_specs = [
                (
                    "Research and Reference",
                    "Academic papers, technical documentation, reference materials, and knowledge resources.",
                    "book",
                    "#4F46E5",
                    True,
                ),
                (
                    "Work and Projects",
                    "Work-related files, project documents, meeting notes, reports, and professional materials.",
                    "briefcase",
                    "#0EA5E9",
                    True,
                ),
                (
                    "Web and Media Saves",
                    "Web pages, articles, blog posts, social content, videos, and online resources.",
                    "globe",
                    "#10B981",
                    True,
                ),
                (
                    "Needs Classification",
                    "Inbox for low-confidence automatic routing that requires user confirmation.",
                    "inbox",
                    "#F59E0B",
                    False,
                ),
            ]

            async with connection.transaction():
                for (
                    name,
                    description,
                    icon_name,
                    color_hex,
                    is_default,
                ) in default_specs:
                    slug = self._bucket_slug(name)
                    await connection.execute(
                        """
                        INSERT INTO buckets (
                            id,
                            user_id,
                            parent_bucket_id,
                            depth,
                            name,
                            description,
                            icon_emoji,
                            color_hex,
                            document_count,
                            is_default,
                            is_deleted,
                            path,
                            storage_backend,
                            storage_bucket,
                            is_active,
                            created_by,
                            updated_by
                        )
                        VALUES (
                            gen_random_uuid(),
                            $1,
                            NULL,
                            0,
                            $2,
                            $3,
                            $4,
                            $5,
                            0,
                            $6,
                            FALSE,
                            $7,
                            'minio',
                            $8,
                            TRUE,
                            $1,
                            $1
                        )
                        ON CONFLICT DO NOTHING
                        """,
                        user_uuid,
                        name,
                        description,
                        icon_name,
                        color_hex,
                        is_default,
                        f"/root/{slug}",
                        self.config.minio_bucket,
                    )

    async def list_buckets_for_user(self, owner_id: str) -> list[dict[str, Any]]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid or not self._pool:
            return []

        await self._ensure_user_default_buckets(user_uuid)

        query = """
            SELECT id, user_id, parent_bucket_id, depth, name, description,
                   icon_emoji, color_hex, document_count, is_default, is_deleted,
                   path, created_at, updated_at
            FROM buckets
            WHERE user_id = $1
              AND is_deleted = FALSE
            ORDER BY path ASC
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, user_uuid)

        return [
            {
                "bucket_id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "parent_bucket_id": (
                    str(row["parent_bucket_id"]) if row["parent_bucket_id"] else None
                ),
                "depth": int(row["depth"]),
                "name": row["name"],
                "description": row["description"],
                "icon_emoji": row["icon_emoji"],
                "color_hex": row["color_hex"],
                "document_count": int(row["document_count"] or 0),
                "is_default": bool(row["is_default"]),
                "is_deleted": bool(row["is_deleted"]),
                "path": row["path"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ]

    async def create_bucket(
        self,
        *,
        owner_id: str,
        name: str,
        description: str | None,
        parent_bucket_id: str | None,
        icon_emoji: str | None,
        color_hex: str | None,
    ) -> dict[str, Any]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid or not self._pool:
            raise RuntimeError("Valid authenticated user is required")

        await self._ensure_user_default_buckets(user_uuid)

        parent_uuid: UUID | None = None
        depth = 0
        parent_path = "/root"
        if parent_bucket_id:
            parent_uuid = UUID(parent_bucket_id)
            parent_row = await self._get_bucket_row(
                user_uuid=user_uuid, bucket_id=parent_uuid
            )
            if not parent_row:
                raise PermissionError(
                    "Parent bucket not found or not accessible to this user"
                )
            depth = int(parent_row["depth"]) + 1
            parent_path = str(parent_row["path"])

        slug = self._bucket_slug(name)
        path = f"{parent_path}/{slug}"

        query = """
            INSERT INTO buckets (
                id, user_id, parent_bucket_id, depth, name, description,
                icon_emoji, color_hex, document_count, is_default, is_deleted,
                path, storage_backend, storage_bucket, is_active, created_by, updated_by
            )
            VALUES (
                gen_random_uuid(), $1, $2, $3, $4, $5,
                $6, $7, 0, FALSE, FALSE,
                $8, 'minio', $9, TRUE, $1, $1
            )
            RETURNING id, user_id, parent_bucket_id, depth, name, description,
                      icon_emoji, color_hex, document_count, is_default, is_deleted,
                      path, created_at, updated_at
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                query,
                user_uuid,
                parent_uuid,
                depth,
                name,
                description,
                icon_emoji,
                color_hex,
                path,
                self.config.minio_bucket,
            )

        if not row:
            raise RuntimeError("Failed to create bucket")

        return {
            "bucket_id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "parent_bucket_id": (
                str(row["parent_bucket_id"]) if row["parent_bucket_id"] else None
            ),
            "depth": int(row["depth"]),
            "name": row["name"],
            "description": row["description"],
            "icon_emoji": row["icon_emoji"],
            "color_hex": row["color_hex"],
            "document_count": int(row["document_count"] or 0),
            "is_default": bool(row["is_default"]),
            "is_deleted": bool(row["is_deleted"]),
            "path": row["path"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    async def move_bucket(
        self,
        *,
        owner_id: str,
        bucket_id: str,
        new_parent_bucket_id: str | None,
    ) -> dict[str, Any]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid or not self._pool:
            raise RuntimeError("Valid authenticated user is required")

        bucket_uuid = UUID(bucket_id)
        bucket_row = await self._get_bucket_row(
            user_uuid=user_uuid, bucket_id=bucket_uuid
        )
        if not bucket_row:
            raise RuntimeError("Bucket not found")

        old_path = str(bucket_row["path"])
        old_depth = int(bucket_row["depth"])

        parent_uuid: UUID | None = None
        new_depth = 0
        new_parent_path = "/root"

        if new_parent_bucket_id:
            parent_uuid = UUID(new_parent_bucket_id)
            if parent_uuid == bucket_uuid:
                raise RuntimeError("Cannot move a bucket into itself")

            parent_row = await self._get_bucket_row(
                user_uuid=user_uuid, bucket_id=parent_uuid
            )
            if not parent_row:
                raise RuntimeError("Target parent bucket not found")

            parent_path = str(parent_row["path"])
            if parent_path.startswith(f"{old_path}/"):
                raise RuntimeError("Cannot move a bucket into its own descendant")

            new_depth = int(parent_row["depth"]) + 1
            new_parent_path = parent_path

        new_path = f"{new_parent_path}/{self._bucket_slug(str(bucket_row['name']))}"
        depth_delta = new_depth - old_depth

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    UPDATE buckets
                    SET parent_bucket_id = $1,
                        depth = $2,
                        path = $3,
                        updated_at = NOW()
                    WHERE user_id = $4
                      AND id = $5
                      AND is_deleted = FALSE
                    """,
                    parent_uuid,
                    new_depth,
                    new_path,
                    user_uuid,
                    bucket_uuid,
                )

                await connection.execute(
                    """
                    UPDATE buckets
                    SET path = regexp_replace(path, '^' || $1, $2),
                        depth = depth + $3,
                        updated_at = NOW()
                    WHERE user_id = $4
                      AND is_deleted = FALSE
                      AND path LIKE $1 || '/%'
                    """,
                    old_path,
                    new_path,
                    depth_delta,
                    user_uuid,
                )

        moved = await self._get_bucket_row(user_uuid=user_uuid, bucket_id=bucket_uuid)
        if not moved:
            raise RuntimeError("Bucket move failed")

        return {
            "bucket_id": str(moved["id"]),
            "user_id": str(moved["user_id"]),
            "parent_bucket_id": (
                str(moved["parent_bucket_id"]) if moved["parent_bucket_id"] else None
            ),
            "depth": int(moved["depth"]),
            "name": moved["name"],
            "description": moved["description"],
            "icon_emoji": moved["icon_emoji"],
            "color_hex": moved["color_hex"],
            "document_count": int(moved["document_count"] or 0),
            "is_default": bool(moved["is_default"]),
            "is_deleted": bool(moved["is_deleted"]),
            "path": moved["path"],
            "created_at": moved["created_at"].isoformat(),
            "updated_at": moved["updated_at"].isoformat(),
        }

    async def _resolve_subtree_bucket_ids(
        self,
        *,
        user_uuid: UUID,
        root_bucket_uuid: UUID,
    ) -> list[UUID]:
        row = await self._get_bucket_row(
            user_uuid=user_uuid, bucket_id=root_bucket_uuid
        )
        if not row or not self._pool:
            return []

        root_path = str(row["path"])
        query = """
            SELECT id
            FROM buckets
            WHERE user_id = $1
              AND is_deleted = FALSE
              AND (path = $2 OR path LIKE $2 || '/%')
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, user_uuid, root_path)

        return [r["id"] for r in rows]

    async def resolve_subtree_bucket_ids_for_owner(
        self,
        *,
        owner_id: str,
        root_bucket_id: str,
    ) -> list[str]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid:
            return []

        try:
            root_uuid = UUID(root_bucket_id)
        except Exception:
            return []

        bucket_ids = await self._resolve_subtree_bucket_ids(
            user_uuid=user_uuid,
            root_bucket_uuid=root_uuid,
        )
        return [str(bucket_id) for bucket_id in bucket_ids]

    async def _refresh_bucket_document_counts(self, user_uuid: UUID) -> None:
        if not self._pool:
            return

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    UPDATE buckets b
                    SET document_count = sub.count,
                        updated_at = NOW()
                    FROM (
                        SELECT parent.id AS bucket_id, COUNT(d.id)::int AS count
                        FROM buckets parent
                        LEFT JOIN buckets child
                          ON child.user_id = parent.user_id
                         AND child.is_deleted = FALSE
                         AND (child.path = parent.path OR child.path LIKE parent.path || '/%')
                        LEFT JOIN documents d
                          ON d.bucket_id = child.id
                         AND d.created_by = parent.user_id
                        WHERE parent.user_id = $1
                          AND parent.is_deleted = FALSE
                        GROUP BY parent.id
                    ) sub
                    WHERE b.id = sub.bucket_id
                    """,
                    user_uuid,
                )

    @staticmethod
    def _routing_content_fingerprint(
        title: str | None, text_preview: str | None
    ) -> str:
        base = re.sub(
            r"\s+", " ", f"{title or ''} {text_preview or ''}".strip().lower()
        )
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    async def _record_bucket_routing_feedback_rows(
        self,
        *,
        user_uuid: UUID,
        moved_rows: list[asyncpg.Record],
        target_bucket_id: UUID,
    ) -> None:
        if not moved_rows or not self._pool:
            return
        if not await self._has_table("bucket_routing_feedback"):
            return

        values: list[tuple[UUID, UUID, UUID | None, UUID, str, str | None]] = []
        for row in moved_rows:
            extracted = row.get("extracted_metadata") or {}
            if isinstance(extracted, str):
                try:
                    extracted = json.loads(extracted)
                except Exception:
                    extracted = {}
            title = str(row.get("title") or "")
            text_preview = str(extracted.get("text_preview") or "")
            fingerprint = self._routing_content_fingerprint(title, text_preview)
            source_bucket_id = row.get("source_bucket_id")
            values.append(
                (
                    user_uuid,
                    row["id"],
                    source_bucket_id,
                    target_bucket_id,
                    fingerprint,
                    "user_bucket_move",
                )
            )

        if not values:
            return

        async with self._pool.acquire() as connection:
            await connection.executemany(
                """
                INSERT INTO bucket_routing_feedback (
                    user_id,
                    document_id,
                    source_bucket_id,
                    target_bucket_id,
                    content_fingerprint,
                    correction_reason
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                values,
            )

    async def bulk_move_documents(
        self,
        *,
        owner_id: str,
        source_bucket_id: str,
        target_bucket_id: str,
    ) -> dict[str, int]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid or not self._pool:
            raise RuntimeError("Valid authenticated user is required")

        source_uuid = UUID(source_bucket_id)
        target_uuid = UUID(target_bucket_id)
        if source_uuid == target_uuid:
            return {"moved_documents": 0}

        source_row = await self._get_bucket_row(
            user_uuid=user_uuid, bucket_id=source_uuid
        )
        target_row = await self._get_bucket_row(
            user_uuid=user_uuid, bucket_id=target_uuid
        )
        if not source_row or not target_row:
            raise RuntimeError("Source or target bucket not found")

        subtree_bucket_ids = await self._resolve_subtree_bucket_ids(
            user_uuid=user_uuid,
            root_bucket_uuid=source_uuid,
        )
        if not subtree_bucket_ids:
            return {"moved_documents": 0}

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                moved_rows = await connection.fetch(
                    """
                    WITH moved AS (
                        SELECT id, bucket_id, title, extracted_metadata
                        FROM documents
                        WHERE created_by = $2
                          AND bucket_id = ANY($3::uuid[])
                    )
                    UPDATE documents d
                    SET bucket_id = $1,
                        updated_by = $2,
                        updated_at = NOW()
                    FROM moved m
                    WHERE d.id = m.id
                    RETURNING d.id,
                              m.bucket_id AS source_bucket_id,
                              m.title,
                              m.extracted_metadata
                    """,
                    target_uuid,
                    user_uuid,
                    subtree_bucket_ids,
                )

                moved_document_ids = [row["id"] for row in moved_rows]

                if moved_document_ids:
                    await connection.execute(
                        """
                        UPDATE document_chunks
                        SET chunk_metadata = jsonb_set(
                                COALESCE(chunk_metadata, '{}'::jsonb),
                                '{bucket_id}',
                                to_jsonb($1::text),
                                TRUE
                            )
                        WHERE document_id = ANY($2::uuid[])
                        """,
                        str(target_uuid),
                        moved_document_ids,
                    )

        await self._record_bucket_routing_feedback_rows(
            user_uuid=user_uuid,
            moved_rows=moved_rows,
            target_bucket_id=target_uuid,
        )

        moved_count = len(moved_document_ids)

        if moved_document_ids and self._qdrant:

            def _set_payload_for_collection(collection_name: str) -> None:
                client = self._qdrant
                if not client:
                    return
                qdrant_filter = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="user_id",
                            match=qmodels.MatchValue(value=str(user_uuid)),
                        ),
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchAny(
                                any=[str(doc_id) for doc_id in moved_document_ids]
                            ),
                        ),
                    ]
                )
                points, _ = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=qdrant_filter,
                    limit=max(len(moved_document_ids) * 256, 1000),
                    with_payload=False,
                    with_vectors=False,
                )
                point_ids = [point.id for point in points if point.id is not None]
                if not point_ids:
                    return
                client.set_payload(
                    collection_name=collection_name,
                    payload={"bucket_id": str(target_uuid)},
                    points=point_ids,
                    wait=False,
                )

            await asyncio.to_thread(
                _set_payload_for_collection, self.config.qdrant_collection
            )
            await asyncio.to_thread(
                _set_payload_for_collection,
                self.config.qdrant_fallback_collection,
            )

        await self._refresh_bucket_document_counts(user_uuid)
        return {"moved_documents": moved_count}

    async def delete_bucket(
        self,
        *,
        owner_id: str,
        bucket_id: str,
        target_bucket_id: str | None,
    ) -> dict[str, int]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid or not self._pool:
            raise RuntimeError("Valid authenticated user is required")

        bucket_uuid = UUID(bucket_id)
        bucket_row = await self._get_bucket_row(
            user_uuid=user_uuid, bucket_id=bucket_uuid
        )
        if not bucket_row:
            raise RuntimeError("Bucket not found")
        if bool(bucket_row["is_default"]):
            raise PermissionError("Default buckets cannot be deleted")

        target_uuid: UUID | None = UUID(target_bucket_id) if target_bucket_id else None
        if target_uuid is None:
            parent_uuid = bucket_row["parent_bucket_id"]
            target_uuid = parent_uuid if parent_uuid else None

        if target_uuid is None:
            fallback = await self._find_needs_classification_bucket(user_uuid)
            if fallback is None:
                await self._ensure_user_default_buckets(user_uuid)
                fallback = await self._find_needs_classification_bucket(user_uuid)
            if fallback is None:
                raise RuntimeError(
                    "No valid target bucket available for redistribution"
                )
            target_uuid = fallback

        subtree_bucket_ids = await self._resolve_subtree_bucket_ids(
            user_uuid=user_uuid,
            root_bucket_uuid=bucket_uuid,
        )
        if not subtree_bucket_ids:
            return {"redistributed_documents": 0, "deleted_buckets": 0}

        if target_uuid in subtree_bucket_ids:
            raise RuntimeError(
                "Cannot redistribute documents into the bucket being deleted"
            )

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                moved = await connection.fetch(
                    """
                    WITH moved AS (
                        SELECT id, bucket_id, title, extracted_metadata
                        FROM documents
                        WHERE created_by = $2
                          AND bucket_id = ANY($3::uuid[])
                    )
                    UPDATE documents d
                    SET bucket_id = $1,
                        updated_by = $2,
                        updated_at = NOW()
                    FROM moved m
                    WHERE d.id = m.id
                    RETURNING d.id,
                              m.bucket_id AS source_bucket_id,
                              m.title,
                              m.extracted_metadata
                    """,
                    target_uuid,
                    user_uuid,
                    subtree_bucket_ids,
                )
                moved_document_ids = [row["id"] for row in moved]

                await connection.execute(
                    """
                    UPDATE buckets
                    SET is_deleted = TRUE,
                        deleted_at = NOW(),
                        updated_at = NOW()
                    WHERE user_id = $1
                      AND id = ANY($2::uuid[])
                    """,
                    user_uuid,
                    subtree_bucket_ids,
                )

        await self._record_bucket_routing_feedback_rows(
            user_uuid=user_uuid,
            moved_rows=moved,
            target_bucket_id=target_uuid,
        )

        if moved_document_ids and self._qdrant:

            def _set_payload_for_collection(collection_name: str) -> None:
                client = self._qdrant
                if not client:
                    return
                qdrant_filter = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="user_id",
                            match=qmodels.MatchValue(value=str(user_uuid)),
                        ),
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchAny(
                                any=[str(doc_id) for doc_id in moved_document_ids]
                            ),
                        ),
                    ]
                )
                points, _ = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=qdrant_filter,
                    limit=max(len(moved_document_ids) * 256, 1000),
                    with_payload=False,
                    with_vectors=False,
                )
                point_ids = [point.id for point in points if point.id is not None]
                if not point_ids:
                    return
                client.set_payload(
                    collection_name=collection_name,
                    payload={"bucket_id": str(target_uuid)},
                    points=point_ids,
                    wait=False,
                )

            await asyncio.to_thread(
                _set_payload_for_collection, self.config.qdrant_collection
            )
            await asyncio.to_thread(
                _set_payload_for_collection,
                self.config.qdrant_fallback_collection,
            )

        await self._refresh_bucket_document_counts(user_uuid)
        return {
            "redistributed_documents": len(moved_document_ids),
            "deleted_buckets": len(subtree_bucket_ids),
        }

    async def _find_needs_classification_bucket(self, user_uuid: UUID) -> UUID | None:
        if not self._pool:
            return None
        query = """
            SELECT id
            FROM buckets
            WHERE user_id = $1
              AND is_deleted = FALSE
              AND lower(name) = 'needs classification'
            ORDER BY created_at ASC
            LIMIT 1
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, user_uuid)
        return row["id"] if row else None

    async def _bucket_routing_feedback_boost(
        self,
        *,
        user_uuid: UUID,
        content_fingerprint: str,
    ) -> dict[str, float]:
        if not self._pool or not await self._has_table("bucket_routing_feedback"):
            return {}

        query = """
            SELECT target_bucket_id, COUNT(*)::int AS count
            FROM bucket_routing_feedback
            WHERE user_id = $1
              AND content_fingerprint = $2
            GROUP BY target_bucket_id
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, user_uuid, content_fingerprint)

        return {
            str(row["target_bucket_id"]): min(0.20, 0.05 * int(row["count"] or 0))
            for row in rows
        }

    async def _rank_bucket_candidates(
        self,
        *,
        user_uuid: UUID,
        title: str,
        preview_text: str,
        bucket_hint: str | None,
        buckets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        source_text = " ".join(
            [title.strip(), preview_text.strip()[:500], (bucket_hint or "").strip()]
        ).strip()
        normalized_source = re.sub(r"\s+", " ", source_text.lower())
        tokens = {token for token in re.findall(r"[a-z0-9]{3,}", normalized_source)}
        content_fingerprint = hashlib.sha256(
            normalized_source.encode("utf-8")
        ).hexdigest()
        boosts = await self._bucket_routing_feedback_boost(
            user_uuid=user_uuid,
            content_fingerprint=content_fingerprint,
        )

        scored: list[dict[str, Any]] = []
        for bucket in buckets:
            name = str(bucket.get("name") or "")
            description = str(bucket.get("description") or "")
            path = str(bucket.get("path") or "")
            bucket_tokens = {
                token
                for token in re.findall(
                    r"[a-z0-9]{3,}",
                    f"{name.lower()} {description.lower()} {path.lower()}",
                )
            }
            overlap = len(tokens & bucket_tokens)
            denom = max(1, len(tokens))
            overlap_score = overlap / denom
            name_bonus = 0.15 if any(t in name.lower() for t in tokens) else 0.0
            hint_bonus = (
                0.2
                if bucket_hint
                and any(
                    t in (name + " " + description).lower()
                    for t in re.findall(r"[a-z0-9]{3,}", bucket_hint.lower())
                )
                else 0.0
            )
            feedback_boost = float(boosts.get(str(bucket["bucket_id"]), 0.0))
            confidence = min(
                0.99,
                max(0.05, overlap_score + name_bonus + hint_bonus + feedback_boost),
            )
            scored.append(
                {
                    "bucket_id": str(bucket["bucket_id"]),
                    "confidence": confidence,
                    "reasoning": f"token_overlap={overlap}; hint_bonus={hint_bonus:.2f}; feedback_boost={feedback_boost:.2f}",
                }
            )

        scored.sort(key=lambda item: item["confidence"], reverse=True)
        return scored[:3]

    async def _gemini_rank_bucket_candidates(
        self,
        *,
        title: str,
        preview_text: str,
        bucket_hint: str | None,
        buckets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not buckets:
            return []

        try:
            client = ResilientGeminiClient(max_retries=2)
        except Exception:
            return []

        bucket_lines = []
        for bucket in buckets:
            bucket_lines.append(
                f"<bucket><bucket_id>{bucket['bucket_id']}</bucket_id><name>{bucket.get('name','')}</name><description>{bucket.get('description','')}</description><path>{bucket.get('path','')}</path><document_count>{bucket.get('document_count',0)}</document_count></bucket>"
            )

        hint_value = bucket_hint or ""
        prompt = (
            "<document_summary>"
            f"<title>{title}</title>"
            f"<preview>{preview_text[:500]}</preview>"
            f"<hint>{hint_value}</hint>"
            "</document_summary>"
            "<available_buckets>" + "".join(bucket_lines) + "</available_buckets>"
            "<classification_instruction>"
            "Return ONLY JSON with a top-level key 'candidates'."
            "Each candidate must include: bucket_id (string), confidence (0..1), reasoning (string)."
            "Return up to 3 candidates ordered best-to-worst."
            "</classification_instruction>"
        )

        try:
            raw = await client.generate_content(prompt=prompt, temperature=0.1)
            cleaned = raw.strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end < 0:
                return []
            payload = json.loads(cleaned[start : end + 1])
            candidates = list(payload.get("candidates") or [])
            normalized: list[dict[str, Any]] = []
            valid_bucket_ids = {str(bucket["bucket_id"]) for bucket in buckets}
            for item in candidates:
                bucket_id = str(item.get("bucket_id") or "")
                if not bucket_id or bucket_id not in valid_bucket_ids:
                    continue
                confidence = float(item.get("confidence") or 0.0)
                normalized.append(
                    {
                        "bucket_id": bucket_id,
                        "confidence": max(0.0, min(1.0, confidence)),
                        "reasoning": str(item.get("reasoning") or "gemini-classified"),
                    }
                )
            normalized.sort(key=lambda row: row["confidence"], reverse=True)
            return normalized[:3]
        except Exception:
            return []

    async def expand_query_gemini(
        self,
        query: str,
    ) -> list[str]:
        """Use Gemini to produce 2-3 alternative phrasings of the query.

        Returns a list of alternative query strings (not including the original).
        Returns an empty list when Gemini is unavailable so callers degrade
        gracefully to the original query.
        """
        if not query or len(query.strip()) < 3:
            return []
        try:
            client = ResilientGeminiClient(max_retries=1)
        except Exception:
            return []

        prompt = (
            "You are a search query expansion assistant. "
            "Given the user search query below, produce 2 to 3 alternative phrasings "
            "that have the same intent but use different words, synonyms, or formulations. "
            "Return ONLY a JSON object with a single key 'alternatives' whose value is an array of strings.\n"
            f"Query: {query}"
        )
        try:
            raw = await client.generate_content(prompt=prompt, temperature=0.3)
            cleaned = raw.strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end < 0:
                return []
            payload = json.loads(cleaned[start : end + 1])
            alternatives = [
                str(alt).strip()
                for alt in (payload.get("alternatives") or [])
                if str(alt).strip()
            ]
            return alternatives[:3]
        except Exception:
            return []

    async def route_content_bucket(
        self,
        *,
        owner_id: str,
        title: str,
        preview_text: str,
        explicit_bucket_id: str | None,
        bucket_hint: str | None,
    ) -> dict[str, Any]:
        user_uuid = await self._resolve_existing_user_uuid(owner_id)
        if not user_uuid:
            return {
                "mode": "anonymous",
                "selected_bucket_id": None,
                "selected_confidence": 0.0,
                "requires_confirmation": False,
                "candidates": [],
            }

        await self._ensure_user_default_buckets(user_uuid)
        bucket_rows = await self.list_buckets_for_user(owner_id)

        if explicit_bucket_id:
            explicit_uuid = UUID(explicit_bucket_id)
            explicit_row = await self._get_bucket_row(
                user_uuid=user_uuid,
                bucket_id=explicit_uuid,
            )
            if not explicit_row:
                raise RuntimeError("Explicit bucket not found")
            return {
                "mode": "explicit",
                "selected_bucket_id": str(explicit_row["id"]),
                "selected_confidence": 1.0,
                "requires_confirmation": False,
                "candidates": [
                    {
                        "bucket_id": str(explicit_row["id"]),
                        "confidence": 1.0,
                        "reasoning": "User explicit override",
                    }
                ],
            }

        heuristic_candidates = await self._rank_bucket_candidates(
            user_uuid=user_uuid,
            title=title,
            preview_text=preview_text,
            bucket_hint=bucket_hint,
            buckets=bucket_rows,
        )
        gemini_candidates = await self._gemini_rank_bucket_candidates(
            title=title,
            preview_text=preview_text,
            bucket_hint=bucket_hint,
            buckets=bucket_rows,
        )

        merged_by_bucket: dict[str, dict[str, Any]] = {}
        for source in (heuristic_candidates, gemini_candidates):
            for candidate in source:
                bucket_id = str(candidate["bucket_id"])
                previous = merged_by_bucket.get(bucket_id)
                confidence = float(candidate["confidence"])
                if previous is None or confidence > float(previous["confidence"]):
                    merged_by_bucket[bucket_id] = {
                        "bucket_id": bucket_id,
                        "confidence": confidence,
                        "reasoning": str(candidate.get("reasoning") or ""),
                    }

        candidates = sorted(
            merged_by_bucket.values(),
            key=lambda item: float(item["confidence"]),
            reverse=True,
        )[:3]

        if not candidates:
            fallback_bucket = await self._find_needs_classification_bucket(user_uuid)
            return {
                "mode": "fallback",
                "selected_bucket_id": str(fallback_bucket) if fallback_bucket else None,
                "selected_confidence": 0.0,
                "requires_confirmation": True,
                "candidates": [],
            }

        top = candidates[0]
        top_confidence = float(top["confidence"])
        needs_classification_bucket = await self._find_needs_classification_bucket(
            user_uuid
        )

        if top_confidence >= self.ROUTING_AUTO_CONFIDENCE_THRESHOLD:
            mode = "hint_auto" if bucket_hint else "auto"
            return {
                "mode": mode,
                "selected_bucket_id": top["bucket_id"],
                "selected_confidence": top_confidence,
                "requires_confirmation": False,
                "candidates": candidates,
            }

        if top_confidence >= self.ROUTING_CONFIRMATION_THRESHOLD:
            mode = "hint_confirmation" if bucket_hint else "confirmation"
            return {
                "mode": mode,
                "selected_bucket_id": top["bucket_id"],
                "selected_confidence": top_confidence,
                "requires_confirmation": True,
                "candidates": candidates[:2],
            }

        return {
            "mode": "needs_classification",
            "selected_bucket_id": (
                str(needs_classification_bucket)
                if needs_classification_bucket
                else top["bucket_id"]
            ),
            "selected_confidence": top_confidence,
            "requires_confirmation": True,
            "candidates": candidates[:2],
        }

    async def _ensure_minio_bucket(self) -> None:
        if not self.config.minio_enabled:
            return

        def _ensure() -> None:
            exists = self._minio_client.bucket_exists(self.config.minio_bucket)
            if not exists:
                self._minio_client.make_bucket(self.config.minio_bucket)

        await asyncio.to_thread(_ensure)

    async def _upload_bytes(
        self, object_key: str, content: bytes, mime_type: str | None
    ) -> None:
        if not self.config.minio_enabled:
            return

        await self._ensure_minio_bucket()

        def _put() -> None:
            self._minio_client.put_object(
                bucket_name=self.config.minio_bucket,
                object_name=object_key,
                data=io.BytesIO(content),
                length=len(content),
                content_type=mime_type or "application/octet-stream",
            )

        await asyncio.to_thread(_put)

    async def ensure_qdrant_collection(self) -> None:
        if not self._qdrant:
            return

        def _extract_vector_size(collection: Any) -> int | None:
            config = getattr(collection, "config", None)
            params = getattr(config, "params", None) if config else None
            vectors = getattr(params, "vectors", None) if params else None

            size = getattr(vectors, "size", None)
            if isinstance(size, int):
                return size

            if isinstance(vectors, dict):
                first_value = next(iter(vectors.values()), None)
                if first_value is not None:
                    dict_size = getattr(first_value, "size", None)
                    if isinstance(dict_size, int):
                        return dict_size
            return None

        def _ensure() -> None:
            client = self._qdrant
            if not client:
                return

            collection_specs = [
                (self.config.qdrant_collection, int(self.config.embedding_dimensions)),
                (self.config.qdrant_fallback_collection, 384),
            ]

            for collection_name, expected_size in collection_specs:
                existing = None
                try:
                    existing = client.get_collection(collection_name=collection_name)
                except Exception:
                    existing = None

                if existing is not None:
                    current_size = _extract_vector_size(existing)
                    if isinstance(current_size, int) and current_size != expected_size:
                        raise RuntimeError(
                            f"Qdrant collection {collection_name} has dimension {current_size}, expected {expected_size}."
                        )
                else:
                    client.create_collection(
                        collection_name=collection_name,
                        vectors_config=qmodels.VectorParams(
                            size=expected_size,
                            distance=qmodels.Distance.COSINE,
                            on_disk=False,
                        ),
                        hnsw_config=qmodels.HnswConfigDiff(
                            m=16,
                            ef_construct=100,
                            full_scan_threshold=10000,
                        ),
                        quantization_config=qmodels.ScalarQuantization(
                            scalar=qmodels.ScalarQuantizationConfig(
                                type=qmodels.ScalarType.INT8,
                                quantile=0.99,
                                always_ram=True,
                            )
                        ),
                    )

                for field_name, schema in (
                    ("user_id", qmodels.PayloadSchemaType.KEYWORD),
                    ("bucket_id", qmodels.PayloadSchemaType.KEYWORD),
                    ("content_type", qmodels.PayloadSchemaType.KEYWORD),
                    ("created_at", qmodels.PayloadSchemaType.INTEGER),
                    ("tags", qmodels.PayloadSchemaType.KEYWORD),
                    ("has_image", qmodels.PayloadSchemaType.BOOL),
                    ("document_id", qmodels.PayloadSchemaType.KEYWORD),
                ):
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=schema,
                    )

        await asyncio.to_thread(_ensure)

    async def get_cached_json(self, key: str) -> dict[str, Any] | None:
        if not self._redis:
            return None
        payload = await self._redis.get(key)
        if not payload:
            return None
        try:
            return json.loads(payload)
        except Exception:
            return None

    async def set_cached_json(
        self, key: str, value: dict[str, Any], ttl_seconds: int
    ) -> None:
        if not self._redis:
            return
        await self._redis.set(key, json.dumps(value), ex=ttl_seconds)

    async def _has_table(self, table_name: str) -> bool:
        if table_name in self._table_exists_cache:
            return self._table_exists_cache[table_name]

        if not self._pool:
            return False

        async with self._pool.acquire() as connection:
            exists = await connection.fetchval(
                "SELECT to_regclass($1) IS NOT NULL",
                f"public.{table_name}",
            )

        self._table_exists_cache[table_name] = bool(exists)
        return bool(exists)

    @staticmethod
    def _exact_dedup_key(normalized_sha256: str) -> str:
        return f"kb:dedup:exact:{normalized_sha256}"

    @staticmethod
    def _exact_dedup_hash_key() -> str:
        return "kb:dedup:exact:hash"

    @staticmethod
    def _exact_chunk_dedup_hash_key() -> str:
        return "kb:dedup:chunk:exact:hash"

    def _start_semantic_chunk_dedup_worker(self) -> None:
        if (
            self._semantic_chunk_dedup_worker_task
            and not self._semantic_chunk_dedup_worker_task.done()
        ):
            return
        self._semantic_chunk_dedup_queue = asyncio.Queue()
        self._semantic_chunk_dedup_worker_task = asyncio.create_task(
            self._semantic_chunk_dedup_worker(),
            name="kb-semantic-chunk-dedup-worker",
        )

    def _start_embedding_dlq_replay_worker(self) -> None:
        if not self._redis or not self.config.embedding_dlq_replay_enabled:
            return
        if (
            self._embedding_dlq_replay_task
            and not self._embedding_dlq_replay_task.done()
        ):
            return
        self._embedding_dlq_replay_task = asyncio.create_task(
            self._embedding_dlq_replay_loop(),
            name="kb-embedding-dlq-replay-worker",
        )

    async def _embedding_dlq_replay_loop(self) -> None:
        interval = max(1, int(self.config.embedding_dlq_replay_interval_seconds))
        logger.info(
            "Embedding DLQ replay worker started",
            extra={
                "interval_seconds": interval,
                "batch_size": int(self.config.embedding_dlq_replay_batch_size),
            },
        )

        while True:
            try:
                stats = await self.replay_embedding_dlq_once()
                if stats["processed"] > 0:
                    logger.info("Embedding DLQ replay cycle complete", extra=stats)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning(
                    "Embedding DLQ replay cycle failed",
                    extra={"error": str(error)},
                )
            await asyncio.sleep(interval)

    async def replay_embedding_dlq_once(self) -> dict[str, int]:
        if not self._redis:
            return {
                "processed": 0,
                "replayed": 0,
                "requeued": 0,
                "failed": 0,
                "unreplayable": 0,
            }

        max_items = max(1, int(self.config.embedding_dlq_replay_batch_size))
        max_attempts = max(1, int(self.config.embedding_dlq_replay_max_attempts))

        stats = {
            "processed": 0,
            "replayed": 0,
            "requeued": 0,
            "failed": 0,
            "unreplayable": 0,
        }

        for _ in range(max_items):
            raw_item = await self._redis.execute_command(
                "LPOP",
                self.EMBEDDING_DLQ_KEY,
            )
            if not raw_item:
                break

            stats["processed"] += 1

            raw_item_text = raw_item if isinstance(raw_item, str) else str(raw_item)

            try:
                payload = json.loads(raw_item_text)
            except Exception:
                await self._redis.execute_command(
                    "RPUSH",
                    self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
                    raw_item_text,
                )
                stats["unreplayable"] += 1
                continue

            texts = payload.get("texts") or payload.get("batch_texts")
            if not isinstance(texts, list) or not texts:
                payload["replay_error"] = "Missing replay payload: texts"
                payload["replay_recorded_at"] = datetime.now(UTC).isoformat()
                await self._redis.execute_command(
                    "RPUSH",
                    self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
                    json.dumps(payload),
                )
                stats["unreplayable"] += 1
                continue

            replay_attempt = int(payload.get("replay_attempt", 0)) + 1

            try:
                if self.config.embedding_queue_enabled:
                    from app.infrastructure.embedding_queue import run_embedding_task

                    vectors = await asyncio.to_thread(
                        run_embedding_task,
                        config=self.config,
                        texts=texts,
                    )
                else:
                    vectors = await self._embedding_provider.embed_documents_batch(
                        texts
                    )

                if len(vectors) != len(texts):
                    raise RuntimeError(
                        f"Embedding replay cardinality mismatch: got {len(vectors)} vectors for {len(texts)} texts"
                    )

                for text, vector in zip(texts, vectors):
                    cache_key = f"kb:embedding:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
                    await self._redis.set(
                        cache_key,
                        json.dumps([float(value) for value in vector]),
                        ex=int(self.config.embedding_cache_ttl_seconds),
                    )

                payload["replay_attempt"] = replay_attempt
                payload["replayed_at"] = datetime.now(UTC).isoformat()
                await self._redis.execute_command(
                    "RPUSH",
                    self.EMBEDDING_DLQ_REPLAYED_KEY,
                    json.dumps(payload),
                )
                stats["replayed"] += 1
            except Exception as error:
                payload["replay_attempt"] = replay_attempt
                payload["last_replay_error"] = str(error)
                payload["last_replay_attempt_at"] = datetime.now(UTC).isoformat()

                if replay_attempt >= max_attempts:
                    await self._redis.execute_command(
                        "RPUSH",
                        self.EMBEDDING_DLQ_FAILED_KEY,
                        json.dumps(payload),
                    )
                    stats["failed"] += 1
                else:
                    await self._redis.execute_command(
                        "RPUSH",
                        self.EMBEDDING_DLQ_KEY,
                        json.dumps(payload),
                    )
                    stats["requeued"] += 1

        return stats

    async def get_embedding_dlq_stats(self) -> dict[str, int]:
        if not self._redis:
            return {
                "active_dlq": 0,
                "unreplayable": 0,
                "replayed": 0,
                "failed": 0,
            }

        active_dlq = int(
            await self._redis.execute_command("LLEN", self.EMBEDDING_DLQ_KEY) or 0
        )
        unreplayable = int(
            await self._redis.execute_command(
                "LLEN", self.EMBEDDING_DLQ_UNREPLAYABLE_KEY
            )
            or 0
        )
        replayed = int(
            await self._redis.execute_command("LLEN", self.EMBEDDING_DLQ_REPLAYED_KEY)
            or 0
        )
        failed = int(
            await self._redis.execute_command("LLEN", self.EMBEDDING_DLQ_FAILED_KEY)
            or 0
        )

        return {
            "active_dlq": active_dlq,
            "unreplayable": unreplayable,
            "replayed": replayed,
            "failed": failed,
        }

    async def reprocess_embedding_unreplayable(
        self,
        *,
        max_items: int,
        purge_unrecoverable: bool,
    ) -> dict[str, int]:
        if not self._redis:
            return {
                "processed": 0,
                "moved_to_dlq": 0,
                "kept_unreplayable": 0,
                "purged": 0,
            }

        stats = {
            "processed": 0,
            "moved_to_dlq": 0,
            "kept_unreplayable": 0,
            "purged": 0,
        }

        for _ in range(max(1, int(max_items))):
            raw_item = await self._redis.execute_command(
                "LPOP",
                self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
            )
            if not raw_item:
                break

            stats["processed"] += 1
            raw_item_text = raw_item if isinstance(raw_item, str) else str(raw_item)

            try:
                payload = json.loads(raw_item_text)
            except Exception:
                if purge_unrecoverable:
                    stats["purged"] += 1
                else:
                    await self._redis.execute_command(
                        "RPUSH",
                        self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
                        raw_item_text,
                    )
                    stats["kept_unreplayable"] += 1
                continue

            texts = payload.get("texts") or payload.get("batch_texts")
            normalized_texts = [
                str(text) for text in list(texts or []) if str(text).strip()
            ]
            if normalized_texts:
                payload["texts"] = normalized_texts
                payload["reprocessed_at"] = datetime.now(UTC).isoformat()
                await self._redis.execute_command(
                    "RPUSH",
                    self.EMBEDDING_DLQ_KEY,
                    json.dumps(payload),
                )
                stats["moved_to_dlq"] += 1
                continue

            if purge_unrecoverable:
                stats["purged"] += 1
            else:
                payload["reprocess_error"] = "Missing replay payload: texts"
                payload["reprocess_checked_at"] = datetime.now(UTC).isoformat()
                await self._redis.execute_command(
                    "RPUSH",
                    self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
                    json.dumps(payload),
                )
                stats["kept_unreplayable"] += 1

        return stats

    async def purge_embedding_unreplayable(self, *, max_items: int) -> dict[str, int]:
        if not self._redis:
            return {"purged": 0}

        if int(max_items) <= 0:
            existing_count = int(
                await self._redis.execute_command(
                    "LLEN", self.EMBEDDING_DLQ_UNREPLAYABLE_KEY
                )
                or 0
            )
            if existing_count > 0:
                await self._redis.execute_command(
                    "DEL",
                    self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
                )
            return {"purged": existing_count}

        purged = 0
        for _ in range(int(max_items)):
            removed = await self._redis.execute_command(
                "LPOP",
                self.EMBEDDING_DLQ_UNREPLAYABLE_KEY,
            )
            if not removed:
                break
            purged += 1

        return {"purged": purged}

    async def _semantic_chunk_dedup_worker(self) -> None:
        queue = self._semantic_chunk_dedup_queue
        if not queue:
            return

        while True:
            (
                minhash_signature,
                minhash_band_hashes,
                semantic_threshold,
                future,
            ) = await queue.get()
            try:
                result = await self._find_semantic_chunk_duplicate(
                    minhash_signature=minhash_signature,
                    minhash_band_hashes=minhash_band_hashes,
                    semantic_threshold=semantic_threshold,
                )
                if not future.done():
                    future.set_result(result)
            except Exception as error:
                if not future.done():
                    future.set_exception(error)
            finally:
                queue.task_done()

    async def _enqueue_semantic_chunk_dedup(
        self,
        *,
        minhash_signature: list[int],
        minhash_band_hashes: list[int],
        semantic_threshold: float,
    ) -> dict[str, Any] | None:
        if not self._semantic_chunk_dedup_queue:
            self._start_semantic_chunk_dedup_worker()
        if not self._semantic_chunk_dedup_queue:
            return await self._find_semantic_chunk_duplicate(
                minhash_signature=minhash_signature,
                minhash_band_hashes=minhash_band_hashes,
                semantic_threshold=semantic_threshold,
            )

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any] | None] = loop.create_future()
        await self._semantic_chunk_dedup_queue.put(
            (minhash_signature, minhash_band_hashes, semantic_threshold, future)
        )
        return await future

    async def _get_document_summary(self, document_id: UUID) -> dict[str, Any] | None:
        if not self._pool:
            return None

        query = """
            SELECT
                d.id,
                d.created_by,
                d.status,
                d.content_type,
                d.created_at,
                d.extracted_metadata,
                d.processing_metadata
            FROM documents d
            WHERE d.id = $1
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, document_id)

        if not row:
            return None

        extracted = row["extracted_metadata"] or {}
        if isinstance(extracted, str):
            try:
                extracted = json.loads(extracted)
            except Exception:
                extracted = {}
        processing = row["processing_metadata"] or {}
        if isinstance(processing, str):
            try:
                processing = json.loads(processing)
            except Exception:
                processing = {}

        return {
            "document_id": str(row["id"]),
            "owner_id": str(row["created_by"]) if row["created_by"] else "anonymous",
            "status": row["status"],
            "content_type": row["content_type"],
            "strategy": extracted.get("strategy", "text_direct"),
            "word_count": extracted.get("word_count") or 0,
            "char_count": extracted.get("char_count") or 0,
            "metadata": {
                **extracted,
                "processing_metadata": processing,
            },
            "created_at": row["created_at"].isoformat(),
        }

    async def find_duplicate_candidate(
        self,
        *,
        normalized_sha256: str,
        simhash: int,
        simhash_band_hashes: list[int],
        minhash_signature: list[int],
        minhash_band_hashes: list[int],
        near_threshold: int = 3,
        semantic_threshold: float = 0.85,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("KnowledgePersistence pool is not initialized")
        if not await self._has_table("document_dedup_signatures"):
            return None

        exact_duplicate = await self._find_exact_duplicate(normalized_sha256)
        if exact_duplicate:
            exact_duplicate["dedup_stage"] = "exact"
            exact_duplicate["dedup_score"] = 1.0
            return exact_duplicate

        near_duplicate = await self._find_near_duplicate(
            simhash=simhash,
            simhash_band_hashes=simhash_band_hashes,
            near_threshold=near_threshold,
        )
        if near_duplicate:
            near_duplicate["dedup_stage"] = "near"
            return near_duplicate

        semantic_duplicate = await self._find_semantic_duplicate(
            minhash_signature=minhash_signature,
            minhash_band_hashes=minhash_band_hashes,
            semantic_threshold=semantic_threshold,
        )
        if semantic_duplicate:
            semantic_duplicate["dedup_stage"] = "semantic"
            return semantic_duplicate

        return None

    async def _find_exact_duplicate(
        self, normalized_sha256: str
    ) -> dict[str, Any] | None:
        pool = self._pool
        if not pool:
            return None

        if self._redis:
            cached = await self._redis.execute_command(
                "HGET", self._exact_dedup_hash_key(), normalized_sha256
            )
            if not cached:
                cached = await self._redis.get(self._exact_dedup_key(normalized_sha256))
            if cached:
                try:
                    summary = await self._get_document_summary(UUID(cached))
                    if summary:
                        return summary
                except Exception:
                    pass

        query = """
            SELECT document_id
            FROM document_dedup_signatures
            WHERE normalized_sha256 = $1
            LIMIT 1
        """
        async with pool.acquire() as connection:
            row = await connection.fetchrow(query, normalized_sha256)

        if not row:
            return None

        document_id = row["document_id"]
        summary = await self._get_document_summary(document_id)
        if summary and self._redis:
            await self._redis.execute_command(
                "HSET",
                self._exact_dedup_hash_key(),
                normalized_sha256,
                str(document_id),
            )
            await self._redis.set(
                self._exact_dedup_key(normalized_sha256),
                str(document_id),
                ex=60 * 60 * 24,
            )
        return summary

    async def _find_near_duplicate(
        self,
        *,
        simhash: int,
        simhash_band_hashes: list[int],
        near_threshold: int,
    ) -> dict[str, Any] | None:
        pool = self._pool
        if not pool:
            return None

        query = """
            SELECT
                s.document_id,
                s.simhash
            FROM document_dedup_signatures s
            WHERE s.simhash_band_hashes && $1::bigint[]
            LIMIT 128
        """
        async with pool.acquire() as connection:
            rows = await connection.fetch(query, simhash_band_hashes)

        candidate_id: UUID | None = None
        best_distance: int | None = None
        current_unsigned = to_unsigned_bigint(simhash)

        for row in rows:
            candidate_unsigned = to_unsigned_bigint(int(row["simhash"]))
            distance = hamming_distance_64(current_unsigned, candidate_unsigned)
            if distance < near_threshold and (
                best_distance is None or distance < best_distance
            ):
                best_distance = distance
                candidate_id = row["document_id"]

        if not candidate_id:
            return None

        summary = await self._get_document_summary(candidate_id)
        if not summary:
            return None
        summary["dedup_score"] = 1.0 - (best_distance / 64.0 if best_distance else 0.0)
        summary["hamming_distance"] = best_distance
        return summary

    async def _find_semantic_duplicate(
        self,
        *,
        minhash_signature: list[int],
        minhash_band_hashes: list[int],
        semantic_threshold: float,
    ) -> dict[str, Any] | None:
        pool = self._pool
        if not pool:
            return None

        query = """
            SELECT
                s.document_id,
                s.minhash_signature
            FROM document_dedup_signatures s
            WHERE s.minhash_band_hashes && $1::bigint[]
            LIMIT 128
        """
        async with pool.acquire() as connection:
            rows = await connection.fetch(query, minhash_band_hashes)

        candidate_id: UUID | None = None
        best_similarity = 0.0

        for row in rows:
            candidate_signature = list(row["minhash_signature"] or [])
            if len(candidate_signature) != len(minhash_signature):
                continue
            similarity = minhash_similarity(minhash_signature, candidate_signature)
            if similarity > semantic_threshold and similarity > best_similarity:
                best_similarity = similarity
                candidate_id = row["document_id"]

        if not candidate_id:
            return None

        summary = await self._get_document_summary(candidate_id)
        if not summary:
            return None
        summary["dedup_score"] = best_similarity
        return summary

    async def register_duplicate_access(
        self,
        *,
        document_id: str,
        source_url: str | None,
        dedup_stage: str,
        dedup_score: float | None,
    ) -> dict[str, Any] | None:
        if not self._pool:
            return None
        if not await self._has_table("documents"):
            return None

        query = """
            SELECT source_metadata, extracted_metadata, processing_metadata
            FROM documents
            WHERE id = $1::uuid
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, document_id)
            if not row:
                return None

            source_raw = row["source_metadata"] or {}
            if isinstance(source_raw, str):
                try:
                    source_raw = json.loads(source_raw)
                except Exception:
                    source_raw = {}
            source_metadata = dict(source_raw)

            extracted_raw = row["extracted_metadata"] or {}
            if isinstance(extracted_raw, str):
                try:
                    extracted_raw = json.loads(extracted_raw)
                except Exception:
                    extracted_raw = {}
            extracted_metadata = dict(extracted_raw)

            processing_raw = row["processing_metadata"] or {}
            if isinstance(processing_raw, str):
                try:
                    processing_raw = json.loads(processing_raw)
                except Exception:
                    processing_raw = {}
            processing_metadata = dict(processing_raw)

            access_count = int(extracted_metadata.get("dedup_access_count", 0)) + 1
            extracted_metadata["dedup_access_count"] = access_count
            extracted_metadata["dedup_last_stage"] = dedup_stage

            duplicate_events = list(processing_metadata.get("duplicate_events", []))
            duplicate_events.append(
                {
                    "stage": dedup_stage,
                    "score": dedup_score,
                }
            )
            processing_metadata["duplicate_events"] = duplicate_events[-20:]

            if source_url:
                existing_urls = list(source_metadata.get("alternate_source_urls", []))
                if source_url not in existing_urls:
                    existing_urls.append(source_url)
                source_metadata["alternate_source_urls"] = existing_urls

            await connection.execute(
                """
                UPDATE documents
                SET
                    source_metadata = $2::jsonb,
                    extracted_metadata = $3::jsonb,
                    processing_metadata = $4::jsonb,
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                document_id,
                json.dumps(source_metadata),
                json.dumps(extracted_metadata),
                json.dumps(processing_metadata),
            )

        return await self._get_document_summary(UUID(document_id))

    async def register_document_signatures(
        self,
        *,
        document_id: UUID,
        normalized_sha256: str,
        simhash: int,
        simhash_band_hashes: list[int],
        minhash_signature: list[int],
        minhash_band_hashes: list[int],
    ) -> None:
        if not self._pool:
            return
        if not await self._has_table("document_dedup_signatures"):
            return

        query = """
            INSERT INTO document_dedup_signatures (
                document_id,
                normalized_sha256,
                simhash,
                simhash_band_hashes,
                minhash_signature,
                minhash_band_hashes
            )
            VALUES ($1, $2, $3, $4::bigint[], $5::bigint[], $6::bigint[])
            ON CONFLICT (normalized_sha256)
            DO NOTHING
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                query,
                document_id,
                normalized_sha256,
                simhash,
                simhash_band_hashes,
                minhash_signature,
                minhash_band_hashes,
            )

        if self._redis:
            await self._redis.execute_command(
                "HSET",
                self._exact_dedup_hash_key(),
                normalized_sha256,
                str(document_id),
            )
            await self._redis.set(
                self._exact_dedup_key(normalized_sha256),
                str(document_id),
                ex=60 * 60 * 24,
            )

    async def _get_chunk_summary(
        self,
        *,
        document_id: UUID,
        chunk_index: int,
    ) -> dict[str, Any] | None:
        if not self._pool:
            return None

        query = """
            SELECT
                c.id AS chunk_id,
                c.chunk_index,
                c.document_id,
                c.content_type,
                c.token_count,
                c.char_count,
                c.chunk_metadata,
                d.created_by,
                d.created_at
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.document_id = $1 AND c.chunk_index = $2
            LIMIT 1
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, document_id, chunk_index)

        if not row:
            return None

        chunk_metadata = row["chunk_metadata"] or {}
        if isinstance(chunk_metadata, str):
            try:
                chunk_metadata = json.loads(chunk_metadata)
            except Exception:
                chunk_metadata = {}

        return {
            "chunk_id": str(row["chunk_id"]),
            "chunk_index": int(row["chunk_index"]),
            "document_id": str(row["document_id"]),
            "owner_id": str(row["created_by"]) if row["created_by"] else "anonymous",
            "content_type": row["content_type"],
            "token_count": int(row["token_count"]),
            "char_count": int(row["char_count"]),
            "metadata": chunk_metadata,
            "created_at": row["created_at"].isoformat(),
        }

    async def find_chunk_duplicate_candidate(
        self,
        *,
        normalized_sha256: str,
        simhash: int,
        simhash_band_hashes: list[int],
        minhash_signature: list[int],
        minhash_band_hashes: list[int],
        near_threshold: int = 3,
        semantic_threshold: float = 0.85,
        semantic_async: bool = True,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("KnowledgePersistence pool is not initialized")
        if not await self._has_table("chunk_dedup_signatures"):
            return None

        exact_duplicate = await self._find_exact_chunk_duplicate(normalized_sha256)
        if exact_duplicate:
            exact_duplicate["dedup_stage"] = "exact"
            exact_duplicate["dedup_score"] = 1.0
            return exact_duplicate

        near_duplicate = await self._find_near_chunk_duplicate(
            simhash=simhash,
            simhash_band_hashes=simhash_band_hashes,
            near_threshold=near_threshold,
        )
        if near_duplicate:
            near_duplicate["dedup_stage"] = "near"
            return near_duplicate

        if semantic_async:
            semantic_duplicate = await self._enqueue_semantic_chunk_dedup(
                minhash_signature=minhash_signature,
                minhash_band_hashes=minhash_band_hashes,
                semantic_threshold=semantic_threshold,
            )
        else:
            semantic_duplicate = await self._find_semantic_chunk_duplicate(
                minhash_signature=minhash_signature,
                minhash_band_hashes=minhash_band_hashes,
                semantic_threshold=semantic_threshold,
            )

        if semantic_duplicate:
            semantic_duplicate["dedup_stage"] = "semantic"
            return semantic_duplicate

        return None

    async def _find_exact_chunk_duplicate(
        self,
        normalized_sha256: str,
    ) -> dict[str, Any] | None:
        if not self._pool:
            return None

        if self._redis:
            cached = await self._redis.execute_command(
                "HGET",
                self._exact_chunk_dedup_hash_key(),
                normalized_sha256,
            )
            if cached:
                try:
                    payload = json.loads(cached)
                    document_id = UUID(payload["document_id"])
                    chunk_index = int(payload["chunk_index"])
                    summary = await self._get_chunk_summary(
                        document_id=document_id,
                        chunk_index=chunk_index,
                    )
                    if summary:
                        return summary
                except Exception:
                    pass

        query = """
            SELECT document_id, chunk_index
            FROM chunk_dedup_signatures
            WHERE normalized_sha256 = $1
            LIMIT 1
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(query, normalized_sha256)

        if not row:
            return None

        summary = await self._get_chunk_summary(
            document_id=row["document_id"],
            chunk_index=int(row["chunk_index"]),
        )
        if summary and self._redis:
            payload = json.dumps(
                {
                    "document_id": summary["document_id"],
                    "chunk_index": summary["chunk_index"],
                }
            )
            await self._redis.execute_command(
                "HSET",
                self._exact_chunk_dedup_hash_key(),
                normalized_sha256,
                payload,
            )

        return summary

    async def _find_near_chunk_duplicate(
        self,
        *,
        simhash: int,
        simhash_band_hashes: list[int],
        near_threshold: int,
    ) -> dict[str, Any] | None:
        if not self._pool:
            return None

        query = """
            SELECT
                s.document_id,
                s.chunk_index,
                s.simhash
            FROM chunk_dedup_signatures s
            WHERE s.simhash_band_hashes && $1::bigint[]
            LIMIT 128
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, simhash_band_hashes)

        candidate_document_id: UUID | None = None
        candidate_chunk_index: int | None = None
        best_distance: int | None = None
        current_unsigned = to_unsigned_bigint(simhash)

        for row in rows:
            candidate_unsigned = to_unsigned_bigint(int(row["simhash"]))
            distance = hamming_distance_64(current_unsigned, candidate_unsigned)
            if distance < near_threshold and (
                best_distance is None or distance < best_distance
            ):
                best_distance = distance
                candidate_document_id = row["document_id"]
                candidate_chunk_index = int(row["chunk_index"])

        if candidate_document_id is None or candidate_chunk_index is None:
            return None

        summary = await self._get_chunk_summary(
            document_id=candidate_document_id,
            chunk_index=candidate_chunk_index,
        )
        if not summary:
            return None

        summary["dedup_score"] = 1.0 - (best_distance / 64.0 if best_distance else 0.0)
        summary["hamming_distance"] = best_distance
        return summary

    async def _find_semantic_chunk_duplicate(
        self,
        *,
        minhash_signature: list[int],
        minhash_band_hashes: list[int],
        semantic_threshold: float,
    ) -> dict[str, Any] | None:
        if not self._pool:
            return None

        query = """
            SELECT
                s.document_id,
                s.chunk_index,
                s.minhash_signature
            FROM chunk_dedup_signatures s
            WHERE s.minhash_band_hashes && $1::bigint[]
            LIMIT 128
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, minhash_band_hashes)

        candidate_document_id: UUID | None = None
        candidate_chunk_index: int | None = None
        best_similarity = 0.0

        for row in rows:
            candidate_signature = list(row["minhash_signature"] or [])
            if len(candidate_signature) != len(minhash_signature):
                continue
            similarity = minhash_similarity(minhash_signature, candidate_signature)
            if similarity > semantic_threshold and similarity > best_similarity:
                best_similarity = similarity
                candidate_document_id = row["document_id"]
                candidate_chunk_index = int(row["chunk_index"])

        if candidate_document_id is None or candidate_chunk_index is None:
            return None

        summary = await self._get_chunk_summary(
            document_id=candidate_document_id,
            chunk_index=candidate_chunk_index,
        )
        if not summary:
            return None

        summary["dedup_score"] = best_similarity
        return summary

    async def register_chunk_signatures(
        self,
        *,
        document_id: UUID,
        signatures: list[dict[str, Any]],
    ) -> None:
        if not self._pool or not signatures:
            return
        if not await self._has_table("chunk_dedup_signatures"):
            return

        query = """
            INSERT INTO chunk_dedup_signatures (
                document_id,
                chunk_index,
                normalized_sha256,
                simhash,
                simhash_band_hashes,
                minhash_signature,
                minhash_band_hashes
            )
            VALUES ($1, $2, $3, $4, $5::bigint[], $6::bigint[], $7::bigint[])
            ON CONFLICT (normalized_sha256)
            DO NOTHING
        """
        async with self._pool.acquire() as connection:
            for signature in signatures:
                await connection.execute(
                    query,
                    document_id,
                    int(signature["chunk_index"]),
                    signature["normalized_sha256"],
                    signature["simhash"],
                    list(signature["simhash_band_hashes"]),
                    list(signature["minhash_signature"]),
                    list(signature["minhash_band_hashes"]),
                )

        if self._redis:
            for signature in signatures:
                await self._redis.execute_command(
                    "HSET",
                    self._exact_chunk_dedup_hash_key(),
                    signature["normalized_sha256"],
                    json.dumps(
                        {
                            "document_id": str(document_id),
                            "chunk_index": int(signature["chunk_index"]),
                        }
                    ),
                )

    async def record_integrity_chain(
        self,
        *,
        document_id: UUID,
        checkpoints: list[IntegrityCheckpoint],
    ) -> None:
        if not self._pool or not checkpoints:
            return
        if not await self._has_table("document_integrity_checks"):
            return

        query = """
            INSERT INTO document_integrity_checks (
                document_id,
                stage_name,
                checksum_md5,
                previous_checksum_md5,
                chain_hash_sha256,
                is_verified
            )
            VALUES ($1, $2, $3, $4, $5, $6)
        """

        async with self._pool.acquire() as connection:
            for checkpoint in checkpoints:
                await connection.execute(
                    query,
                    document_id,
                    checkpoint.stage_name,
                    checkpoint.checksum_md5,
                    checkpoint.previous_checksum_md5,
                    checkpoint.chain_hash_sha256,
                    checkpoint.is_verified,
                )

    async def persist_processed_document(
        self,
        *,
        owner_id: str,
        filename: str,
        source_url: str | None,
        mime_type: str | None,
        content_bytes: bytes | None,
        structured: StructuredDocument,
        content_bucket_id: str | None = None,
        routing_metadata: dict[str, Any] | None = None,
        dedup: dict[str, Any] | None = None,
        integrity_checkpoints: list[IntegrityCheckpoint] | None = None,
    ) -> dict[str, Any]:
        if not self._pool:
            raise RuntimeError("KnowledgePersistence pool is not initialized")

        user_uuid = await self._resolve_existing_user_uuid(owner_id)

        document_id = uuid4()
        safe_filename = Path(filename).name or "document.bin"
        source_type = "upload" if content_bytes else ("url" if source_url else "api")

        resolved_content_bucket_id: UUID | None = None
        if content_bucket_id and user_uuid:
            candidate_uuid = UUID(content_bucket_id)
            bucket_row = await self._get_bucket_row(
                user_uuid=user_uuid,
                bucket_id=candidate_uuid,
            )
            if bucket_row:
                resolved_content_bucket_id = candidate_uuid

        if resolved_content_bucket_id is None:
            resolved_content_bucket_id = await self._ensure_storage_bucket_record(
                user_uuid
            )

        minio_storage_bucket_name = self.config.minio_bucket

        storage_key: str | None = None
        if content_bytes:
            storage_key = f"documents/{document_id}/v1/{safe_filename}"
            try:
                await self._upload_bytes(storage_key, content_bytes, mime_type)
            except S3Error as error:
                raise RuntimeError(f"MinIO upload failed: {error}") from error

        extracted_metadata = {
            **structured.metadata,
            "strategy": structured.strategy_used.value,
            "format": structured.format.value,
            "content_class": structured.content_class.value,
            "sections_count": len(structured.sections),
            "tables_count": len(structured.tables),
            "images_count": len(structured.images),
            "chunk_count": len(structured.chunks),
        }
        if routing_metadata:
            extracted_metadata["bucket_routing"] = routing_metadata
        if dedup:
            extracted_metadata["dedup"] = {
                "normalized_sha256": dedup.get("normalized_sha256"),
                "simhash": dedup.get("simhash"),
            }
        if integrity_checkpoints:
            extracted_metadata["integrity_final_checksum_md5"] = integrity_checkpoints[
                -1
            ].checksum_md5

        processing_metadata = {
            "confidence_scores": structured.confidence_scores,
            "strategy": structured.strategy_used.value,
            "detected_format": structured.metadata.get("detected_format"),
        }

        chunk_insert = """
            INSERT INTO document_chunks (
                document_id,
                chunk_index,
                total_chunks,
                content,
                token_count,
                char_count,
                page_start,
                page_end,
                section_heading,
                parent_chunk_id,
                content_type,
                embedding_model,
                chunk_metadata,
                has_image,
                image_ids,
                created_by
            )
            VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14,$15::jsonb,$16
            )
        """

        document_insert = """
            INSERT INTO documents (
                id,
                bucket_id,
                title,
                content_type,
                mime_type,
                source_type,
                source_url,
                source_metadata,
                storage_backend,
                storage_bucket,
                storage_key,
                file_size,
                checksum,
                status,
                processing_stage,
                processing_metadata,
                language,
                page_count,
                word_count,
                char_count,
                extracted_metadata,
                created_by,
                updated_by,
                processed_at
            )
            VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,$20,$21::jsonb,$22,$23,NOW()
            )
            RETURNING id, created_at
        """

        source_metadata = {
            "filename": filename,
            "source_url": source_url,
        }

        file_size = (
            len(content_bytes)
            if content_bytes
            else structured.metadata.get("file_size")
        )
        checksum = structured.metadata.get("checksum")
        word_count = structured.metadata.get("word_count", len(structured.text.split()))
        char_count = structured.metadata.get("char_count", len(structured.text))
        page_count = structured.metadata.get("page_count")

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                created = await connection.fetchrow(
                    document_insert,
                    document_id,
                    resolved_content_bucket_id,
                    Path(filename).stem,
                    structured.format.value,
                    mime_type,
                    source_type,
                    source_url,
                    json.dumps(source_metadata),
                    "minio" if storage_key else "inline",
                    minio_storage_bucket_name if storage_key else None,
                    storage_key,
                    file_size,
                    checksum,
                    "completed",
                    "ingestion_complete",
                    json.dumps(processing_metadata),
                    structured.metadata.get("language", "en"),
                    page_count,
                    word_count,
                    char_count,
                    json.dumps(extracted_metadata),
                    user_uuid,
                    user_uuid,
                )

                if storage_key:
                    await connection.execute(
                        """
                        INSERT INTO document_versions (
                            document_id,
                            version_number,
                            storage_key,
                            checksum,
                            file_size,
                            change_summary,
                            created_by
                        )
                        VALUES ($1, 1, $2, $3, $4, $5, $6)
                        """,
                        document_id,
                        storage_key,
                        checksum,
                        file_size,
                        "Initial ingestion version",
                        user_uuid,
                    )

                total_chunks = len(structured.chunks)
                for chunk_index, chunk in enumerate(structured.chunks):
                    chunk_metadata = dict(chunk.metadata or {})
                    chunk_metadata["document_id"] = str(document_id)
                    chunk_metadata["source_document_id"] = str(document_id)
                    chunk_metadata["bucket_id"] = (
                        str(resolved_content_bucket_id)
                        if resolved_content_bucket_id
                        else None
                    )
                    if integrity_checkpoints:
                        chunk_metadata["integrity_final_checksum_md5"] = (
                            integrity_checkpoints[-1].checksum_md5
                        )

                    page_range = chunk_metadata.get("page_range") or []
                    page_start = (
                        page_range[0]
                        if isinstance(page_range, list) and len(page_range) >= 1
                        else None
                    )
                    page_end = (
                        page_range[1]
                        if isinstance(page_range, list) and len(page_range) >= 2
                        else page_start
                    )

                    image_ids = chunk_metadata.get("image_ids") or []
                    if not isinstance(image_ids, list):
                        image_ids = []

                    parent_chunk = chunk_metadata.get(
                        "parent_chunk_id"
                    ) or chunk_metadata.get("parent_chunk")
                    parent_chunk_uuid = None
                    if isinstance(parent_chunk, str):
                        try:
                            parent_chunk_uuid = UUID(parent_chunk)
                        except Exception:
                            parent_chunk_uuid = None

                    chunk_metadata["parent_chunk_id"] = (
                        str(parent_chunk_uuid) if parent_chunk_uuid else None
                    )

                    await connection.execute(
                        chunk_insert,
                        document_id,
                        chunk_index,
                        total_chunks,
                        chunk.text,
                        chunk.token_count,
                        chunk.char_count,
                        page_start,
                        page_end,
                        chunk_metadata.get("section_heading"),
                        parent_chunk_uuid,
                        chunk_metadata.get("content_type", "text"),
                        chunk_metadata.get("embedding_model"),
                        json.dumps(chunk_metadata),
                        bool(chunk_metadata.get("has_image")),
                        json.dumps(image_ids),
                        user_uuid,
                    )

        if dedup:
            await self.register_document_signatures(
                document_id=document_id,
                normalized_sha256=dedup["normalized_sha256"],
                simhash=dedup["simhash"],
                simhash_band_hashes=dedup["simhash_band_hashes"],
                minhash_signature=dedup["minhash_signature"],
                minhash_band_hashes=dedup["minhash_band_hashes"],
            )

        if integrity_checkpoints:
            await self.record_integrity_chain(
                document_id=document_id,
                checkpoints=integrity_checkpoints,
            )

        if user_uuid:
            await self._refresh_bucket_document_counts(user_uuid)

        return {
            "document_id": str(created["id"]),
            "created_at": created["created_at"].isoformat(),
            "storage_key": storage_key,
            "bucket_id": (
                str(resolved_content_bucket_id) if resolved_content_bucket_id else None
            ),
            "content_bucket_id": (
                str(resolved_content_bucket_id) if resolved_content_bucket_id else None
            ),
            "minio_storage_bucket_name": (
                minio_storage_bucket_name if storage_key else None
            ),
        }

    async def list_documents_for_owner(self, owner_id: str) -> list[dict[str, Any]]:
        if not self._pool:
            return []

        try:
            user_uuid = UUID(owner_id)
        except Exception:
            return []

        query = """
            SELECT
                id,
                created_by,
                title,
                status,
                content_type,
                extracted_metadata,
                created_at
            FROM documents
            WHERE created_by = $1
            ORDER BY created_at DESC
            LIMIT 100
        """

        async with self._pool.acquire() as connection:
            rows = await connection.fetch(query, user_uuid)

        documents: list[dict[str, Any]] = []
        for row in rows:
            extracted = row["extracted_metadata"] or {}
            if isinstance(extracted, str):
                try:
                    extracted = json.loads(extracted)
                except Exception:
                    extracted = {}
            documents.append(
                {
                    "document_id": str(row["id"]),
                    "owner_id": str(row["created_by"]),
                    "filename": row["title"] or "document",
                    "status": row["status"],
                    "content_type": row["content_type"],
                    "strategy": extracted.get("strategy"),
                    "word_count": extracted.get("word_count"),
                    "char_count": extracted.get("char_count"),
                    "text_preview": None,
                    "metadata": extracted,
                    "created_at": row["created_at"].isoformat(),
                }
            )
        return documents

    @staticmethod
    def _epoch_seconds(iso_value: str | None) -> int | None:
        if not iso_value:
            return None
        try:
            value = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
            return int(value.astimezone(UTC).timestamp())
        except Exception:
            return None

    async def index_document_vectors(
        self,
        *,
        document_id: str,
        owner_id: str,
        content_bucket_id: str | None,
        content_type: str,
        chunks: list[DocumentChunk],
        created_at: str,
    ) -> None:
        if not self._qdrant:
            return
        await self.ensure_qdrant_collection()

        points_primary: list[qmodels.PointStruct] = []
        points_fallback: list[qmodels.PointStruct] = []
        created_epoch = self._epoch_seconds(created_at) or int(
            datetime.now(UTC).timestamp()
        )

        batch_size = max(1, int(self.config.embedding_batch_size))
        chunk_records: list[tuple[int, DocumentChunk, str]] = [
            (index, chunk, chunk.text or "") for index, chunk in enumerate(chunks)
        ]

        text_to_vector: dict[str, list[float]] = {}
        uncached_texts: list[str] = []

        for _, _, text in chunk_records:
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            cache_key = f"kb:embedding:{text_hash}"
            if self._redis:
                cached = await self._redis.get(cache_key)
                if cached:
                    try:
                        vector = [float(value) for value in json.loads(cached)]
                        if vector:
                            text_to_vector[text] = vector
                            continue
                    except Exception:
                        pass
            uncached_texts.append(text)

        unique_uncached_texts = list(dict.fromkeys(uncached_texts))
        for start in range(0, len(unique_uncached_texts), batch_size):
            batch_texts = unique_uncached_texts[start : start + batch_size]
            try:
                if self.config.embedding_queue_enabled:
                    from app.infrastructure.embedding_queue import run_embedding_task

                    batch_vectors = await asyncio.to_thread(
                        run_embedding_task,
                        config=self.config,
                        texts=batch_texts,
                    )
                else:
                    batch_vectors = (
                        await self._embedding_provider.embed_documents_batch(
                            batch_texts
                        )
                    )
            except Exception as error:
                if self._redis:
                    await self._redis.execute_command(
                        "RPUSH",
                        self.EMBEDDING_DLQ_KEY,
                        json.dumps(
                            {
                                "document_id": document_id,
                                "batch_start": start,
                                "batch_size": len(batch_texts),
                                "texts": batch_texts,
                                "error": str(error),
                                "created_at": datetime.now(UTC).isoformat(),
                            }
                        ),
                    )
                raise RuntimeError(
                    f"Embedding batch failed after retries (start={start}, size={len(batch_texts)}): {error}"
                ) from error

            if len(batch_vectors) != len(batch_texts):
                raise RuntimeError(
                    f"Embedding batch cardinality mismatch: got {len(batch_vectors)} vectors for {len(batch_texts)} texts"
                )

            for text, vector in zip(batch_texts, batch_vectors):
                text_to_vector[text] = vector
                if self._redis:
                    cache_key = f"kb:embedding:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
                    await self._redis.set(
                        cache_key,
                        json.dumps(vector),
                        ex=int(self.config.embedding_cache_ttl_seconds),
                    )

        expected_dimension = int(self.config.embedding_dimensions)
        for index, chunk, text in chunk_records:
            vector = text_to_vector.get(text)
            if not vector:
                continue

            vector_dimension = len(vector)
            use_fallback_collection = vector_dimension != expected_dimension
            if use_fallback_collection and vector_dimension != 384:
                raise RuntimeError(
                    f"Unsupported embedding dimension {vector_dimension}. Expected {expected_dimension} or fallback 384."
                )

            payload = {
                "document_id": document_id,
                "chunk_id": chunk.chunk_id,
                "chunk_index": index,
                "user_id": owner_id,
                "bucket_id": content_bucket_id,
                "content_type": content_type,
                "section_heading": (chunk.metadata or {}).get("section_heading"),
                "page_range": (chunk.metadata or {}).get("page_range"),
                "token_count": int(
                    (chunk.metadata or {}).get("token_count") or chunk.token_count or 0
                ),
                "char_count": int(
                    (chunk.metadata or {}).get("char_count") or chunk.char_count or 0
                ),
                "split_boundary": (chunk.metadata or {}).get("split_boundary"),
                "parent_chunk_id": (chunk.metadata or {}).get("parent_chunk_id"),
                "tags": list((chunk.metadata or {}).get("tags") or []),
                "created_at": created_epoch,
                "has_image": bool((chunk.metadata or {}).get("has_image")),
                "embedding_source": "fallback" if use_fallback_collection else "gemini",
                "requires_reembedding": bool(use_fallback_collection),
                "text_preview": chunk.text[:200],
                "text": chunk.text[:4000],
            }
            point = qmodels.PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload=payload,
            )
            if use_fallback_collection:
                points_fallback.append(point)
            else:
                points_primary.append(point)

        if not points_primary and not points_fallback:
            return

        def _upsert(
            collection_name: str,
            points: list[qmodels.PointStruct],
        ) -> None:
            client = self._qdrant
            if not client or not points:
                return
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=False,
            )

        if points_primary:
            await asyncio.to_thread(
                _upsert, self.config.qdrant_collection, points_primary
            )
        if points_fallback:
            await asyncio.to_thread(
                _upsert,
                self.config.qdrant_fallback_collection,
                points_fallback,
            )

        if self._meili and chunk_records:
            meili_docs = [
                {
                    "id": chunk.chunk_id,
                    "document_id": document_id,
                    "user_id": owner_id,
                    "bucket_id": content_bucket_id or "",
                    "content_type": content_type,
                    "text": (chunk.text or "")[:10000],
                    "created_at": created_epoch,
                }
                for _, chunk, _ in chunk_records
                if chunk.chunk_id
            ]
            if meili_docs:
                index_name = self.config.meilisearch_index

                def _meili_upsert(docs: list[dict]) -> None:
                    if self._meili:
                        self._meili.index(index_name).add_documents(docs)

                try:
                    await asyncio.to_thread(_meili_upsert, meili_docs)
                except Exception as exc:
                    logger.warning(
                        "Meilisearch indexing failed for document %s: %s",
                        document_id,
                        exc,
                    )

    def _filter_conditions(
        self,
        owner_id: str,
        filters: dict[str, Any],
        *,
        owner_column: str = "created_by",
        start_index: int = 3,
    ) -> tuple[str, list[Any]]:
        conditions = [f"{owner_column} = $1"]
        params: list[Any] = [UUID(owner_id)]
        index = start_index

        bucket_ids = list(filters.get("bucket_ids") or [])
        if bucket_ids:
            conditions.append(f"bucket_id = ANY(${index}::uuid[])")
            params.append(bucket_ids)
            index += 1
        else:
            bucket_id = filters.get("bucket_id")
            if bucket_id:
                conditions.append(f"bucket_id = ${index}::uuid")
                params.append(bucket_id)
                index += 1

        content_bucket_id = filters.get("content_bucket_id")
        if content_bucket_id and not bucket_ids and not filters.get("bucket_id"):
            conditions.append(f"bucket_id = ${index}::uuid")
            params.append(content_bucket_id)
            index += 1

        content_type = filters.get("content_type")
        if content_type:
            conditions.append(f"content_type = ${index}")
            params.append(content_type)
            index += 1

        created_after = filters.get("created_after")
        if created_after:
            conditions.append(f"created_at >= ${index}::timestamptz")
            params.append(created_after)
            index += 1

        created_before = filters.get("created_before")
        if created_before:
            conditions.append(f"created_at <= ${index}::timestamptz")
            params.append(created_before)
            index += 1

        return " AND ".join(conditions), params

    async def search_semantic_multi(
        self,
        *,
        owner_id: str,
        queries: list[str],
        top_k: int,
        ef_search: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run semantic search for multiple query variants in parallel and merge.

        Each variant is searched independently. For each unique document_id the
        best score across all variants is kept, preserving maximum recall.
        """
        if not queries:
            return []
        search_tasks = [
            self.search_semantic(
                owner_id=owner_id,
                query=q,
                top_k=top_k,
                ef_search=ef_search,
                filters=filters,
            )
            for q in queries
        ]
        results_per_variant: list[list[dict[str, Any]]] = await asyncio.gather(
            *search_tasks
        )
        merged: dict[str, float] = {}
        for variant_results in results_per_variant:
            for row in variant_results:
                doc_id = str(row.get("document_id") or "")
                score = float(row.get("score") or 0.0)
                if doc_id and score > merged.get(doc_id, -1.0):
                    merged[doc_id] = score
        return sorted(
            [
                {"document_id": doc_id, "score": score}
                for doc_id, score in merged.items()
            ],
            key=lambda r: r["score"],
            reverse=True,
        )[:top_k]

    async def search_keyword(
        self,
        *,
        owner_id: str,
        query: str,
        top_k: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not self._pool:
            return []

        where_clause, params = self._filter_conditions(owner_id, filters, start_index=3)
        params.insert(1, query)
        params.append(top_k)
        limit_placeholder = f"${len(params)}"

        sql = f"""
            SELECT id, ts_rank(search_vector, plainto_tsquery('english', $2)) AS score
            FROM documents
            WHERE {where_clause}
              AND search_vector @@ plainto_tsquery('english', $2)
            ORDER BY score DESC, created_at DESC
            LIMIT {limit_placeholder}
        """

        async with self._pool.acquire() as connection:
            rows = await connection.fetch(sql, *params)

        return [
            {"document_id": str(row["id"]), "score": float(row["score"] or 0.0)}
            for row in rows
        ]

    async def _ensure_meili_index(self) -> None:
        """Create and configure the Meilisearch index if it does not already exist."""
        if not self._meili:
            return
        index_name = self.config.meilisearch_index
        client = self._meili

        def _setup() -> None:
            try:
                client.get_index(index_name)
            except meilisearch.errors.MeilisearchApiError:
                task = client.create_index(index_name, {"primaryKey": "id"})
                client.wait_for_task(task.task_uid, timeout_in_ms=10000)
            idx = client.index(index_name)
            idx.update_settings(
                {
                    "searchableAttributes": ["text", "content_type"],
                    "filterableAttributes": ["user_id", "bucket_id", "content_type"],
                    "sortableAttributes": ["created_at"],
                    "rankingRules": [
                        "words",
                        "typo",
                        "proximity",
                        "attribute",
                        "sort",
                        "exactness",
                    ],
                    "typoTolerance": {
                        "enabled": True,
                        "minWordSizeForTypos": {
                            "oneTypo": 5,
                            "twoTypos": 9,
                        },
                    },
                }
            )

        await asyncio.to_thread(_setup)

    async def check_meilisearch(self) -> str:
        """Return health status for Meilisearch."""
        if not self._meili:
            return "disabled"
        try:
            result = await asyncio.to_thread(self._meili.health)
            status = (
                result.get("status")
                if isinstance(result, dict)
                else getattr(result, "status", None)
            )
            return "healthy" if status == "available" else "degraded"
        except Exception:
            return "unreachable"

    async def search_typo_tolerant(
        self,
        *,
        owner_id: str,
        query: str,
        top_k: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if self._meili:
            return await self._search_typo_tolerant_meili(
                owner_id=owner_id,
                query=query,
                top_k=top_k,
                filters=filters,
            )
        return await self._search_typo_tolerant_pg(
            owner_id=owner_id,
            query=query,
            top_k=top_k,
            filters=filters,
        )

    async def _search_typo_tolerant_meili(
        self,
        *,
        owner_id: str,
        query: str,
        top_k: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Typo-tolerant search powered by Meilisearch."""
        index_name = self.config.meilisearch_index
        filter_parts: list[str] = [f'user_id = "{owner_id}"']

        bucket_ids = list(filters.get("bucket_ids") or [])
        if bucket_ids:
            ids_joined = " OR ".join(f'bucket_id = "{bid}"' for bid in bucket_ids)
            filter_parts.append(f"({ids_joined})")
        elif filters.get("bucket_id"):
            filter_parts.append(f'bucket_id = "{filters["bucket_id"]}"')

        if filters.get("content_type"):
            filter_parts.append(f'content_type = "{filters["content_type"]}"')

        meili_filter = " AND ".join(filter_parts)

        def _do_search() -> list[dict[str, Any]]:
            if not self._meili:
                return []
            result = self._meili.index(index_name).search(
                query,
                {
                    "limit": top_k * 3,
                    "filter": meili_filter,
                    "showRankingScore": True,
                    "attributesToRetrieve": ["document_id"],
                },
            )
            hits: list[dict] = (
                result.get("hits", []) if isinstance(result, dict) else []
            )
            aggregated: dict[str, float] = {}
            for hit in hits:
                doc_id = hit.get("document_id", "")
                score = float(hit.get("_rankingScore", 0.0))
                if doc_id and score > aggregated.get(doc_id, -1.0):
                    aggregated[doc_id] = score
            sorted_docs = sorted(aggregated.items(), key=lambda kv: kv[1], reverse=True)
            return [
                {"document_id": doc_id, "score": score}
                for doc_id, score in sorted_docs[:top_k]
            ]

        try:
            return await asyncio.to_thread(_do_search)
        except Exception as exc:
            logger.warning(
                "Meilisearch search failed, falling back to pg_trgm: %s", exc
            )
            return await self._search_typo_tolerant_pg(
                owner_id=owner_id,
                query=query,
                top_k=top_k,
                filters=filters,
            )

    async def _search_typo_tolerant_pg(
        self,
        *,
        owner_id: str,
        query: str,
        top_k: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """pg_trgm similarity fallback used when Meilisearch is unavailable."""
        if not self._pool:
            return []

        where_clause, params = self._filter_conditions(
            owner_id,
            filters,
            owner_column="d.created_by",
            start_index=3,
        )
        params.insert(1, query)
        similarity_threshold = 0.2
        threshold_placeholder = f"${len(params) + 1}"
        limit_placeholder = f"${len(params) + 2}"
        params.extend([similarity_threshold, top_k])

        sql = f"""
            SELECT
                d.id,
                GREATEST(
                    similarity(COALESCE(MAX(d.title), ''), $2),
                    similarity(COALESCE(MAX(d.source_url), ''), $2),
                    similarity(COALESCE(MAX(dc.content), ''), $2)
                ) AS score
            FROM documents d
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            WHERE {where_clause}
            GROUP BY d.id
            HAVING GREATEST(
                similarity(COALESCE(MAX(d.title), ''), $2),
                similarity(COALESCE(MAX(d.source_url), ''), $2),
                similarity(COALESCE(MAX(dc.content), ''), $2)
            ) >= {threshold_placeholder}
            ORDER BY score DESC
            LIMIT {limit_placeholder}
        """

        async with self._pool.acquire() as connection:
            rows = await connection.fetch(sql, *params)

        return [
            {"document_id": str(row["id"]), "score": float(row["score"] or 0.0)}
            for row in rows
        ]

    async def search_semantic(
        self,
        *,
        owner_id: str,
        query: str,
        top_k: int,
        ef_search: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not self._qdrant:
            return []

        query_vector = await self._embedding_provider.embed_query(query)
        created_after = self._epoch_seconds(filters.get("created_after"))
        created_before = self._epoch_seconds(filters.get("created_before"))

        qdrant_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=owner_id),
                )
            ]
        )

        bucket_ids = list(filters.get("bucket_ids") or [])
        if bucket_ids:
            qdrant_filter.must.append(
                qmodels.FieldCondition(
                    key="bucket_id",
                    match=qmodels.MatchAny(
                        any=[str(bucket_id) for bucket_id in bucket_ids]
                    ),
                )
            )
        elif filters.get("bucket_id"):
            qdrant_filter.must.append(
                qmodels.FieldCondition(
                    key="bucket_id",
                    match=qmodels.MatchValue(value=filters["bucket_id"]),
                )
            )

        if filters.get("content_type"):
            qdrant_filter.must.append(
                qmodels.FieldCondition(
                    key="content_type",
                    match=qmodels.MatchValue(value=filters["content_type"]),
                )
            )

        if filters.get("tags"):
            qdrant_filter.must.append(
                qmodels.FieldCondition(
                    key="tags",
                    match=qmodels.MatchAny(any=list(filters["tags"])),
                )
            )

        if created_after is not None or created_before is not None:
            qdrant_filter.must.append(
                qmodels.FieldCondition(
                    key="created_at",
                    range=qmodels.Range(
                        gte=created_after,
                        lte=created_before,
                    ),
                )
            )

        def _search() -> list[qmodels.ScoredPoint]:
            client = self._qdrant
            if not client:
                return []
            hits = client.search(
                collection_name=self.config.qdrant_collection,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                search_params=qmodels.SearchParams(
                    hnsw_ef=ef_search,
                    exact=False,
                ),
                with_payload=True,
                with_vectors=False,
            )
            return list(hits)

        try:
            hits = await asyncio.to_thread(_search)
        except Exception:
            return []

        best_by_document: dict[str, float] = {}
        for hit in hits:
            payload = hit.payload or {}
            document_id = str(payload.get("document_id") or "")
            if not document_id:
                continue
            score = float(hit.score or 0.0)
            if score > best_by_document.get(document_id, -1.0):
                best_by_document[document_id] = score

        ranked = sorted(
            best_by_document.items(), key=lambda item: item[1], reverse=True
        )
        return [
            {"document_id": document_id, "score": score}
            for document_id, score in ranked[:top_k]
        ]

    async def fetch_documents_by_ids(
        self, document_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        if not self._pool or not document_ids:
            return {}

        uuids: list[UUID] = []
        for raw_id in document_ids:
            try:
                uuids.append(UUID(raw_id))
            except Exception:
                continue
        if not uuids:
            return {}

        sql = """
            SELECT
                d.id,
                d.bucket_id,
                b.path AS bucket_path,
                d.title,
                d.source_url,
                d.content_type,
                d.status,
                d.created_at,
                d.extracted_metadata
            FROM documents d
            LEFT JOIN buckets b ON b.id = d.bucket_id
            WHERE d.id = ANY($1::uuid[])
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(sql, uuids)

        documents: dict[str, dict[str, Any]] = {}
        for row in rows:
            extracted = row["extracted_metadata"] or {}
            if isinstance(extracted, str):
                try:
                    extracted = json.loads(extracted)
                except Exception:
                    extracted = {}
            documents[str(row["id"])] = {
                "document_id": str(row["id"]),
                "bucket_id": str(row["bucket_id"]) if row["bucket_id"] else None,
                "bucket_path": row["bucket_path"],
                "title": row["title"] or "document",
                "source_url": row["source_url"],
                "status": row["status"],
                "content_type": row["content_type"],
                "created_at": row["created_at"].isoformat(),
                "text_preview": (extracted.get("text_preview") or "")[:300],
                "metadata": extracted,
            }
        return documents

    async def store_document_entities(
        self,
        *,
        document_id: str,
        entities: list[ExtractedEntity],
    ) -> None:
        if not self._pool or not entities:
            return
        if not await self._has_table("document_entities"):
            return

        insert_sql = """
            INSERT INTO document_entities (
                document_id,
                entity_text,
                canonical_name,
                entity_type,
                confidence,
                aliases,
                entity_metadata
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
            ON CONFLICT (document_id, canonical_name, entity_type)
            DO UPDATE SET
                confidence = GREATEST(document_entities.confidence, EXCLUDED.confidence),
                aliases = EXCLUDED.aliases,
                entity_metadata = EXCLUDED.entity_metadata,
                updated_at = NOW()
        """

        async with self._pool.acquire() as connection:
            for entity in entities:
                await connection.execute(
                    insert_sql,
                    document_id,
                    entity.text,
                    entity.canonical_name,
                    entity.entity_type,
                    entity.confidence,
                    json.dumps(entity.aliases),
                    json.dumps(entity.metadata),
                )

    async def get_document_engagement(
        self, document_ids: list[str]
    ) -> dict[str, dict[str, int]]:
        if not self._pool or not document_ids:
            return {}
        if not await self._has_table("document_engagement"):
            return {}

        valid_ids: list[UUID] = []
        for raw_id in document_ids:
            try:
                valid_ids.append(UUID(raw_id))
            except Exception:
                continue
        if not valid_ids:
            return {}

        sql = """
            SELECT document_id, impressions, clicks
            FROM document_engagement
            WHERE document_id = ANY($1::uuid[])
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(sql, valid_ids)

        return {
            str(row["document_id"]): {
                "impressions": int(row["impressions"] or 0),
                "clicks": int(row["clicks"] or 0),
            }
            for row in rows
        }

    async def record_search_impressions(self, document_ids: list[str]) -> None:
        if not self._pool or not document_ids:
            return
        if not await self._has_table("document_engagement"):
            return

        upsert_sql = """
            INSERT INTO document_engagement (
                document_id,
                impressions,
                clicks,
                last_impression_at
            )
            VALUES ($1::uuid, 1, 0, NOW())
            ON CONFLICT (document_id)
            DO UPDATE SET
                impressions = document_engagement.impressions + 1,
                last_impression_at = NOW(),
                updated_at = NOW()
        """
        async with self._pool.acquire() as connection:
            for raw_id in document_ids:
                try:
                    await connection.execute(upsert_sql, raw_id)
                except Exception:
                    continue

    async def rerank_query_documents(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, float]:
        if not candidates:
            return {}

        try:
            from sentence_transformers import CrossEncoder
        except Exception:
            return {
                candidate["document_id"]: float(candidate.get("base_score") or 0.0)
                for candidate in candidates
            }

        pairs = [(query, candidate.get("text") or "") for candidate in candidates]
        try:
            preferred_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            try:
                import torch

                if torch.cuda.is_available():
                    preferred_model = "BAAI/bge-reranker-base"
            except Exception:
                pass

            model = CrossEncoder(preferred_model)
            scores = await asyncio.to_thread(model.predict, pairs, 32)
            return {
                candidate["document_id"]: float(score)
                for candidate, score in zip(candidates, scores)
            }
        except Exception:
            return {
                candidate["document_id"]: float(candidate.get("base_score") or 0.0)
                for candidate in candidates
            }
