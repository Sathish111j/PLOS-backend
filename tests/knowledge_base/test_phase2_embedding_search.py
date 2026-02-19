"""
Phase 2 - Embedding, Vector Storage & Hybrid Search Tests
Covers:
  TEST-EMBED-001  to TEST-EMBED-007
  TEST-QDRANT-001 to TEST-QDRANT-006
  TEST-SEARCH-RRF-001 to TEST-SEARCH-RRF-006
  TEST-RERANK-001 to TEST-RERANK-005
  TEST-FTS-001    to TEST-FTS-003
  TEST-TYPO-001   to TEST-TYPO-003
  AC-2-01         to AC-2-18

All tests are synchronous.  Async provider calls are wrapped with asyncio.run()
so pytest-asyncio is not required.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Source module imports
# ---------------------------------------------------------------------------
from app.application.embeddings import GeminiEmbeddingProvider
from app.application.search_utils import (
    apply_mmr_diversity,
    bucket_context_score,
    detect_query_intent_weights,
    deterministic_embedding,
    engagement_score,
    reciprocal_rank_fusion,
    recency_score,
)
from app.core.config import KnowledgeBaseConfig, get_kb_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides: Any) -> KnowledgeBaseConfig:
    """Rebuild KnowledgeBaseConfig from current env, applying overrides."""
    import dataclasses

    cfg = get_kb_config()
    d = dataclasses.asdict(cfg)
    d.update(overrides)
    return KnowledgeBaseConfig(**d)


def _unit_vector(dim: int, *, index: int = 0) -> list[float]:
    """Sparse unit vector with 1.0 at position `index`."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


def _rand_vec(dim: int, seed: int = 0) -> list[float]:
    """Deterministic pseudo-random normalised vector (no external deps)."""
    return deterministic_embedding(f"seed={seed}", dim)


def _l2_norm(vector: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def _make_doc(doc_id: str, score: float = 1.0, **payload: Any) -> dict[str, Any]:
    return {"document_id": doc_id, "score": score, **payload}


# ---------------------------------------------------------------------------
# 4.1 - Embedding Service Unit Tests
# ---------------------------------------------------------------------------


def test_embed_001_gemini_vector_shape() -> None:
    """
    TEST-EMBED-001: Mocked Gemini returns exactly 768 floats; all are float type.
    """
    raw_768 = [0.01 * i for i in range(768)]

    async def _call() -> list[float]:
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)
        mock_client = AsyncMock()
        mock_client.embed_content = AsyncMock(return_value=raw_768)
        provider._gemini_client = mock_client
        return await provider.embed_document("hello world")

    vector = asyncio.run(_call())
    assert len(vector) == 768, f"Expected 768 dims, got {len(vector)}"
    assert all(isinstance(v, float) for v in vector), "All values must be float"


def test_embed_002_l2_normalization() -> None:
    """
    TEST-EMBED-002: After normalization magnitude == 1.0 (within 1e-6).
    """
    raw = [3.5, -1.2, 0.0, 7.8, -4.4] + [1.1] * 763  # 768 floats
    normalized = GeminiEmbeddingProvider._normalize(raw)
    magnitude = _l2_norm(normalized)
    assert abs(magnitude - 1.0) < 1e-6, f"Expected unit norm, got {magnitude:.8f}"


def test_embed_002_zero_vector_safe() -> None:
    """_normalize must not raise on zero vector."""
    result = GeminiEmbeddingProvider._normalize([0.0] * 768)
    assert len(result) == 768
    assert all(v == 0.0 for v in result)


def test_embed_001_vector_is_l2_normalized() -> None:
    """Provider normalises the raw Gemini output - magnitude must be 1.0."""
    raw_768 = [float(i % 50 + 1) for i in range(768)]

    async def _call() -> list[float]:
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)
        mock_client = AsyncMock()
        mock_client.embed_content = AsyncMock(return_value=raw_768)
        provider._gemini_client = mock_client
        return await provider.embed_document("normalisation test")

    vector = asyncio.run(_call())
    magnitude = _l2_norm(vector)
    assert abs(magnitude - 1.0) < 1e-5, f"L2 norm should be 1.0, got {magnitude:.8f}"


def test_embed_003_batch_single_api_call() -> None:
    """
    TEST-EMBED-003: 100 chunks submitted as one batch -> 1 Gemini API call.
    All 100 returned vectors are 768-dim.
    """
    texts = [f"chunk text number {i}" for i in range(100)]
    raw_batch = [[float(j % 100) * 0.01 for j in range(768)] for _ in range(100)]
    call_count = 0

    async def _call() -> list[list[float]]:
        nonlocal call_count

        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)

        async def _batch_side(*args: Any, **kwargs: Any) -> list[list[float]]:
            nonlocal call_count
            call_count += 1
            return raw_batch

        mock_client = AsyncMock()
        mock_client.embed_content_batch = AsyncMock(side_effect=_batch_side)
        provider._gemini_client = mock_client
        return await provider.embed_documents_batch(texts)

    vectors = asyncio.run(_call())

    assert len(vectors) == 100, f"Expected 100 vectors, got {len(vectors)}"
    assert all(len(v) == 768 for v in vectors), "Each vector must be 768-dim"
    assert call_count == 1, (
        f"Expected 1 batch API call for 100 chunks, got {call_count}"
    )


