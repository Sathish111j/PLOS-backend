import base64
from datetime import UTC, datetime
from typing import Any, Dict, List
from uuid import UUID

from app.api.schemas import SearchRequest
from app.application.deduplication import (
    build_dedup_computation,
    build_integrity_chain,
    md5_hex,
)
from app.application.entity_extraction import extract_entities
from app.application.ingestion.chunking import SemanticChunkingEngine
from app.application.ingestion.models import DocumentChunk
from app.application.ingestion.unified_processor import UnifiedDocumentProcessor
from app.application.search_utils import (
    bucket_context_score,
    detect_query_intent_weights,
    engagement_score,
    normalize_query,
    query_hash,
    recency_score,
    reciprocal_rank_fusion,
    select_ef_search,
)
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
        chunks = self._chunker.chunk_document(
            source_document_id="pending",
            filename=filename,
            structured=structured,
        )

        dedup_stage_counts = {"exact": 0, "near": 0, "semantic": 0}
        retained_chunk_pairs: list[tuple[DocumentChunk, Any]] = []

        for chunk in chunks:
            chunk_dedup = build_dedup_computation(chunk.text)
            duplicate_chunk = await self._persistence.find_chunk_duplicate_candidate(
                normalized_sha256=chunk_dedup.normalized_sha256,
                simhash=chunk_dedup.simhash,
                simhash_band_hashes=chunk_dedup.simhash_band_hashes,
                minhash_signature=chunk_dedup.minhash_signature,
                minhash_band_hashes=chunk_dedup.minhash_band_hashes,
                semantic_async=True,
            )

            if duplicate_chunk:
                dedup_stage = str(duplicate_chunk.get("dedup_stage", "exact"))
                if dedup_stage in dedup_stage_counts:
                    dedup_stage_counts[dedup_stage] += 1
                continue

            retained_chunk_pairs.append((chunk, chunk_dedup))

        filtered_chunks: list[DocumentChunk] = []
        chunk_signature_payloads: list[dict[str, Any]] = []

        for chunk_index, (chunk, chunk_dedup) in enumerate(retained_chunk_pairs):
            chunk.metadata = dict(chunk.metadata or {})
            chunk.metadata["chunk_index"] = chunk_index
            chunk.metadata["total_chunks"] = len(retained_chunk_pairs)
            filtered_chunks.append(chunk)
            chunk_signature_payloads.append(
                {
                    "chunk_index": chunk_index,
                    "normalized_sha256": chunk_dedup.normalized_sha256,
                    "simhash": chunk_dedup.simhash,
                    "simhash_band_hashes": chunk_dedup.simhash_band_hashes,
                    "minhash_signature": chunk_dedup.minhash_signature,
                    "minhash_band_hashes": chunk_dedup.minhash_band_hashes,
                }
            )

        structured.chunks = filtered_chunks
        structured.metadata["chunk_count"] = len(filtered_chunks)
        structured.metadata["deduplication"] = {
            "input_chunks": len(chunks),
            "retained_chunks": len(filtered_chunks),
            "filtered_chunks": len(chunks) - len(filtered_chunks),
            "stage_counts": dedup_stage_counts,
        }

        ingestion_bytes = content_bytes or structured.text.encode("utf-8")
        if not structured.metadata.get("checksum"):
            structured.metadata["checksum"] = md5_hex(ingestion_bytes)
        integrity_checkpoints = build_integrity_chain(
            ingestion_bytes=ingestion_bytes,
            extracted_text=structured.text,
            chunk_texts=[chunk.text for chunk in filtered_chunks],
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

        await self._persistence.register_chunk_signatures(
            document_id=UUID(persisted["document_id"]),
            signatures=chunk_signature_payloads,
        )

        await self._persistence.index_document_vectors(
            document_id=persisted["document_id"],
            owner_id=owner_id,
            bucket_id=persisted.get("bucket_id"),
            content_type=structured.format.value,
            chunks=filtered_chunks,
            created_at=persisted["created_at"],
        )

        entities = extract_entities(structured.text)
        await self._persistence.store_document_entities(
            document_id=persisted["document_id"],
            entities=entities,
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
            "chunk_count": len(filtered_chunks),
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

    async def get_embedding_dlq_stats(self) -> Dict[str, int]:
        return await self._persistence.get_embedding_dlq_stats()

    async def reprocess_embedding_unreplayable(
        self,
        *,
        max_items: int,
        purge_unrecoverable: bool,
        trigger_replay_cycle: bool,
    ) -> Dict[str, Any]:
        action = await self._persistence.reprocess_embedding_unreplayable(
            max_items=max_items,
            purge_unrecoverable=purge_unrecoverable,
        )
        replay_cycle: Dict[str, int] | None = None
        if trigger_replay_cycle:
            replay_cycle = await self._persistence.replay_embedding_dlq_once()

        stats = await self._persistence.get_embedding_dlq_stats()
        return {
            **action,
            "replay_cycle": replay_cycle,
            "stats": stats,
        }

    async def purge_embedding_unreplayable(self, *, max_items: int) -> Dict[str, Any]:
        action = await self._persistence.purge_embedding_unreplayable(
            max_items=max_items
        )
        stats = await self._persistence.get_embedding_dlq_stats()
        return {
            "processed": 0,
            "moved_to_dlq": 0,
            "kept_unreplayable": 0,
            "purged": int(action.get("purged", 0)),
            "replay_cycle": None,
            "stats": stats,
        }

    async def search(self, owner_id: str, request: SearchRequest) -> Dict[str, Any]:
        if owner_id == "anonymous":
            return {
                "query": request.query,
                "top_k": request.top_k,
                "results": [],
                "owner_id": owner_id,
                "message": "Authentication is required for personalized hybrid search.",
                "diagnostics": {
                    "cache": "bypass",
                    "reason": "anonymous_user",
                },
            }

        started = datetime.now(UTC)
        normalized_query = normalize_query(request.query)
        weights = detect_query_intent_weights(normalized_query)

        filters = {
            "bucket_id": request.bucket_id,
            "content_type": request.content_type,
            "tags": request.tags or [],
            "created_after": request.created_after,
            "created_before": request.created_before,
        }

        cache_fingerprint = query_hash(str(filters))
        cache_key = (
            f"kb:search:v2:{owner_id}:{query_hash(normalized_query)}:"
            f"{cache_fingerprint}:{request.top_k}:{request.latency_budget_ms}:{int(request.enable_rerank)}"
        )
        cached = await self._persistence.get_cached_json(cache_key)
        if cached:
            diagnostics = dict(cached.get("diagnostics") or {})
            diagnostics["cache"] = "hit"
            cached["diagnostics"] = diagnostics
            return cached

        ef_search = select_ef_search(request.latency_budget_ms)
        semantic_results = await self._persistence.search_semantic(
            owner_id=owner_id,
            query=normalized_query,
            top_k=max(50, request.top_k),
            ef_search=ef_search,
            filters=filters,
        )
        keyword_results = await self._persistence.search_keyword(
            owner_id=owner_id,
            query=normalized_query,
            top_k=max(50, request.top_k),
            filters=filters,
        )
        typo_results = await self._persistence.search_typo_tolerant(
            owner_id=owner_id,
            query=normalized_query,
            top_k=max(20, request.top_k),
            filters=filters,
        )

        fused = reciprocal_rank_fusion(
            [
                (weights["semantic"], semantic_results),
                (weights["keyword"], keyword_results),
                (weights["typo"], typo_results),
            ],
            k=60,
        )

        candidate_ids = [document_id for document_id, _ in fused[:50]]
        metadata_by_id = await self._persistence.fetch_documents_by_ids(candidate_ids)
        engagement_by_id = await self._persistence.get_document_engagement(
            candidate_ids
        )
        fused_by_id = {document_id: score for document_id, score in fused}

        scored_results: list[dict[str, Any]] = []
        for document_id in candidate_ids:
            document = metadata_by_id.get(document_id)
            if not document:
                continue

            engagement = engagement_by_id.get(document_id, {})
            base_score = fused_by_id.get(document_id, 0.0)
            recency = recency_score(document.get("created_at"))
            engagement_value = engagement_score(
                engagement.get("clicks"), engagement.get("impressions")
            )
            bucket_score = bucket_context_score(
                document.get("bucket_id"), request.bucket_id
            )

            scored_results.append(
                {
                    **document,
                    "base_score": base_score,
                    "recency_score": recency,
                    "engagement_score": engagement_value,
                    "bucket_context_score": bucket_score,
                }
            )

        rerank_candidates = [
            {
                "document_id": item["document_id"],
                "text": (item.get("text_preview") or item.get("title") or "")[:1200],
                "base_score": item["base_score"],
            }
            for item in scored_results
        ]
        rerank_scores = (
            await self._persistence.rerank_query_documents(
                query=normalized_query,
                candidates=rerank_candidates,
            )
            if request.enable_rerank
            else {}
        )

        for item in scored_results:
            rerank_relevance_raw = rerank_scores.get(item["document_id"])
            rerank_relevance = float(
                rerank_relevance_raw
                if rerank_relevance_raw is not None
                else item["base_score"]
            )
            item["score"] = (
                0.6 * rerank_relevance
                + 0.15 * item["recency_score"]
                + 0.15 * item["engagement_score"]
                + 0.1 * item["bucket_context_score"]
            )

        scored_results.sort(key=lambda value: value["score"], reverse=True)
        final_results = scored_results[: request.top_k]
        await self._persistence.record_search_impressions(
            [result["document_id"] for result in final_results]
        )

        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        response = {
            "query": request.query,
            "top_k": request.top_k,
            "results": final_results,
            "owner_id": owner_id,
            "message": "Hybrid search pipeline executed with semantic, keyword, and typo-tolerant tiers.",
            "diagnostics": {
                "cache": "miss",
                "latency_ms": elapsed_ms,
                "ef_search": ef_search,
                "weights": weights,
                "candidate_counts": {
                    "semantic": len(semantic_results),
                    "keyword": len(keyword_results),
                    "typo": len(typo_results),
                    "fused": len(fused),
                },
            },
        }

        ttl_seconds = 3600 if len(final_results) >= 5 else 300
        await self._persistence.set_cached_json(cache_key, response, ttl_seconds)
        return response

    async def chat(self, owner_id: str, message: str) -> Dict[str, Any]:
        return {
            "owner_id": owner_id,
            "answer": "Knowledge-base chat skeleton is online. RAG orchestration will be added in the next phase.",
            "sources": [],
            "input": message,
        }
