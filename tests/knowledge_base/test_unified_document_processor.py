import base64
import asyncio

from app.application.ingestion.format_detector import detect_document_format
from app.application.ingestion.models import DocumentFormat
from app.application.ingestion.unified_processor import UnifiedDocumentProcessor


def test_detect_pdf_by_magic_number() -> None:
    detected = detect_document_format(
        filename="sample.bin",
        content_bytes=b"%PDF-1.7\nrest",
        mime_type=None,
        source_url=None,
    )
    assert detected.format == DocumentFormat.PDF
    assert detected.detector_confidence >= 0.9


def test_detect_text_subtype_json() -> None:
    detected = detect_document_format(
        filename="notes.txt",
        content_bytes=b'{"name":"plos"}',
        mime_type="text/plain",
        source_url=None,
    )
    assert detected.format == DocumentFormat.TEXT
    assert detected.text_subtype == "json"


def test_unified_processor_text_flow() -> None:
    processor = UnifiedDocumentProcessor()
    text = "# Daily Log\n\n- Slept 7 hours\n- Mood 8"
    payload = base64.b64encode(text.encode("utf-8")).decode("utf-8")

    result = asyncio.run(
        processor.process(
            filename="journal.md",
            content_bytes=base64.b64decode(payload),
            mime_type="text/markdown",
            source_url=None,
        )
    )

    assert result.format == DocumentFormat.TEXT
    assert result.strategy_used.value == "text_direct"
    assert len(result.sections) >= 2
    assert "detected_format" in result.metadata


def test_unified_processor_web_detection_without_content() -> None:
    processor = UnifiedDocumentProcessor()
    result = asyncio.run(
        processor.process(
            filename="from_url",
            content_bytes=None,
            mime_type=None,
            source_url="https://example.com",
        )
    )
    assert result.format == DocumentFormat.WEB
    assert result.strategy_used.value == "web_static_dynamic"