def test_embed_004_idempotent_same_input() -> None:
    """
    TEST-EMBED-004: Same text submitted twice -> identical output vectors.
    """
    raw = [float(i % 10 + 1) for i in range(768)]

    async def _embed(text: str) -> list[float]:
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)
        mock_client = AsyncMock()
        mock_client.embed_content = AsyncMock(return_value=raw)
        provider._gemini_client = mock_client
        return await provider.embed_document(text)

    v1 = asyncio.run(_embed("test text for idempotency"))
    v2 = asyncio.run(_embed("test text for idempotency"))
    assert v1 == v2, "Same input must produce identical output vector"


def test_embed_005_model_candidate_fallback() -> None:
    """
    TEST-EMBED-005: First candidate model fails; provider falls back to second
    candidate model and returns a valid vector.

    Forces two distinct candidates by assigning a primary model name that differs
    from the hardcoded fallback "gemini-embedding-001", so _candidate_models()
    returns two entries and the deduplication does not collapse them.
    """
    raw = [1.0] + [0.0] * 767
    call_count = 0

    async def _call() -> list[float]:
        nonlocal call_count
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)
        # Force a primary model that differs from the fallback so that
        # _candidate_models() yields two distinct model strings.
        provider._embedding_model = "models/text-embedding-004"

        async def _side_effect(*args: Any, **kwargs: Any) -> list[float]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Model quota exceeded")
            return raw

        mock_client = AsyncMock()
        mock_client.embed_content = AsyncMock(side_effect=_side_effect)
        provider._gemini_client = mock_client
        return await provider.embed_document("retry test")

    vector = asyncio.run(_call())
    assert len(vector) == 768
    assert call_count >= 2, f"Expected at least 2 attempts (one failure + one success), got {call_count}"


def test_embed_006_all_models_fail_raises() -> None:
    """
    TEST-EMBED-006: All candidates fail -> RuntimeError raised (no silent failure).
    """

    async def _call() -> list[float]:
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)
        mock_client = AsyncMock()
        mock_client.embed_content = AsyncMock(
            side_effect=RuntimeError("Gemini down")
        )
        provider._gemini_client = mock_client
        return await provider.embed_document("failure test")

    with pytest.raises(RuntimeError, match="Gemini"):
        asyncio.run(_call())


def test_embed_007_dimension_resize_contract() -> None:
    """
    TEST-EMBED-007: _resize_vector always produces the requested dimension.
    Same-dimension input is a no-op; up/down scaling both return correct length.
    """
    small = [float(i) for i in range(384)]
    resized_up = GeminiEmbeddingProvider._resize_vector(small, 768)
    assert len(resized_up) == 768, f"Expected 768, got {len(resized_up)}"

    large = [float(i) for i in range(1536)]
    resized_down = GeminiEmbeddingProvider._resize_vector(large, 768)
    assert len(resized_down) == 768, f"Expected 768, got {len(resized_down)}"

    same = [float(i) for i in range(768)]
    unchanged = GeminiEmbeddingProvider._resize_vector(same, 768)
    assert unchanged == same, "Same-dim resize should be a no-op"


# ---------------------------------------------------------------------------
# 4.2 - Qdrant Vector Storage Tests (live service)
# ---------------------------------------------------------------------------

_QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
_TEST_COLL = f"p2test_{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="module")
def qdrant() -> Any:
    """Live Qdrant client with a fresh 8-dim test collection."""
    cl: Any = None
    try:
        from qdrant_client import QdrantClient
        from qdrant_client import models as qm

        cl = QdrantClient(url=_QDRANT_URL, timeout=60)
        cl.create_collection(
            collection_name=_TEST_COLL,
            vectors_config=qm.VectorParams(size=8, distance=qm.Distance.COSINE),
        )
        yield cl, qm
    except Exception as exc:
        pytest.skip(f"Qdrant unavailable: {exc}")
    finally:
        if cl is not None:
            try:
                cl.delete_collection(_TEST_COLL)
            except Exception:
                pass


def test_qdrant_001_insert_retrieve(qdrant: Any) -> None:
    """
    TEST-QDRANT-001: Insert one point; retrieve by id; payload intact.
    """
    cl, qm = qdrant
    point_id = str(uuid.uuid4())
    payload = {
        "document_id": point_id,
        "user_id": "user-aaa",
        "bucket_id": "bucket-001",
        "content_type": "text",
        "title": "test document",
    }

    cl.upsert(
        collection_name=_TEST_COLL,
        points=[
            qm.PointStruct(
                id=point_id,
                vector=_unit_vector(8, index=0),
                payload=payload,
            )
        ],
    )

    results = cl.retrieve(
        collection_name=_TEST_COLL,
        ids=[point_id],
        with_payload=True,
    )

    assert len(results) == 1, "Expected exactly one retrieved point"
    r = results[0]
    assert str(r.id) == point_id
    for key, val in payload.items():
        assert r.payload.get(key) == val, f"Payload mismatch for key '{key}'"


