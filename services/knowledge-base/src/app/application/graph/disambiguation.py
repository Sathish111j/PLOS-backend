"""
Phase 4 — Component 2: Entity Disambiguation & Canonicalization.

Three-signal pipeline (Section 3 of spec):
  Signal 1 — Embedding vector cosine similarity against existing entities.
  Signal 2 — Gemini context co-reference check.
  Signal 3 — Wikidata API lookup with Redis cache.

Canonicalization rules (Section 3.3) are applied before storage.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
import uuid
from typing import Any

import httpx

from app.application.graph.models import CanonicalEntity, RawEntity
from app.core.config import KnowledgeBaseConfig

from shared.gemini.client import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)

_WIKIDATA_ENDPOINT = "https://www.wikidata.org/w/api.php"
_WIKIDATA_RATE_LIMIT_CALLS = 5  # max calls per second
_COREF_PROMPT = """\
Given this sentence: '{context}'
The entity '{name}' of type '{etype}' appears.
Is this the same as '{candidate}'?
Answer with exactly one word: YES, NO, or UNCERTAIN."""


# ---------------------------------------------------------------------------
# Canonicalization helpers
# ---------------------------------------------------------------------------

_ABBREV_MAP: dict[str, str] = {
    r"\bML\b": "Machine Learning",
    r"\bNLP\b": "Natural Language Processing",
    r"\bCV\b": "Computer Vision",
    r"\bAI\b": "Artificial Intelligence",
    r"\bDL\b": "Deep Learning",
    r"\bAPI\b": "Application Programming Interface",
    r"\bUI\b": "User Interface",
    r"\bUX\b": "User Experience",
}

_LEGAL_SUFFIXES = re.compile(
    r"\s+(?:LLC|Inc\.?|Corp\.?|Ltd\.?|PLC|GmbH|S\.A\.)$", re.IGNORECASE
)
_LEADING_THE = re.compile(r"^the\s+", re.IGNORECASE)
_LASTNAME_FIRSTNAME = re.compile(r"^([A-Za-z\-']+),\s+([A-Za-z\-']+)$")


def canonicalize_name(name: str, entity_type: str) -> str:
    """Apply canonicalization rules from Section 3.3."""
    # Unicode NFC normalisation
    name = unicodedata.normalize("NFC", name.strip())

    # Expand abbreviations (only for non-PERSON types)
    if entity_type != "PERSON":
        for pattern, replacement in _ABBREV_MAP.items():
            name = re.sub(pattern, replacement, name)

    # Person: last, first → first last
    if entity_type == "PERSON":
        m = _LASTNAME_FIRSTNAME.match(name)
        if m:
            name = f"{m.group(2)} {m.group(1)}"

    # Remove leading "the" for organizations
    if entity_type == "ORGANIZATION":
        name = _LEADING_THE.sub("", name)
        # Keep short names without legal suffix appended
        # "OpenAI LLC" when entity is commonly "OpenAI" → keep "OpenAI"
        # We don't strip suffixes here; that would change the canonical name.

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Wikidata helpers
# ---------------------------------------------------------------------------

async def _wikidata_search(
    name: str,
    entity_type: str,
    redis_client: Any,
    cache_ttl: int,
) -> dict | None:
    """
    Search Wikidata for a canonical entity name.
    Results are cached in Redis for `cache_ttl` seconds.
    Returns a dict with keys: canonical_name, description, wikipedia_url, wikidata_id
    or None on miss / error.
    """
    cache_key = f"wikidata:{name.lower()}:{entity_type}"
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            params = {
                "action": "wbsearchentities",
                "search": name,
                "language": "en",
                "format": "json",
                "limit": 5,
            }
            resp = await client.get(_WIKIDATA_ENDPOINT, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as exc:
        logger.warning("Wikidata lookup failed", extra={"entity_name": name, "error": str(exc)})
        return None

    results = data.get("search", [])
    if not results:
        return None

    top = results[0]
    result = {
        "canonical_name": top.get("label", name),
        "description": top.get("description", ""),
        "wikipedia_url": top.get("url", ""),
        "wikidata_id": top.get("id", ""),
    }

    if redis_client is not None:
        try:
            await redis_client.setex(cache_key, cache_ttl, json.dumps(result))
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Disambiguation service
# ---------------------------------------------------------------------------


class EntityDisambiguator:
    """
    Resolves RawEntity objects to CanonicalEntity objects.

    Maintains an in-memory embedding cache of existing entities which is
    rebuilt from the Kuzu store at startup and updated on each new entity
    insertion.
    """

    def __init__(
        self,
        config: KnowledgeBaseConfig,
        redis_client: Any = None,
    ) -> None:
        self._config = config
        self._redis = redis_client
        self._high_threshold = config.graph_disambig_vector_high
        self._low_threshold = config.graph_disambig_vector_low
        self._wikidata_ttl = config.graph_wikidata_cache_ttl_seconds
        self._gemini: ResilientGeminiClient | None = None
        # entity_id → (embedding, canonical_entity)
        self._entity_cache: dict[str, tuple[list[float], CanonicalEntity]] = {}

    def _get_gemini(self) -> ResilientGeminiClient:
        if self._gemini is None:
            self._gemini = ResilientGeminiClient()
        return self._gemini

    def load_entity_cache(self, entities: list[CanonicalEntity]) -> None:
        """Populate the embedding cache from a list of existing entities."""
        for entity in entities:
            if entity.embedding:
                self._entity_cache[entity.entity_id] = (entity.embedding, entity)

    def _find_best_candidate(
        self, embedding: list[float], entity_type: str
    ) -> tuple[float, CanonicalEntity | None]:
        """Return (max_similarity, best_matching_entity) among same-type entities."""
        best_sim = 0.0
        best_entity: CanonicalEntity | None = None
        for eid, (cached_emb, cached_entity) in self._entity_cache.items():
            if cached_entity.entity_type != entity_type:
                continue
            sim = _cosine(embedding, cached_emb)
            if sim > best_sim:
                best_sim = sim
                best_entity = cached_entity
        return best_sim, best_entity

    async def _embed_text(self, text: str) -> list[float]:
        """Embed a short text using Gemini text-embedding-004."""
        gemini = self._get_gemini()
        try:
            result = await gemini.embed_text(text, model="text-embedding-004")
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.warning(
                "Embedding failed during disambiguation",
                extra={"text": text[:80], "error": str(exc)},
            )
        return []

    async def _signal_2_coref(
        self,
        entity: RawEntity,
        candidate: CanonicalEntity,
    ) -> str:
        """
        Ask Gemini if entity and candidate refer to the same thing.
        Returns 'YES', 'NO', or 'UNCERTAIN'.
        """
        prompt = _COREF_PROMPT.format(
            context=entity.context[:500],
            name=entity.name,
            etype=entity.entity_type,
            candidate=candidate.canonical_name,
        )
        try:
            gemini = self._get_gemini()
            raw = await gemini.generate_content(
                prompt=prompt,
                model="gemini-2.0-flash",
                temperature=0.0,
                max_output_tokens=10,
            )
            answer = str(raw).strip().upper()
            if "YES" in answer:
                return "YES"
            if "NO" in answer:
                return "NO"
        except Exception as exc:
            logger.warning(
                "Signal 2 co-ref check failed",
                extra={"error": str(exc)},
            )
        return "UNCERTAIN"

    async def resolve(
        self,
        raw: RawEntity,
        user_id: str,
        document_id: str,
    ) -> CanonicalEntity:
        """
        Resolve a RawEntity to a CanonicalEntity via the three-signal pipeline.
        """
        canonical_name = canonicalize_name(raw.canonical_form or raw.name, raw.entity_type)
        embedding = await self._embed_text(canonical_name)

        # Signal 1 — vector similarity
        sim, candidate = self._find_best_candidate(embedding, raw.entity_type)

        if sim >= self._high_threshold and candidate is not None:
            # Very high confidence — merge without further checks
            entity = self._merge(candidate, raw, canonical_name, embedding, sim)
            logger.debug(
                "Signal 1 merge (high)",
                extra={"name": raw.name, "canonical": canonical_name, "sim": sim},
            )
            return entity

        # Signal 2 — co-reference context
        if sim >= self._low_threshold and candidate is not None:
            answer = await self._signal_2_coref(raw, candidate)
            if answer == "YES":
                entity = self._merge(candidate, raw, canonical_name, embedding, (sim + 1.0) / 2)
                logger.debug(
                    "Signal 2 merge (co-ref YES)",
                    extra={"name": raw.name, "candidate": candidate.canonical_name},
                )
                return entity
            if answer == "NO":
                # Definitely different — create new
                pass
            # UNCERTAIN → fall through to Signal 3

        # Signal 3 — Wikidata
        wiki = await _wikidata_search(
            canonical_name,
            raw.entity_type,
            self._redis,
            self._wikidata_ttl,
        )

        entity_id = str(uuid.uuid4())
        if wiki:
            canonical_name = wiki.get("canonical_name", canonical_name)
            description = wiki.get("description", "")
            wikipedia_url = wiki.get("wikipedia_url", "")
            wikidata_id = wiki.get("wikidata_id", "")
            aliases = [raw.name, raw.canonical_form, wikidata_id]
            aliases = [a for a in aliases if a and a != canonical_name]
            confidence = min(raw.confidence + 0.05, 1.0)
        else:
            description = ""
            wikipedia_url = ""
            aliases = [raw.name] if raw.name != canonical_name else []
            confidence = raw.confidence

        new_entity = CanonicalEntity(
            entity_id=entity_id,
            name=raw.name,
            canonical_name=canonical_name,
            entity_type=raw.entity_type,
            description=description,
            wikipedia_url=wikipedia_url,
            mention_count=1,
            aliases=list(set(aliases)),
            confidence=confidence,
            embedding=embedding,
            first_seen_document_id=document_id,
            user_id=user_id,
            is_new=True,
        )
        if embedding:
            self._entity_cache[entity_id] = (embedding, new_entity)
        return new_entity

    def _merge(
        self,
        existing: CanonicalEntity,
        raw: RawEntity,
        canonical_name: str,
        embedding: list[float],
        merged_confidence: float,
    ) -> CanonicalEntity:
        """Add a new surface form to an existing entity's aliases."""
        new_alias = raw.name
        if new_alias not in existing.aliases and new_alias != existing.canonical_name:
            existing.aliases.append(new_alias)
        existing.confidence = merged_confidence
        if embedding and not existing.embedding:
            existing.embedding = embedding
        existing.mention_count += 1
        existing.is_new = False
        return existing

    async def resolve_batch(
        self,
        raw_entities: list[RawEntity],
        user_id: str,
        document_id: str,
    ) -> list[CanonicalEntity]:
        """Resolve a list of raw entities to canonical entities."""
        results: list[CanonicalEntity] = []
        for raw in raw_entities:
            entity = await self.resolve(raw, user_id, document_id)
            results.append(entity)
        return results
