import re
import unicodedata

from app.application.ingestion.models import StructuredSection


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def infer_sections_from_text(text: str) -> list[StructuredSection]:
    sections: list[StructuredSection] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            level = min(len(stripped) - len(stripped.lstrip("#")), 6)
            content = stripped[level:].strip()
            sections.append(
                StructuredSection(section_type="heading", level=level, content=content)
            )
        elif re.match(r"^[-*]\s+", stripped):
            sections.append(StructuredSection(section_type="list_item", content=stripped))
        else:
            sections.append(StructuredSection(section_type="paragraph", content=stripped))
    return sections
