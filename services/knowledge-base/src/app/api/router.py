import time

from app.api.schemas import (
    BucketBulkMoveRequest,
    BucketCreateRequest,
    BucketDeleteRequest,
    BucketItem,
    BucketMoveRequest,
    BucketOperationResponse,
    BucketRoutePreviewRequest,
    BucketRoutingCandidate,
    BucketRoutingDecision,
    BucketTreeResponse,
    ChatRequest,
    ChatResponse,
    DocumentItem,
    EmbeddingDlqActionResponse,
    EmbeddingDlqPurgeRequest,
    EmbeddingDlqReprocessRequest,
    EmbeddingDlqStatsResponse,
    SearchRequest,
    SearchResponse,
    UploadRequest,
    UploadResponse,
)
from app.core.config import get_kb_config
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.dependencies.container import infra_health_client, knowledge_service
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from shared.auth.dependencies import get_current_user, get_current_user_optional
from shared.auth.models import TokenData

router = APIRouter()
config = get_kb_config()


def _owner_id(user: TokenData | None) -> str:
    if user:
        return str(user.user_id)
    return "anonymous"


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
    current_user: TokenData | None = Depends(get_current_user_optional),
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
    REQUEST_COUNT.labels(method="POST", endpoint="/upload", status="200").inc()
    REQUEST_LATENCY.labels(method="POST", endpoint="/upload").observe(duration)
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


@router.post("/ingest", response_model=UploadResponse, tags=["documents"])
async def ingest_document(
    request: UploadRequest,
    current_user: TokenData | None = Depends(get_current_user_optional),
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
    REQUEST_COUNT.labels(method="POST", endpoint="/ingest", status="200").inc()
    REQUEST_LATENCY.labels(method="POST", endpoint="/ingest").observe(duration)
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


@router.get("/documents", response_model=list[DocumentItem], tags=["documents"])
async def list_documents(
    current_user: TokenData | None = Depends(get_current_user_optional),
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


@router.delete("/buckets/{bucket_id}", response_model=BucketOperationResponse, tags=["buckets"])
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
        candidates=[BucketRoutingCandidate(**candidate) for candidate in result.get("candidates") or []],
    )


@router.post("/search", response_model=SearchResponse, tags=["search"])
async def search(
    request: SearchRequest,
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> SearchResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.search(owner_id, request)
    return SearchResponse(**result)


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    request: ChatRequest,
    current_user: TokenData | None = Depends(get_current_user_optional),
) -> ChatResponse:
    owner_id = _owner_id(current_user)
    result = await knowledge_service.chat(owner_id, request.message)
    return ChatResponse(**result)


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
