from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str | None = None
    mime_type: str | None = None
    source_url: str | None = None
    bucket_id: str | None = None
    bucket_hint: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_content_source(self) -> "UploadRequest":
        if not self.content_base64 and not self.source_url:
            raise ValueError(
                "At least one of 'content_base64' or 'source_url' must be provided"
            )
        return self


class UploadResponse(BaseModel):
    document_id: str
    status: str
    content_bucket_id: str | None = None
    minio_storage_bucket_name: str | None = None
    content_type: str
    strategy: str
    word_count: int
    char_count: int
    metadata: Dict[str, Any]
    created_at: str


class DocumentItem(BaseModel):
    document_id: str
    owner_id: str
    filename: str
    status: str
    content_type: str | None = None
    strategy: str | None = None
    word_count: int | None = None
    char_count: int | None = None
    text_preview: str | None = None
    metadata: Dict[str, Any] | None = None
    created_at: str


class BucketItem(BaseModel):
    bucket_id: str
    user_id: str
    parent_bucket_id: str | None = None
    depth: int
    name: str
    description: str | None = None
    icon_emoji: str | None = None
    color_hex: str | None = None
    document_count: int
    is_default: bool
    is_deleted: bool
    path: str
    max_depth: int = -1
    auto_classify: bool = True
    created_at: str
    updated_at: str


class BucketCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    parent_bucket_id: str | None = None
    icon_emoji: str | None = Field(default=None, max_length=32)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    max_depth: int = Field(default=-1, ge=-1, description="-1 = unlimited, 0 = flat (no children)")
    auto_classify: bool = Field(default=True, description="Allow AI to route documents into this bucket")


class BucketUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    icon_emoji: str | None = Field(default=None, max_length=32)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    max_depth: int | None = Field(default=None, ge=-1)
    auto_classify: bool | None = None


class BucketMoveRequest(BaseModel):
    parent_bucket_id: str | None = None


class BucketDeleteRequest(BaseModel):
    target_bucket_id: str | None = None


class BucketBulkMoveRequest(BaseModel):
    source_bucket_id: str
    target_bucket_id: str


class BucketRoutePreviewRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    preview_text: str = Field(min_length=1, max_length=4000)
    bucket_hint: str | None = Field(default=None, max_length=500)


class BucketRoutingCandidate(BaseModel):
    bucket_id: str
    confidence: float
    reasoning: str | None = None


class BucketRoutingDecision(BaseModel):
    mode: str
    selected_bucket_id: str
    selected_confidence: float
    requires_confirmation: bool
    candidates: list[BucketRoutingCandidate]


class BucketTreeResponse(BaseModel):
    buckets: list[BucketItem]


class BucketOperationResponse(BaseModel):
    status: str
    details: Dict[str, Any]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    latency_budget_ms: int = Field(default=100, ge=10, le=1000)
    bucket_id: str | None = None
    content_type: str | None = None
    tags: List[str] | None = None
    created_after: str | None = None
    created_before: str | None = None
    enable_rerank: bool = True


class SearchResponse(BaseModel):
    query: str
    top_k: int
    results: List[Dict[str, Any]]
    total_candidates: int | None = None
    latency_ms: int | None = None
    cache_hit: bool | None = None
    query_intent: str | None = None
    owner_id: str
    message: str
    diagnostics: Dict[str, Any] | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = Field(
        default=None, description="Existing session ID to continue a conversation"
    )
    stream: bool = Field(default=False, description="Enable SSE streaming response")
    bucket_id: str | None = Field(
        default=None, description="Restrict retrieval to a specific bucket"
    )


class CitationSource(BaseModel):
    index: int
    document_id: str
    document_title: str = ""
    section_heading: str | None = None
    source_url: str | None = None
    bucket_name: str | None = None
    score: float = 0.0
    text_preview: str = ""


class ChatResponse(BaseModel):
    owner_id: str
    answer: str
    sources: List[CitationSource] = []
    input: str
    session_id: str | None = None
    model: str | None = None
    token_count: int | None = None
    latency_ms: int | None = None
    confidence: float | None = None


class ChatSessionItem(BaseModel):
    session_id: str
    user_id: str
    title: str | None = None
    model: str | None = None
    is_archived: bool = False
    created_at: str
    updated_at: str


class ChatMessageItem(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    sources: List[Dict[str, Any]] = []
    token_count: int = 0
    latency_ms: int = 0
    created_at: str


class ChatSessionDetail(BaseModel):
    session: ChatSessionItem
    messages: List[ChatMessageItem]


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionItem]


