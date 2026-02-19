import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from app.application.ingestion.models import DetectedFormat, DocumentFormat

MAGIC_SIGNATURES: list[tuple[bytes, DocumentFormat, str]] = [
    (b"%PDF", DocumentFormat.PDF, "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", DocumentFormat.IMAGE, "image/png"),
    (b"\xff\xd8\xff", DocumentFormat.IMAGE, "image/jpeg"),
    (b"GIF87a", DocumentFormat.IMAGE, "image/gif"),
    (b"GIF89a", DocumentFormat.IMAGE, "image/gif"),
    (b"PK\x03\x04", DocumentFormat.OFFICE, "application/zip"),
]

EXTENSION_MAP: dict[str, tuple[DocumentFormat, str | None]] = {
    ".pdf": (DocumentFormat.PDF, "application/pdf"),
    ".png": (DocumentFormat.IMAGE, "image/png"),
    ".jpg": (DocumentFormat.IMAGE, "image/jpeg"),
    ".jpeg": (DocumentFormat.IMAGE, "image/jpeg"),
    ".gif": (DocumentFormat.IMAGE, "image/gif"),
    ".bmp": (DocumentFormat.IMAGE, "image/bmp"),
    ".webp": (DocumentFormat.IMAGE, "image/webp"),
    ".docx": (
        DocumentFormat.OFFICE,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ".doc": (DocumentFormat.OFFICE, "application/msword"),
    ".xlsx": (
        DocumentFormat.OFFICE,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ".xls": (DocumentFormat.OFFICE, "application/vnd.ms-excel"),
    ".pptx": (
        DocumentFormat.OFFICE,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    ".ppt": (DocumentFormat.OFFICE, "application/vnd.ms-powerpoint"),
    ".txt": (DocumentFormat.TEXT, "text/plain"),
    ".md": (DocumentFormat.TEXT, "text/markdown"),
    ".csv": (DocumentFormat.TEXT, "text/csv"),
    ".json": (DocumentFormat.TEXT, "application/json"),
    ".xml": (DocumentFormat.TEXT, "application/xml"),
    ".html": (DocumentFormat.WEB, "text/html"),
    ".htm": (DocumentFormat.WEB, "text/html"),
}


def _detect_from_magic(header: bytes) -> tuple[DocumentFormat, str | None, float]:
    for signature, detected_format, mime in MAGIC_SIGNATURES:
        if header.startswith(signature):
            return detected_format, mime, 0.99
    return DocumentFormat.UNKNOWN, None, 0.0


def _detect_encoding(sample: bytes) -> str:
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8"
    if sample.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if sample.startswith(b"\xfe\xff"):
        return "utf-16-be"

    for encoding in ("utf-8", "utf-16", "ascii"):
        try:
            sample.decode(encoding)
            return encoding
        except Exception:
            continue
    return "latin-1"


def _sniff_text_subtype(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "plain"

    try:
        json.loads(stripped)
        return "json"
    except Exception:
        pass

    try:
        ET.fromstring(stripped)
        return "xml"
    except Exception:
        pass

    try:
        dialect = csv.Sniffer().sniff(stripped[:1024], delimiters=",;\t")
        if dialect.delimiter in {",", ";", "\t"}:
            return "csv"
    except Exception:
        pass

    if stripped.startswith("#"):
        return "markdown"
    return "plain"


def detect_document_format(
    *,
    filename: str,
    content_bytes: bytes | None,
    mime_type: str | None,
    source_url: str | None,
) -> DetectedFormat:
    extension = Path(filename).suffix.lower() if filename else None
    header = (content_bytes or b"")[:8]
    sniff_sample = (content_bytes or b"")[:1024]

    detected_format, magic_mime, confidence = _detect_from_magic(header)
    detected_mime = mime_type or magic_mime

    if detected_format == DocumentFormat.UNKNOWN and mime_type:
        normalized_mime = mime_type.lower()
        if normalized_mime.startswith("image/"):
            detected_format, confidence = DocumentFormat.IMAGE, 0.9
        elif normalized_mime == "application/pdf":
            detected_format, confidence = DocumentFormat.PDF, 0.9
        elif (
            "word" in normalized_mime
            or "excel" in normalized_mime
            or "powerpoint" in normalized_mime
        ):
            detected_format, confidence = DocumentFormat.OFFICE, 0.88
        elif normalized_mime.startswith("text/"):
            detected_format, confidence = DocumentFormat.TEXT, 0.85

    if detected_format == DocumentFormat.UNKNOWN and extension in EXTENSION_MAP:
        fallback_format, fallback_mime = EXTENSION_MAP[extension]
        detected_format = fallback_format
        detected_mime = detected_mime or fallback_mime
        confidence = max(confidence, 0.7)

    if detected_format == DocumentFormat.UNKNOWN and source_url:
        if source_url.startswith("http://") or source_url.startswith("https://"):
            detected_format = DocumentFormat.WEB
            confidence = max(confidence, 0.7)

    encoding: str | None = None
    text_subtype: str | None = None
    if detected_format in {DocumentFormat.TEXT, DocumentFormat.WEB} and sniff_sample:
        encoding = _detect_encoding(sniff_sample)
        try:
            text = sniff_sample.decode(encoding, errors="replace")
            text_subtype = _sniff_text_subtype(text)
        except Exception:
            text_subtype = "plain"

    return DetectedFormat(
        format=detected_format,
        mime_type=detected_mime,
        extension=extension,
        encoding=encoding,
        text_subtype=text_subtype,
        detector_confidence=confidence,
    )
