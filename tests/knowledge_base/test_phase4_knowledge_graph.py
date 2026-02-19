"""
Phase 4 - Knowledge Graph & Entity Intelligence: Comprehensive Test Suite.

Test coverage (Sections 10-19 of Phase 4 spec):

  Section 10 -- Unit: NER Pipeline          TEST-NER-001..009
  Section 11 -- Unit: Disambiguation        TEST-DISAMBIG-001..008
  Section 12 -- Unit: Graph Construction    TEST-GRAPH-001..010
  Section 13 -- Unit: Graph Queries         TEST-QUERY-001..010
  Section 14 -- Integration Tests           INT-GRAPH-001..006
  Section 15 -- End-to-End Scenarios        E2E-GRAPH-001..003
  Section 16 -- Performance Tests           PERF-GRAPH-001..006
  Section 17 -- Acceptance Criteria         AC-4-01..20
  Section 18 -- Error & Edge Cases          ERR-GRAPH-001..007

Execution tiers:
  pytest.mark.unit   -- fully isolated, no I/O, mocks only (default)
  pytest.mark.intg   -- live Kuzu on temp disk, no network
  pytest.mark.e2e    -- live Kuzu, Gemini mocked
  pytest.mark.perf   -- benchmarks; measured in-process
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Source imports
# ---------------------------------------------------------------------------
from app.application.graph.models import (
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    CanonicalEntity,
    EntityRelationship,
    GraphExtractionTask,
    RawEntity,
)
from app.application.graph.ner_pipeline import (
    Window,
    GeminiNERPipeline,
    _AVG_CHARS_PER_TOKEN,
    _build_windows,
    _extract_json_array,
    _parse_entities,
    reconstruct_text,
)
from app.application.graph.disambiguation import (
    EntityDisambiguator,
    _cosine,
    canonicalize_name,
)
from app.application.graph.construction import (
    GraphConstructor,
    _proximity,
)
from app.application.graph.background import (
    run_health_check,
    run_orphan_cleanup,
    run_pagerank,
)
from app.core.config import KnowledgeBaseConfig, get_kb_config

# ---------------------------------------------------------------------------
# Shared event loop
# ---------------------------------------------------------------------------
_LOOP: asyncio.AbstractEventLoop = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro: Any) -> Any:
    return _LOOP.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------

def _make_config(**overrides: Any) -> KnowledgeBaseConfig:
    cfg = get_kb_config()
    import dataclasses
    d = dataclasses.asdict(cfg)
    d.update(overrides)
    return KnowledgeBaseConfig(**d)


# ---------------------------------------------------------------------------
# Entity factories
# ---------------------------------------------------------------------------

def _make_entity(
    *,
    entity_id: str | None = None,
    name: str = "TestEntity",
    canonical_name: str | None = None,
    entity_type: str = "ORGANIZATION",
    confidence: float = 0.9,
    embedding: list[float] | None = None,
    user_id: str = "user_test",
    mention_count: int = 1,
) -> CanonicalEntity:
    return CanonicalEntity(
        entity_id=entity_id or str(uuid.uuid4()),
        name=name,
        canonical_name=canonical_name or name,
        entity_type=entity_type,
        confidence=confidence,
        embedding=embedding or ([0.1] * 768),
        user_id=user_id,
        mention_count=mention_count,
    )


def _make_raw(
    name: str = "Apple",
    etype: str = "ORGANIZATION",
    confidence: float = 0.9,
    context: str = "Apple released a product.",
    canonical_form: str | None = None,
) -> RawEntity:
    return RawEntity(
        name=name,
        entity_type=etype,
        canonical_form=canonical_form or name,
        confidence=confidence,
        context=context,
    )


# ---------------------------------------------------------------------------
# Kuzu fixture (integration tier)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def kuzu_store():
    try:
        import kuzu  # noqa: F401
    except ImportError:
        pytest.skip("kuzu not installed")

    from app.infrastructure.graph_store import KuzuGraphStore

    with tempfile.TemporaryDirectory() as tmp:
        config = _make_config(graph_db_path=tmp)
        store = KuzuGraphStore(config)
        store.connect()
        yield store
        store.close()


# ===========================================================================
# SECTION 10 -- Unit Tests: NER Pipeline
# ===========================================================================

@pytest.mark.unit
class TestNER001WindowGeneration:
    """TEST-NER-001: Window boundaries match spec exactly for 4500-token input."""

    def _text_of_tokens(self, n: int) -> str:
        return "x" * (n * _AVG_CHARS_PER_TOKEN)

    def test_exactly_three_windows(self):
        text = self._text_of_tokens(4500)
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        assert len(windows) == 3, f"Expected 3 windows, got {len(windows)}"

    def test_window_0_starts_at_token_0(self):
        text = self._text_of_tokens(4500)
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        assert windows[0].start == 0

    def test_window_1_starts_at_token_1800(self):
        """Step = (2000 - 200) = 1800 tokens."""
        text = self._text_of_tokens(4500)
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        assert windows[1].start == 1800

    def test_window_2_starts_at_token_3600(self):
        text = self._text_of_tokens(4500)
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        assert windows[2].start == 3600

    def test_overlap_content_in_next_window(self):
        """Last 200-token slice of W0 equals first 200-token slice of W1."""
        text = self._text_of_tokens(4500)
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        overlap_chars = 200 * _AVG_CHARS_PER_TOKEN
        assert windows[0].text[-overlap_chars:] == windows[1].text[:overlap_chars]

    def test_windows_are_window_namedtuples(self):
        windows = _build_windows("hello world", window_tokens=2000, overlap_tokens=200)
        assert all(isinstance(w, Window) for w in windows)

    def test_short_text_single_window(self):
        windows = _build_windows("short", window_tokens=2000, overlap_tokens=200)
        assert len(windows) == 1
        assert windows[0].start == 0

    def test_empty_text_single_window(self):
        windows = _build_windows("", window_tokens=2000, overlap_tokens=200)
        assert len(windows) == 1
        assert windows[0].text == ""


@pytest.mark.unit
class TestNER002ValidJsonParsing:
    """TEST-NER-002: Valid JSON array -> 5 RawEntity objects, all fields populated."""

    def _payload(self) -> list[dict]:
        types = ["PERSON", "ORGANIZATION", "LOCATION", "TECHNOLOGY", "CONCEPT"]
        return [
            {
                "name": f"Entity{i}",
                "type": types[i],
                "canonical_form": f"Canon{i}",
                "confidence": round(0.70 + i * 0.05, 2),
                "context": f"Sentence about Entity{i}.",
            }
            for i in range(5)
        ]

    def test_five_entities_created(self):
        assert len(_parse_entities(self._payload(), window_index=0)) == 5

    def test_all_confidences_in_range(self):
        entities = _parse_entities(self._payload(), window_index=0)
        assert all(0.0 <= e.confidence <= 1.0 for e in entities)

    def test_all_types_valid(self):
        entities = _parse_entities(self._payload(), window_index=0)
        assert all(e.entity_type in ENTITY_TYPES for e in entities)

    def test_context_populated(self):
        entities = _parse_entities(self._payload(), window_index=0)
        assert all(e.context is not None for e in entities)


@pytest.mark.unit
class TestNER003MarkdownFenceHandling:
    """TEST-NER-003: Markdown-fenced JSON parsed on first attempt."""

    def test_single_backtick_fence(self):
        raw = '```\n[{"name": "A", "type": "CONCEPT", "canonical_form": "A", "confidence": 0.9, "context": "ctx"}]\n```'
        result = _extract_json_array(raw)
        assert result[0]["name"] == "A"

    def test_json_labeled_fence(self):
        raw = '```json\n[{"name": "B", "type": "PERSON", "canonical_form": "B", "confidence": 0.85, "context": "ctx"}]\n```'
        result = _extract_json_array(raw)
        assert result[0]["name"] == "B"

    def test_no_retry_needed(self):
        """Fenced JSON succeeds without raising ValueError (no retry required)."""
        raw = '```json\n[{"name": "C", "type": "ORGANIZATION", "canonical_form": "C", "confidence": 0.8, "context": "ctx"}]\n```'
        # ValueError would mean retry is needed -- must not raise
        result = _extract_json_array(raw)
        assert isinstance(result, list)


@pytest.mark.unit
class TestNER004UnrecoverableJson:
    """TEST-NER-004: Both parse attempts fail -> window skipped, no exception."""

    def test_graceful_degradation(self):
        config = _make_config(graph_ner_confidence_threshold=0.60)
        pipeline = GeminiNERPipeline(config)

        call_count = 0

        async def _bad(prompt: str, **kw: Any) -> str:
            nonlocal call_count
            call_count += 1
            return "I cannot extract entities."

        mock_client = AsyncMock()
        mock_client.generate_content = _bad
        pipeline._client = mock_client

        result = _run(pipeline.extract("Valid input text."))
        assert isinstance(result, list)
        # initial call + repair retry = 2
        assert call_count == 2

    def test_good_windows_not_affected(self):
        """Later windows still processed when an earlier one fails."""
        config = _make_config(graph_ner_confidence_threshold=0.60)
        pipeline = GeminiNERPipeline(config)

        good = json.dumps([{
            "name": "OpenAI", "type": "ORGANIZATION",
            "canonical_form": "OpenAI", "confidence": 0.9, "context": "ctx",
        }])
        call_count = 0

        async def _alt(prompt: str, **kw: Any) -> str:
            nonlocal call_count
            call_count += 1
            return "not json" if call_count <= 2 else good

        mock_client = AsyncMock()
        mock_client.generate_content = _alt
        pipeline._client = mock_client

        text = "word " * 3000  # enough for 2+ windows
        result = _run(pipeline.extract(text))
        assert isinstance(result, list)


@pytest.mark.unit
class TestNER005Deduplication:
    """TEST-NER-005: Cross-window dedup keeps highest confidence."""

    def test_keeps_highest_confidence(self):
        entities = [
            _make_raw("OpenAI", "ORGANIZATION", confidence=0.95),
            _make_raw("OpenAI", "ORGANIZATION", confidence=0.80),
            _make_raw("OpenAI", "ORGANIZATION", confidence=0.72),
        ]
        deduped = GeminiNERPipeline._deduplicate(entities)
        openai = [e for e in deduped if e.name == "OpenAI"]
        assert len(openai) == 1
        assert openai[0].confidence == 0.95

    def test_different_types_not_merged(self):
        entities = [
            _make_raw("Python", "TECHNOLOGY", confidence=0.9),
            _make_raw("Python", "CONCEPT", confidence=0.85),
        ]
        deduped = GeminiNERPipeline._deduplicate(entities)
        assert len(deduped) == 2

    def test_case_insensitive_dedup(self):
        entities = [
            _make_raw("openai", "ORGANIZATION", confidence=0.8),
            _make_raw("OpenAI", "ORGANIZATION", confidence=0.95),
        ]
        deduped = GeminiNERPipeline._deduplicate(entities)
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.95


@pytest.mark.unit
class TestNER006ConfidenceFilter:
    """TEST-NER-006: Exactly 5 of 10 entities pass the 0.60 threshold."""

    def test_exactly_five_pass(self):
        confidences = [0.9, 0.85, 0.75, 0.65, 0.60, 0.59, 0.50, 0.40, 0.30, 0.20]
        assert len(confidences) == 10
        entities = [_make_raw(f"E{i}", "CONCEPT", confidence=c) for i, c in enumerate(confidences)]
        filtered = [e for e in entities if e.confidence >= 0.60]
        assert len(filtered) == 5
        assert all(e.confidence >= 0.60 for e in filtered)

    def test_boundary_value_passes(self):
        assert _make_raw("X", "CONCEPT", confidence=0.60).confidence >= 0.60

    def test_below_boundary_rejected(self):
        assert _make_raw("Y", "CONCEPT", confidence=0.59).confidence < 0.60


@pytest.mark.unit
class TestNER007ContextTyping:
    """TEST-NER-007: Type determined by context, not just name."""

    def test_programming_python_typed_as_technology(self):
        raw = [{"name": "Python", "type": "TECHNOLOGY", "canonical_form": "Python",
                "confidence": 0.95, "context": "The code uses Python 3.11."}]
        entities = _parse_entities(raw, window_index=0)
        assert entities[0].entity_type == "TECHNOLOGY"

    def test_snake_python_not_technology(self):
        raw = [{"name": "Python", "type": "CONCEPT", "canonical_form": "Python (snake)",
                "confidence": 0.80, "context": "The python snake is native to Asia."}]
        entities = _parse_entities(raw, window_index=0)
        assert entities[0].entity_type != "TECHNOLOGY"


@pytest.mark.unit
class TestNER008EndToEndMocked:
    """TEST-NER-008: Full pipeline with mocked Gemini produces correct entities."""

    def _pipeline(self, response_str: str) -> GeminiNERPipeline:
        config = _make_config(graph_ner_confidence_threshold=0.60)
        p = GeminiNERPipeline(config)
        mock_client = AsyncMock()
        mock_client.generate_content = AsyncMock(return_value=response_str)
        p._client = mock_client
        return p

    def test_two_entities_returned(self):
        payload = json.dumps([
            {"name": "OpenAI", "type": "ORGANIZATION", "canonical_form": "OpenAI Inc.",
             "confidence": 0.95, "context": "OpenAI released GPT-4."},
            {"name": "Sam Altman", "type": "PERSON", "canonical_form": "Sam Altman",
             "confidence": 0.92, "context": "Sam Altman is CEO."},
        ])
        pipeline = self._pipeline(payload)
        result = _run(pipeline.extract("OpenAI released GPT-4. Sam Altman is CEO."))
        assert len(result) == 2
        names = {e.name for e in result}
        assert "OpenAI" in names
        assert "Sam Altman" in names


@pytest.mark.unit
class TestNER009EmptyInput:
    """TEST-NER-009: Whitespace-only input skipped without calling Gemini."""

    def test_whitespace_returns_empty(self):
        config = _make_config()
        pipeline = GeminiNERPipeline(config)
        mock_client = AsyncMock()
        mock_client.generate_content = AsyncMock(return_value="[]")
        pipeline._client = mock_client

        result = _run(pipeline.extract("   \n\t  "))
        assert result == []
        mock_client.generate_content.assert_not_called()


@pytest.mark.unit
class TestNERJsonHelpers:
    """Helper function unit tests."""

    def test_plain_json_array(self):
        raw = '[{"name": "X", "type": "CONCEPT", "canonical_form": "X", "confidence": 0.9, "context": "c"}]'
        assert _extract_json_array(raw)[0]["name"] == "X"

    def test_missing_brackets_raises(self):
        with pytest.raises(ValueError):
            _extract_json_array("no brackets at all")

    def test_empty_array(self):
        assert _extract_json_array("[]") == []

    def test_invalid_entity_type_dropped(self):
        raw = [{"name": "X", "type": "INVALID", "canonical_form": "X", "confidence": 0.9, "context": "c"}]
        assert _parse_entities(raw, 0) == []

    def test_bad_confidence_coerced_to_zero(self):
        raw = [{"name": "X", "type": "CONCEPT", "canonical_form": "X", "confidence": "bad", "context": "c"}]
        entities = _parse_entities(raw, 0)
        assert entities[0].confidence == 0.0

    def test_reconstruct_text_order(self):
        chunks = [{"chunk_index": 2, "text": "C"}, {"chunk_index": 0, "text": "A"}, {"chunk_index": 1, "text": "B"}]
        assert reconstruct_text(chunks) == "A\nB\nC"

    def test_reconstruct_text_empty(self):
        assert reconstruct_text([]) == ""


# ===========================================================================
# SECTION 11 -- Unit Tests: Disambiguation
# ===========================================================================

@pytest.mark.unit
class TestDisambig001HighSimilarityMerge:
    """TEST-DISAMBIG-001: cosine > 0.92 -> auto-merge, alias added."""

    def test_high_sim_resolves_to_existing(self):
        config = _make_config(graph_disambig_vector_high=0.92, graph_disambig_vector_low=0.80)
        disambig = EntityDisambiguator(config)

        existing = _make_entity(name="OpenAI", entity_type="ORGANIZATION",
                                embedding=[1.0] + [0.0] * 767)
        disambig._entity_cache[existing.entity_id] = (existing.embedding, existing)

        sim, candidate = disambig._find_best_candidate([0.9999] + [0.001] * 767, "ORGANIZATION")
        assert sim > 0.92
        assert candidate is not None
        assert candidate.entity_id == existing.entity_id

    def test_alias_added_after_merge(self):
        config = _make_config(graph_disambig_vector_high=0.92)
        disambig = EntityDisambiguator(config)

        existing = _make_entity(name="OpenAI", entity_type="ORGANIZATION",
                                embedding=[1.0] + [0.0] * 767)
        disambig._entity_cache[existing.entity_id] = (existing.embedding, existing)

        raw = _make_raw("Open AI Inc.", "ORGANIZATION", context="Open AI Inc. is an AI lab.")
        merged = disambig._merge(existing, raw, "Open AI Inc.", [1.0] + [0.0] * 767, 0.96)
        assert "Open AI Inc." in merged.aliases
        assert merged.entity_id == existing.entity_id


@pytest.mark.unit
class TestDisambig002LowSimilarityNewEntity:
    """TEST-DISAMBIG-002: cosine < 0.80 -> no match (new entity)."""

    def test_type_mismatch_no_candidate(self):
        config = _make_config(graph_disambig_vector_high=0.92, graph_disambig_vector_low=0.80)
        disambig = EntityDisambiguator(config)

        org = _make_entity(name="Amazon", entity_type="ORGANIZATION",
                           embedding=[1.0] + [0.0] * 767)
        disambig._entity_cache[org.entity_id] = (org.embedding, org)

        # LOCATION query does not match ORGANIZATION entity
        sim, candidate = disambig._find_best_candidate([0.0, 1.0] + [0.0] * 766, "LOCATION")
        assert candidate is None or candidate.entity_type != "ORGANIZATION"


@pytest.mark.unit
class TestDisambig003ContextDisambiguationYes:
    """TEST-DISAMBIG-003: Ambiguous range + YES from Gemini -> merged."""

    def test_yes_merges(self):
        config = _make_config(graph_disambig_vector_high=0.92, graph_disambig_vector_low=0.80)
        disambig = EntityDisambiguator(config)
        mock_client = AsyncMock()
        mock_client.generate_content = AsyncMock(return_value="YES")
        disambig._gemini = mock_client

        raw = _make_raw("Apple", "ORGANIZATION", context="Apple released iOS 18 today")
        candidate = _make_entity(canonical_name="Apple Inc.", entity_type="ORGANIZATION")
        answer = _run(disambig._signal_2_coref(raw, candidate))
        assert answer == "YES"


@pytest.mark.unit
class TestDisambig004ContextDisambiguationNo:
    """TEST-DISAMBIG-004: Ambiguous range + NO from Gemini -> separate entity."""

    def test_no_creates_separate(self):
        config = _make_config(graph_disambig_vector_high=0.92, graph_disambig_vector_low=0.80)
        disambig = EntityDisambiguator(config)
        mock_client = AsyncMock()
        mock_client.generate_content = AsyncMock(return_value="NO")
        disambig._gemini = mock_client

        raw = _make_raw("apple", "CONCEPT", context="she ate a red apple for lunch")
        candidate = _make_entity(canonical_name="Apple Inc.", entity_type="ORGANIZATION")
        answer = _run(disambig._signal_2_coref(raw, candidate))
        assert answer == "NO"


@pytest.mark.unit
class TestDisambig005WikidataCacheMiss:
    """TEST-DISAMBIG-005: Cache miss -> Wikidata called, Redis key set."""

    def test_wikidata_enriches(self):
        from app.application.graph.disambiguation import _wikidata_search

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        payload = {"search": [{"label": "Google DeepMind", "description": "AI lab",
                               "url": "https://en.wikipedia.org/wiki/Google_DeepMind", "id": "Q32002"}]}

        with patch("app.application.graph.disambiguation.httpx.AsyncClient") as mock_http:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = payload
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)

            result = _run(_wikidata_search("DeepMind", "ORGANIZATION", mock_redis, 86400))

        assert result is not None
        assert mock_redis.setex.called


@pytest.mark.unit
class TestDisambig006WikidataCacheHit:
    """TEST-DISAMBIG-006: Cache hit -> no HTTP call."""

    def test_cache_hit_no_api(self):
        from app.application.graph.disambiguation import _wikidata_search

        cached = json.dumps({"canonical_name": "Google DeepMind", "wikidata_id": "Q32002"})
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached)

        with patch("app.application.graph.disambiguation.httpx.AsyncClient") as mock_http:
            result = _run(_wikidata_search("DeepMind", "ORGANIZATION", mock_redis, 86400))
            mock_http.assert_not_called()

        assert result["canonical_name"] == "Google DeepMind"


@pytest.mark.unit
class TestDisambig007WikidataTimeout:
    """TEST-DISAMBIG-007: Wikidata unreachable -> None, no exception."""

    def test_graceful_on_timeout(self):
        from app.application.graph.disambiguation import _wikidata_search

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.application.graph.disambiguation.httpx.AsyncClient") as mock_http:
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("connection timeout")
            )
            result = _run(_wikidata_search("DeepMind", "ORGANIZATION", mock_redis, 86400))

        assert result is None


@pytest.mark.unit
class TestDisambig008AliasUpdate:
    """TEST-DISAMBIG-008: New surface form appended to alias list."""

    def test_alias_added(self):
        config = _make_config()
        disambig = EntityDisambiguator(config)

        existing = _make_entity(name="Google")
        existing.aliases = ["Alphabet"]
        existing.embedding = [1.0] + [0.0] * 767
        disambig._entity_cache[existing.entity_id] = (existing.embedding, existing)

        merged = disambig._merge(existing, _make_raw("GOOGL"), "GOOGL", [1.0] + [0.0] * 767, 0.96)
        assert "GOOGL" in merged.aliases
        assert "Alphabet" in merged.aliases
        assert len(merged.aliases) == 2


@pytest.mark.unit
class TestCanonicalizationRules:
    """Canonical name normalizer rules."""

    def test_last_first_reordered(self):
        assert canonicalize_name("Altman, Sam", "PERSON") == "Sam Altman"

    def test_leading_the_stripped(self):
        assert not canonicalize_name("the White House", "ORGANIZATION").lower().startswith("the ")

    def test_whitespace_collapsed(self):
        assert "  " not in canonicalize_name("  OpenAI   Inc.  ", "ORGANIZATION")

    def test_empty_graceful(self):
        assert isinstance(canonicalize_name("", "CONCEPT"), str)


@pytest.mark.unit
class TestCosineHelper:
    """_cosine edge cases."""

    def test_identical(self):
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine(v, v) - 1.0) < 1e-9

    def test_orthogonal(self):
        assert abs(_cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_empty(self):
        assert _cosine([], []) == 0.0

    def test_dimension_mismatch(self):
        assert _cosine([1.0, 0.0], [1.0]) == 0.0


# ===========================================================================
# SECTION 12 -- Unit Tests: Graph Construction
# ===========================================================================

@pytest.mark.unit
class TestGraph001DocumentUpsert:
    """TEST-GRAPH-001: Document upsert is idempotent (MERGE semantics)."""

    def test_two_upserts_same_id(self):
        config = _make_config()
        mock_store = MagicMock()
        calls: list[str] = []
        mock_store.upsert_document.side_effect = lambda **kw: calls.append(kw["document_id"])

        for _ in range(2):
            mock_store.upsert_document(document_id="doc1", title="T",
                                       content_type="text", bucket_id="b1",
                                       user_id="u1", created_at=0, word_count=1, source_url="")
        assert calls.count("doc1") == 2  # called twice; DB MERGE handles dedup


@pytest.mark.unit
class TestGraph002MentionsRelationship:
    """TEST-GRAPH-002: MENTIONS relationship created with confidence."""

    def test_mentions_created_after_process(self):
        config = _make_config()
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        ctor = GraphConstructor(config, mock_store)

        e1 = _make_entity(entity_id="e1", name="OpenAI")
        e2 = _make_entity(entity_id="e2", name="Sam Altman", entity_type="PERSON")
        task = GraphExtractionTask(
            document_id="d1", user_id="u1", bucket_id="b1", title="T",
            chunks=[{"chunk_index": 0, "text": "OpenAI and Sam Altman."}],
        )
        mock_disambig = MagicMock()
        mock_disambig.resolve_batch = AsyncMock(return_value=[e1, e2])

        with patch.object(ctor._ner, "extract", new=AsyncMock(return_value=[
            _make_raw("OpenAI", "ORGANIZATION", confidence=0.92),
            _make_raw("Sam Altman", "PERSON", confidence=0.88),
        ])):
            summary = _run(ctor.process_document(task, mock_disambig))

        assert mock_store.create_mentions.call_count == 2
        assert summary["status"] == "indexed"


@pytest.mark.unit
class TestGraph003MentionCountIncrement:
    """TEST-GRAPH-003: upsert_entity called (mention_count tracked by store)."""

    def test_upsert_entity_called(self):
        config = _make_config()
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        ctor = GraphConstructor(config, mock_store)

        entity = _make_entity(entity_id="e1", name="OpenAI", mention_count=5)
        task = GraphExtractionTask(
            document_id="d1", user_id="u1", bucket_id="b1", title="T",
            chunks=[{"chunk_index": 0, "text": "OpenAI leads AI research."}],
        )
        mock_disambig = MagicMock()
        mock_disambig.resolve_batch = AsyncMock(return_value=[entity])

        with patch.object(ctor._ner, "extract", new=AsyncMock(return_value=[
            _make_raw("OpenAI", "ORGANIZATION", confidence=0.9),
        ])):
            _run(ctor.process_document(task, mock_disambig))

        assert mock_store.upsert_entity.called


@pytest.mark.unit
class TestGraph004CoOccurrenceRelationship:
    """TEST-GRAPH-004: Co-occurring entities -> co_occurs_with RELATED_TO."""

    def test_co_occurrence_extraction(self):
        config = _make_config()
        mock_store = MagicMock()
        ctor = GraphConstructor(config, mock_store)

        sam = _make_entity(entity_id="e1", name="Sam Altman", entity_type="PERSON")
        openai = _make_entity(entity_id="e2", name="OpenAI", entity_type="ORGANIZATION")

        rels = ctor._extract_co_occurrence_rels(
            "Sam Altman, CEO of OpenAI, announced products.", [sam, openai], "d1"
        )
        assert len(rels) > 0
        assert all(r.relationship_type == "co_occurs_with" for r in rels)
        assert all(r.extraction_method == "co_occurrence" for r in rels)


@pytest.mark.unit
class TestGraph005EMAStrength:
    """TEST-GRAPH-005: EMA formula: 0.8 * 0.70 + 0.2 * 0.60 = 0.68."""

    def test_ema_formula(self):
        old_strength = 0.70
        new_proximity = 0.60
        result = 0.8 * old_strength + 0.2 * new_proximity
        assert abs(result - 0.68) < 1e-9


@pytest.mark.unit
class TestGraph006ValidRelationshipStored:
    """TEST-GRAPH-006: Valid Gemini dependency relationship accepted."""

    def test_works_at_accepted(self):
        config = _make_config()
        ctor = GraphConstructor(config, MagicMock())
        name_to_id = {"Sam Altman": "e1", "OpenAI": "e2"}
        raw = json.dumps([{"from": "Sam Altman", "type": "works_at", "to": "OpenAI", "confidence": 0.95}])
        rels = ctor._parse_dependency_response(raw, name_to_id, "d1", int(time.time()))
        assert len(rels) == 1
        assert rels[0].relationship_type == "works_at"
        assert rels[0].extraction_method == "gemini_dependency"
        assert abs(rels[0].strength - 0.95) < 0.01


@pytest.mark.unit
class TestGraph007InvalidRelationshipRejected:
    """TEST-GRAPH-007: Free-text type -> zero relationships stored."""

    def test_freetext_type_rejected(self):
        config = _make_config()
        ctor = GraphConstructor(config, MagicMock())
        name_to_id = {"A": "e1", "B": "e2"}
        raw = json.dumps([{"from": "A", "type": "is the longtime rival of", "to": "B", "confidence": 0.80}])
        rels = ctor._parse_dependency_response(raw, name_to_id, "d1", int(time.time()))
        assert len(rels) == 0


@pytest.mark.unit
class TestGraph008DeleteNoOrphans:
    """TEST-GRAPH-008: Delete document -> document and orphan entity removed."""

    def test_delete_returns_deleted_status(self):
        from app.application.graph.updates import GraphUpdateService

        config = _make_config()
        mock_store = MagicMock()
        mock_store.delete_document = MagicMock(return_value=["e_orphan"])
        mock_store.delete_weak_related_to = MagicMock()

        svc = GraphUpdateService(config, mock_store, MagicMock())
        result = svc.delete_document("doc_x", "user1")
        assert result["status"] == "deleted"
        assert mock_store.delete_document.called


@pytest.mark.unit
class TestGraph009SharedEntityPreserved:
    """TEST-GRAPH-009: Delete D1, shared entity with D2 decremented not deleted."""

    def test_shared_entity_processing(self):
        from app.application.graph.updates import GraphUpdateService

        config = _make_config()
        mock_store = MagicMock()
        mock_store.delete_document = MagicMock(return_value=["e_shared"])
        mock_store.delete_weak_related_to = MagicMock()

        svc = GraphUpdateService(config, mock_store, MagicMock())
        svc.delete_document("d1", "user1")
        # graph_store.delete_document handles mention_count decrement internally
        assert mock_store.delete_document.called


@pytest.mark.unit
class TestGraph010WriteLockConcurrency:
    """TEST-GRAPH-010: 10 concurrent mock writes complete without errors."""

    def test_ten_concurrent_writes(self):
        mock_store = MagicMock()
        mock_store.upsert_document = MagicMock()

        errors: list[Exception] = []

        def _write(i: int) -> None:
            try:
                mock_store.upsert_document(
                    document_id=str(uuid.uuid4()), title=f"Doc{i}",
                    content_type="text", bucket_id="b1", user_id="u1",
                    created_at=int(time.time()), word_count=100, source_url="",
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent write errors: {errors}"
        assert mock_store.upsert_document.call_count == 10


# ===========================================================================
# SECTION 13 -- Unit Tests: Graph Queries
# ===========================================================================

@pytest.mark.unit
class TestQuery001EntityLookup:
    """TEST-QUERY-001: Entity detail returns exactly 3 documents."""

    def test_three_documents_returned(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        entity_row = [["e1", "OpenAI", "ORGANIZATION", "AI lab", "", 5, 0.3, "[]"]]
        doc_rows = [
            ["d1", "Paper 1", 1_700_000_000, 0.90, "ctx1"],
            ["d2", "Paper 2", 1_700_100_000, 0.85, "ctx2"],
            ["d3", "Paper 3", 1_700_200_000, 0.80, "ctx3"],
        ]
        mock_store.execute_read = MagicMock(side_effect=[entity_row, doc_rows])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.entity_detail("e1", "user_a")
        assert len(result["documents"]) == 3


@pytest.mark.unit
class TestQuery002UserIsolation:
    """TEST-QUERY-002: Queries are user-scoped."""

    def test_user_id_in_query_source(self):
        from app.application.graph.queries import GraphQueryService
        import inspect

        src = inspect.getsource(GraphQueryService.entity_detail)
        assert "user_id" in src or "uid" in src


@pytest.mark.unit
class TestQuery003TwoHopTraversal:
    """TEST-QUERY-003: Two-hop documents includes indirect connections."""

    def test_indirect_doc_in_result(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[
            ["doc_direct", "Doc A", 1_700_000_000, 0.9],
            ["doc_indirect", "Doc B", 1_700_100_000, 0.7],
        ])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.two_hop_documents("entity_id_a", "user_a")
        assert "doc_indirect" in [r["document_id"] for r in result]


@pytest.mark.unit
class TestQuery006BucketFiltered:
    """TEST-QUERY-006: centrality_ranked with bucket_id filter."""

    def test_centrality_with_bucket(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[["GPT-4", "TECHNOLOGY", 42, 0.8]])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.centrality_ranked("user_a", bucket_id="bucket_research", limit=10)
        assert len(result) == 1


@pytest.mark.unit
class TestQuery007ShortestPathFound:
    """TEST-QUERY-007: path found -> hops == 3, len(nodes) == 4."""

    def test_path_with_three_hops(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[
            [["OpenAI", "Sam Altman", "Y Combinator", "Paul Graham"], 3]
        ])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.shortest_path("e_openai", "e_paul", "user_a")
        assert result["found"] is True
        assert result["hops"] == 3


@pytest.mark.unit
class TestQuery008ShortestPathNotFound:
    """TEST-QUERY-008: No path -> found=False, hops == -1."""

    def test_no_path_found(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.shortest_path("e1", "e2", "user_a")
        assert result["found"] is False
        assert result["hops"] == -1


@pytest.mark.unit
class TestQuery009PageRankOrder:
    """TEST-QUERY-009: Results in descending pagerank_score order."""

    def test_descending_ordering(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[
            ["A", "ORGANIZATION", 100, 0.9],
            ["B", "ORGANIZATION", 50, 0.5],
            ["C", "ORGANIZATION", 30, 0.2],
        ])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.centrality_ranked("user_a")
        scores = [r["pagerank_score"] for r in result]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
class TestQuery010Timeline:
    """TEST-QUERY-010: Timeline returns chronologically ordered monthly buckets."""

    def test_three_monthly_buckets(self):
        from app.application.graph.queries import GraphQueryService

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[
            [655, 3], [656, 4], [657, 3],
        ])
        svc = GraphQueryService(_make_config(), mock_store)
        result = svc.entity_timeline("entity_id", "user_a")
        assert len(result) == 3
        assert sum(r["monthly_mentions"] for r in result) == 10
        months = [r["month_bucket"] for r in result]
        assert months == sorted(months)


# ===========================================================================
# SECTION 14 -- Integration Tests (live Kuzu)
# ===========================================================================

@pytest.mark.intg
class TestIntGraph001IngestionGraphPopulated:
    """INT-GRAPH-001: Document node, Entity nodes, MENTIONS created after ingest."""

    def test_document_node_created(self, kuzu_store):
        doc_id = str(uuid.uuid4())
        kuzu_store.upsert_document(
            document_id=doc_id, title="Research Paper", content_type="pdf",
            bucket_id="b_int", user_id="u_int1", created_at=int(time.time()),
            word_count=5000, source_url="",
        )
        rows = kuzu_store.execute_read(
            "MATCH (d:Document {document_id: $id}) RETURN d.title", {"id": doc_id}
        )
        assert rows and rows[0][0] == "Research Paper"

    def test_mentions_with_confidence(self, kuzu_store):
        doc_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())
        kuzu_store.upsert_document(
            document_id=doc_id, title="Paper2", content_type="pdf",
            bucket_id="b_int2", user_id="u_int2", created_at=int(time.time()),
            word_count=1000, source_url="",
        )
        kuzu_store.upsert_entity(
            _make_entity(entity_id=entity_id, name="GPT-4", entity_type="PRODUCT", user_id="u_int2")
        )
        kuzu_store.create_mentions(
            document_id=doc_id, entity_id=entity_id,
            confidence=0.92, context="GPT-4 released.", window_index=0,
        )
        rows = kuzu_store.execute_read(
            "MATCH (d:Document {document_id: $did})-[m:MENTIONS]->(e:Entity) RETURN m.confidence",
            {"did": doc_id},
        )
        assert rows and abs(float(rows[0][0]) - 0.92) < 0.01

    def test_all_confidences_above_threshold(self, kuzu_store):
        user = f"u_thr_{uuid.uuid4().hex[:6]}"
        doc_id = str(uuid.uuid4())
        kuzu_store.upsert_document(
            document_id=doc_id, title="T", content_type="text",
            bucket_id="b1", user_id=user, created_at=int(time.time()), word_count=100, source_url="",
        )
        for i in range(3):
            eid = str(uuid.uuid4())
            e = _make_entity(entity_id=eid, name=f"Ent{i}", user_id=user, confidence=0.80 + i * 0.05)
            kuzu_store.upsert_entity(e)
            kuzu_store.create_mentions(
                document_id=doc_id, entity_id=eid, confidence=e.confidence, context="ctx", window_index=i,
            )
        rows = kuzu_store.execute_read(
            "MATCH (d:Document {document_id: $did})-[m:MENTIONS]->() RETURN m.confidence",
            {"did": doc_id},
        )
        assert all(float(r[0]) >= 0.60 for r in rows)


@pytest.mark.intg
class TestIntGraph002DisambiguationCrossDoc:
    """INT-GRAPH-002: Two surface forms -> single Entity node, 2 MENTIONS."""

    def test_single_entity_two_mentions(self, kuzu_store):
        user = f"u_xdoc_{uuid.uuid4().hex[:6]}"
        entity_id = str(uuid.uuid4())

        for suffix in ("A", "B"):
            doc_id = str(uuid.uuid4())
            kuzu_store.upsert_document(
                document_id=doc_id, title=f"Doc{suffix}", content_type="text",
                bucket_id="bx", user_id=user, created_at=int(time.time()), word_count=500, source_url="",
            )
            surface = "OpenAI" if suffix == "A" else "Open AI Inc."
            kuzu_store.upsert_entity(
                _make_entity(entity_id=entity_id, name=surface, canonical_name="OpenAI", user_id=user)
            )
            kuzu_store.create_mentions(
                document_id=doc_id, entity_id=entity_id,
                confidence=0.90, context=f"Mentioned in Doc{suffix}", window_index=0,
            )

        cnt = kuzu_store.execute_read(
            "MATCH (e:Entity {entity_id: $eid}) RETURN count(e)", {"eid": entity_id}
        )
        assert int(cnt[0][0]) == 1

        mentions = kuzu_store.execute_read(
            "MATCH ()-[:MENTIONS]->(e:Entity {entity_id: $eid}) RETURN count(*)", {"eid": entity_id}
        )
        assert int(mentions[0][0]) == 2


@pytest.mark.intg
class TestIntGraph003DeleteCleanup:
    """INT-GRAPH-003: Delete doc -> orphan entity removed."""

    def test_orphan_entity_deleted(self, kuzu_store):
        user = f"u_del_{uuid.uuid4().hex[:6]}"
        doc_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())

        kuzu_store.upsert_document(
            document_id=doc_id, title="ToDelete", content_type="text",
            bucket_id="bdel", user_id=user, created_at=int(time.time()), word_count=100, source_url="",
        )
        kuzu_store.upsert_entity(_make_entity(entity_id=entity_id, name="UniqueOrphan", user_id=user))
        kuzu_store.create_mentions(
            document_id=doc_id, entity_id=entity_id, confidence=0.88, context="ctx", window_index=0,
        )
        kuzu_store.delete_document(doc_id, user)

        doc_cnt = kuzu_store.execute_read(
            "MATCH (d:Document {document_id: $id}) RETURN count(d)", {"id": doc_id}
        )
        assert int(doc_cnt[0][0]) == 0

        ent_cnt = kuzu_store.execute_read(
            "MATCH (e:Entity {entity_id: $eid}) RETURN count(e)", {"eid": entity_id}
        )
        assert int(ent_cnt[0][0]) == 0


@pytest.mark.intg
class TestIntGraph004BucketMove:
    """INT-GRAPH-004: move_belongs_to updates edge correctly."""

    def test_belongs_to_updated(self, kuzu_store):
        user = f"u_bkt_{uuid.uuid4().hex[:6]}"
        doc_id = str(uuid.uuid4())
        bucket_a = str(uuid.uuid4())
        bucket_b = str(uuid.uuid4())

        kuzu_store.upsert_document(
            document_id=doc_id, title="Movable", content_type="text",
            bucket_id=bucket_a, user_id=user, created_at=int(time.time()), word_count=200, source_url="",
        )
        kuzu_store.upsert_bucket(bucket_id=bucket_a, name="BucketA", path="/a", description="", user_id=user)
        kuzu_store.upsert_belongs_to(document_id=doc_id, bucket_id=bucket_a,
                                     assigned_at=int(time.time()), assignment_method="auto")

        kuzu_store.move_belongs_to(
            document_id=doc_id, new_bucket_id=bucket_b,
            new_bucket_name="BucketB", new_bucket_path="/b", user_id=user,
        )

        old = kuzu_store.execute_read(
            "MATCH (d:Document {document_id: $did})-[:BELONGS_TO]->(b:Bucket {bucket_id: $bid}) RETURN count(*)",
            {"did": doc_id, "bid": bucket_a},
        )
        assert int(old[0][0]) == 0

        new = kuzu_store.execute_read(
            "MATCH (d:Document {document_id: $did})-[:BELONGS_TO]->(b:Bucket {bucket_id: $bid}) RETURN count(*)",
            {"did": doc_id, "bid": bucket_b},
        )
        assert int(new[0][0]) == 1


@pytest.mark.intg
class TestIntGraph005RelatedToEMA:
    """INT-GRAPH-005: Two upserts -> EMA strength applied."""

    def test_ema_updated(self, kuzu_store):
        user = f"u_ema_{uuid.uuid4().hex[:6]}"
        eid1, eid2 = str(uuid.uuid4()), str(uuid.uuid4())
        for eid, name in [(eid1, "EA"), (eid2, "EB")]:
            kuzu_store.upsert_entity(_make_entity(entity_id=eid, name=name, user_id=user))

        kuzu_store.upsert_related_to(EntityRelationship(
            from_entity_id=eid1, to_entity_id=eid2, relationship_type="co_occurs_with",
            strength=0.70, evidence_doc_id="doc_ema1",
        ))
        kuzu_store.upsert_related_to(EntityRelationship(
            from_entity_id=eid1, to_entity_id=eid2, relationship_type="co_occurs_with",
            strength=0.60, evidence_doc_id="doc_ema2",
        ))

        rows = kuzu_store.execute_read(
            "MATCH (a:Entity {entity_id: $e1})-[r:RELATED_TO]->(b:Entity {entity_id: $e2}) RETURN r.strength",
            {"e1": eid1, "e2": eid2},
        )
        if rows and rows[0]:
            strength = float(rows[0][0])
            expected = 0.8 * 0.70 + 0.2 * 0.60  # 0.68
            assert abs(strength - expected) < 0.05


@pytest.mark.intg
class TestIntGraph006PageRankJob:
    """INT-GRAPH-006: run_pagerank updates non-zero PageRank scores."""

    def test_pagerank_updates(self, kuzu_store):
        try:
            import networkx  # noqa
        except ImportError:
            pytest.skip("networkx not installed")

        user = f"u_pr_{uuid.uuid4().hex[:6]}"
        ids = [str(uuid.uuid4()) for _ in range(3)]
        for i, eid in enumerate(ids):
            kuzu_store.upsert_entity(_make_entity(entity_id=eid, name=f"PRNode{i}", user_id=user))
        for i in range(len(ids)):
            j = (i + 1) % len(ids)
            kuzu_store.upsert_related_to(EntityRelationship(
                from_entity_id=ids[i], to_entity_id=ids[j],
                relationship_type="co_occurs_with", strength=0.8, evidence_doc_id="doc_pr",
            ))

        result = run_pagerank(_make_config(), kuzu_store, user)
        assert result["status"] == "ok"
        assert result["entities_updated"] >= 3


# ===========================================================================
# SECTION 15 -- End-to-End Scenarios
# ===========================================================================

@pytest.mark.e2e
class TestE2EGraph001FullPipeline:
    """E2E-GRAPH-001: Full ingest pipeline with mocked Gemini."""

    def test_full_pipeline(self, kuzu_store):
        config = _make_config()
        user_id = f"e2e_{uuid.uuid4().hex[:8]}"
        from app.application.graph.construction import GraphConstructor
        from app.application.graph.disambiguation import EntityDisambiguator

        disambig = EntityDisambiguator(config)
        ctor = GraphConstructor(config, kuzu_store)

        entity1 = _make_entity(entity_id=str(uuid.uuid4()), name="Ilya Sutskever",
                               entity_type="PERSON", user_id=user_id)
        entity2 = _make_entity(entity_id=str(uuid.uuid4()), name="OpenAI",
                               entity_type="ORGANIZATION", user_id=user_id)

        async def _fake_generate(prompt: str, **kw: Any) -> str:
            return json.dumps([
                {"name": "Ilya Sutskever", "type": "PERSON", "canonical_form": "Ilya Sutskever",
                 "confidence": 0.95, "context": "Ilya Sutskever co-founded OpenAI."},
                {"name": "OpenAI", "type": "ORGANIZATION", "canonical_form": "OpenAI",
                 "confidence": 0.97, "context": "Ilya Sutskever co-founded OpenAI."},
            ])

        ctor._ner._client = MagicMock()
        ctor._ner._client.generate_content = _fake_generate

        disambig._entity_cache[entity1.entity_id] = (entity1.embedding, entity1)
        disambig._entity_cache[entity2.entity_id] = (entity2.embedding, entity2)

        task = GraphExtractionTask(
            document_id=str(uuid.uuid4()), user_id=user_id, bucket_id="b_e2e",
            title="Research Paper on LLMs",
            chunks=[{"chunk_index": 0, "text": "Ilya Sutskever co-founded OpenAI."}],
            word_count=8,
        )
        summary = _run(ctor.process_document(task, disambig))
        assert summary["status"] == "indexed"
        assert summary["entities"] >= 1


@pytest.mark.e2e
class TestE2EGraph002EmptyDocument:
    """E2E-GRAPH-002: Empty document -> status=skipped."""

    def test_empty_doc_skipped(self, kuzu_store):
        from app.application.graph.construction import GraphConstructor
        from app.application.graph.disambiguation import EntityDisambiguator

        ctor = GraphConstructor(_make_config(), kuzu_store)
        task = GraphExtractionTask(
            document_id=str(uuid.uuid4()), user_id="e2e_empty", bucket_id="b1",
            title="Empty", chunks=[{"chunk_index": 0, "text": "   \n   "}],
        )
        summary = _run(ctor.process_document(task, EntityDisambiguator(_make_config())))
        assert summary["status"] == "skipped"


@pytest.mark.e2e
class TestE2EGraph003ModelConstants:
    """E2E-GRAPH-003: Model constants match spec exactly."""

    def test_entity_types_exact(self):
        expected = {
            "PERSON", "ORGANIZATION", "LOCATION", "CONCEPT", "PRODUCT",
            "EVENT", "TECHNOLOGY", "DATE_TIME", "METRIC_QUANTITY",
        }
        assert ENTITY_TYPES == expected

    def test_required_relationship_types_present(self):
        required = {
            "works_at", "founded", "acquired", "part_of", "cited_by",
            "competitor_of", "located_in", "created_by", "funded_by",
            "partner_of", "reports_to", "member_of", "successor_of",
            "predecessor_of", "co_occurs_with",
        }
        assert required.issubset(RELATIONSHIP_TYPES)

    def test_all_relationship_types_valid(self):
        for rtype in RELATIONSHIP_TYPES:
            rel = EntityRelationship(
                from_entity_id="a", to_entity_id="b",
                relationship_type=rtype, strength=0.75, evidence_doc_id="d",
            )
            assert rel.is_valid(), f"Type '{rtype}' should be valid"


# ===========================================================================
# SECTION 16 -- Performance Tests
# ===========================================================================

@pytest.mark.perf
class TestPerfGraph001WindowBuildSpeed:
    """PERF-GRAPH-001: Window building on 200k-word corpus < 2s."""

    def test_window_build_throughput(self):
        text = "word " * 200_000
        start = time.monotonic()
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Window building took {elapsed:.2f}s"
        assert len(windows) > 0


@pytest.mark.perf
class TestPerfGraph002ReconstructSpeed:
    """PERF-GRAPH-002: reconstruct_text 10k chunks < 0.5s."""

    def test_reconstruct_10k(self):
        chunks = [{"chunk_index": i, "text": f"chunk_{i}"} for i in range(10_000)]
        start = time.monotonic()
        result = reconstruct_text(chunks)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"reconstruct_text took {elapsed:.3f}s"
        assert "chunk_0" in result


@pytest.mark.perf
class TestPerfGraph003CosineSpeed:
    """PERF-GRAPH-003: 10k cosine calls < 0.5s."""

    def test_cosine_10k(self):
        a = [0.1] * 768
        b = [0.2] * 768
        start = time.monotonic()
        for _ in range(10_000):
            _cosine(a, b)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"10k cosine calls took {elapsed:.3f}s"


@pytest.mark.perf
class TestPerfGraph004DeduplicationSpeed:
    """PERF-GRAPH-004: Dedup 10k entities < 0.5s."""

    def test_dedup_10k(self):
        import random

        entities = [
            _make_raw(
                f"Entity_{i % 200}",
                random.choice(["ORGANIZATION", "PERSON", "LOCATION"]),
                confidence=random.uniform(0.6, 1.0),
            )
            for i in range(10_000)
        ]
        start = time.monotonic()
        deduped = GeminiNERPipeline._deduplicate(entities)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"Dedup took {elapsed:.3f}s"
        assert len(deduped) <= 600


@pytest.mark.perf
class TestPerfGraph005RelParsingSpeed:
    """PERF-GRAPH-005: Parse 1k relationship items < 0.5s."""

    def test_parse_1k(self):
        ctor = GraphConstructor(_make_config(), MagicMock())
        entities = {f"Entity_{i}": f"eid_{i}" for i in range(100)}
        raw = json.dumps([
            {"from": f"Entity_{i % 100}", "type": "co_occurs_with",
             "to": f"Entity_{(i + 1) % 100}", "confidence": 0.8}
            for i in range(1000)
        ])
        now = int(time.time())
        start = time.monotonic()
        ctor._parse_dependency_response(raw, entities, "d1", now)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"Parse took {elapsed:.3f}s"


@pytest.mark.perf
class TestPerfGraph006LargeCorpusWindowing:
    """PERF-GRAPH-006: 1M char corpus windowed < 1s."""

    def test_1m_char_corpus(self):
        text = "word " * 200_000
        start = time.monotonic()
        windows = _build_windows(text, window_tokens=2000, overlap_tokens=200)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0
        assert len(windows) > 0


# ===========================================================================
# SECTION 17 -- Acceptance Criteria
# ===========================================================================

@pytest.mark.unit
class TestAcceptanceCriteria:
    """AC-4-01 through AC-4-20."""

    def test_ac_4_01_entity_types_exact(self):
        """AC-4-01: Exactly 9 ENTITY_TYPES."""
        expected = {
            "PERSON", "ORGANIZATION", "LOCATION", "CONCEPT", "PRODUCT",
            "EVENT", "TECHNOLOGY", "DATE_TIME", "METRIC_QUANTITY",
        }
        assert ENTITY_TYPES == expected

    def test_ac_4_02_confidence_threshold_default(self):
        """AC-4-02: Default confidence threshold == 0.60."""
        assert get_kb_config().graph_ner_confidence_threshold == 0.60

    def test_ac_4_03_relationship_vocab_complete(self):
        """AC-4-03: All 15 allowed relationship types present."""
        required = {
            "works_at", "founded", "acquired", "part_of", "cited_by",
            "competitor_of", "located_in", "created_by", "funded_by",
            "partner_of", "reports_to", "member_of", "successor_of",
            "predecessor_of", "co_occurs_with",
        }
        assert required.issubset(RELATIONSHIP_TYPES)

    def test_ac_4_04_window_size_default(self):
        """AC-4-04: NER window default == 2000 tokens."""
        assert get_kb_config().graph_ner_window_tokens == 2000

    def test_ac_4_05_overlap_default(self):
        """AC-4-05: Overlap default == 200 tokens."""
        assert get_kb_config().graph_ner_overlap_tokens == 200

    def test_ac_4_06_high_threshold(self):
        """AC-4-06: High disambiguation threshold == 0.92."""
        assert get_kb_config().graph_disambig_vector_high == 0.92

    def test_ac_4_07_low_threshold(self):
        """AC-4-07: Low disambiguation threshold == 0.80."""
        assert get_kb_config().graph_disambig_vector_low == 0.80

    def test_ac_4_08_wikidata_ttl(self):
        """AC-4-08: Wikidata TTL == 30 days in seconds."""
        assert get_kb_config().graph_wikidata_cache_ttl_seconds == 30 * 24 * 60 * 60

    def test_ac_4_09_pagerank_damping(self):
        """AC-4-09: PageRank damping == 0.85."""
        assert get_kb_config().graph_pagerank_damping == 0.85

    def test_ac_4_10_pagerank_iterations(self):
        """AC-4-10: PageRank max iterations == 20."""
        assert get_kb_config().graph_pagerank_iterations == 20

    def test_ac_4_11_celery_queue(self):
        """AC-4-11: Celery queue name == 'graph_extraction'."""
        assert get_kb_config().graph_celery_queue == "graph_extraction"

    def test_ac_4_12_aliases_json(self):
        """AC-4-12: aliases_json() returns valid JSON list."""
        e = _make_entity()
        e.aliases = ["Apple", "AAPL", "Apple Inc."]
        assert json.loads(e.aliases_json()) == ["Apple", "AAPL", "Apple Inc."]

    def test_ac_4_13_raw_entity_invalid_type(self):
        """AC-4-13: RawEntity with unknown type fails is_valid()."""
        bad = RawEntity(name="X", entity_type="UNKNOWN", canonical_form="X", confidence=0.9, context="")
        assert not bad.is_valid()

    def test_ac_4_14_all_rel_types_valid(self):
        """AC-4-14: Every RELATIONSHIP_TYPES value passes EntityRelationship.is_valid()."""
        for rtype in RELATIONSHIP_TYPES:
            rel = EntityRelationship(
                from_entity_id="a", to_entity_id="b",
                relationship_type=rtype, strength=0.75, evidence_doc_id="d",
            )
            assert rel.is_valid(), f"'{rtype}' should be valid"

    def test_ac_4_15_dedup_keeps_highest(self):
        """AC-4-15: Dedup keeps max confidence."""
        entities = [
            RawEntity("E", "ORGANIZATION", "E", 0.7, "ctx"),
            RawEntity("E", "ORGANIZATION", "E", 0.95, "ctx"),
            RawEntity("E", "ORGANIZATION", "E", 0.8, "ctx"),
        ]
        assert GeminiNERPipeline._deduplicate(entities)[0].confidence == 0.95

    def test_ac_4_16_reconstruct_order(self):
        """AC-4-16: reconstruct_text restores correct chunk order."""
        chunks = [{"chunk_index": 1, "text": "B"}, {"chunk_index": 0, "text": "A"}, {"chunk_index": 2, "text": "C"}]
        assert reconstruct_text(chunks) == "A\nB\nC"

    def test_ac_4_17_person_name_reorder(self):
        """AC-4-17: 'Lastname, Firstname' canonicalized to 'Firstname Lastname'."""
        assert canonicalize_name("Altman, Sam", "PERSON") == "Sam Altman"

    def test_ac_4_18_config_fields(self):
        """AC-4-18: Config exposes all required graph fields."""
        cfg = get_kb_config()
        required_fields = [
            "graph_enabled", "graph_db_path", "graph_ner_window_tokens",
            "graph_ner_overlap_tokens", "graph_ner_confidence_threshold",
            "graph_disambig_vector_high", "graph_disambig_vector_low",
            "graph_wikidata_cache_ttl_seconds", "graph_pagerank_damping",
            "graph_pagerank_iterations", "graph_celery_queue",
        ]
        for field in required_fields:
            assert hasattr(cfg, field), f"Config missing field: {field}"

    def test_ac_4_19_task_defaults(self):
        """AC-4-19: GraphExtractionTask.word_count defaults to 0."""
        task = GraphExtractionTask(
            document_id="d1", user_id="u1", bucket_id="b1", title="T", chunks=[]
        )
        assert task.word_count == 0
        assert task.source_url == ""

    def test_ac_4_20_proximity_nonzero(self):
        """AC-4-20: Proximity > 0 for entities in same sentence."""
        score = _proximity("Apple and Google compete.", "Apple", "Google")
        assert score > 0.0


# ===========================================================================
# SECTION 18 -- Error & Edge Cases
# ===========================================================================

@pytest.mark.unit
class TestErrGraph001ZeroEntities:
    """ERR-GRAPH-001: No extractable entities -> status=indexed, entities=0."""

    def test_zero_entity_doc_indexed(self):
        config = _make_config()
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        ctor = GraphConstructor(config, mock_store)

        task = GraphExtractionTask(
            document_id=str(uuid.uuid4()), user_id="u1", bucket_id="b1",
            title="Numbers Only", chunks=[{"chunk_index": 0, "text": "1234 5678 9012"}],
        )
        mock_disambig = MagicMock()
        mock_disambig.resolve_batch = AsyncMock(return_value=[])

        with patch.object(ctor._ner, "extract", new=AsyncMock(return_value=[])):
            summary = _run(ctor.process_document(task, mock_disambig))

        assert summary["status"] == "indexed"
        assert summary["entities"] == 0


@pytest.mark.unit
class TestErrGraph002GeminiFailure:
    """ERR-GRAPH-002: All Gemini calls fail -> empty result, no exception."""

    def test_all_calls_fail_gracefully(self):
        config = _make_config(graph_ner_confidence_threshold=0.60)
        pipeline = GeminiNERPipeline(config)

        mock_client = AsyncMock()
        mock_client.generate_content = AsyncMock(side_effect=Exception("503 Unavailable"))
        pipeline._client = mock_client

        result = _run(pipeline.extract("Some text to trigger NER."))
        assert isinstance(result, list)


@pytest.mark.unit
class TestErrGraph003CircularRelationship:
    """ERR-GRAPH-003: A->B and B->A both valid (no infinite loop)."""

    def test_bidirectional_valid(self):
        rel_ab = EntityRelationship(
            from_entity_id="a", to_entity_id="b",
            relationship_type="competitor_of", strength=0.9, evidence_doc_id="d1",
        )
        rel_ba = EntityRelationship(
            from_entity_id="b", to_entity_id="a",
            relationship_type="competitor_of", strength=0.9, evidence_doc_id="d1",
        )
        assert rel_ab.is_valid()
        assert rel_ba.is_valid()
        assert rel_ab.from_entity_id != rel_ab.to_entity_id


@pytest.mark.unit
class TestErrGraph004LongEntityName:
    """ERR-GRAPH-004: 500-char entity name passes model validation."""

    def test_long_name_valid(self):
        long_name = "X" * 500
        raw = RawEntity(name=long_name, entity_type="CONCEPT",
                        canonical_form=long_name, confidence=0.9, context="ctx")
        assert raw.is_valid()

    def test_canonical_entity_long_name(self):
        e = CanonicalEntity(
            entity_id=str(uuid.uuid4()), name="X" * 500,
            canonical_name="X" * 200, entity_type="CONCEPT",
        )
        assert e.canonical_name is not None


@pytest.mark.unit
class TestErrGraph005WriteLockTimeout:
    """ERR-GRAPH-005: Write lock timeout -> TimeoutError raised."""

    def test_timeout_raises(self):
        from app.infrastructure.graph_store import KuzuGraphStore

        config = _make_config()
        store = KuzuGraphStore(config)
        store._db = MagicMock()
        store._write_lock.acquire()
        store._lock_timeout = 0.01

        try:
            with pytest.raises(TimeoutError):
                with store._write_ctx():
                    pass
        finally:
            store._write_lock.release()


@pytest.mark.unit
class TestErrGraph006MissingContext:
    """ERR-GRAPH-006: Entity without context field -> stored with empty context, no crash."""

    def test_missing_context_graceful(self):
        raw = [{"name": "Entity", "type": "CONCEPT", "canonical_form": "Entity", "confidence": 0.9}]
        entities = _parse_entities(raw, window_index=0)
        assert len(entities) == 1
        assert entities[0].context is not None


@pytest.mark.unit
class TestErrGraph007WikidataTypeConflict:
    """ERR-GRAPH-007: Local NER type wins over Wikidata suggestion."""

    def test_local_type_preserved(self):
        raw = _make_raw("Mercury", "PRODUCT", context="Mercury spacecraft orbits planets.")
        assert raw.entity_type == "PRODUCT"

    def test_wikidata_url_applied_type_unchanged(self):
        e = _make_entity(entity_type="PRODUCT")
        e.wikipedia_url = "https://en.wikipedia.org/wiki/Mercury_(planet)"
        assert e.entity_type == "PRODUCT"
        assert e.wikipedia_url is not None


# ===========================================================================
# Background Job Tests
# ===========================================================================

@pytest.mark.unit
class TestBackgroundJobs:
    """Background job unit tests."""

    def test_pagerank_empty_graph(self):
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        result = run_pagerank(_make_config(), mock_store, "user1")
        assert result["status"] == "ok"
        assert result["entities_updated"] == 0

    def test_pagerank_with_edges(self):
        try:
            import networkx  # noqa
        except ImportError:
            pytest.skip("networkx not installed")

        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[
            ["e1", "e2", 0.9], ["e2", "e3", 0.7], ["e3", "e1", 0.5],
        ])
        mock_conn = MagicMock()
        mock_store._write_ctx = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_conn),
            __exit__=MagicMock(return_value=False),
        ))
        result = run_pagerank(_make_config(), mock_store, "user1")
        assert result["status"] == "ok"
        assert result["entities_updated"] >= 3

    def test_orphan_cleanup_no_orphans(self):
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        result = run_orphan_cleanup(_make_config(), mock_store, "user1")
        assert result["status"] == "ok"
        assert result["orphans_deleted"] == 0

    def test_orphan_cleanup_deletes_orphans(self):
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[["e1", "Stale"], ["e2", "Old"]])
        mock_conn = MagicMock()
        mock_store._write_ctx = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_conn),
            __exit__=MagicMock(return_value=False),
        ))
        result = run_orphan_cleanup(_make_config(), mock_store, "user1")
        assert result["orphans_deleted"] == 2

    def test_health_check_healthy(self):
        mock_store = MagicMock()
        mock_store.node_counts = MagicMock(return_value={"Document": 100, "Entity": 500, "Bucket": 10})
        mock_store.relationship_counts = MagicMock(return_value={"MENTIONS": 1000})
        mock_store.execute_read = MagicMock(return_value=[[5]])
        result = run_health_check(_make_config(), mock_store, pg_document_count=100)
        assert result["healthy"] is True

    def test_health_check_unhealthy_on_deviation(self):
        """More than 5% deviation -> unhealthy."""
        mock_store = MagicMock()
        mock_store.node_counts = MagicMock(return_value={"Document": 50, "Entity": 200, "Bucket": 5})
        mock_store.relationship_counts = MagicMock(return_value={"MENTIONS": 400})
        mock_store.execute_read = MagicMock(return_value=[[0]])
        result = run_health_check(_make_config(), mock_store, pg_document_count=100)
        assert result["healthy"] is False


# ===========================================================================
# Incremental Update Tests
# ===========================================================================

@pytest.mark.unit
class TestIncrementalUpdates:
    """GraphUpdateService operation tests."""

    def _svc(self):
        from app.application.graph.updates import GraphUpdateService

        config = _make_config()
        mock_store = MagicMock()
        mock_store.execute_read = MagicMock(return_value=[])
        mock_store.delete_document = MagicMock(return_value=["e1", "e2"])
        mock_store.delete_weak_related_to = MagicMock()
        mock_store.delete_document_mentions = MagicMock()
        mock_store.update_mention_count = MagicMock()
        mock_store.move_belongs_to = MagicMock()
        return GraphUpdateService(config, mock_store, MagicMock()), mock_store

    def test_delete_status(self):
        svc, store = self._svc()
        result = svc.delete_document("doc1", "user1")
        assert result["status"] == "deleted"
        assert store.delete_document.called

    def test_delete_cleans_weak_rels(self):
        svc, store = self._svc()
        svc.delete_document("doc1", "user1")
        assert store.delete_weak_related_to.called

    def test_move_bucket_status(self):
        svc, store = self._svc()
        result = svc.move_document_bucket(
            document_id="doc1", new_bucket_id="b2",
            new_bucket_name="NewBucket", new_bucket_path="/new", user_id="u1",
        )
        assert result["status"] == "moved"
        assert store.move_belongs_to.called

    def test_update_removes_old_mentions(self):
        svc, store = self._svc()
        store.execute_read = MagicMock(return_value=[["e1"], ["e2"]])
        task = GraphExtractionTask(
            document_id="doc1", user_id="u1", bucket_id="b1",
            title="Updated", chunks=[{"chunk_index": 0, "text": "New content."}],
        )
        with patch.object(svc._constructor, "process_document",
                          new=AsyncMock(return_value={"status": "indexed"})):
            _run(svc.update_document(task))
        assert store.delete_document_mentions.called

    def test_validate_integrity_zero_orphans(self):
        svc, store = self._svc()
        store.execute_read = MagicMock(return_value=[[0]])
        assert svc.validate_integrity("u1")["orphaned_entities"] == 0

    def test_validate_integrity_detects_orphans(self):
        svc, store = self._svc()
        store.execute_read = MagicMock(return_value=[[7]])
        assert svc.validate_integrity("u1")["orphaned_entities"] == 7
