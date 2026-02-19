import asyncio
import io
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from minio import Minio
from minio.error import S3Error

from app.application.ingestion.models import StructuredDocument
from app.core.config import KnowledgeBaseConfig


class KnowledgePersistence:
    def __init__(self, config: KnowledgeBaseConfig):
        self.config = config
        self._pool: asyncpg.Pool | None = None
        self._minio_client = Minio(
            config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure,
        )

    async def connect(self) -> None:
        dsn = self.config.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)

    async def close(self) -> None:
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

    async def _upload_bytes(self, object_key: str, content: bytes, mime_type: str | None) -> None:
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

    async def persist_processed_document(
        self,
        *,
        owner_id: str,
        filename: str,
        source_url: str | None,
        mime_type: str | None,
        content_bytes: bytes | None,
        structured: StructuredDocument,
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

        file_size = len(content_bytes) if content_bytes else structured.metadata.get("file_size")
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
                    chunk_metadata["source_document_id"] = str(document_id)

                    page_range = chunk_metadata.get("page_range") or []
                    page_start = page_range[0] if isinstance(page_range, list) and len(page_range) >= 1 else None
                    page_end = page_range[1] if isinstance(page_range, list) and len(page_range) >= 2 else page_start

                    image_ids = chunk_metadata.get("image_ids") or []
                    if not isinstance(image_ids, list):
                        image_ids = []

                    parent_chunk = chunk_metadata.get("parent_chunk")
                    parent_chunk_uuid = None
                    if isinstance(parent_chunk, str):
                        try:
                            parent_chunk_uuid = UUID(parent_chunk)
                        except Exception:
                            parent_chunk_uuid = None

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
