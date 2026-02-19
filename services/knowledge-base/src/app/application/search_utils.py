import hashlib
import math
import re
from collections import defaultdict
from datetime import UTC, datetime
from random import Random
from typing import Any


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def query_hash(query: str) -> str:
    return hashlib.sha256(normalize_query(query).encode("utf-8")).hexdigest()


def select_ef_search(latency_budget_ms: int) -> int:
    if latency_budget_ms < 50:
        return 10
    if latency_budget_ms < 100:
        return 64
    return 200


def detect_query_intent_weights(query: str) -> dict[str, float]:
    normalized = normalize_query(query)
    if normalized.startswith("what is") or normalized.startswith("explain"):
        return {"semantic": 0.8, "keyword": 0.15, "typo": 0.05}
    if "find" in normalized or "document" in normalized:
        return {"semantic": 0.6, "keyword": 0.3, "typo": 0.1}
    if any(token in normalized for token in ("pdf", "last week", "show me", "from")):
        return {"semantic": 0.45, "keyword": 0.4, "typo": 0.15}
    return {"semantic": 0.6, "keyword": 0.3, "typo": 0.1}


def reciprocal_rank_fusion(
    results_lists: list[tuple[float, list[dict[str, Any]]]],
    k: int = 60,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for source_weight, results in results_lists:
        for rank, doc in enumerate(results, start=1):
            document_id = str(doc["document_id"])
            scores[document_id] += source_weight * (1.0 / (k + rank))
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def deterministic_embedding(text: str, dimension: int = 384) -> list[float]:
    seed_hex = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    rng = Random(int(seed_hex, 16))
    vector = [rng.uniform(-1.0, 1.0) for _ in range(dimension)]
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def recency_score(created_at: str | None, lambda_decay: float = 0.1) -> float:
    if not created_at:
        return 0.5
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        days_old = max(0.0, (now - created.astimezone(UTC)).total_seconds() / 86400.0)
        days_old = min(days_old, 30.0)
        return math.exp(-lambda_decay * days_old)
    except Exception:
        return 0.5


def engagement_score(clicks: int | None, impressions: int | None) -> float:
    safe_clicks = max(0, clicks or 0)
    safe_impressions = max(0, impressions or 0)
    return (safe_clicks + 1.0) / (safe_impressions + 2.0)


def bucket_context_score(
    document_bucket_id: str | None, active_bucket_id: str | None
) -> float:
    if (
        active_bucket_id
        and document_bucket_id
        and active_bucket_id == document_bucket_id
    ):
        return 1.0
    return 0.5
