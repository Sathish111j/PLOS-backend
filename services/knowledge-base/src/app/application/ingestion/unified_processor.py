from __future__ import annotations

from app.application.ingestion.format_detector import detect_document_format
from app.application.ingestion.models import (
    ContentClass,
    DocumentFormat,
    ExtractionStrategy,
    StructuredDocument,
)
from app.application.ingestion.processors import (
    FallbackProcessor,
    ImageProcessor,
    OfficeProcessor,
    PdfProcessor,
    ProcessorInput,
    TextProcessor,
    WebProcessor,
    parse_text_subtype,
)


class UnifiedDocumentProcessor:
    def __init__(self):
        self._text_processor = TextProcessor()
        self._pdf_processor = PdfProcessor()
        self._image_processor = ImageProcessor()
        self._office_processor = OfficeProcessor()
        self._web_processor = WebProcessor()
        self._fallback_processor = FallbackProcessor()

    def _select_strategy(
        self,
        detected_format: DocumentFormat,
        content_class: ContentClass,
    ) -> ExtractionStrategy:
        if detected_format == DocumentFormat.PDF:
            if content_class == ContentClass.TEXT_BASED:
                return ExtractionStrategy.PDF_TEXT_FAST
            if content_class == ContentClass.IMAGE_BASED:
                return ExtractionStrategy.PDF_SCANNED_HIGH_ACCURACY
            if content_class == ContentClass.MIXED:
                return ExtractionStrategy.PDF_MIXED_HYBRID
        if detected_format == DocumentFormat.IMAGE:
            return ExtractionStrategy.IMAGE_OCR_CHAIN
        if detected_format == DocumentFormat.OFFICE:
            return ExtractionStrategy.OFFICE_NATIVE
        if detected_format == DocumentFormat.WEB:
            return ExtractionStrategy.WEB_STATIC_DYNAMIC
        if detected_format == DocumentFormat.TEXT:
            return ExtractionStrategy.TEXT_DIRECT
        return ExtractionStrategy.FALLBACK_GENERIC

    async def process(
        self,
        *,
        filename: str,
        content_bytes: bytes | None,
        mime_type: str | None,
        source_url: str | None,
    ) -> StructuredDocument:
        detected = detect_document_format(
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            source_url=source_url,
        )

        payload = ProcessorInput(
            filename=filename,
            content_bytes=content_bytes,
            source_url=source_url,
            mime_type=detected.mime_type,
            text_encoding=detected.encoding,
        )

        if detected.format == DocumentFormat.PDF:
            result = self._pdf_processor.process(payload)
        elif detected.format == DocumentFormat.IMAGE:
            result = self._image_processor.process(payload)
        elif detected.format == DocumentFormat.OFFICE:
            result = self._office_processor.process(payload)
        elif detected.format == DocumentFormat.WEB:
            result = await self._web_processor.process(payload)
        elif detected.format == DocumentFormat.TEXT:
            result = self._text_processor.process(payload)
            result.metadata.update(
                parse_text_subtype(result.text, detected.text_subtype)
            )
        else:
            result = self._fallback_processor.process(payload)

        selected_strategy = self._select_strategy(result.format, result.content_class)
        result.strategy_used = selected_strategy
        result.metadata["detected_format"] = detected.format.value
        result.metadata["detector_confidence"] = detected.detector_confidence
        result.metadata["detected_extension"] = detected.extension
        result.metadata["detected_encoding"] = detected.encoding
        result.metadata["text_subtype"] = detected.text_subtype
        return result