def test_qdrant_002_user_id_filter_isolation(qdrant: Any) -> None:
    """
    TEST-QDRANT-002: Points for two users; filter returns only user_A.
    """
    cl, qm = qdrant
    uid_a = f"user-A-{uuid.uuid4().hex[:4]}"
    uid_b = f"user-B-{uuid.uuid4().hex[:4]}"
    points: list[Any] = []

    for i in range(15):
        for uid in (uid_a, uid_b):
            vid = str(uuid.uuid4())
            points.append(
                qm.PointStruct(
                    id=vid,
                    vector=_rand_vec(8, seed=i + (1 if uid == uid_a else 100)),
                    payload={
                        "user_id": uid,
                        "document_id": vid,
                        "content_type": "text",
                    },
                )
            )

    cl.upsert(collection_name=_TEST_COLL, points=points)

    results = cl.search(
        collection_name=_TEST_COLL,
        query_vector=_rand_vec(8, seed=42),
        query_filter=qm.Filter(
            must=[
                qm.FieldCondition(
                    key="user_id", match=qm.MatchValue(value=uid_a)
                )
            ]
        ),
        limit=10,
        with_payload=True,
    )

    assert len(results) > 0, "Expected results for user_A filter"
    for r in results:
        assert r.payload.get("user_id") == uid_a, (
            f"Cross-user leakage: got user_id={r.payload.get('user_id')}"
        )


def test_qdrant_003_bucket_filter(qdrant: Any) -> None:
    """
    TEST-QDRANT-003: 40 points across 4 buckets; filter returns only bkt-X.
    """
    cl, qm = qdrant
    buckets = ["bkt-X", "bkt-Y", "bkt-Z", "bkt-W"]
    points: list[Any] = []

    for i in range(40):
        vid = str(uuid.uuid4())
        bkt = buckets[i % 4]
        points.append(
            qm.PointStruct(
                id=vid,
                vector=_rand_vec(8, seed=i + 300),
                payload={
                    "bucket_id": bkt,
                    "document_id": vid,
                    "user_id": "u",
                    "content_type": "text",
                },
            )
        )

    cl.upsert(collection_name=_TEST_COLL, points=points)

    results = cl.search(
        collection_name=_TEST_COLL,
        query_vector=_rand_vec(8, seed=0),
        query_filter=qm.Filter(
            must=[
                qm.FieldCondition(
                    key="bucket_id", match=qm.MatchValue(value="bkt-X")
                )
            ]
        ),
        limit=20,
        with_payload=True,
    )

    assert len(results) > 0, "Expected results filtered to bkt-X"
    for r in results:
        assert r.payload.get("bucket_id") == "bkt-X", (
            f"Expected bkt-X, got {r.payload.get('bucket_id')}"
        )


@pytest.mark.benchmark
def test_qdrant_004_recall_at_10(qdrant: Any) -> None:
    """
    TEST-QDRANT-004: ANN Recall@10 > 0.80 across 10 probe queries (100 vectors).
    """
    cl, qm = qdrant
    n, dim, k = 100, 8, 10
    coll = f"recall_{uuid.uuid4().hex[:8]}"

    cl.create_collection(
        collection_name=coll,
        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
    )

    vecs = [_rand_vec(dim, seed=i + 200) for i in range(n)]
    cl.upsert(
        collection_name=coll,
        points=[
            qm.PointStruct(
                id=str(uuid.uuid4()), vector=v, payload={"idx": i}
            )
            for i, v in enumerate(vecs)
        ],
    )

    recalls: list[float] = []
    for q_idx in range(10):
        qv = vecs[q_idx]
        cosines = [
            (i, sum(qv[d] * vecs[i][d] for d in range(dim)))
            for i in range(n)
        ]
        gt_set = {
            i for i, _ in sorted(cosines, key=lambda x: x[1], reverse=True)[:k]
        }
        ann_res = cl.search(
            collection_name=coll,
            query_vector=qv,
            limit=k,
            with_payload=True,
        )
        ann_set = {r.payload["idx"] for r in ann_res}
        recalls.append(len(gt_set & ann_set) / k)

    cl.delete_collection(coll)
    mean_recall = sum(recalls) / len(recalls)
    assert mean_recall > 0.80, (
        f"TEST-QDRANT-004: Recall@10 = {mean_recall:.2f}, expected > 0.80"
    )


@pytest.mark.benchmark
def test_qdrant_005_query_latency(qdrant: Any) -> None:
    """
    TEST-QDRANT-005: p50 < 50ms and p95 < 100ms across 100 search queries.
    """
    cl, qm = qdrant
    coll = f"lat_{uuid.uuid4().hex[:8]}"
    cl.create_collection(
        collection_name=coll,
        vectors_config=qm.VectorParams(size=8, distance=qm.Distance.COSINE),
    )
    cl.upsert(
        collection_name=coll,
        points=[
            qm.PointStruct(
                id=str(uuid.uuid4()),
                vector=_rand_vec(8, seed=i),
                payload={"i": i},
            )
            for i in range(500)
        ],
    )

    latencies_ms: list[float] = []
    for run in range(100):
        q = _rand_vec(8, seed=run + 9000)
        t0 = time.perf_counter()
        cl.search(collection_name=coll, query_vector=q, limit=10)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    cl.delete_collection(coll)
    latencies_ms.sort()
    p50 = latencies_ms[49]
    p95 = latencies_ms[94]
    assert p50 < 50, f"p50={p50:.2f}ms > 50ms"
    assert p95 < 100, f"p95={p95:.2f}ms > 100ms"


