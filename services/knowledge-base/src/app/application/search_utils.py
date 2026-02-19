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

    conceptual_prefixes = (
        "what is",
        "explain",
        "how does",
        "why does",
        "what are",
    )
    if normalized.startswith(conceptual_prefixes):
        return {"semantic": 0.8, "keyword": 0.15, "typo": 0.05}

    if re.search(r'"[^"]+"', query) or re.search(r"\b[A-Z]{2,}-?\d+[A-Z0-9-]*\b", query):
        return {"semantic": 0.3, "keyword": 0.6, "typo": 0.1}

    if "find" in normalized or "document" in normalized or "report" in normalized:
        return {"semantic": 0.6, "keyword": 0.3, "typo": 0.1}

    if len(normalized) <= 12 and re.search(r"[^a-z0-9\s\-]", normalized):
        return {"semantic": 0.55, "keyword": 0.15, "typo": 0.3}

    if any(
        token in normalized
        for token in (
            "pdf",
            "docx",
            "ppt",
            "xlsx",
            "last week",
            "from",
            "before",
            "after",
            "between",
            "author",
            "bucket",
        )
    ):
        return {"semantic": 0.6, "keyword": 0.3, "typo": 0.1}

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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def apply_mmr_diversity(
    *,
    query: str,
    results: list[dict[str, Any]],
    top_k: int,
    lambda_weight: float = 0.7,
) -> list[dict[str, Any]]:
    if top_k <= 0 or not results:
        return []

    working = list(results)
    if len(working) <= 1:
        return working[:top_k]

    query_vec = deterministic_embedding(query, 128)
    for item in working:
        text = str(item.get("text_preview") or item.get("title") or "")
        item["_mmr_vec"] = deterministic_embedding(text, 128)
        item["_mmr_rel"] = float(item.get("score") or 0.0)
        item["_mmr_query_sim"] = _cosine_similarity(query_vec, item["_mmr_vec"])

    selected: list[dict[str, Any]] = []
    remaining = working

    while remaining and len(selected) < top_k:
        best_item = None
        best_score = float("-inf")
        for candidate in remaining:
            if not selected:
                novelty_penalty = 0.0
            else:
                novelty_penalty = max(
                    _cosine_similarity(candidate["_mmr_vec"], chosen["_mmr_vec"])
                    for chosen in selected
                )

            mmr_score = (
                lambda_weight * candidate["_mmr_rel"]
                + 0.15 * candidate["_mmr_query_sim"]
                - (1.0 - lambda_weight) * novelty_penalty
            )
            if mmr_score > best_score:
                best_score = mmr_score
                best_item = candidate

        if best_item is None:
            break

        selected.append(best_item)
        remaining = [item for item in remaining if item is not best_item]

    for item in selected:
        item.pop("_mmr_vec", None)
        item.pop("_mmr_rel", None)
        item.pop("_mmr_query_sim", None)
    return selected
