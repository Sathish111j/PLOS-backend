"""
Phase 4 — Component 1: Gemini NER Pipeline.

Implements the sliding-window NER strategy described in Section 2 of the
Phase 4 specification.

Key behaviors:
- Splits document text into 2 000-token windows with 200-token overlap.
- Calls Gemini (temperature=0.0) with a structured XML prompt.
- Retries once on JSON parse failure.
- Deduplicates entities across windows (keep highest confidence).
- Filters entities below the configured confidence threshold.
"""

from __future__ import annotations

import json
import re
from typing import Any, NamedTuple

from app.application.graph.models import ENTITY_TYPES, RawEntity
from app.core.config import KnowledgeBaseConfig

from shared.gemini.client import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_NER_PROMPT = """\
<task>
You are a named entity recognition system. Extract all named entities from the text below.
Return ONLY a valid JSON array. No explanation, no markdown, no preamble.
</task>

<entity_types>
PERSON, ORGANIZATION, LOCATION, CONCEPT, PRODUCT, EVENT, TECHNOLOGY, DATE_TIME, METRIC_QUANTITY
</entity_types>

<guidance>
- "Python" in a programming context → TECHNOLOGY
- "Apple" when referring to the company → ORGANIZATION
- Dates and time periods → DATE_TIME
- Abstract non-specific references → CONCEPT
- Percentages expressing performance → METRIC_QUANTITY
</guidance>

<output_format>
[
  {{
    "name": "exact text as it appears in source",
    "type": "one of the entity types above",
    "canonical_form": "standardized/full name if different from surface form",
    "confidence": 0.0,
    "context": "the sentence where this entity appears"
  }}
]
</output_format>

<text>
{window_text}
</text>"""

_REPAIR_PROMPT = """\
The previous response was not valid JSON. Fix it and return ONLY a valid JSON array of
entity objects with keys: name, type, canonical_form, confidence, context.
Previous output:
{bad_output}"""


# ---------------------------------------------------------------------------
# Tokenizer helpers (simple whitespace-based; Gemini counts ~4 chars/token)
# ---------------------------------------------------------------------------

_AVG_CHARS_PER_TOKEN = 4


class Window(NamedTuple):
    """A sliding window over the document text.

    ``start`` and ``end`` are approximate *token* offsets (chars / 4).
    ``text`` is the raw character slice.
    """

    start: int  # approximate token offset (inclusive)
    end: int    # approximate token offset (exclusive)
    text: str


def _char_budget(tokens: int) -> int:
    return tokens * _AVG_CHARS_PER_TOKEN


def _build_windows(text: str, window_tokens: int, overlap_tokens: int) -> list[Window]:
    """Split text into overlapping Window objects approximating token counts."""
    if not text:
        return [Window(start=0, end=0, text="")]

    window_chars = _char_budget(window_tokens)
    overlap_chars = _char_budget(overlap_tokens)
    step = window_chars - overlap_chars
    if step <= 0:
        step = window_chars

    windows: list[Window] = []
    char_start = 0
    while char_start < len(text):
        char_end = char_start + window_chars
        tok_start = char_start // _AVG_CHARS_PER_TOKEN
        tok_end = min(char_end, len(text)) // _AVG_CHARS_PER_TOKEN
        windows.append(Window(start=tok_start, end=tok_end, text=text[char_start:char_end]))
        if char_end >= len(text):
            break
        char_start += step
    return windows


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json_array(raw: str) -> Any:
    """Strip markdown fences and parse the first JSON array found."""
    # Remove markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    # Find array boundaries
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in response")
    return json.loads(cleaned[start : end + 1])


def _parse_entities(raw_json: Any, window_index: int) -> list[RawEntity]:
    """Convert parsed JSON items to RawEntity objects, filtering invalids."""
    entities: list[RawEntity] = []
    if not isinstance(raw_json, list):
        return entities
    for item in raw_json:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        etype = str(item.get("type", "")).strip().upper()
        canonical = str(item.get("canonical_form", name)).strip() or name
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        context = str(item.get("context", "")).strip()

        if not name or etype not in ENTITY_TYPES:
            continue

        entities.append(
            RawEntity(
                name=name,
                entity_type=etype,
                canonical_form=canonical,
                confidence=confidence,
                context=context,
                window_index=window_index,
            )
        )
    return entities