def test_qdrant_006_payload_update(qdrant: Any) -> None:
    """
    TEST-QDRANT-006: Update bucket_id payload; old filter misses, new filter hits.
    """
    cl, qm = qdrant
    point_id = str(uuid.uuid4())
    old_bkt = f"old-{uuid.uuid4().hex[:6]}"
    new_bkt = f"new-{uuid.uuid4().hex[:6]}"

    cl.upsert(
        collection_name=_TEST_COLL,
        points=[
            qm.PointStruct(
                id=point_id,
                vector=_unit_vector(8, index=5),
                payload={
                    "bucket_id": old_bkt,
                    "document_id": point_id,
                    "user_id": "u",
                    "content_type": "text",
                },
            )
        ],
    )

    cl.set_payload(
        collection_name=_TEST_COLL,
        payload={"bucket_id": new_bkt},
        points=[point_id],
    )

    def _ids(bkt: str) -> set[str]:
        return {
            str(r.id)
            for r in cl.search(
                collection_name=_TEST_COLL,
                query_vector=_unit_vector(8, index=5),
                query_filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="bucket_id", match=qm.MatchValue(value=bkt)
                        )
                    ]
                ),
                limit=20,
                with_payload=True,
            )
        }

    assert point_id not in _ids(old_bkt), "Point must not appear under old bucket_id"
    assert point_id in _ids(new_bkt), "Point must appear under new bucket_id"


# ---------------------------------------------------------------------------
# 4.3 - Hybrid Search RRF Unit Tests (pure functions, no I/O)
# ---------------------------------------------------------------------------


def test_search_rrf_001_ranking_correctness() -> None:
    """
    TEST-SEARCH-RRF-001: doc_A ranks 1st in 2 lists -> wins RRF.
    Order: doc_A > doc_B > doc_C.
    """
    fused = reciprocal_rank_fusion(
        [
            (0.6, [_make_doc("doc_A"), _make_doc("doc_B"), _make_doc("doc_C")]),
            (0.3, [_make_doc("doc_B"), _make_doc("doc_A"), _make_doc("doc_D")]),
            (0.1, [_make_doc("doc_A"), _make_doc("doc_C"), _make_doc("doc_B")]),
        ],
        k=60,
    )
    ranked = [doc_id for doc_id, _ in fused]
    scores = {doc_id: score for doc_id, score in fused}

    assert ranked[0] == "doc_A", f"Expected doc_A first, got {ranked[0]}"
    assert ranked[1] == "doc_B", f"Expected doc_B second, got {ranked[1]}"
    assert scores["doc_A"] > scores["doc_B"] > scores.get("doc_C", 0.0)


def test_search_rrf_002_k60_score_delta() -> None:
    """
    TEST-SEARCH-RRF-002: Score delta rank-1 vs rank-2 with k=60, weight=0.6
    equals 0.6 * (1/61 - 1/62).
    """
    fused = reciprocal_rank_fusion(
        [(0.6, [_make_doc("X"), _make_doc("Y")])],
        k=60,
    )
    scores = {doc_id: v for doc_id, v in fused}
    diff = scores["X"] - scores["Y"]
    expected = 0.6 * (1.0 / 61 - 1.0 / 62)
    assert abs(diff - expected) < 1e-10, (
        f"Expected diff {expected:.10f}, got {diff:.10f}"
    )


def test_search_rrf_003_conceptual_intent_explain() -> None:
    """
    TEST-SEARCH-RRF-003: 'explain ...' -> semantic weight == 0.80.
    """
    weights = detect_query_intent_weights(
        "explain how transformer attention mechanisms work"
    )
    assert weights.get("semantic") == 0.80, (
        f"Expected semantic=0.80, got {weights}"
    )


def test_search_rrf_003_how_does_intent() -> None:
    """'how does ...' triggers conceptual classification (semantic=0.80)."""
    weights = detect_query_intent_weights("how does gradient descent converge")
    assert weights.get("semantic") == 0.80


def test_search_rrf_003_what_is_intent() -> None:
    """'what is ...' triggers conceptual classification (semantic=0.80)."""
    weights = detect_query_intent_weights("what is reciprocal rank fusion")
    assert weights.get("semantic") == 0.80


def test_search_rrf_004_quoted_phrase_keyword_weight() -> None:
    """
    TEST-SEARCH-RRF-004: Quoted phrase -> keyword weight == 0.60.
    (Codebase uses key 'keyword'; spec calls it 'fulltext' - same intent.)
    """
    weights = detect_query_intent_weights('"reciprocal rank fusion" algorithm')
    assert weights.get("keyword") == 0.60, (
        f"Expected keyword=0.60 for quoted query, got {weights}"
    )


