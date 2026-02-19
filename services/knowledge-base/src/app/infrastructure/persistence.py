import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
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


class KnowledgePersistence:
    def __init__(self, config: KnowledgeBaseConfig):
        self.config = config
        self._pool: asyncpg.Pool | None = None
        self._redis: Redis | None = None
        self._qdrant: QdrantClient | None = None
        self._table_exists_cache: dict[str, bool] = {}
        self._embedding_provider = GeminiEmbeddingProvider(config)
        self._minio_client = Minio(
            config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure,
        )

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

        await self.ensure_qdrant_collection()

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
        if self._qdrant:
            self._qdrant.close()
            self._qdrant = None
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

    async def _ensure_bucket_record(self, user_uuid: UUID | None) -> UUID | None:
        if not self._pool:
            return None

        query = """
            INSERT INTO buckets (name, storage_backend, storage_bucket, is_active, created_by, updated_by)
            VALUES ($1, 'minio', $2, TRUE, $3, $3)
            ON CONFLICT (name)
            DO UPDATE SET
                storage_bucket = EXCLUDED.storage_bucket,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            RETURNING id
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                query,
                self.config.minio_bucket,
                self.config.minio_bucket,
                user_uuid,
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

        def _ensure() -> None:
            client = self._qdrant
            if not client:
                return
            collection_name = self.config.qdrant_collection
            try:
                client.get_collection(collection_name=collection_name)
                return
            except Exception:
                pass

            client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(
                    size=384,
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
            await self._redis.set(
                self._exact_dedup_key(normalized_sha256),
                str(document_id),
                ex=60 * 60 * 24,
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
        dedup: dict[str, Any] | None = None,
        integrity_checkpoints: list[IntegrityCheckpoint] | None = None,
    ) -> dict[str, Any]:
        if not self._pool:
            raise RuntimeError("KnowledgePersistence pool is not initialized")

        user_uuid = await self._resolve_existing_user_uuid(owner_id)

        document_id = uuid4()
        safe_filename = Path(filename).name or "document.bin"
        source_type = "upload" if content_bytes else ("url" if source_url else "api")

        bucket_id = await self._ensure_bucket_record(user_uuid)

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
                    bucket_id,
                    Path(filename).stem,
                    structured.format.value,
                    mime_type,
                    source_type,
                    source_url,
                    json.dumps(source_metadata),
                    "minio" if storage_key else "inline",
                    self.config.minio_bucket if storage_key else None,
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
                    chunk_metadata["bucket_id"] = str(bucket_id) if bucket_id else None
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

                    parent_chunk = chunk_metadata.get("parent_chunk_id") or chunk_metadata.get("parent_chunk")
                    parent_chunk_uuid = None
                    if isinstance(parent_chunk, str):
                        try:
                            parent_chunk_uuid = UUID(parent_chunk)
                        except Exception:
                            parent_chunk_uuid = None

                    chunk_metadata["parent_chunk_id"] = str(parent_chunk_uuid) if parent_chunk_uuid else None

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

        return {
            "document_id": str(created["id"]),
            "created_at": created["created_at"].isoformat(),
            "storage_key": storage_key,
            "bucket_id": str(bucket_id) if bucket_id else None,
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
        bucket_id: str | None,
        content_type: str,
        chunks: list[DocumentChunk],
        created_at: str,
    ) -> None:
        if not self._qdrant:
            return
        await self.ensure_qdrant_collection()

        points: list[qmodels.PointStruct] = []
        created_epoch = self._epoch_seconds(created_at) or int(
            datetime.now(UTC).timestamp()
        )

        for index, chunk in enumerate(chunks):
            vector = await self._embedding_provider.embed_document(chunk.text)
            payload = {
                "document_id": document_id,
                "chunk_id": chunk.chunk_id,
                "chunk_index": index,
                "user_id": owner_id,
                "bucket_id": bucket_id,
                "content_type": content_type,
                "tags": list((chunk.metadata or {}).get("tags") or []),
                "created_at": created_epoch,
                "text": chunk.text[:4000],
            }
            point_id = str(uuid4())
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        if not points:
            return

        def _upsert() -> None:
            client = self._qdrant
            if not client:
                return
            client.upsert(
                collection_name=self.config.qdrant_collection,
                points=points,
                wait=False,
            )

        await asyncio.to_thread(_upsert)

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

        bucket_id = filters.get("bucket_id")
        if bucket_id:
            conditions.append(f"bucket_id = ${index}::uuid")
            params.append(bucket_id)
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

    async def search_typo_tolerant(
        self,
        *,
        owner_id: str,
        query: str,
        top_k: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
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

        if filters.get("bucket_id"):
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
                id,
                bucket_id,
                title,
                source_url,
                content_type,
                status,
                created_at,
                extracted_metadata
            FROM documents
            WHERE id = ANY($1::uuid[])
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
            model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
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
