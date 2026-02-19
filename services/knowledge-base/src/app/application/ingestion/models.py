from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    OFFICE = "office"
    WEB = "web"
    TEXT = "text"
    UNKNOWN = "unknown"


class ContentClass(str, Enum):
    TEXT_BASED = "text_based"
    IMAGE_BASED = "image_based"
    MIXED = "mixed"
    NOT_APPLICABLE = "not_applicable"


class ExtractionStrategy(str, Enum):
    PDF_TEXT_FAST = "pdf_text_fast"
    PDF_SCANNED_HIGH_ACCURACY = "pdf_scanned_high_accuracy"
    PDF_MIXED_HYBRID = "pdf_mixed_hybrid"
    IMAGE_OCR_CHAIN = "image_ocr_chain"
    OFFICE_NATIVE = "office_native"
    WEB_STATIC_DYNAMIC = "web_static_dynamic"
    TEXT_DIRECT = "text_direct"
    FALLBACK_GENERIC = "fallback_generic"


class DetectedFormat(BaseModel):
    format: DocumentFormat
    mime_type: str | None = None
    extension: str | None = None
    encoding: str | None = None
    text_subtype: str | None = None
    detector_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StructuredSection(BaseModel):
    section_type: str
    content: str
    level: int | None = None


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0
    char_count: int = 0


class StructuredDocument(BaseModel):
    text: str
    sections: list[StructuredSection] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
    chunks: list[DocumentChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    strategy_used: ExtractionStrategy
    format: DocumentFormat
    content_class: ContentClass = ContentClass.NOT_APPLICABLE