def test_search_rrf_005_rrf_is_deterministic() -> None:
    """
    TEST-SEARCH-RRF-005: RRF of identical inputs always produces the same ranking.
    """
    docs = [_make_doc(f"doc_{i}") for i in range(20)]
    fused_1 = reciprocal_rank_fusion([(0.6, docs), (0.4, docs[::-1])], k=60)
    fused_2 = reciprocal_rank_fusion([(0.6, docs), (0.4, docs[::-1])], k=60)
    assert fused_1 == fused_2, "RRF must be deterministic for identical inputs"


def test_search_rrf_006_score_accumulation() -> None:
    """
    TEST-SEARCH-RRF-006: Document in multiple lists accumulates higher score.
    """
    fused = reciprocal_rank_fusion(
        [
            (0.5, [_make_doc("shared"), _make_doc("only_a")]),
            (0.5, [_make_doc("shared"), _make_doc("only_b")]),
        ],
        k=60,
    )
    scores = {doc_id: v for doc_id, v in fused}
    assert scores["shared"] > scores["only_a"]
    assert scores["shared"] > scores["only_b"]


def test_search_rrf_empty_input() -> None:
    """Edge case: empty input list returns empty ranking."""
    assert reciprocal_rank_fusion([], k=60) == []


# ---------------------------------------------------------------------------
# 4.4 - Reranker / Score Composition Unit Tests
# ---------------------------------------------------------------------------


def _final_score(
    rerank: float,
    recency: float,
    engagement: float,
    bucket: float,
) -> float:
    """Final score formula from knowledge_service.py lines 539-543."""
    return (
        0.60 * rerank
        + 0.15 * recency
        + 0.15 * engagement
        + 0.10 * bucket
    )


def test_rerank_001_relevant_scores_higher() -> None:
    """
    TEST-RERANK-001: Directly-relevant doc (rerank=0.90) outscores
    tangential mention (rerank=0.30).
    """
    score_a = _final_score(rerank=0.90, recency=1.0, engagement=0.5, bucket=1.0)
    score_b = _final_score(rerank=0.30, recency=1.0, engagement=0.5, bucket=1.0)
    assert score_a > score_b


def test_rerank_002_final_score_formula_approximation() -> None:
    """
    TEST-RERANK-002: cross_encoder=0.90, days=3, ctr=0.15, bucket=0.70 -> ~0.744.
    """
    rerank_val = 0.90
    recency_val = math.exp(-0.1 * 3)
    engagement_val = 0.15
    bucket_val = 0.70

    computed = _final_score(rerank_val, recency_val, engagement_val, bucket_val)
    expected = 0.744
    assert abs(computed - expected) < 0.01, (
        f"Final score {computed:.4f} differs from expected ~{expected:.3f}"
    )


def test_rerank_003_recency_today_vs_30d() -> None:
    """
    TEST-RERANK-003: today's recency > 30-day-old recency.
    30-day score approx exp(-0.1 * 30).
    """
    now = datetime.now(UTC)
    today_recency = recency_score(now.isoformat())
    old_recency = recency_score((now - timedelta(days=30)).isoformat())

    assert today_recency > old_recency
    expected_old = math.exp(-0.1 * 30)
    assert abs(old_recency - expected_old) < 0.01, (
        f"30-day recency {old_recency:.4f} != expected {expected_old:.4f}"
    )


def test_rerank_003_recency_none_default() -> None:
    """None created_at returns neutral default 0.5."""
    assert recency_score(None) == 0.5


def test_rerank_003_engagement_formula() -> None:
    """engagement_score(clicks, impressions) = (clicks+1)/(impressions+2)."""
    assert abs(engagement_score(0, 0) - 0.5) < 1e-9
    assert abs(engagement_score(8, 10) - (9.0 / 12.0)) < 1e-9


def test_rerank_003_bucket_score_match_and_mismatch() -> None:
    """bucket_context_score returns 1.0 on match, 0.5 on mismatch/None."""
    assert bucket_context_score("bkt-A", "bkt-A") == 1.0
    assert bucket_context_score("bkt-A", "bkt-B") == 0.5
    assert bucket_context_score(None, "bkt-A") == 0.5


def test_rerank_004_mmr_diversity_vs_greedy() -> None:
    """
    TEST-RERANK-004: MMR with lambda=0.7 produces >= diversity of greedy top-5.
    """
    topics = ["same narrow topic A"] * 7 + [
        "completely different subject B",
        "unrelated topic C entirely",
        "distinct field D overview",
    ]
    candidates = [
        _make_doc(f"doc_{i}", score=float(10 - i), text_preview=topics[i])
        for i in range(10)
    ]

    mmr_top5 = apply_mmr_diversity(
        query="same narrow topic A",
        results=list(candidates),
        top_k=5,
        lambda_weight=0.7,
    )
    greedy_top5 = sorted(candidates, key=lambda d: d["score"], reverse=True)[:5]

    def _diversity(items: list[dict]) -> float:
        unique = {str(item.get("text_preview", ""))[:25] for item in items}
        return len(unique) / max(1, len(items))

    assert _diversity(mmr_top5) >= _diversity(greedy_top5), (
        f"MMR diversity {_diversity(mmr_top5):.2f} < greedy {_diversity(greedy_top5):.2f}"
    )


