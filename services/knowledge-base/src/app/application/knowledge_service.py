import base64
from typing import Any, Dict, List

from app.application.deduplication import (
    build_dedup_computation,
    build_integrity_chain,
    md5_hex,
)
from app.application.ingestion.chunking import SemanticChunkingEngine
from app.application.ingestion.unified_processor import UnifiedDocumentProcessor
from app.infrastructure.persistence import KnowledgePersistence


class KnowledgeService:
    def __init__(self, persistence: KnowledgePersistence):
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._processor = UnifiedDocumentProcessor()
        self._chunker = SemanticChunkingEngine()
        self._persistence = persistence

    async def upload_document(
        self,
        owner_id: str,
        filename: str,
        content_base64: str | None = None,
        mime_type: str | None = None,
        source_url: str | None = None,
    ) -> Dict[str, Any]:
        content_bytes = base64.b64decode(content_base64) if content_base64 else None
        structured = await self._processor.process(
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            source_url=source_url,
        )

        dedup_computation = build_dedup_computation(structured.text)
        duplicate_candidate = await self._persistence.find_duplicate_candidate(
            normalized_sha256=dedup_computation.normalized_sha256,
            simhash=dedup_computation.simhash,
            simhash_band_hashes=dedup_computation.simhash_band_hashes,
            minhash_signature=dedup_computation.minhash_signature,
            minhash_band_hashes=dedup_computation.minhash_band_hashes,
        )

        if duplicate_candidate:
            dedup_stage = duplicate_candidate.get("dedup_stage", "exact")
            dedup_score = duplicate_candidate.get("dedup_score")
            updated = await self._persistence.register_duplicate_access(
                document_id=duplicate_candidate["document_id"],
                source_url=source_url,
                dedup_stage=dedup_stage,
                dedup_score=dedup_score,
            )
            duplicate_response = updated or duplicate_candidate
            duplicate_metadata = dict(duplicate_response.get("metadata") or {})
            duplicate_metadata["deduplication"] = {
                "stage": dedup_stage,
                "score": dedup_score,
                "duplicate_of": duplicate_response["document_id"],
            }

            return {
                "document_id": duplicate_response["document_id"],
                "owner_id": duplicate_response.get("owner_id", owner_id),
                "filename": filename,
                "status": f"duplicate_{dedup_stage}",
                "content_type": duplicate_response.get(
                    "content_type", structured.format.value
                ),
                "strategy": duplicate_response.get(
                    "strategy", structured.strategy_used.value
                ),
                "word_count": duplicate_response.get("word_count", 0),
                "char_count": duplicate_response.get("char_count", 0),
                "text_preview": None,
                "metadata": duplicate_metadata,
                "confidence_scores": structured.confidence_scores,
                "chunk_count": 0,
                "created_at": duplicate_response["created_at"],
            }

        chunks = self._chunker.chunk_document(
            source_document_id="pending",
            filename=filename,
            structured=structured,
        )
        structured.chunks = chunks
        structured.metadata["chunk_count"] = len(chunks)

        ingestion_bytes = content_bytes or structured.text.encode("utf-8")
        if not structured.metadata.get("checksum"):
            structured.metadata["checksum"] = md5_hex(ingestion_bytes)
        integrity_checkpoints = build_integrity_chain(
            ingestion_bytes=ingestion_bytes,
            extracted_text=structured.text,
            chunk_texts=[chunk.text for chunk in chunks],
        )
        structured.metadata["integrity_chain"] = [
            {
                "stage": checkpoint.stage_name,
                "checksum_md5": checkpoint.checksum_md5,
                "previous_checksum_md5": checkpoint.previous_checksum_md5,
                "chain_hash_sha256": checkpoint.chain_hash_sha256,
                "is_verified": checkpoint.is_verified,
            }
            for checkpoint in integrity_checkpoints
        ]

        persisted = await self._persistence.persist_processed_document(
            owner_id=owner_id,
            filename=filename,
            source_url=source_url,
            mime_type=mime_type,
            content_bytes=content_bytes,
            structured=structured,
            dedup={
                "normalized_sha256": dedup_computation.normalized_sha256,
                "simhash": dedup_computation.simhash,
                "simhash_band_hashes": dedup_computation.simhash_band_hashes,
                "minhash_signature": dedup_computation.minhash_signature,
                "minhash_band_hashes": dedup_computation.minhash_band_hashes,
            },
            integrity_checkpoints=integrity_checkpoints,
        )

        document = {
            "document_id": persisted["document_id"],
            "owner_id": owner_id,
            "filename": filename,
            "status": "completed",
            "content_type": structured.format.value,
            "strategy": structured.strategy_used.value,
            "word_count": structured.metadata.get(
                "word_count", len(structured.text.split())
            ),
            "char_count": structured.metadata.get("char_count", len(structured.text)),
            "text_preview": structured.text[:300],
            "metadata": structured.metadata,
            "confidence_scores": structured.confidence_scores,
            "chunk_count": len(chunks),
            "created_at": persisted["created_at"],
        }
        self._documents[persisted["document_id"]] = document
        return document

    async def list_documents(self, owner_id: str) -> List[Dict[str, Any]]:
        persisted_documents = await self._persistence.list_documents_for_owner(owner_id)
        if persisted_documents:
            return persisted_documents
        return [
            doc for doc in self._documents.values() if doc.get("owner_id") == owner_id
        ]

    async def list_buckets(self) -> List[Dict[str, str]]:
        return [{"name": "knowledge-base-documents", "provider": "minio"}]

    async def search(self, owner_id: str, query: str, top_k: int) -> Dict[str, Any]:
        return {
            "query": query,
            "top_k": top_k,
            "results": [],
            "owner_id": owner_id,
            "message": "Search pipeline skeleton is ready for vector + keyword wiring.",
        }

    async def chat(self, owner_id: str, message: str) -> Dict[str, Any]:
        return {
            "owner_id": owner_id,
            "answer": "Knowledge-base chat skeleton is online. RAG orchestration will be added in the next phase.",
            "sources": [],
            "input": message,
        }
