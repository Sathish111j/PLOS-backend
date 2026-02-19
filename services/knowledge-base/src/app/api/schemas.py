from typing import Any, Dict, List

from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str | None = None
    mime_type: str | None = None
    source_url: str | None = None


class UploadResponse(BaseModel):
    document_id: str
    status: str
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
    name: str
    provider: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResponse(BaseModel):
    query: str
    top_k: int
    results: List[Dict[str, Any]]
    owner_id: str
    message: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    owner_id: str
    answer: str
    sources: List[Dict[str, Any]]
    input: str
