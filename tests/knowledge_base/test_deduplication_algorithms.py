from app.application.deduplication import (
    build_dedup_computation,
    build_integrity_chain,
    hamming_distance_64,
    minhash_similarity,
)


def test_exact_dedup_normalization_is_whitespace_and_case_invariant() -> None:
    left = "Hello   WORLD\nThis is a test."
    right = "hello world this is a test."

    left_result = build_dedup_computation(left)
    right_result = build_dedup_computation(right)

    assert left_result.normalized_sha256 == right_result.normalized_sha256


def test_near_duplicate_simhash_distance_is_small_for_minor_edits() -> None:
    base = (
        "personal knowledge base ingestion pipeline with retrieval and semantic chunking "
        "should handle metadata and storage efficiently " * 8
    )
    edited = base.replace("storage efficiently", "storage very efficiently", 1)

    left_result = build_dedup_computation(base)
    right_result = build_dedup_computation(edited)

    distance = hamming_distance_64(
        left_result.simhash & ((1 << 64) - 1),
        right_result.simhash & ((1 << 64) - 1),
    )
    assert distance < 16


def test_semantic_minhash_similarity_is_high_for_paraphrase_like_text() -> None:
    first = (
        "The system stores documents immutably and computes signatures for deduplication. "
        "It tracks integrity checksums at each stage for auditing and trust. " * 5
    )
    second = (
        "The system persists documents immutably and computes deduplication signatures. "
        "It records integrity checksums across each stage for auditing and trust. " * 5
    )

    first_result = build_dedup_computation(first)
    second_result = build_dedup_computation(second)

    similarity = minhash_similarity(
        first_result.minhash_signature,
        second_result.minhash_signature,
    )
    assert similarity > 0.3


def test_integrity_chain_preserves_previous_links() -> None:
    checkpoints = build_integrity_chain(
        ingestion_bytes=b"raw-bytes",
        extracted_text="normalized text",
        chunk_texts=["chunk one", "chunk two"],
    )

    assert len(checkpoints) == 4
    assert checkpoints[0].previous_checksum_md5 is None
    assert checkpoints[1].previous_checksum_md5 == checkpoints[0].checksum_md5
    assert checkpoints[2].previous_checksum_md5 == checkpoints[1].checksum_md5
    assert checkpoints[3].previous_checksum_md5 == checkpoints[2].checksum_md5
