from __future__ import annotations

import asyncio
import base64
import time
from collections import OrderedDict
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
    apply_mmr_diversity,
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

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeService:
    def __init__(
        self,
        persistence: KnowledgePersistence,
        unified_processor: UnifiedDocumentProcessor | None = None,
    ):
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._processor = unified_processor or UnifiedDocumentProcessor()
        self._chunker = SemanticChunkingEngine()
        self._persistence = persistence
        self._l1_cache: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
        self._l1_cache_max_items = 1000
        self._l1_cache_ttl_seconds = 300

    def _get_l1_cache(self, cache_key: str) -> Dict[str, Any] | None:
        cached = self._l1_cache.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at < time.time():
            self._l1_cache.pop(cache_key, None)
            return None
        self._l1_cache.move_to_end(cache_key)
        return payload

    def _set_l1_cache(self, cache_key: str, payload: Dict[str, Any]) -> None:
        expires_at = time.time() + float(self._l1_cache_ttl_seconds)
        self._l1_cache[cache_key] = (expires_at, payload)
        self._l1_cache.move_to_end(cache_key)
        while len(self._l1_cache) > self._l1_cache_max_items:
            self._l1_cache.popitem(last=False)

    async def upload_document(
        self,
        owner_id: str,
        filename: str,
        content_base64: str | None = None,
        mime_type: str | None = None,
        source_url: str | None = None,
        content_bucket_id: str | None = None,
        bucket_hint: str | None = None,
    ) -> Dict[str, Any]:
        logger.info(
            "[UPLOAD] Starting document upload",
            extra={
                "owner_id": owner_id,
                "doc_filename": filename,
                "mime_type": mime_type,
                "has_content": bool(content_base64),
                "has_url": bool(source_url),
                "bucket_id": content_bucket_id,
                "bucket_hint": bucket_hint,
            },
        )
        upload_start = time.time()
        content_bytes = base64.b64decode(content_base64) if content_base64 else None

        preview_text = ""
        if content_bytes:
            preview_text = content_bytes[:2000].decode("utf-8", errors="ignore")
        elif source_url:
            preview_text = source_url

        routing_decision = await self._persistence.route_content_bucket(
            owner_id=owner_id,
            title=filename,
            preview_text=preview_text,
            explicit_bucket_id=content_bucket_id,
            bucket_hint=bucket_hint,
        )
        logger.info(
            "[UPLOAD] Bucket routing completed",
            extra={"routing_decision": routing_decision, "owner_id": owner_id},
        )

        structured = await self._processor.process(
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            source_url=source_url,
        )

        logger.info(
            "[UPLOAD] Document processed",
            extra={
                "format": structured.format.value,
                "strategy": structured.strategy_used.value,
                "text_len": len(structured.text),
                "metadata": structured.metadata,
            },
        )
        dedup_computation = build_dedup_computation(structured.text)
        chunks = self._chunker.chunk_document(
            source_document_id="pending",
            filename=filename,
            structured=structured,
        )

        logger.info(
            "[UPLOAD] Chunking completed",
            extra={"total_chunks": len(chunks), "doc_filename": filename},
        )
        dedup_stage_counts = {"exact": 0, "near": 0, "semantic": 0}
        retained_chunk_pairs: list[tuple[DocumentChunk, Any]] = []
        forced_chunk_retention = False

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

        logger.info(
            "[UPLOAD] Chunk deduplication completed",
            extra={
                "dedup_stage_counts": dedup_stage_counts,
                "retained": len(retained_chunk_pairs),
                "total": len(chunks),
            },
        )
        if not retained_chunk_pairs and chunks:
            fallback_chunk = chunks[0]
            fallback_dedup = build_dedup_computation(fallback_chunk.text)
            retained_chunk_pairs.append((fallback_chunk, fallback_dedup))
            forced_chunk_retention = True
            logger.warning(
                "[UPLOAD] All chunks were duplicates - force-retained first chunk"
            )

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
            "forced_retention": forced_chunk_retention,
        }

        selected_bucket_id = routing_decision.get("selected_bucket_id")
        for chunk in filtered_chunks:
            chunk.metadata = dict(chunk.metadata or {})
            chunk.metadata["bucket_id"] = selected_bucket_id

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

        logger.info(
            "[UPLOAD] Persisting document",
            extra={
                "filtered_chunks": len(filtered_chunks),
                "bucket_id": routing_decision.get("selected_bucket_id"),
            },
        )
        persisted = await self._persistence.persist_processed_document(
            owner_id=owner_id,
            filename=filename,
            source_url=source_url,
            mime_type=mime_type,
            content_bytes=content_bytes,
            structured=structured,
            content_bucket_id=routing_decision.get("selected_bucket_id"),
            routing_metadata=routing_decision,
            dedup={
                "normalized_sha256": dedup_computation.normalized_sha256,
                "simhash": dedup_computation.simhash,
                "simhash_band_hashes": dedup_computation.simhash_band_hashes,
                "minhash_signature": dedup_computation.minhash_signature,
                "minhash_band_hashes": dedup_computation.minhash_band_hashes,
            },
            integrity_checkpoints=integrity_checkpoints,
        )

        logger.info(
            "[UPLOAD] Document persisted to DB",
            extra={
                "document_id": persisted["document_id"],
                "created_at": str(persisted.get("created_at")),
            },
        )
        await self._persistence.register_chunk_signatures(
            document_id=UUID(persisted["document_id"]),
            signatures=chunk_signature_payloads,
        )
        logger.info(
            "[UPLOAD] Chunk signatures registered",
            extra={"count": len(chunk_signature_payloads)},
        )

        await self._persistence.index_document_vectors(
            document_id=persisted["document_id"],
            owner_id=owner_id,
            content_bucket_id=(
                persisted.get("content_bucket_id") or persisted.get("bucket_id")
            ),
            content_type=structured.format.value,
            chunks=filtered_chunks,
            created_at=persisted["created_at"],
        )

        logger.info(
            "[UPLOAD] Vectors indexed in Qdrant",
            extra={"document_id": persisted["document_id"]},
        )

        entities = extract_entities(structured.text)
        logger.info(
            "[UPLOAD] Entity extraction completed",
            extra={"entity_count": len(entities)},
        )
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
            "content_bucket_id": persisted.get("content_bucket_id"),
            "minio_storage_bucket_name": persisted.get("minio_storage_bucket_name"),
            "bucket_routing": routing_decision,
        }
        self._documents[persisted["document_id"]] = document
        elapsed = time.time() - upload_start
        logger.info(
            "[UPLOAD] Document upload completed successfully",
            extra={
                "document_id": persisted["document_id"],
                "elapsed_seconds": round(elapsed, 3),
                "chunk_count": len(filtered_chunks),
                "owner_id": owner_id,
            },
        )
        return document

    async def list_documents(self, owner_id: str) -> List[Dict[str, Any]]:
        persisted_documents = await self._persistence.list_documents_for_owner(owner_id)
        if persisted_documents:
            return persisted_documents
        return [
            doc for doc in self._documents.values() if doc.get("owner_id") == owner_id
        ]

    async def list_buckets(self) -> List[Dict[str, str]]:
        raise RuntimeError("Use list_buckets_for_owner")

    async def list_buckets_for_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        return await self._persistence.list_buckets_for_user(owner_id)

    async def create_bucket(
        self,
        *,
        owner_id: str,
        name: str,
        description: str | None,
        parent_bucket_id: str | None,
        icon_emoji: str | None,
        color_hex: str | None,
        max_depth: int = -1,
        auto_classify: bool = True,
    ) -> Dict[str, Any]:
        return await self._persistence.create_bucket(
            owner_id=owner_id,
            name=name,
            description=description,
            parent_bucket_id=parent_bucket_id,
            icon_emoji=icon_emoji,
            color_hex=color_hex,
            max_depth=max_depth,
            auto_classify=auto_classify,
        )

    async def move_bucket(
        self,
        *,
        owner_id: str,
        bucket_id: str,
        parent_bucket_id: str | None,
    ) -> Dict[str, Any]:
        return await self._persistence.move_bucket(
            owner_id=owner_id,
            bucket_id=bucket_id,
            new_parent_bucket_id=parent_bucket_id,
        )

    async def delete_bucket(
        self,
        *,
        owner_id: str,
        bucket_id: str,
        target_bucket_id: str | None,
    ) -> Dict[str, int]:
        return await self._persistence.delete_bucket(
            owner_id=owner_id,
            bucket_id=bucket_id,
            target_bucket_id=target_bucket_id,
        )

    async def bulk_move_documents(
        self,
        *,
        owner_id: str,
        source_bucket_id: str,
        target_bucket_id: str,
    ) -> Dict[str, int]:
        return await self._persistence.bulk_move_documents(
            owner_id=owner_id,
            source_bucket_id=source_bucket_id,
            target_bucket_id=target_bucket_id,
        )

    async def route_bucket_preview(
        self,
        *,
        owner_id: str,
        title: str,
        preview_text: str,
        bucket_hint: str | None,
    ) -> Dict[str, Any]:
        return await self._persistence.route_content_bucket(
            owner_id=owner_id,
            title=title,
            preview_text=preview_text,
            explicit_bucket_id=None,
            bucket_hint=bucket_hint,
        )

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
        logger.info(
            "[SEARCH] Starting search",
            extra={
                "owner_id": owner_id,
                "query": request.query,
                "top_k": request.top_k,
                "bucket_id": request.bucket_id,
            },
        )
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

        if request.bucket_id:
            subtree_bucket_ids = (
                await self._persistence.resolve_subtree_bucket_ids_for_owner(
                    owner_id=owner_id,
                    root_bucket_id=request.bucket_id,
                )
            )
            if subtree_bucket_ids:
                filters["bucket_ids"] = subtree_bucket_ids

        cache_fingerprint = query_hash(str(filters))
        cache_key = (
            f"kb:search:v2:{owner_id}:{query_hash(normalized_query)}:"
            f"{cache_fingerprint}:{request.top_k}:{request.latency_budget_ms}:{int(request.enable_rerank)}"
        )

        l1_cached = self._get_l1_cache(cache_key)
        if l1_cached:
            logger.debug("[SEARCH] L1 cache hit", extra={"cache_key": cache_key})
            diagnostics = dict(l1_cached.get("diagnostics") or {})
            diagnostics["cache"] = "l1_hit"
            l1_cached["diagnostics"] = diagnostics
            return l1_cached

        cached = await self._persistence.get_cached_json(cache_key)
        if cached:
            logger.debug("[SEARCH] L2 cache hit", extra={"cache_key": cache_key})
            diagnostics = dict(cached.get("diagnostics") or {})
            diagnostics["cache"] = "l2_hit"
            cached["diagnostics"] = diagnostics
            self._set_l1_cache(cache_key, dict(cached))
            return cached

        ef_search = select_ef_search(request.latency_budget_ms)

        expanded_queries = await self._persistence.expand_query_gemini(normalized_query)
        all_semantic_queries = [normalized_query] + expanded_queries

        semantic_results, keyword_results, typo_results = await asyncio.gather(
            self._persistence.search_semantic_multi(
                owner_id=owner_id,
                queries=all_semantic_queries,
                top_k=max(50, request.top_k),
                ef_search=ef_search,
                filters=filters,
            ),
            self._persistence.search_keyword(
                owner_id=owner_id,
                query=normalized_query,
                top_k=max(50, request.top_k),
                filters=filters,
            ),
            self._persistence.search_typo_tolerant(
                owner_id=owner_id,
                query=normalized_query,
                top_k=max(20, request.top_k),
                filters=filters,
            ),
        )

        logger.info(
            "[SEARCH] Search tiers completed",
            extra={
                "semantic_count": len(semantic_results),
                "keyword_count": len(keyword_results),
                "typo_count": len(typo_results),
            },
        )

        fused = reciprocal_rank_fusion(
            [
                (weights["semantic"], semantic_results),
                (weights["keyword"], keyword_results),
                (weights["typo"], typo_results),
            ],
            k=60,
        )

        tier_matches: dict[str, set[str]] = {}
        for tier_name, tier_results in (
            ("semantic", semantic_results),
            ("fulltext", keyword_results),
            ("typo", typo_results),
        ):
            for row in tier_results:
                document_id = str(row.get("document_id") or "")
                if not document_id:
                    continue
                tier_matches.setdefault(document_id, set()).add(tier_name)

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
                    "chunk_id": None,
                    "document_title": document.get("title") or "document",
                    "bucket_path": document.get("bucket_path"),
                    "rrf_score": base_score,
                    "tiers_matched": sorted(tier_matches.get(document_id, set())),
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
            item["rerank_score"] = rerank_relevance
            item["relevance_score"] = item["score"]

        scored_results.sort(key=lambda value: value["score"], reverse=True)
        final_results = apply_mmr_diversity(
            query=normalized_query,
            results=scored_results,
            top_k=request.top_k,
            lambda_weight=0.7,
        )
        await self._persistence.record_search_impressions(
            [result["document_id"] for result in final_results]
        )

        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        response = {
            "query": request.query,
            "top_k": request.top_k,
            "results": final_results,
            "total_candidates": len(candidate_ids),
            "latency_ms": elapsed_ms,
            "cache_hit": False,
            "query_intent": "hybrid",
            "owner_id": owner_id,
            "message": "Hybrid search pipeline executed with semantic, keyword, and typo-tolerant tiers.",
            "diagnostics": {
                "cache": "miss",
                "latency_ms": elapsed_ms,
                "ef_search": ef_search,
                "weights": weights,
                "query_expansion": {
                    "enabled": True,
                    "expanded_count": len(expanded_queries),
                    "alternatives": expanded_queries,
                },
                "candidate_counts": {
                    "semantic": len(semantic_results),
                    "keyword": len(keyword_results),
                    "typo": len(typo_results),
                    "fused": len(fused),
                },
                "diversity": {
                    "enabled": True,
                    "method": "mmr",
                    "lambda": 0.7,
                },
            },
        }

        logger.info(
            "[SEARCH] Search completed",
            extra={
                "result_count": len(final_results),
                "latency_ms": elapsed_ms,
                "weights": weights,
                "expanded_queries": len(expanded_queries),
            },
        )
        ttl_seconds = 3600 if len(final_results) >= 5 else 300
        await self._persistence.set_cached_json(cache_key, response, ttl_seconds)
        self._set_l1_cache(cache_key, dict(response))
        return response

    async def chat(self, owner_id: str, message: str) -> Dict[str, Any]:
        return {
            "owner_id": owner_id,
            "answer": "Knowledge-base chat skeleton is online. RAG orchestration will be added in the next phase.",
            "sources": [],
            "input": message,
        }

    # ------------------------------------------------------------------
    # KB Settings
    # ------------------------------------------------------------------

    async def get_kb_settings(self, owner_id: str) -> Dict[str, Any]:
        return await self._persistence.get_kb_settings(owner_id)

    async def update_kb_settings(self, owner_id: str, **updates: Any) -> Dict[str, Any]:
        return await self._persistence.update_kb_settings(owner_id, **updates)

    # ------------------------------------------------------------------
    # Bucket extras
    # ------------------------------------------------------------------

    async def update_bucket(
        self,
        *,
        owner_id: str,
        bucket_id: str,
        name: str | None = None,
        description: str | None = None,
        icon_emoji: str | None = None,
        color_hex: str | None = None,
        max_depth: int | None = None,
        auto_classify: bool | None = None,
    ) -> Dict[str, Any]:
        return await self._persistence.update_bucket(
            owner_id=owner_id,
            bucket_id=bucket_id,
            name=name,
            description=description,
            icon_emoji=icon_emoji,
            color_hex=color_hex,
            max_depth=max_depth,
            auto_classify=auto_classify,
        )

    async def merge_buckets(
        self,
        *,
        owner_id: str,
        source_bucket_id: str,
        target_bucket_id: str,
    ) -> Dict[str, int]:
        return await self._persistence.merge_buckets(
            owner_id=owner_id,
            source_bucket_id=source_bucket_id,
            target_bucket_id=target_bucket_id,
        )

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    async def list_items(
        self,
        owner_id: str,
        *,
        bucket_id: str | None = None,
        content_type: str | None = None,
        classified_by: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return await self._persistence.list_items_for_user(
            owner_id,
            bucket_id=bucket_id,
            content_type=content_type,
            classified_by=classified_by,
            offset=offset,
            limit=limit,
        )

    async def get_item(self, owner_id: str, item_id: str) -> Dict[str, Any] | None:
        return await self._persistence.get_item(owner_id, item_id)

    async def move_item(
        self,
        owner_id: str,
        item_id: str,
        bucket_id: str,
    ) -> Dict[str, Any]:
        return await self._persistence.move_item(owner_id, item_id, bucket_id)

    async def delete_item(self, owner_id: str, item_id: str) -> bool:
        return await self._persistence.delete_item(owner_id, item_id)

    # ------------------------------------------------------------------
    # Async ingest jobs
    # ------------------------------------------------------------------

    async def create_ingest_job(
        self, owner_id: str, item_id: str | None = None
    ) -> Dict[str, Any]:
        return await self._persistence.create_ingest_job(owner_id, item_id)

    async def update_ingest_job(self, job_id: str, **kwargs: Any) -> None:
        await self._persistence.update_ingest_job(job_id, **kwargs)

    async def get_ingest_job(
        self, owner_id: str, job_id: str
    ) -> Dict[str, Any] | None:
        return await self._persistence.get_ingest_job(owner_id, job_id)

    async def list_ingest_jobs(
        self, owner_id: str, *, offset: int = 0, limit: int = 50
    ) -> Dict[str, Any]:
        return await self._persistence.list_ingest_jobs(owner_id, offset=offset, limit=limit)

    # ------------------------------------------------------------------
    # AI bucket suggestions
    # ------------------------------------------------------------------

    async def list_suggestions(
        self,
        owner_id: str,
        *,
        status: str = "pending",
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return await self._persistence.list_suggestions(
            owner_id, status=status, offset=offset, limit=limit
        )

    async def approve_suggestion(
        self,
        owner_id: str,
        suggestion_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Dict[str, Any]:
        return await self._persistence.approve_suggestion(
            owner_id, suggestion_id, name=name, description=description
        )

    async def reject_suggestion(
        self,
        owner_id: str,
        suggestion_id: str,
    ) -> None:
        return await self._persistence.reject_suggestion(owner_id, suggestion_id)