# ---------------------------------------------------------------------------
# Main NER pipeline class
# ---------------------------------------------------------------------------


class GeminiNERPipeline:
    """
    Sliding-window NER pipeline backed by Gemini.

    Usage:
        pipeline = GeminiNERPipeline(config)
        entities = await pipeline.extract(full_text)
    """

    def __init__(self, config: KnowledgeBaseConfig) -> None:
        self._config = config
        self._window_tokens = config.graph_ner_window_tokens
        self._overlap_tokens = config.graph_ner_overlap_tokens
        self._min_confidence = config.graph_ner_confidence_threshold
        self._client: ResilientGeminiClient | None = None

    def _get_client(self) -> ResilientGeminiClient:
        if self._client is None:
            self._client = ResilientGeminiClient()
        return self._client

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini and return the raw text response."""
        client = self._get_client()
        response = await client.generate_content(
            prompt=prompt,
            model="gemini-2.0-flash",
            temperature=0.0,
            max_output_tokens=4096,
            response_mime_type="application/json",
        )
        if isinstance(response, dict):
            return response.get("text", "") or str(response)
        return str(response)

    async def _extract_window(self, window_text: str, window_index: int) -> list[RawEntity]:
        """Run NER on a single window; retry once on JSON parse failure."""
        prompt = _NER_PROMPT.format(window_text=window_text)

        try:
            raw = await self._call_gemini(prompt)
            parsed = _extract_json_array(raw)
            return _parse_entities(parsed, window_index)
        except Exception as first_error:
            logger.warning(
                "NER JSON parse failed on first attempt, retrying",
                extra={"window_index": window_index, "error": str(first_error)},
            )
            try:
                repair_prompt = _REPAIR_PROMPT.format(bad_output=raw if "raw" in dir() else "")
                raw2 = await self._call_gemini(repair_prompt)
                parsed2 = _extract_json_array(raw2)
                return _parse_entities(parsed2, window_index)
            except Exception as second_error:
                logger.warning(
                    "NER JSON parse failed on retry — skipping window",
                    extra={"window_index": window_index, "error": str(second_error)},
                )
                return []

    @staticmethod
    def _deduplicate(entities: list[RawEntity]) -> list[RawEntity]:
        """Keep the highest-confidence entity for each (name, type) pair."""
        best: dict[tuple[str, str], RawEntity] = {}
        for entity in entities:
            key = (entity.name.lower(), entity.entity_type)
            existing = best.get(key)
            if existing is None or entity.confidence > existing.confidence:
                best[key] = entity
        return list(best.values())

    async def extract(self, full_text: str) -> list[RawEntity]:
        """
        Extract named entities from a full document text.

        Returns a deduplicated list of RawEntity objects whose confidence
        meets the configured threshold.
        """
        if not full_text or not full_text.strip():
            return []

        windows = _build_windows(full_text, self._window_tokens, self._overlap_tokens)
        all_entities: list[RawEntity] = []

        for idx, window in enumerate(windows):
            window_entities = await self._extract_window(window.text, idx)
            all_entities.extend(window_entities)

        deduped = self._deduplicate(all_entities)
        filtered = [e for e in deduped if e.confidence >= self._min_confidence]

        logger.info(
            "NER extraction complete",
            extra={
                "windows": len(windows),
                "raw_entities": len(all_entities),
                "after_dedup": len(deduped),
                "after_filter": len(filtered),
            },
        )
        return filtered


# ---------------------------------------------------------------------------
# Text reconstruction from ordered chunks
# ---------------------------------------------------------------------------


def reconstruct_text(chunks: list[dict]) -> str:
    """
    Reconstruct full document text from ordered chunk dicts.

    Chunks must have 'chunk_index' and 'text' keys.
    """
    ordered = sorted(chunks, key=lambda c: int(c.get("chunk_index", 0)))
    return "\n".join(str(c.get("text", "")) for c in ordered if c.get("text"))