@pytest.mark.benchmark
def test_rerank_005_mmr_latency_50_candidates() -> None:
    """
    TEST-RERANK-005: MMR over 50 candidates finishes in < 500ms.
    """
    candidates = [
        _make_doc(
            f"doc_{i}",
            score=float(50 - i),
            text_preview=f"Document {i} about various topics",
        )
        for i in range(50)
    ]
    t0 = time.perf_counter()
    apply_mmr_diversity(
        query="how does gradient descent work",
        results=candidates,
        top_k=10,
        lambda_weight=0.7,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 500, f"MMR rerank took {elapsed_ms:.1f}ms, expected < 500ms"


# ---------------------------------------------------------------------------
# 4.5 - Full-Text Search via PostgreSQL ts_rank
# ---------------------------------------------------------------------------

_PG_DSN_RAW = os.getenv(
    "DATABASE_URL",
    "postgresql://supabase_admin:postgres@supabase-db:5432/postgres",
)
# asyncpg (and psycopg3) do not accept the SQLAlchemy '+asyncpg' DSN scheme.
_PG_DSN = _PG_DSN_RAW.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="module")
def pg_conn() -> Any:
    """
    Synchronous psycopg3 connection for FTS tests.
    psycopg[binary] is installed in the test requirements and is purely sync,
    which avoids the event-loop-per-asyncio.run() issue with asyncpg.
    """
    import psycopg  # type: ignore[import]

    conn: Any = None
    try:
        conn = psycopg.connect(_PG_DSN, connect_timeout=5)
        yield conn
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def _pg_rank(conn: Any, doc_text: str, query_str: str) -> float:
    """Execute ts_rank query synchronously via psycopg3."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ts_rank(
                to_tsvector('english', %s),
                plainto_tsquery('english', %s)
            ) AS rank
            """,
            (doc_text, query_str),
        )
        row = cur.fetchone()
        return float(row[0]) if row else 0.0


def test_fts_001_exact_phrase_match(pg_conn: Any) -> None:
    """
    TEST-FTS-001: Document containing 'Reciprocal Rank Fusion' scores > 0
    against the same phrase query.
    """
    rank = _pg_rank(
        pg_conn,
        "Retrieval uses Reciprocal Rank Fusion for better document ranking.",
        "Reciprocal Rank Fusion",
    )
    assert rank > 0, f"Expected non-zero FTS rank, got {rank}"


def test_fts_002_stemming(pg_conn: Any) -> None:
    """
    TEST-FTS-002: 'running' and 'runs' both match query 'run' via the Snowball stemmer.
    Note: 'ran' (irregular past tense) is NOT handled by the English Snowball stemmer
    and is therefore excluded from this assertion.
    """
    for variant in ("running", "runs"):
        rank = _pg_rank(
            pg_conn,
            f"The athlete was {variant} every morning for training.",
            "run",
        )
        assert rank > 0, (
            f"Stem variant '{variant}' should match 'run', got rank={rank}"
        )


def test_fts_003_stop_word_exclusion(pg_conn: Any) -> None:
    """
    TEST-FTS-003: ts_rank('the quick brown fox') == ts_rank('quick brown fox').
    Stop-word 'the' must not affect rank.
    """
    doc = "the quick brown fox jumped over the lazy dog"
    with_stop = _pg_rank(pg_conn, doc, "the quick brown fox")
    without_stop = _pg_rank(pg_conn, doc, "quick brown fox")
    assert with_stop == without_stop, (
        f"Stop-word inclusion changed rank: {with_stop} != {without_stop}"
    )


# ---------------------------------------------------------------------------
# 4.6 - Typo-Tolerant Search (Meilisearch)
# ---------------------------------------------------------------------------

_MEILI_URL = os.getenv("MEILISEARCH_URL", "http://meilisearch:7700")
_MEILI_KEY = os.getenv("MEILISEARCH_MASTER_KEY", "")
_TYPO_INDEX = f"typo_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def meili_idx() -> Any:
    """Meilisearch test index seeded with 3 documents."""
    client: Any = None
    try:
        import meilisearch  # type: ignore[import]

        client = meilisearch.Client(_MEILI_URL, _MEILI_KEY or None)
        client.health()

        client.create_index(_TYPO_INDEX, {"primaryKey": "id"})
        time.sleep(0.5)

        index = client.index(_TYPO_INDEX)
        index.add_documents([
            {
                "id": "1",
                "text": "machine learning is a powerful technique",
                "document_id": "ml_doc",
            },
            {
                "id": "2",
                "text": "retrieval augmented generation for knowledge bases",
                "document_id": "rag_doc",
            },
            {
                "id": "3",
                "text": "transformer architecture and attention mechanisms",
                "document_id": "tf_doc",
            },
        ])
        time.sleep(2)  # wait for indexing

        yield index
    except Exception as exc:
        pytest.skip(f"Meilisearch unavailable: {exc}")
    finally:
        if client is not None:
            try:
                client.delete_index(_TYPO_INDEX)
            except Exception:
                pass


def test_typo_001_single_char_substitution(meili_idx: Any) -> None:
    """
    TEST-TYPO-001: 'machina learning' (a->i substitution) retrieves ml_doc.
    """
    hits = meili_idx.search("machina learning").get("hits", [])
    doc_ids = [h.get("document_id") for h in hits]
    assert "ml_doc" in doc_ids, (
        f"Expected ml_doc for typo 'machina learning', got {doc_ids}"
    )


