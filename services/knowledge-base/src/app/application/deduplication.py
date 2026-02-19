from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

FNV64_OFFSET_BASIS = 14695981039346656037
FNV64_PRIME = 1099511628211
UINT64_MASK = (1 << 64) - 1
SIGN_BIT_64 = 1 << 63
UINT64_MOD = 1 << 64
MINHASH_PERMUTATIONS = 128
MINHASH_BANDS = 16
MINHASH_ROWS_PER_BAND = 8
MINHASH_PRIME = 18446744073709551557
SIMHASH_BANDS = 4
SIMHASH_BITS_PER_BAND = 16


@dataclass(frozen=True)
class IntegrityCheckpoint:
    stage_name: str
    checksum_md5: str
    previous_checksum_md5: str | None
    chain_hash_sha256: str
    is_verified: bool = True


@dataclass(frozen=True)
class DedupComputation:
    normalized_content: str
    normalized_sha256: str
    simhash: int
    simhash_band_hashes: list[int]
    minhash_signature: list[int]
    minhash_band_hashes: list[int]


def to_signed_bigint(value: int) -> int:
    masked = value & UINT64_MASK
    if masked >= SIGN_BIT_64:
        return masked - UINT64_MOD
    return masked


def to_unsigned_bigint(value: int) -> int:
    if value < 0:
        return value + UINT64_MOD
    return value


def normalize_for_dedup(text: str, *, remove_punctuation: bool = False) -> str:
    normalized = unicodedata.normalize("NFC", text or "")
    normalized = normalized.lower()
    if remove_punctuation:
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.category(character).startswith("P")
        )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def md5_hex(raw: bytes) -> str:
    return hashlib.md5(raw).hexdigest()


def fnv1a_64(raw: bytes) -> int:
    value = FNV64_OFFSET_BASIS
    for byte in raw:
        value ^= byte
        value = (value * FNV64_PRIME) & UINT64_MASK
    return value


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"\s+", text.strip()) if token]


def shingles(text: str, *, size: int = 3) -> list[str]:
    tokens = _tokens(text)
    if not tokens:
        return []
    if len(tokens) < size:
        return [" ".join(tokens)]
    return [" ".join(tokens[index : index + size]) for index in range(0, len(tokens) - size + 1)]


def simhash_64(shingle_values: Iterable[str]) -> int:
    vector = [0] * 64
    frequencies: dict[str, int] = {}
    for shingle in shingle_values:
        frequencies[shingle] = frequencies.get(shingle, 0) + 1

    if not frequencies:
        return 0

    for shingle, weight in frequencies.items():
        hashed = fnv1a_64(shingle.encode("utf-8"))
        for bit_index in range(64):
            if (hashed >> bit_index) & 1:
                vector[bit_index] += weight
            else:
                vector[bit_index] -= weight

    fingerprint = 0
    for bit_index, score in enumerate(vector):
        if score >= 0:
            fingerprint |= 1 << bit_index
    return fingerprint & UINT64_MASK


def simhash_band_hashes(simhash_value: int) -> list[int]:
    bands: list[int] = []
    for index in range(SIMHASH_BANDS):
        shift = index * SIMHASH_BITS_PER_BAND
        band_value = (simhash_value >> shift) & ((1 << SIMHASH_BITS_PER_BAND) - 1)
        bands.append(to_signed_bigint(band_value))
    return bands


def hamming_distance_64(left: int, right: int) -> int:
    return ((left ^ right) & UINT64_MASK).bit_count()


def _minhash_coefficients() -> tuple[list[int], list[int]]:
    # Deterministic pseudo-random coefficients for reproducibility.
    a_values: list[int] = []
    b_values: list[int] = []
    seed = 1469598103934665603
    for _ in range(MINHASH_PERMUTATIONS):
        seed = (seed * 6364136223846793005 + 1442695040888963407) & UINT64_MASK
        a_values.append((seed % (MINHASH_PRIME - 1)) + 1)
        seed = (seed * 2862933555777941757 + 3037000493) & UINT64_MASK
        b_values.append(seed % MINHASH_PRIME)
    return a_values, b_values


