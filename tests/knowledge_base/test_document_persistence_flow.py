import asyncio
import base64
import os
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
from app.application.knowledge_service import KnowledgeService

from app.application.ingestion.models import (
    ContentClass,
    DocumentChunk,
    DocumentFormat,
    ExtractionStrategy,
    StructuredDocument,
)
from app.core.config import get_kb_config
from app.infrastructure.persistence import KnowledgePersistence


def _run(coroutine):
    return asyncio.run(coroutine)


def _sample_structured() -> StructuredDocument:
    return StructuredDocument(
        text="Sample extracted text",
        chunks=[
            DocumentChunk(
                chunk_id=str(uuid4()),
                text="Sample extracted text",
                token_count=120,
                char_count=22,
                metadata={
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "section_heading": "Intro",
                    "content_type": "text",
                    "embedding_model": "all-MiniLM-L6-v2",
                },
            )
        ],
        metadata={
            "word_count": 3,
            "char_count": 20,
            "checksum": "abc123",
            "page_count": 1,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
        confidence_scores={"text_extraction": 0.9},
        strategy_used=ExtractionStrategy.TEXT_DIRECT,
        format=DocumentFormat.TEXT,
        content_class=ContentClass.TEXT_BASED,
    )


async def _fetchval(query: str, *args):
    config = get_kb_config()
    dsn = config.database_url.replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(dsn)
    try:
        return await connection.fetchval(query, *args)
    finally:
        await connection.close()


def test_persist_processed_document_creates_db_rows() -> None:
    config = get_kb_config()
    persistence = KnowledgePersistence(config)

    async def scenario():
        await persistence.connect()
        try:
            dedup_table_exists = await _fetchval(
                "SELECT to_regclass('public.document_dedup_signatures') IS NOT NULL"
            )
            integrity_table_exists = await _fetchval(
                "SELECT to_regclass('public.document_integrity_checks') IS NOT NULL"
            )
            if not dedup_table_exists or not integrity_table_exists:
                pytest.skip("Deduplication/integrity migration is not applied yet")

            owner_id = str(uuid4())
            result = await persistence.persist_processed_document(
                owner_id=owner_id,
                filename="integration.txt",
                source_url=None,
                mime_type="text/plain",
                content_bytes=b"hello persistence",
                structured=_sample_structured(),
            )

            document_id = result["document_id"]

            doc_exists = await _fetchval(
                "SELECT EXISTS (SELECT 1 FROM documents WHERE id = $1::uuid)",
                document_id,
            )
            version_exists = await _fetchval(
                "SELECT EXISTS (SELECT 1 FROM document_versions WHERE document_id = $1::uuid)",
                document_id,
            )
            chunks_count = await _fetchval(
                "SELECT COUNT(*) FROM document_chunks WHERE document_id = $1::uuid",
                document_id,
            )
            assert doc_exists is True
            assert version_exists is True
            assert chunks_count == 1
            assert result["storage_key"] is not None
        finally:
            await persistence.close()

    _run(scenario())


def test_upload_document_exact_duplicate_filters_chunks_before_indexing() -> None:
    config = get_kb_config()
    persistence = KnowledgePersistence(config)
    service = KnowledgeService(persistence)

    async def scenario():
        await persistence.connect()
        try:
            dedup_table_exists = await _fetchval(
                "SELECT to_regclass('public.document_dedup_signatures') IS NOT NULL"
            )
            chunk_dedup_table_exists = await _fetchval(
                "SELECT to_regclass('public.chunk_dedup_signatures') IS NOT NULL"
            )
            integrity_table_exists = await _fetchval(
                "SELECT to_regclass('public.document_integrity_checks') IS NOT NULL"
            )
            if (
                not dedup_table_exists
                or not chunk_dedup_table_exists
                or not integrity_table_exists
            ):
                pytest.skip("Deduplication/integrity/chunk dedup migrations are not applied yet")

            has_gemini_keys = bool(
                (os.getenv("GEMINI_API_KEY") or "").strip()
                or (os.getenv("GEMINI_API_KEYS") or "").strip()
            )
            if not has_gemini_keys:
                pytest.skip("Gemini API keys are required in strict embedding mode")

            owner_id = str(uuid4())
            marker_a = uuid4().hex
            marker_b = uuid4().hex
            marker_c = uuid4().hex
            content = f"{marker_a} {marker_b} {marker_c} zxqvplmtr qxjznv".encode(
                "utf-8"
            )
            payload = base64.b64encode(content).decode("utf-8")

            first = await service.upload_document(
                owner_id=owner_id,
                filename="dup-1.txt",
                content_base64=payload,
                mime_type="text/plain",
                source_url="https://example.com/first",
            )
            second = await service.upload_document(
                owner_id=owner_id,
                filename="dup-2.txt",
                content_base64=payload,
                mime_type="text/plain",
                source_url="https://example.com/second",
            )

            assert first["status"] == "completed"
            assert second["status"] == "completed"
            assert second["document_id"] != first["document_id"]
            assert second["chunk_count"] == 0

            dedup_meta = dict(second.get("metadata") or {}).get("deduplication") or {}
            stage_counts = dict(dedup_meta.get("stage_counts") or {})
            assert int(stage_counts.get("exact", 0)) >= 1

            dedup_rows = await _fetchval(
                "SELECT COUNT(*) FROM document_dedup_signatures WHERE document_id = $1::uuid",
                first["document_id"],
            )
            chunk_dedup_rows = await _fetchval(
                "SELECT COUNT(*) FROM chunk_dedup_signatures WHERE document_id = $1::uuid",
                first["document_id"],
            )
            integrity_rows = await _fetchval(
                "SELECT COUNT(*) FROM document_integrity_checks WHERE document_id = $1::uuid",
                first["document_id"],
            )

            assert dedup_rows == 1
            assert chunk_dedup_rows >= 1
            assert integrity_rows >= 4
        finally:
            await persistence.close()

    _run(scenario())
