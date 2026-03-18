import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ExtractedEntity:
    text: str
    canonical_name: str
    entity_type: str
    confidence: float
    aliases: list[str]
    metadata: dict[str, Any]


def _canonicalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def _regex_entities(text: str) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []

    api_pattern = re.compile(r"\b[A-Z][a-zA-Z0-9]+(?:API|SDK|Service|Engine)\b")
    version_pattern = re.compile(r"\bv\d+(?:\.\d+){0,2}\b", flags=re.IGNORECASE)
    acronym_pattern = re.compile(r"\b[A-Z]{2,10}\b")

    for match in api_pattern.finditer(text):
        name = _canonicalize(match.group(0))
        entities.append(
            ExtractedEntity(
                text=name,
                canonical_name=name,
                entity_type="TECHNICAL_TERM",
                confidence=0.88,
                aliases=[name],
                metadata={"source": "regex_api"},
            )
        )

    for match in version_pattern.finditer(text):
        value = match.group(0)
        entities.append(
            ExtractedEntity(
                text=value,
                canonical_name=value.lower(),
                entity_type="VERSION",
                confidence=0.9,
                aliases=[value],
                metadata={"source": "regex_version"},
            )
        )

    for match in acronym_pattern.finditer(text):
        acronym = match.group(0)
        if len(acronym) <= 2:
            continue
        entities.append(
            ExtractedEntity(
                text=acronym,
                canonical_name=acronym,
                entity_type="ACRONYM",
                confidence=0.75,
                aliases=[acronym],
                metadata={"source": "regex_acronym"},
            )
        )

    return entities


def _titlecase_entities(text: str) -> list[ExtractedEntity]:
    """Lightweight proper-noun extraction when spaCy is unavailable.

    This intentionally favors recall over perfect precision so the graph
    search API has useful results even on simple prose documents.
    """

    common_starts = {
        "A",
        "An",
        "And",
        "But",
        "For",
        "From",
        "In",
        "Into",
        "Of",
        "On",
        "Or",
        "The",
        "To",
        "With",
        "This",
        "That",
        "These",
        "Those",
        "Morning",
        "Evening",
        "Night",
        "Good",
    }

    titlecase_pattern = re.compile(r"\b(?:[A-Z][a-z]{2,})(?:\s+[A-Z][a-z]{2,})*\b")
    entities: list[ExtractedEntity] = []

    for match in titlecase_pattern.finditer(text):
        name = _canonicalize(match.group(0))
        if not name:
            continue
        parts = name.split()
        if not parts:
            continue
        if len(parts) == 1 and parts[0] in common_starts:
            continue
        if all(part in common_starts for part in parts):
            continue
        entities.append(
            ExtractedEntity(
                text=name,
                canonical_name=name,
                entity_type="PROPER_NOUN",
                confidence=0.55,
                aliases=[name],
                metadata={"source": "heuristic_titlecase"},
            )
        )

    return entities


def _spacy_entities(text: str) -> list[ExtractedEntity]:
    try:
        import spacy
    except Exception:
        return []

    try:
        model = spacy.load("en_core_web_lg")
    except Exception:
        try:
            model = spacy.load("en_core_web_sm")
        except Exception:
            return []

    doc = model(text)
    entities: list[ExtractedEntity] = []
    for ent in doc.ents:
        name = _canonicalize(ent.text)
        if not name:
            continue
        entities.append(
            ExtractedEntity(
                text=name,
                canonical_name=name,
                entity_type=ent.label_,
                confidence=0.86,
                aliases=[name],
                metadata={"source": "spacy"},
            )
        )
    return entities


def extract_entities(text: str) -> list[ExtractedEntity]:
    if not text:
        return []

    merged: dict[tuple[str, str], ExtractedEntity] = {}
    for entity in _spacy_entities(text) + _regex_entities(text) + _titlecase_entities(text):
        key = (entity.canonical_name.lower(), entity.entity_type)
        existing = merged.get(key)
        if not existing or entity.confidence > existing.confidence:
            merged[key] = entity

    return list(merged.values())