def minhash_signature_128(shingle_values: Iterable[str]) -> list[int]:
    unique_hashes = {
        fnv1a_64(shingle.encode("utf-8")) % MINHASH_PRIME for shingle in shingle_values
    }
    if not unique_hashes:
        return [0] * MINHASH_PERMUTATIONS

    a_values, b_values = _minhash_coefficients()
    signature: list[int] = []

    for index in range(MINHASH_PERMUTATIONS):
        a_value = a_values[index]
        b_value = b_values[index]
        minimum = min(
            ((a_value * shingle_hash + b_value) % MINHASH_PRIME)
            for shingle_hash in unique_hashes
        )
        signature.append(to_signed_bigint(minimum))

    return signature


def minhash_band_hashes(signature: list[int]) -> list[int]:
    if len(signature) != MINHASH_PERMUTATIONS:
        raise ValueError(
            f"Expected {MINHASH_PERMUTATIONS} minhash values, got {len(signature)}"
        )

    band_hashes: list[int] = []
    for band_index in range(MINHASH_BANDS):
        start = band_index * MINHASH_ROWS_PER_BAND
        end = start + MINHASH_ROWS_PER_BAND
        band = signature[start:end]
        encoded = "|".join(str(value) for value in band).encode("utf-8")
        digest = hashlib.blake2b(encoded, digest_size=8).digest()
        band_hashes.append(to_signed_bigint(int.from_bytes(digest, byteorder="big")))

    return band_hashes


def minhash_similarity(left: list[int], right: list[int]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    matches = sum(1 for a_value, b_value in zip(left, right) if a_value == b_value)
    return matches / len(left)


def build_dedup_computation(text: str) -> DedupComputation:
    exact_normalized = normalize_for_dedup(text, remove_punctuation=False)
    fuzzy_normalized = normalize_for_dedup(text, remove_punctuation=True)
    shingle_values = shingles(fuzzy_normalized, size=3)
    token_values = _tokens(fuzzy_normalized)

    simhash_value = simhash_64(shingle_values)
    minhash_signature = minhash_signature_128(token_values)

    return DedupComputation(
        normalized_content=exact_normalized,
        normalized_sha256=sha256_hex(exact_normalized),
        simhash=to_signed_bigint(simhash_value),
        simhash_band_hashes=simhash_band_hashes(simhash_value),
        minhash_signature=minhash_signature,
        minhash_band_hashes=minhash_band_hashes(minhash_signature),
    )


def build_integrity_chain(
    *,
    ingestion_bytes: bytes,
    extracted_text: str,
    chunk_texts: list[str],
) -> list[IntegrityCheckpoint]:
    extraction_bytes = extracted_text.encode("utf-8")
    chunked_bytes = "\n\n".join(chunk_texts).encode("utf-8")

    stages: list[tuple[str, bytes]] = [
        ("ingestion", ingestion_bytes),
        ("extraction", extraction_bytes),
        ("chunking", chunked_bytes),
        ("embedding", chunked_bytes),
    ]

    checkpoints: list[IntegrityCheckpoint] = []
    previous_checksum: str | None = None
    previous_chain = ""

    for stage_name, raw in stages:
        checksum = md5_hex(raw)
        payload = f"{previous_chain}:{stage_name}:{checksum}".encode("utf-8")
        chain_hash = hashlib.sha256(payload).hexdigest()
        checkpoints.append(
            IntegrityCheckpoint(
                stage_name=stage_name,
                checksum_md5=checksum,
                previous_checksum_md5=previous_checksum,
                chain_hash_sha256=chain_hash,
                is_verified=True,
            )
        )
        previous_checksum = checksum
        previous_chain = chain_hash

    return checkpoints
