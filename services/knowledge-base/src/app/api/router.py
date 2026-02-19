import time

from app.api.schemas import (
    BucketItem,
    ChatRequest,
    ChatResponse,
    DocumentItem,
    SearchRequest,
    SearchResponse,
    UploadRequest,
    UploadResponse,
)
from app.core.config import get_kb_config
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.dependencies.container import infra_health_client, knowledge_service
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from shared.auth.dependencies import get_current_user_optional
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


@router.get("/buckets", response_model=list[BucketItem], tags=["documents"])
async def list_buckets() -> list[BucketItem]:
    buckets = await knowledge_service.list_buckets()
    return [BucketItem(**item) for item in buckets]


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
