import time

from app.api.schemas import (
    BucketBulkMoveRequest,
    BucketCreateRequest,
    BucketDeleteRequest,
    BucketItem,
    BucketMergeRequest,
    BucketMoveRequest,
    BucketOperationResponse,
    BucketRoutePreviewRequest,
    BucketRoutingCandidate,
    BucketRoutingDecision,
    BucketTreeResponse,
    BucketUpdateRequest,
    ChatMessageItem,
    ChatRequest,
    ChatResponse,
    ChatSessionDeleteResponse,
    ChatSessionDetail,
    ChatSessionItem,
    ChatSessionListResponse,
    CitationSource,
    DocumentItem,
    EmbeddingDlqActionResponse,
    EmbeddingDlqPurgeRequest,
    EmbeddingDlqReprocessRequest,
    EmbeddingDlqStatsResponse,
    IngestJobListResponse,
    IngestJobStatus,
    ItemDetail,
    ItemListResponse,
    ItemMoveRequest,
    KBSettingsPatchRequest,
    KBSettingsResponse,
    SearchRequest,
    SearchResponse,
    SuggestionApproveRequest,
    SuggestionHistoryResponse,
    SuggestionItem,
    SuggestionListResponse,
    UploadRequest,
    UploadResponse,
)
from app.core.config import get_kb_config
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.dependencies.container import (
    infra_health_client,
    knowledge_service,
    rag_engine,
)
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import StreamingResponse

from shared.auth.dependencies import get_current_user
from shared.auth.models import TokenData

router = APIRouter()
config = get_kb_config()


def _owner_id(user: TokenData) -> str:
    return str(user.user_id)


@router.get("/health", tags=["health"])
async def health() -> dict:
    dependency_status = await infra_health_client.check_dependencies()
    return {
        "status": "healthy",
        "service": config.service_name,
        "version": "0.1.0",
        "dependencies": dependency_status,
    }


@router.get("/metrics", tags=["health"])
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post("/upload", response_model=UploadResponse, tags=["documents"])
async def upload_document(
    request: UploadRequest,
    current_user: TokenData = Depends(get_current_user),
) -> UploadResponse:
    start = time.perf_counter()
    owner_id = _owner_id(current_user)
    result = await knowledge_service.upload_document(
        owner_id,
        request.filename,
        content_base64=request.content_base64,
        mime_type=request.mime_type,
        source_url=request.source_url,
        content_bucket_id=request.bucket_id,
        bucket_hint=request.bucket_hint,
    )
    duration = time.perf_counter() - start
    REQUEST_COUNT.labels(
        service="knowledge-base", method="POST", endpoint="/upload", status="200"
    ).inc()
    REQUEST_LATENCY.labels(
        service="knowledge-base", method="POST", endpoint="/upload"
    ).observe(duration)
    return UploadResponse(
        document_id=result["document_id"],
        status=result["status"],
        content_type=result["content_type"],
        strategy=result["strategy"],
        word_count=result["word_count"],
        char_count=result["char_count"],
        metadata=result["metadata"],
        created_at=result["created_at"],
    )


@router.post("/ingest", response_model=IngestJobStatus, tags=["documents"])
async def ingest_document(
    request: UploadRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
) -> IngestJobStatus:
    """Accept a document and immediately return a job ID.

    The actual ingestion and bucket classification happen asynchronously in
    the background.  Poll ``GET /ingest/{job_id}`` to check progress.
    """
    owner_id = _owner_id(current_user)

    # Create a pending job entry synchronously so the caller gets a job_id now.
    job = await knowledge_service.create_ingest_job(owner_id)
    job_id = job["job_id"]

    async def _do_ingest(oid: str, jid: str) -> None:
        try:
            result = await knowledge_service.upload_document(
                oid,
                request.filename,
                content_base64=request.content_base64,
                mime_type=request.mime_type,
                source_url=request.source_url,
                content_bucket_id=request.bucket_id,
                bucket_hint=request.bucket_hint,
            )
            await knowledge_service.update_ingest_job(
                jid,
                status="classified",
                item_id=result.get("document_id"),
                bucket_id=result.get("bucket_id"),
                bucket_path=result.get("bucket_path"),
                confidence=result.get("classification_confidence"),
                ai_reasoning=result.get("classification_reasoning"),
            )
        except Exception as exc:
            await knowledge_service.update_ingest_job(
                jid,
                status="failed",
                error_message=str(exc)[:500],
            )

    background_tasks.add_task(_do_ingest, owner_id, job_id)

    return IngestJobStatus(**job)