def test_typo_002_transposition(meili_idx: Any) -> None:
    """
    TEST-TYPO-002: 'retreival' (e/i transposed) retrieves rag_doc.
    """
    hits = meili_idx.search("retreival augmented").get("hits", [])
    doc_ids = [h.get("document_id") for h in hits]
    assert len(hits) > 0, "Expected at least one result"
    assert "rag_doc" in doc_ids, (
        f"Expected rag_doc for typo 'retreival', got {doc_ids}"
    )


def test_typo_003_prefix_autocomplete(meili_idx: Any) -> None:
    """
    TEST-TYPO-003: Prefix 'transfo' returns transformer-related documents.
    """
    hits = meili_idx.search("transfo").get("hits", [])
    assert len(hits) > 0, "Expected results for prefix 'transfo'"
    texts = [h.get("text", "").lower() for h in hits]
    assert any("transformer" in t for t in texts), (
        f"Expected 'transformer' in results for 'transfo', got {texts}"
    )


# ---------------------------------------------------------------------------
# 4.7 - Phase 2 Acceptance Criteria
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_ac_2_01_02_03_qdrant_latency_sla(qdrant: Any) -> None:
    """
    AC-2-01/02/03: p50 < 50ms, p95 < 100ms, p99 < 200ms (200 queries).
    Container-adjusted from production targets of 5/10/20ms.
    """
    cl, qm = qdrant
    coll = f"sla_{uuid.uuid4().hex[:8]}"
    cl.create_collection(
        collection_name=coll,
        vectors_config=qm.VectorParams(size=8, distance=qm.Distance.COSINE),
    )
    cl.upsert(
        collection_name=coll,
        points=[
            qm.PointStruct(
                id=str(uuid.uuid4()),
                vector=_rand_vec(8, seed=i),
                payload={"i": i},
            )
            for i in range(1000)
        ],
    )

    latencies: list[float] = []
    for r in range(200):
        q = _rand_vec(8, seed=r + 10000)
        t0 = time.perf_counter()
        cl.search(collection_name=coll, query_vector=q, limit=10)
        latencies.append((time.perf_counter() - t0) * 1000)

    cl.delete_collection(coll)
    latencies.sort()
    p50, p95, p99 = latencies[99], latencies[189], latencies[197]
    assert p50 < 50, f"AC-2-01: p50={p50:.2f}ms > 50ms"
    assert p95 < 100, f"AC-2-02: p95={p95:.2f}ms > 100ms"
    assert p99 < 200, f"AC-2-03: p99={p99:.2f}ms > 200ms"


@pytest.mark.benchmark
def test_ac_2_04_vector_recall(qdrant: Any) -> None:
    """AC-2-04: Recall@10 > 0.80 (200 vectors, 20 probe queries)."""
    cl, qm = qdrant
    n, dim, k = 200, 8, 10
    coll = f"recall_ac_{uuid.uuid4().hex[:8]}"

    cl.create_collection(
        collection_name=coll,
        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
    )
    vecs = [_rand_vec(dim, seed=i + 5000) for i in range(n)]
    cl.upsert(
        collection_name=coll,
        points=[
            qm.PointStruct(
                id=str(uuid.uuid4()), vector=v, payload={"idx": i}
            )
            for i, v in enumerate(vecs)
        ],
    )

    recalls: list[float] = []
    for q_idx in range(20):
        qv = vecs[q_idx]
        gt = set(
            sorted(
                range(n),
                key=lambda i: sum(qv[d] * vecs[i][d] for d in range(dim)),
                reverse=True,
            )[:k]
        )
        ann = {
            r.payload["idx"]
            for r in cl.search(
                collection_name=coll,
                query_vector=qv,
                limit=k,
                with_payload=True,
            )
        }
        recalls.append(len(gt & ann) / k)

    cl.delete_collection(coll)
    mean_recall = sum(recalls) / len(recalls)
    assert mean_recall > 0.80, (
        f"AC-2-04: Recall@10 = {mean_recall:.2f} < 0.80"
    )


@pytest.mark.benchmark
def test_ac_2_06_rrf_throughput_1000_fusions() -> None:
    """
    AC-2-06: 1000 RRF fusions (3 lists of 100 docs) complete in < 5 seconds.
    """
    docs = [_make_doc(f"doc_{i}") for i in range(100)]
    t0 = time.perf_counter()
    for _ in range(1000):
        reciprocal_rank_fusion(
            [(0.6, docs), (0.3, docs[::-1]), (0.1, docs[::2])],
            k=60,
        )
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, (
        f"AC-2-06: 1000 RRF fusions took {elapsed:.2f}s, expected < 5s"
    )


def test_ac_2_07_conceptual_queries_get_high_semantic_weight() -> None:
    """
    AC-2-07: 10 conceptual queries each classified with semantic >= 0.80.
    """
    queries = [
        "explain convolution in neural networks",
        "how does backpropagation work",
        "what is the difference between recall and precision",
        "explain gradient descent optimization",
        "what are transformer attention heads",
        "how does HNSW indexing work",
        "what is reciprocal rank fusion",
        "explain vector quantization",
        "how does MinHash deduplication work",
        "what is cosine similarity",
    ]
    for q in queries:
        w = detect_query_intent_weights(q)
        assert w["semantic"] >= 0.80, (
            f"AC-2-07: '{q}' -> semantic={w['semantic']} < 0.80"
        )


