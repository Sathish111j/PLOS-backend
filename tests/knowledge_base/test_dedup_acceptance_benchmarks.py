import random
import time

import pytest
from app.application.deduplication import (
    build_dedup_computation,
    hamming_distance_64,
    minhash_similarity,
)


def _variant(base: str, index: int) -> str:
    if index % 3 == 0:
        return f"  {base.upper()}  "
    if index % 3 == 1:
        return base.replace("knowledge", "knowledge   ").replace("pipeline", "pipeline\n")
    return base


@pytest.mark.benchmark
def test_dedup_exact_detection_rate_threshold() -> None:
    base_text = "knowledge pipeline stores normalized text for exact dedup checks"
    expected = build_dedup_computation(base_text).normalized_sha256

    cases = [_variant(base_text, i) for i in range(120)]
    matches = sum(
        1
        for case in cases
        if build_dedup_computation(case).normalized_sha256 == expected
    )
    detection_rate = matches / len(cases)

    assert detection_rate >= 0.99


@pytest.mark.benchmark
def test_dedup_near_recall_threshold() -> None:
    random.seed(42)
    base = (
        "semantic chunk retrieval and storage layer should keep metadata stable for ranking "
        "and respect dedup signatures across ingestion steps "
    ) * 10

    positives = []
    for i in range(50):
        edited = base
        edited = edited.replace("ranking", f"ranking-{i}", 1)
        edited = edited.replace("stable", "reliable", 1)
        positives.append(edited)

    base_sig = build_dedup_computation(base)

    hits = 0
    for text in positives:
        candidate = build_dedup_computation(text)
        distance = hamming_distance_64(
            base_sig.simhash & ((1 << 64) - 1),
            candidate.simhash & ((1 << 64) - 1),
        )
        if distance <= 12:
            hits += 1

    recall = hits / len(positives)
    assert recall >= 0.90


@pytest.mark.benchmark
def test_dedup_semantic_false_positive_rate_threshold() -> None:
    related = (
        "system records immutable checkpoints for extraction chunking and embedding stages "
        "to keep integrity verifiable"
    )
    unrelated_samples = [
        "weather forecast includes rain and temperature in coastal cities",
        "football tactics rely on compact defensive blocks and transitions",
        "bread recipe uses flour yeast water salt and proofing steps",
        "astronomy catalog tracks redshift and luminosity for distant galaxies",
        "database vacuum and indexing maintenance optimize transaction throughput",
    ]

    related_sig = build_dedup_computation(related)
    semantic_hits = 0
    for sample in unrelated_samples:
        sample_sig = build_dedup_computation(sample)
        similarity = minhash_similarity(
            related_sig.minhash_signature,
            sample_sig.minhash_signature,
        )
        if similarity >= 0.85:
            semantic_hits += 1

    false_positive_rate = semantic_hits / len(unrelated_samples)
    assert false_positive_rate <= 0.05


@pytest.mark.benchmark
def test_dedup_algorithm_overhead_threshold() -> None:
    texts = [
        (
            "knowledge graph enrichment and retrieval context ranking "
            "for user intent aware search and summarization"
        )
        * 6
        for _ in range(250)
    ]

    baseline_start = time.perf_counter()
    baseline_hashes = [hash(text) for text in texts]
    baseline_elapsed = time.perf_counter() - baseline_start

    dedup_start = time.perf_counter()
    dedup_hashes = [build_dedup_computation(text).normalized_sha256 for text in texts]
    dedup_elapsed = time.perf_counter() - dedup_start

    assert len(baseline_hashes) == len(dedup_hashes)
    assert dedup_elapsed <= max(2.5, baseline_elapsed * 25)


@pytest.mark.benchmark
def test_dedup_storage_reduction_threshold() -> None:
    corpus = []
    for index in range(200):
        base = f"chunk-{index % 60} stable content for storage reduction"
        if index % 5 == 0:
            corpus.append(base.upper())
        elif index % 7 == 0:
            corpus.append(base.replace("storage", "storage   "))
        else:
            corpus.append(base)

    total = len(corpus)
    unique = len({build_dedup_computation(text).normalized_sha256 for text in corpus})
    reduction = 1.0 - (unique / total)

    assert reduction >= 0.40
