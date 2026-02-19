from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class DocumentFormat(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    OFFICE = "office"
    WEB = "web"
    TEXT = "text"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    PDF_TEXT = "pdf_text"
    PDF_SCANNED = "pdf_scanned"
    PDF_MIXED = "pdf_mixed"
    IMAGE = "image"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    WEB_STATIC = "web_static"
    WEB_DYNAMIC = "web_dynamic"
    TEXT = "text"


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
    document_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType = SourceType.TEXT
    raw_text: str = ""
    text: str = ""
    sections: list[StructuredSection] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
    chunks: list[DocumentChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_path: str = ""
    strategy_used: ExtractionStrategy
    format: DocumentFormat
    content_class: ContentClass = ContentClass.NOT_APPLICABLE

    @model_validator(mode="before")
    @classmethod
    def _sync_text_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        text = values.get("text")
        raw_text = values.get("raw_text")

        if raw_text is None and text is not None:
            values["raw_text"] = text
        if text is None and raw_text is not None:
            values["text"] = raw_text

        return values

    @model_validator(mode="after")
    def _finalize_contract_fields(self) -> "StructuredDocument":
        if not self.raw_text and self.text:
            self.raw_text = self.text
        if not self.text and self.raw_text:
            self.text = self.raw_text

        if not self.extraction_path:
            self.extraction_path = self.strategy_used.value

        if self.confidence_score <= 0.0:
            if self.confidence_scores:
                self.confidence_score = max(
                    0.0,
                    min(1.0, sum(self.confidence_scores.values()) / len(self.confidence_scores)),
                )
            else:
                self.confidence_score = 0.0

        return self