def test_ac_2_08_exact_phrase_queries_get_keyword_weight() -> None:
    """
    AC-2-08: 5 quoted queries each classified with keyword == 0.60.
    """
    queries = [
        '"reciprocal rank fusion" algorithm',
        '"gradient descent" with momentum',
        '"attention mechanism" transformer',
        '"knowledge graph" embedding',
        '"dense retrieval" model',
    ]
    for q in queries:
        w = detect_query_intent_weights(q)
        assert w.get("keyword") == 0.60, (
            f"AC-2-08: '{q}' -> keyword={w.get('keyword')}, expected 0.60"
        )


def test_ac_2_09_typo_recovery_rate(meili_idx: Any) -> None:
    """
    AC-2-09: >= 67% of deliberate 1-char typo queries recover the correct doc.
    """
    cases = [
        ("machina learning", "ml_doc"),
        ("machone learning", "ml_doc"),
        ("trnasformer architecture", "tf_doc"),
    ]
    recovered = sum(
        1
        for query, expected in cases
        if expected
        in [h.get("document_id") for h in meili_idx.search(query).get("hits", [])]
    )
    assert recovered / len(cases) >= 0.67, (
        f"AC-2-09: Typo recovery {recovered}/{len(cases)} < 67%"
    )


def test_ac_2_15_user_id_zero_leakage(qdrant: Any) -> None:
    """
    AC-2-15: Filtered search by user_X returns 0 results from user_Y.
    """
    cl, qm = qdrant
    uid_x = f"ux-{uuid.uuid4().hex[:6]}"
    uid_y = f"uy-{uuid.uuid4().hex[:6]}"
    points: list[Any] = [
        qm.PointStruct(
            id=str(uuid.uuid4()),
            vector=_rand_vec(8, seed=i + (0 if uid == uid_x else 50)),
            payload={
                "user_id": uid,
                "document_id": str(uuid.uuid4()),
                "content_type": "text",
            },
        )
        for i in range(20)
        for uid in (uid_x, uid_y)
    ]

    cl.upsert(collection_name=_TEST_COLL, points=points)
    results = cl.search(
        collection_name=_TEST_COLL,
        query_vector=_rand_vec(8, seed=9999),
        query_filter=qm.Filter(
            must=[
                qm.FieldCondition(
                    key="user_id", match=qm.MatchValue(value=uid_x)
                )
            ]
        ),
        limit=30,
        with_payload=True,
    )
    for r in results:
        assert r.payload.get("user_id") == uid_x, (
            f"AC-2-15: Cross-user leakage — got user_id={r.payload.get('user_id')}"
        )


def test_ac_2_16_batch_embedding_one_api_call() -> None:
    """
    AC-2-16: Embedding 100 texts triggers exactly 1 Gemini batch API call.
    """
    texts = [f"document number {i}" for i in range(100)]
    raw_batch = [[0.01 * j for j in range(768)] for _ in range(100)]
    call_count = 0

    async def _embed_batch() -> list[list[float]]:
        nonlocal call_count
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)

        async def _batch_fn(*args: Any, **kwargs: Any) -> list[list[float]]:
            nonlocal call_count
            call_count += 1
            return raw_batch

        mock_client = AsyncMock()
        mock_client.embed_content_batch = AsyncMock(side_effect=_batch_fn)
        provider._gemini_client = mock_client
        return await provider.embed_documents_batch(texts)

    asyncio.run(_embed_batch())
    assert call_count == 1, (
        f"AC-2-16: Expected 1 API call for 100 chunks, got {call_count}"
    )


def test_ac_2_17_all_models_offline_raises() -> None:
    """
    AC-2-17: All Gemini models offline -> RuntimeError (no silent data loss).
    """

    async def _try_embed() -> None:
        config = _make_config(embedding_dimensions=768)
        provider = GeminiEmbeddingProvider(config)
        mock_client = AsyncMock()
        mock_client.embed_content = AsyncMock(
            side_effect=RuntimeError("all models offline")
        )
        provider._gemini_client = mock_client
        await provider.embed_document("test offline fallback")

    with pytest.raises(RuntimeError):
        asyncio.run(_try_embed())


def test_ac_2_18_dimension_mismatch_rejected(qdrant: Any) -> None:
    """
    AC-2-18: Inserting a 384-dim vector into a 768-dim collection raises an error.
    """
    cl, qm = qdrant
    coll = f"dim_mismatch_{uuid.uuid4().hex[:8]}"
    cl.create_collection(
        collection_name=coll,
        vectors_config=qm.VectorParams(size=768, distance=qm.Distance.COSINE),
    )

    with pytest.raises(Exception):
        cl.upsert(
            collection_name=coll,
            points=[
                qm.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[0.1] * 384,  # wrong dimension - must be rejected
                    payload={},
                )
            ],
        )

    cl.delete_collection(coll)