class ChatSessionDeleteResponse(BaseModel):
    status: str
    session_id: str


class EmbeddingDlqStatsResponse(BaseModel):
    active_dlq: int
    unreplayable: int
    replayed: int
    failed: int


class EmbeddingDlqReprocessRequest(BaseModel):
    max_items: int = Field(default=100, ge=1, le=1000)
    purge_unrecoverable: bool = False
    trigger_replay_cycle: bool = True


class EmbeddingDlqPurgeRequest(BaseModel):
    max_items: int = Field(default=100, ge=1, le=100000)


class EmbeddingDlqActionResponse(BaseModel):
    processed: int
    moved_to_dlq: int
    kept_unreplayable: int
    purged: int
    replay_cycle: Dict[str, int] | None = None
    stats: EmbeddingDlqStatsResponse


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

LowConfidenceAction = Literal["suggest_bucket", "send_to_unassigned", "force_classify"]


class KBSettingsResponse(BaseModel):
    auto_classify: bool
    auto_create: bool
    default_max_depth: int
    confidence_threshold: float
    low_confidence_action: LowConfidenceAction


class KBSettingsPatchRequest(BaseModel):
    auto_classify: bool | None = None
    auto_create: bool | None = None
    default_max_depth: int | None = Field(default=None, ge=-1)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    low_confidence_action: LowConfidenceAction | None = None


# -------------------------------------------------------------------------
# Item (document) endpoints
# -------------------------------------------------------------------------

class ItemDetail(BaseModel):
    document_id: str
    owner_id: str
    filename: str
    status: str
    content_type: str | None = None
    strategy: str | None = None
    word_count: int | None = None
    char_count: int | None = None
    text_preview: str | None = None
    source_url: str | None = None
    bucket_id: str | None = None
    bucket_path: str | None = None
    classified_by: str | None = None
    classification_confidence: float | None = None
    classification_reasoning: str | None = None
    metadata: Dict[str, Any] | None = None
    created_at: str


class ItemListResponse(BaseModel):
    items: List[ItemDetail]
    total: int
    offset: int
    limit: int


class ItemMoveRequest(BaseModel):
    bucket_id: str = Field(description="Target bucket ID to move this item into")


# -------------------------------------------------------------------------
# Async ingest jobs
# -------------------------------------------------------------------------

class IngestJobStatus(BaseModel):
    job_id: str
    status: Literal["processing", "classified", "pending_approval", "unassigned", "failed"]
    item_id: str | None = None
    bucket_id: str | None = None
    bucket_path: str | None = None
    confidence: float | None = None
    ai_reasoning: str | None = None
    error_message: str | None = None
    suggestion_id: str | None = None
    created_at: str
    updated_at: str


class IngestJobListResponse(BaseModel):
    jobs: List[IngestJobStatus]
    total: int
    offset: int
    limit: int


# -------------------------------------------------------------------------
# AI bucket suggestions
# -------------------------------------------------------------------------

class SuggestionItem(BaseModel):
    suggestion_id: str
    user_id: str
    proposed_name: str
    proposed_parent_id: str | None = None
    proposed_description: str | None = None
    triggered_by_item_id: str | None = None
    triggered_by_job_id: str | None = None
    ai_reasoning: str | None = None
    status: Literal["pending", "approved", "rejected"]
    created_at: str
    updated_at: str


class SuggestionListResponse(BaseModel):
    suggestions: List[SuggestionItem]
    total: int


class SuggestionApproveRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, description="Override proposed name before approving")
    description: str | None = Field(default=None, max_length=2000, description="Override proposed description before approving")


class SuggestionHistoryResponse(BaseModel):
    suggestions: List[SuggestionItem]
    total: int


# -------------------------------------------------------------------------
# Bucket merge
# -------------------------------------------------------------------------

class BucketMergeRequest(BaseModel):
    source_bucket_id: str = Field(description="Bucket to merge from (will be deleted after merge)")
    target_bucket_id: str = Field(description="Bucket to merge into (kept)")


# -------------------------------------------------------------------------
# Reclassification
# -------------------------------------------------------------------------

class ReclassifyResponse(BaseModel):
    item_id: str
    bucket_id: str | None = None
    bucket_path: str | None = None
    confidence: float | None = None
    ai_reasoning: str | None = None
    status: str
