"""
Phase 4 — Component 4: Graph Construction & Relationship Extraction.

Implements the full document-processing sequence (Section 5.4) and both
relationship extraction methods:
  Method A — Co-occurrence (always runs).
  Method B — Gemini dependency parsing (for high-density paragraphs).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.application.graph.disambiguation import EntityDisambiguator
from app.application.graph.models import (
    RELATIONSHIP_TYPES,
    CanonicalEntity,
    EntityRelationship,
    GraphExtractionTask,
    RawEntity,
)
from app.application.graph.ner_pipeline import GeminiNERPipeline, reconstruct_text
from app.core.config import KnowledgeBaseConfig
from app.infrastructure.graph_store import KuzuGraphStore

from shared.gemini.client import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Co-occurrence counter (in-memory, per-document)
# ---------------------------------------------------------------------------

_DEPENDENCY_REL_PROMPT = """\
<task>
Extract explicit relationships between the entities listed below from the given text.
Return ONLY a JSON array. No explanation.
</task>

<entities>
{entities_list}
</entities>

<relationship_types>
ALLOWED TYPES ONLY:
works_at, founded, acquired, part_of, cited_by, competitor_of,
located_in, created_by, funded_by, partner_of, reports_to, member_of,
successor_of, predecessor_of
</relationship_types>

<output_format>
[{{"from": "Entity A", "type": "relationship_type", "to": "Entity B", "confidence": 0.0}}]
</output_format>