@router.get("/documents", response_model=list[DocumentItem], tags=["documents"])
async def list_documents(
    current_user: TokenData = Depends(get_current_user),
) -> list[DocumentItem]:
    owner_id = _owner_id(current_user)
    documents = await knowledge_service.list_documents(owner_id)
    return [DocumentItem(**item) for item in documents]


@router.get("/buckets", response_model=list[BucketItem], tags=["buckets"])
async def list_buckets(
    current_user: TokenData = Depends(get_current_user),
) -> list[BucketItem]:
    owner_id = str(current_user.user_id)
    buckets = await knowledge_service.list_buckets_for_owner(owner_id)
    return [BucketItem(**item) for item in buckets]


@router.get("/buckets/tree", response_model=BucketTreeResponse, tags=["buckets"])
async def get_bucket_tree(
    current_user: TokenData = Depends(get_current_user),
) -> BucketTreeResponse:
    owner_id = str(current_user.user_id)
    buckets = await knowledge_service.list_buckets_for_owner(owner_id)
    return BucketTreeResponse(buckets=[BucketItem(**item) for item in buckets])


@router.post("/buckets", response_model=BucketItem, tags=["buckets"])
async def create_bucket(
    request: BucketCreateRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketItem:
    owner_id = str(current_user.user_id)
    try:
        bucket = await knowledge_service.create_bucket(
            owner_id=owner_id,
            name=request.name,
            description=request.description,
            parent_bucket_id=request.parent_bucket_id,
            icon_emoji=request.icon_emoji,
            color_hex=request.color_hex,
            max_depth=request.max_depth,
            auto_classify=request.auto_classify,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BucketItem(**bucket)


@router.post("/buckets/{bucket_id}/move", response_model=BucketItem, tags=["buckets"])
async def move_bucket(
    bucket_id: str,
    request: BucketMoveRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketItem:
    owner_id = str(current_user.user_id)
    try:
        bucket = await knowledge_service.move_bucket(
            owner_id=owner_id,
            bucket_id=bucket_id,
            parent_bucket_id=request.parent_bucket_id,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BucketItem(**bucket)


@router.delete(
    "/buckets/{bucket_id}", response_model=BucketOperationResponse, tags=["buckets"]
)
async def delete_bucket(
    bucket_id: str,
    request: BucketDeleteRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketOperationResponse:
    owner_id = str(current_user.user_id)
    try:
        details = await knowledge_service.delete_bucket(
            owner_id=owner_id,
            bucket_id=bucket_id,
            target_bucket_id=request.target_bucket_id,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return BucketOperationResponse(status="deleted", details=details)


@router.post(
    "/buckets/bulk-move-documents",
    response_model=BucketOperationResponse,
    tags=["buckets"],
)
async def bulk_move_documents(
    request: BucketBulkMoveRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketOperationResponse:
    owner_id = str(current_user.user_id)
    try:
        details = await knowledge_service.bulk_move_documents(
            owner_id=owner_id,
            source_bucket_id=request.source_bucket_id,
            target_bucket_id=request.target_bucket_id,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return BucketOperationResponse(status="moved", details=details)


@router.post(
    "/buckets/route-preview",
    response_model=BucketRoutingDecision,
    tags=["buckets"],
)
async def route_bucket_preview(
    request: BucketRoutePreviewRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketRoutingDecision:
    owner_id = str(current_user.user_id)
    try:
        result = await knowledge_service.route_bucket_preview(
            owner_id=owner_id,
            title=request.title,
            preview_text=request.preview_text,
            bucket_hint=request.bucket_hint,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return BucketRoutingDecision(
        mode=str(result.get("mode") or "auto"),
        selected_bucket_id=str(result.get("selected_bucket_id") or ""),
        selected_confidence=float(result.get("selected_confidence") or 0.0),
        requires_confirmation=bool(result.get("requires_confirmation")),
        candidates=[
            BucketRoutingCandidate(**candidate)
            for candidate in result.get("candidates") or []
        ],
    )


@router.post("/search", response_model=SearchResponse, tags=["search"])
async def search(
    request: SearchRequest,
    current_user: TokenData = Depends(get_current_user),
) -> SearchResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.search(owner_id, request)
    return SearchResponse(**result)


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    request: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
) -> ChatResponse | StreamingResponse:
    owner_id = _owner_id(current_user)

    if rag_engine is None:
        # Graceful fallback when RAG engine is not wired (e.g. missing Gemini keys)
        result = await knowledge_service.chat(owner_id, request.message)
        return ChatResponse(**result, input=request.message)

    # --- Streaming path ---
    if request.stream:
        return StreamingResponse(
            rag_engine.answer_stream(
                owner_id=owner_id,
                message=request.message,
                session_id=request.session_id,
                bucket_id=request.bucket_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # --- Non-streaming path ---
    try:
        result = await rag_engine.answer(
            owner_id=owner_id,
            message=request.message,
            session_id=request.session_id,
            bucket_id=request.bucket_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"RAG generation failed: {exc}",
        ) from exc
    return ChatResponse(
        owner_id=owner_id,
        answer=result["answer"],
        sources=[CitationSource(**s) for s in result.get("sources", [])],
        input=request.message,
        session_id=result.get("session_id"),
        model=result.get("model"),
        token_count=result.get("token_count"),
        latency_ms=result.get("latency_ms"),
        confidence=result.get("confidence"),
    )


# ------------------------------------------------------------------
# Chat session management endpoints
# ------------------------------------------------------------------


@router.get(
    "/chat/sessions",
    response_model=ChatSessionListResponse,
    tags=["chat"],
)
async def list_chat_sessions(
    current_user: TokenData = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = Query(default=False),
) -> ChatSessionListResponse:
    owner_id = str(current_user.user_id)
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not available")
    rows = await rag_engine.list_sessions(
        owner_id,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )
    return ChatSessionListResponse(sessions=[ChatSessionItem(**row) for row in rows])


@router.get(
    "/chat/sessions/{session_id}",
    response_model=ChatSessionDetail,
    tags=["chat"],
)
async def get_chat_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
) -> ChatSessionDetail:
    owner_id = str(current_user.user_id)
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not available")
    detail = await rag_engine.get_session_detail(
        owner_id, session_id, message_limit=limit
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionDetail(
        session=ChatSessionItem(**detail["session"]),
        messages=[ChatMessageItem(**m) for m in detail["messages"]],
    )


@router.delete(
    "/chat/sessions/{session_id}",
    response_model=ChatSessionDeleteResponse,
    tags=["chat"],
)
async def delete_chat_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> ChatSessionDeleteResponse:
    owner_id = str(current_user.user_id)
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not available")
    deleted = await rag_engine.delete_session(session_id, owner_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionDeleteResponse(status="deleted", session_id=session_id)


@router.get(
    "/ops/embedding-dlq/stats",
    response_model=EmbeddingDlqStatsResponse,
    tags=["ops"],
)
async def embedding_dlq_stats(
    current_user: TokenData = Depends(get_current_user),
) -> EmbeddingDlqStatsResponse:
    _ = current_user
    result = await knowledge_service.get_embedding_dlq_stats()
    return EmbeddingDlqStatsResponse(**result)


@router.post(
    "/ops/embedding-dlq/reprocess-unreplayable",
    response_model=EmbeddingDlqActionResponse,
    tags=["ops"],
)
async def reprocess_embedding_dlq_unreplayable(
    request: EmbeddingDlqReprocessRequest,
    current_user: TokenData = Depends(get_current_user),
) -> EmbeddingDlqActionResponse:
    _ = current_user
    result = await knowledge_service.reprocess_embedding_unreplayable(
        max_items=request.max_items,
        purge_unrecoverable=request.purge_unrecoverable,
        trigger_replay_cycle=request.trigger_replay_cycle,
    )
    return EmbeddingDlqActionResponse(**result)


@router.post(
    "/ops/embedding-dlq/purge-unreplayable",
    response_model=EmbeddingDlqActionResponse,
    tags=["ops"],
)
async def purge_embedding_dlq_unreplayable(
    request: EmbeddingDlqPurgeRequest,
    current_user: TokenData = Depends(get_current_user),
) -> EmbeddingDlqActionResponse:
    _ = current_user
    result = await knowledge_service.purge_embedding_unreplayable(
        max_items=request.max_items
    )
    return EmbeddingDlqActionResponse(**result)


# ------------------------------------------------------------------
# KB Settings
# ------------------------------------------------------------------


@router.get("/settings", response_model=KBSettingsResponse, tags=["settings"])
async def get_settings(
    current_user: TokenData = Depends(get_current_user),
) -> KBSettingsResponse:
    owner_id = _owner_id(current_user)
    settings = await knowledge_service.get_kb_settings(owner_id)
    return KBSettingsResponse(**settings)


@router.patch("/settings", response_model=KBSettingsResponse, tags=["settings"])
async def patch_settings(
    request: KBSettingsPatchRequest,
    current_user: TokenData = Depends(get_current_user),
) -> KBSettingsResponse:
    owner_id = _owner_id(current_user)
    settings = await knowledge_service.update_kb_settings(
        owner_id, **request.model_dump(exclude_none=True)
    )
    return KBSettingsResponse(**settings)


# ------------------------------------------------------------------
# Bucket extras (PATCH, GET single, merge, items)
# NOTE: Static paths must be registered before parameterized ones.
# ------------------------------------------------------------------


@router.post("/buckets/merge", response_model=BucketOperationResponse, tags=["buckets"])
async def merge_buckets(
    request: BucketMergeRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketOperationResponse:
    owner_id = _owner_id(current_user)
    try:
        details = await knowledge_service.merge_buckets(
            owner_id=owner_id,
            source_bucket_id=request.source_bucket_id,
            target_bucket_id=request.target_bucket_id,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BucketOperationResponse(status="merged", details=details)


@router.get("/buckets/{bucket_id}", response_model=BucketItem, tags=["buckets"])
async def get_bucket(
    bucket_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> BucketItem:
    owner_id = _owner_id(current_user)
    buckets = await knowledge_service.list_buckets_for_owner(owner_id)
    for b in buckets:
        if b["bucket_id"] == bucket_id:
            return BucketItem(**b)
    raise HTTPException(status_code=404, detail="Bucket not found")


@router.patch("/buckets/{bucket_id}", response_model=BucketItem, tags=["buckets"])
async def patch_bucket(
    bucket_id: str,
    request: BucketUpdateRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketItem:
    owner_id = _owner_id(current_user)
    try:
        bucket = await knowledge_service.update_bucket(
            owner_id=owner_id,
            bucket_id=bucket_id,
            **request.model_dump(exclude_none=True),
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BucketItem(**bucket)


@router.get("/buckets/{bucket_id}/items", response_model=ItemListResponse, tags=["buckets"])
async def get_bucket_items(
    bucket_id: str,
    current_user: TokenData = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ItemListResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.list_items(
        owner_id, bucket_id=bucket_id, offset=offset, limit=limit
    )
    return ItemListResponse(**result)


# ------------------------------------------------------------------
# Items
# ------------------------------------------------------------------


@router.get("/items", response_model=ItemListResponse, tags=["items"])
async def list_items(
    current_user: TokenData = Depends(get_current_user),
    bucket_id: str | None = Query(default=None),
    content_type: str | None = Query(default=None),
    classified_by: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ItemListResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.list_items(
        owner_id,
        bucket_id=bucket_id,
        content_type=content_type,
        classified_by=classified_by,
        offset=offset,
        limit=limit,
    )
    return ItemListResponse(**result)


@router.get("/items/{item_id}", response_model=ItemDetail, tags=["items"])
async def get_item(
    item_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> ItemDetail:
    owner_id = _owner_id(current_user)
    item = await knowledge_service.get_item(owner_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemDetail(**item)


@router.patch("/items/{item_id}/move", response_model=ItemDetail, tags=["items"])
async def move_item(
    item_id: str,
    request: ItemMoveRequest,
    current_user: TokenData = Depends(get_current_user),
) -> ItemDetail:
    owner_id = _owner_id(current_user)
    try:
        item = await knowledge_service.move_item(owner_id, item_id, request.bucket_id)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ItemDetail(**item)


@router.delete("/items/{item_id}", tags=["items"])
async def delete_item(
    item_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    owner_id = _owner_id(current_user)
    deleted = await knowledge_service.delete_item(owner_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted", "item_id": item_id}


# ------------------------------------------------------------------
# Ingest jobs
# NOTE: /ingest/history must be registered before /ingest/{job_id}
# ------------------------------------------------------------------


@router.get("/ingest/history", response_model=IngestJobListResponse, tags=["ingest"])
async def ingest_history(
    current_user: TokenData = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> IngestJobListResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.list_ingest_jobs(owner_id, offset=offset, limit=limit)
    return IngestJobListResponse(**result)


@router.get("/ingest/{job_id}", response_model=IngestJobStatus, tags=["ingest"])
async def get_ingest_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> IngestJobStatus:
    owner_id = _owner_id(current_user)
    job = await knowledge_service.get_ingest_job(owner_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return IngestJobStatus(**job)


# ------------------------------------------------------------------
# AI bucket suggestions
# NOTE: /suggestions/history before /suggestions/{suggestion_id}
# ------------------------------------------------------------------


@router.get("/suggestions", response_model=SuggestionListResponse, tags=["suggestions"])
async def list_suggestions(
    current_user: TokenData = Depends(get_current_user),
    status: str = Query(default="pending"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> SuggestionListResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.list_suggestions(
        owner_id, status=status, offset=offset, limit=limit
    )
    return SuggestionListResponse(**result)


@router.get(
    "/suggestions/history",
    response_model=SuggestionListResponse,
    tags=["suggestions"],
)
async def suggestions_history(
    current_user: TokenData = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> SuggestionListResponse:
    owner_id = _owner_id(current_user)
    # return both approved and rejected
    import asyncio as _asyncio
    approved, rejected = await _asyncio.gather(
        knowledge_service.list_suggestions(owner_id, status="approved", offset=0, limit=limit),
        knowledge_service.list_suggestions(owner_id, status="rejected", offset=0, limit=limit),
    )
    combined = approved["suggestions"] + rejected["suggestions"]
    combined.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    combined = combined[offset: offset + limit]
    return SuggestionListResponse(
        suggestions=[SuggestionItem(**s) for s in combined],
        total=approved["total"] + rejected["total"],
    )


@router.post(
    "/suggestions/{suggestion_id}/approve",
    response_model=BucketItem,
    tags=["suggestions"],
)
async def approve_suggestion(
    suggestion_id: str,
    request: SuggestionApproveRequest,
    current_user: TokenData = Depends(get_current_user),
) -> BucketItem:
    owner_id = _owner_id(current_user)
    try:
        bucket = await knowledge_service.approve_suggestion(
            owner_id,
            suggestion_id,
            name=request.name,
            description=request.description,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BucketItem(**bucket)


@router.post(
    "/suggestions/{suggestion_id}/reject",
    tags=["suggestions"],
)
async def reject_suggestion(
    suggestion_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    owner_id = _owner_id(current_user)
    try:
        await knowledge_service.reject_suggestion(owner_id, suggestion_id)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "rejected", "suggestion_id": suggestion_id}
