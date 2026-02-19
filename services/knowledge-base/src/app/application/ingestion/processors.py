from __future__ import annotations

import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from app.application.ingestion.models import (
    ContentClass,
    DocumentFormat,
    ExtractionStrategy,
    StructuredDocument,
)
from app.application.ingestion.normalizer import (
    infer_sections_from_text,
    normalize_text,
)


@dataclass
class ProcessorInput:
    filename: str
    content_bytes: bytes | None
    source_url: str | None
    mime_type: str | None
    text_encoding: str | None


def _base_metadata(payload: ProcessorInput) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    raw = payload.content_bytes or b""
    return {
        "filename": payload.filename,
        "mime_type": payload.mime_type,
        "source_url": payload.source_url,
        "file_size": len(raw),
        "checksum": hashlib.sha256(raw).hexdigest() if raw else None,
        "processed_at": now,
    }


def _decode_bytes(raw: bytes, encoding: str | None = None) -> str:
    if not raw:
        return ""
    preferred = [encoding] if encoding else []
    for enc in [*preferred, "utf-8", "utf-16", "ascii", "latin-1"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


class TextProcessor:
    def process(self, payload: ProcessorInput) -> StructuredDocument:
        text = _decode_bytes(payload.content_bytes or b"", payload.text_encoding)
        normalized = normalize_text(text)
        metadata = _base_metadata(payload)
        metadata.update(
            {
                "word_count": len(normalized.split()),
                "char_count": len(normalized),
                "line_count": len(normalized.splitlines()),
            }
        )
        return StructuredDocument(
            text=normalized,
            sections=infer_sections_from_text(normalized),
            metadata=metadata,
            confidence_scores={"text_extraction": 0.99},
            strategy_used=ExtractionStrategy.TEXT_DIRECT,
            format=DocumentFormat.TEXT,
            content_class=ContentClass.TEXT_BASED,
        )


class PdfProcessor:
    def classify_pdf(self, payload: ProcessorInput) -> ContentClass:
        raw = payload.content_bytes or b""
        text_markers = sum(raw.count(marker) for marker in (b"BT", b"/Font", b"Tj"))
        image_markers = sum(raw.count(marker) for marker in (b"/Image", b"/XObject"))
        if text_markers > 0 and image_markers == 0:
            return ContentClass.TEXT_BASED
        if image_markers > 0 and text_markers == 0:
            return ContentClass.IMAGE_BASED
        if image_markers > 0 and text_markers > 0:
            return ContentClass.MIXED
        return ContentClass.TEXT_BASED

    def _extract_text_pdfplumber(
        self, payload: ProcessorInput
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        try:
            import pdfplumber
        except Exception:
            return "", [], {"pdfplumber_available": False}

        text_parts: list[str] = []
        tables: list[dict[str, Any]] = []
        page_count = 0

        with pdfplumber.open(io.BytesIO(payload.content_bytes or b"")) as pdf:
            page_count = len(pdf.pages)
            for index, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text(layout=True) or ""
                if page_text:
                    text_parts.append(f"\n[Page {index}]\n{page_text}")

                extracted_tables = page.extract_tables() or []
                for table in extracted_tables:
                    tables.append({"page": index, "rows": table})

        combined = normalize_text("\n".join(text_parts))
        return (
            combined,
            tables,
            {"pdfplumber_available": True, "page_count": page_count},
        )

    def _extract_image_pdf_fallback(
        self, payload: ProcessorInput, content_class: ContentClass
    ) -> StructuredDocument:
        metadata = _base_metadata(payload)
        metadata.update(
            {
                "ocr_chain": ["mineru", "paddleocr", "tesseract"],
                "note": "High-accuracy OCR pipeline placeholders are wired. Install and configure OCR runtimes for full extraction.",
            }
        )
        return StructuredDocument(
            text="",
            sections=[],
            metadata=metadata,
            confidence_scores={"text_extraction": 0.2},
            strategy_used=(
                ExtractionStrategy.PDF_SCANNED_HIGH_ACCURACY
                if content_class == ContentClass.IMAGE_BASED
                else ExtractionStrategy.PDF_MIXED_HYBRID
            ),
            format=DocumentFormat.PDF,
            content_class=content_class,
        )

    def process(self, payload: ProcessorInput) -> StructuredDocument:
        content_class = self.classify_pdf(payload)

        if content_class == ContentClass.TEXT_BASED:
            try:
                text, tables, extra_meta = self._extract_text_pdfplumber(payload)
            except Exception:
                return self._extract_image_pdf_fallback(payload, ContentClass.MIXED)
            metadata = _base_metadata(payload)
            metadata.update(extra_meta)
            metadata.update(
                {
                    "word_count": len(text.split()),
                    "char_count": len(text),
                }
            )
            return StructuredDocument(
                text=text,
                sections=infer_sections_from_text(text),
                tables=tables,
                metadata=metadata,
                confidence_scores={"text_extraction": 0.95, "table_extraction": 0.7},
                strategy_used=ExtractionStrategy.PDF_TEXT_FAST,
                format=DocumentFormat.PDF,
                content_class=content_class,
            )

        return self._extract_image_pdf_fallback(payload, content_class)


class ImageProcessor:
    def process(self, payload: ProcessorInput) -> StructuredDocument:
        metadata = _base_metadata(payload)
        metadata["ocr_chain"] = ["paddleocr", "tesseract"]

        text = ""
        confidence = 0.2

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(payload.content_bytes or b""))
            text = normalize_text(pytesseract.image_to_string(image))
            confidence = 0.7 if text else 0.3
            metadata["ocr_engine"] = "tesseract"
        except Exception:
            metadata["ocr_engine"] = "fallback_chain_unavailable"

        return StructuredDocument(
            text=text,
            sections=infer_sections_from_text(text),
            metadata=metadata,
            confidence_scores={"ocr_confidence": confidence},
            strategy_used=ExtractionStrategy.IMAGE_OCR_CHAIN,
            format=DocumentFormat.IMAGE,
            content_class=ContentClass.IMAGE_BASED,
        )


class OfficeProcessor:
    def _process_docx(self, payload: ProcessorInput) -> tuple[str, dict[str, Any]]:
        try:
            from docx import Document
        except Exception:
            return "", {"docx_parser": "unavailable"}

        document = Document(io.BytesIO(payload.content_bytes or b""))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        table_count = len(document.tables)
        return normalize_text("\n\n".join(paragraphs)), {"table_count": table_count}

    def _process_xlsx(self, payload: ProcessorInput) -> tuple[str, dict[str, Any]]:
        try:
            from openpyxl import load_workbook
        except Exception:
            return "", {"xlsx_parser": "unavailable"}

        workbook = load_workbook(
            io.BytesIO(payload.content_bytes or b""), data_only=False
        )
        markdown_parts: list[str] = []
        for sheet in workbook.worksheets:
            markdown_parts.append(f"## Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = ["" if cell is None else str(cell) for cell in row]
                markdown_parts.append(" | ".join(values))
        return normalize_text("\n".join(markdown_parts)), {
            "sheet_count": len(workbook.worksheets)
        }

    def _process_pptx(self, payload: ProcessorInput) -> tuple[str, dict[str, Any]]:
        try:
            from pptx import Presentation
        except Exception:
            return "", {"pptx_parser": "unavailable"}

        presentation = Presentation(io.BytesIO(payload.content_bytes or b""))
        lines: list[str] = []
        for index, slide in enumerate(presentation.slides, start=1):
            lines.append(f"## Slide {index}")
            for shape in slide.shapes:
                text = getattr(shape, "text", "")
                if text and text.strip():
                    lines.append(text.strip())
        return normalize_text("\n".join(lines)), {
            "slide_count": len(presentation.slides)
        }

    def process(self, payload: ProcessorInput) -> StructuredDocument:
        extension = Path(payload.filename).suffix.lower()
        text = ""
        details: dict[str, Any] = {}

        if extension in {".docx", ".doc"}:
            text, details = self._process_docx(payload)
        elif extension in {".xlsx", ".xls"}:
            text, details = self._process_xlsx(payload)
        elif extension in {".pptx", ".ppt"}:
            text, details = self._process_pptx(payload)

        metadata = _base_metadata(payload)
        metadata.update(details)
        metadata["office_extension"] = extension

        return StructuredDocument(
            text=text,
            sections=infer_sections_from_text(text),
            metadata=metadata,
            confidence_scores={"text_extraction": 0.9 if text else 0.2},
            strategy_used=ExtractionStrategy.OFFICE_NATIVE,
            format=DocumentFormat.OFFICE,
            content_class=ContentClass.TEXT_BASED,
        )


class WebProcessor:
    async def _fetch_html(self, url: str) -> str:
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _extract_static(self, html: str) -> tuple[str, dict[str, Any]]:
        try:
            import trafilatura

            extracted = trafilatura.extract(html, output_format="txt")
            if extracted:
                return normalize_text(extracted), {"extractor": "trafilatura"}
        except Exception:
            pass

        try:
            from bs4 import BeautifulSoup
            from readability import Document

            summary_html = Document(html).summary()
            text = BeautifulSoup(summary_html, "lxml").get_text("\n")
            return normalize_text(text), {"extractor": "readability"}
        except Exception:
            pass

        from bs4 import BeautifulSoup

        text = BeautifulSoup(html, "lxml").get_text("\n")
        return normalize_text(text), {"extractor": "beautifulsoup"}

    async def process(self, payload: ProcessorInput) -> StructuredDocument:
        if not payload.source_url:
            return StructuredDocument(
                text="",
                metadata={"error": "missing source_url"},
                confidence_scores={"text_extraction": 0.0},
                strategy_used=ExtractionStrategy.WEB_STATIC_DYNAMIC,
                format=DocumentFormat.WEB,
            )

        try:
            html = await self._fetch_html(payload.source_url)
            text, details = self._extract_static(html)
        except Exception as error:
            text = ""
            details = {"extractor": "network_fallback", "error": str(error)}
        metadata = _base_metadata(payload)
        metadata.update(details)
        metadata["word_count"] = len(text.split())

        return StructuredDocument(
            text=text,
            sections=infer_sections_from_text(text),
            metadata=metadata,
            confidence_scores={"text_extraction": 0.9 if text else 0.2},
            strategy_used=ExtractionStrategy.WEB_STATIC_DYNAMIC,
            format=DocumentFormat.WEB,
            content_class=ContentClass.TEXT_BASED,
        )


class FallbackProcessor:
    def process(self, payload: ProcessorInput) -> StructuredDocument:
        text = _decode_bytes(payload.content_bytes or b"", payload.text_encoding)
        normalized = normalize_text(text)
        metadata = _base_metadata(payload)
        return StructuredDocument(
            text=normalized,
            sections=infer_sections_from_text(normalized),
            metadata=metadata,
            confidence_scores={"text_extraction": 0.4},
            strategy_used=ExtractionStrategy.FALLBACK_GENERIC,
            format=DocumentFormat.UNKNOWN,
        )


def parse_text_subtype(text: str, subtype: str | None) -> dict[str, Any]:
    if not subtype:
        return {}
    if subtype == "json":
        try:
            data = json.loads(text)
            return {"json_keys": list(data.keys()) if isinstance(data, dict) else None}
        except Exception:
            return {}
    if subtype == "xml":
        try:
            root = ET.fromstring(text)
            return {"xml_root_tag": root.tag}
        except Exception:
            return {}
    if subtype == "csv":
        try:
            reader = csv.reader(io.StringIO(text))
            first = next(reader, [])
            return {"csv_header": first}
        except Exception:
            return {}
    return {}