<text>{paragraph_text}</text>"""

_MIN_COOCCURRENCE_FOR_GEMINI = 5
_PROXIMITY_GEMINI_ENTITY_COUNT = 3


@dataclass
class _CooccurrenceCounter:
    """Tracks how many times entity pairs co-occur in the same sentence."""

    counts: dict[tuple[str, str], int] = field(default_factory=dict)

    def increment(self, a: str, b: str) -> int:
        key = (min(a, b), max(a, b))
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def get(self, a: str, b: str) -> int:
        key = (min(a, b), max(a, b))
        return self.counts.get(key, 0)


# ---------------------------------------------------------------------------
# Sentence-level entity grouping
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return _SENT_SPLIT.split(text)


def _entity_mention_in_sentence(sentence: str, name: str) -> bool:
    return name.lower() in sentence.lower()


def _proximity(sentence: str, name_a: str, name_b: str) -> float:
    """
    Compute token proximity score: 1 / (1 + distance_in_tokens_between_A_and_B).
    """
    tokens = sentence.lower().split()
    positions_a = [i for i, t in enumerate(tokens) if name_a.lower() in t]
    positions_b = [i for i, t in enumerate(tokens) if name_b.lower() in t]
    if not positions_a or not positions_b:
        return 0.1
    min_dist = min(abs(pa - pb) for pa in positions_a for pb in positions_b)
    return 1.0 / (1 + min_dist)


# ---------------------------------------------------------------------------
# Graph construction orchestrator
# ---------------------------------------------------------------------------


class GraphConstructor:
    """
    Orchestrates the full Phase 4 pipeline for a single document.

    Workflow: reconstruct → NER → disambiguate → upsert nodes → extract
    relationships → mark complete.
    """

    def __init__(
        self,
        config: KnowledgeBaseConfig,
        graph_store: KuzuGraphStore,
    ) -> None:
        self._config = config
        self._store = graph_store
        self._ner = GeminiNERPipeline(config)
        self._gemini: ResilientGeminiClient | None = None

    def _get_gemini(self) -> ResilientGeminiClient:
        if self._gemini is None:
            self._gemini = ResilientGeminiClient()
        return self._gemini

    async def process_document(
        self,
        task: GraphExtractionTask,
        disambiguator: EntityDisambiguator,
    ) -> dict[str, Any]:
        """
        Full document processing sequence (Steps 1–6 from spec Section 5.4).

        Returns a summary dict with counts.
        """
        start = time.monotonic()

        # Step 1 — Reconstruct full text
        full_text = reconstruct_text(task.chunks)
        if not full_text.strip():
            logger.warning(
                "Empty document text — skipping graph extraction",
                extra={"document_id": task.document_id},
            )
            return {"status": "skipped", "reason": "empty_text"}

        # Step 2 — NER
        raw_entities: list[RawEntity] = await self._ner.extract(full_text)
        if not raw_entities:
            logger.info(
                "No entities extracted",
                extra={"document_id": task.document_id},
            )

        # Step 3 — Disambiguation
        canonical_entities: list[CanonicalEntity] = await disambiguator.resolve_batch(
            raw_entities, task.user_id, task.document_id
        )

        # Step 4 — Kuzu upserts (nodes + base relationships)
        self._upsert_nodes(task, canonical_entities)

        # Step 5 — Relationship extraction
        relationships = self._extract_co_occurrence_rels(
            full_text, canonical_entities, task.document_id
        )

        # Step 5b — Gemini dependency for high-density paragraphs
        gemini_rels = await self._extract_dependency_rels(
            full_text, canonical_entities, task.document_id
        )
        relationships.extend(gemini_rels)

        # Insert relationships
        for rel in relationships:
            if rel.is_valid():
                self._store.upsert_related_to(rel)

        elapsed = time.monotonic() - start
        summary = {
            "status": "indexed",
            "document_id": task.document_id,
            "entities": len(canonical_entities),
            "relationships": len(relationships),
            "elapsed_seconds": round(elapsed, 2),
        }
        logger.info("Graph extraction complete", extra=summary)
        return summary

    # ------------------------------------------------------------------
    # Step 4 helpers — node upserts
    # ------------------------------------------------------------------

    def _upsert_nodes(
        self,
        task: GraphExtractionTask,
        canonical_entities: list[CanonicalEntity],
    ) -> None:
        now = int(time.time())

        # Document node
        self._store.upsert_document(
            document_id=task.document_id,
            title=task.title,
            content_type="document",
            bucket_id=task.bucket_id,
            user_id=task.user_id,
            created_at=now,
            word_count=task.word_count,
            source_url=task.source_url,
        )

        # Bucket node
        self._store.upsert_bucket(
            bucket_id=task.bucket_id,
            name=task.bucket_id,
            path=task.bucket_id,
            description="",
            user_id=task.user_id,
        )

        # BELONGS_TO
        self._store.upsert_belongs_to(
            document_id=task.document_id,
            bucket_id=task.bucket_id,
            assigned_at=now,
            assignment_method="auto",
        )

        # Entity nodes + MENTIONS relationships
        for entity in canonical_entities:
            self._store.upsert_entity(entity)
            self._store.create_mentions(
                document_id=task.document_id,
                entity_id=entity.entity_id,
                confidence=entity.confidence,
                context="",
                window_index=0,
            )

    # ------------------------------------------------------------------
    # Step 5a — Co-occurrence relationship extraction (Method A)
    # ------------------------------------------------------------------

    def _extract_co_occurrence_rels(
        self,
        full_text: str,
        entities: list[CanonicalEntity],
        document_id: str,
    ) -> list[EntityRelationship]:
        """Find entity pairs that co-occur in the same sentence."""
        if len(entities) < 2:
            return []

        sentences = _split_sentences(full_text)
        counter = _CooccurrenceCounter()
        relationships: list[EntityRelationship] = []
        now = int(time.time())

        for sentence in sentences:
            present = [
                e for e in entities if _entity_mention_in_sentence(sentence, e.name)
            ]
            if len(present) < 2:
                continue
            # All pairs in the sentence
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    ea, eb = present[i], present[j]
                    prox = _proximity(sentence, ea.name, eb.name)
                    counter.increment(ea.entity_id, eb.entity_id)
                    relationships.append(
                        EntityRelationship(
                            from_entity_id=ea.entity_id,
                            to_entity_id=eb.entity_id,
                            relationship_type="co_occurs_with",
                            strength=prox,
                            evidence_doc_id=document_id,
                            evidence_context=sentence[:500],
                            extraction_method="co_occurrence",
                            created_at=now,
                        )
                    )

        return relationships

    # ------------------------------------------------------------------
    # Step 5b — Gemini dependency parsing (Method B)
    # ------------------------------------------------------------------

    async def _extract_dependency_rels(
        self,
        full_text: str,
        entities: list[CanonicalEntity],
        document_id: str,
    ) -> list[EntityRelationship]:
        """
        For paragraphs with 3+ entities and high co-occurrence, call Gemini
        for explicit relationship extraction.
        """
        if len(entities) < _PROXIMITY_GEMINI_ENTITY_COUNT:
            return []

        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        relationships: list[EntityRelationship] = []
        now = int(time.time())
        entity_name_to_id = {e.canonical_name: e.entity_id for e in entities}

        for paragraph in paragraphs:
            present = [
                e for e in entities if _entity_mention_in_sentence(paragraph, e.name)
            ]
            if len(present) < _PROXIMITY_GEMINI_ENTITY_COUNT:
                continue

            names_list = "\n".join(f"- {e.canonical_name}" for e in present)
            prompt = _DEPENDENCY_REL_PROMPT.format(
                entities_list=names_list,
                paragraph_text=paragraph[:2000],
            )

            try:
                gemini = self._get_gemini()
                raw = await gemini.generate_content(
                    prompt=prompt,
                    model="gemini-2.0-flash",
                    temperature=0.0,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                )
                rels = self._parse_dependency_response(
                    str(raw), entity_name_to_id, document_id, now
                )
                relationships.extend(rels)
            except Exception as exc:
                logger.warning(
                    "Gemini dependency extraction failed",
                    extra={"error": str(exc)},
                )

        return relationships

    def _parse_dependency_response(
        self,
        raw: str,
        entity_name_to_id: dict[str, str],
        document_id: str,
        now: int,
    ) -> list[EntityRelationship]:
        """Parse Gemini's relationship JSON, validating against controlled vocabulary."""
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1:
            return []

        try:
            items = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return []

        results: list[EntityRelationship] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            from_name = str(item.get("from", "")).strip()
            to_name = str(item.get("to", "")).strip()
            rtype = str(item.get("type", "")).strip().lower()
            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0

            if rtype not in RELATIONSHIP_TYPES:
                logger.debug(
                    "Rejected relationship type not in vocabulary",
                    extra={"type": rtype},
                )
                continue

            from_id = entity_name_to_id.get(from_name)
            to_id = entity_name_to_id.get(to_name)
            if not from_id or not to_id:
                continue

            results.append(
                EntityRelationship(
                    from_entity_id=from_id,
                    to_entity_id=to_id,
                    relationship_type=rtype,
                    strength=max(0.0, min(1.0, confidence)),
                    evidence_doc_id=document_id,
                    extraction_method="gemini_dependency",
                    created_at=now,
                )
            )
        return results
