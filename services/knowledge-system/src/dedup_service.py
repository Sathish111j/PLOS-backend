"""
Deduplication Service for PLOS Knowledge System - CPU-Optimized
Hash-based exact duplicate detection + MinHash/SimHash + semantic similarity

Sweet-spot: Embeddings are verification tools, not first filters
"""

import hashlib
from typing import List, Optional, Tuple

import mmh3
from datasketch import MinHash, MinHashLSH

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class DeduplicationService:
    """
    CPU-optimized deduplication with escalation strategy.

    Stages:
    1. Exact Dedup - Hash (SHA/xxHash) - O(1), zero false positives
    2. Near Dedup - MinHash/SimHash - Cheap semantic pruning
    3. Final Check - Cosine similarity - Run on small candidate set only

    Sweet-spot: Min Hash before embeddings = 10-100x faster
    """

    def __init__(
        self,
        similarity_threshold: float = 0.95,
        minhash_threshold: float = 0.85,
        num_perm: int = 128,
    ):
        """
        Initialize deduplication service.

        Args:
            similarity_threshold: Cosine similarity threshold (0-1)
            minhash_threshold: MinHash similarity threshold (0-1)
            num_perm: Number of permutations for MinHash (higher = more accurate)
        """
        self.similarity_threshold = similarity_threshold
        self.minhash_threshold = minhash_threshold
        self.num_perm = num_perm

        # LSH index for fast near-duplicate detection
        self.lsh = MinHashLSH(threshold=minhash_threshold, num_perm=num_perm)
        self._hash_cache = set()  # Exact dedup cache

    def compute_hash(self, content: str) -> str:
        """
        Stage 1: Compute SHA-256 hash for exact dedup (O(1)).

        Args:
            content: Text content to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        normalized = content.lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def compute_minhash(self, content: str) -> MinHash:
        """
        Stage 2: Compute MinHash for near-dedup (cheap semantic pruning).

        Args:
            content: Text content

        Returns:
            MinHash object
        """
        m = MinHash(num_perm=self.num_perm)

        # Tokenize (simple word-based)
        words = content.lower().split()

        # Add shingles (3-grams of words)
        for i in range(len(words) - 2):
            shingle = " ".join(words[i : i + 3])
            m.update(shingle.encode("utf-8"))

        return m

    def compute_simhash(self, content: str) -> int:
        """
        Alternative Stage 2: Compute SimHash for near-dedup.

        SimHash is faster than MinHash but slightly less accurate.

        Args:
            content: Text content

        Returns:
            64-bit SimHash fingerprint
        """
        # Tokenize
        words = content.lower().split()

        # Use MurmurHash3 for speed
        hash_bits = 64
        v = [0] * hash_bits

        for word in words:
            # Hash each word
            h = mmh3.hash64(word.encode("utf-8"))[0]

            # Update bit vector
            for i in range(hash_bits):
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1

        # Generate final fingerprint
        fingerprint = 0
        for i in range(hash_bits):
            if v[i] > 0:
                fingerprint |= 1 << i

        return fingerprint

    def is_exact_duplicate(self, content: str, existing_hashes: set) -> bool:
        """
        Stage 1: Check exact duplicate using hash (O(1)).

        Args:
            content: Content to check
            existing_hashes: Set of existing content hashes

        Returns:
            True if exact duplicate exists
        """
        content_hash = self.compute_hash(content)
        return content_hash in existing_hashes

    def is_near_duplicate_minhash(
        self, content: str, content_id: str, check_only: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Stage 2: Check near-duplicate using MinHash LSH (fast).

        Args:
            content: Content to check
            content_id: Unique ID for this content
            check_only: If True, don't insert into LSH

        Returns:
            Tuple of (is_duplicate, duplicate_id)
        """
        m = self.compute_minhash(content)

        # Query LSH index
        candidates = self.lsh.query(m)

        if candidates:
            logger.info(f"MinHash found {len(candidates)} near-duplicate candidates")
            # Insert if not check-only
            if not check_only:
                self.lsh.insert(content_id, m)
            return True, candidates[0] if candidates else None

        # Insert if not check-only
        if not check_only:
            self.lsh.insert(content_id, m)

        return False, None

    def is_near_duplicate_simhash(
        self,
        content: str,
        existing_simhashes: List[Tuple[str, int]],
        hamming_threshold: int = 3,
    ) -> Tuple[bool, Optional[str]]:
        """
        Stage 2 (Alternative): Check near-duplicate using SimHash.

        Args:
            content: Content to check
            existing_simhashes: List of (id, simhash) tuples
            hamming_threshold: Max Hamming distance to consider duplicate

        Returns:
            Tuple of (is_duplicate, duplicate_id)
        """
        content_simhash = self.compute_simhash(content)

        for doc_id, existing_hash in existing_simhashes:
            # Compute Hamming distance (count differing bits)
            hamming_dist = bin(content_simhash ^ existing_hash).count("1")

            if hamming_dist <= hamming_threshold:
                logger.info(f"SimHash match: hamming distance={hamming_dist}")
                return True, doc_id

        return False, None

    def is_semantic_duplicate(
        self,
        content_embedding: List[float],
        existing_embeddings: List[Tuple[str, List[float]]],
    ) -> Tuple[bool, Optional[str]]:
        """
        Stage 3: Final verification with semantic similarity (expensive).

        Only run this on small candidate sets from Stage 2.

        Args:
            content_embedding: Embedding vector of content to check
            existing_embeddings: List of (item_id, embedding) tuples

        Returns:
            Tuple of (is_duplicate, duplicate_item_id)
        """
        if not existing_embeddings:
            return False, None

        logger.info(f"Semantic check on {len(existing_embeddings)} candidates")

        max_similarity = 0.0
        most_similar_id = None

        for item_id, existing_emb in existing_embeddings:
            similarity = self._cosine_similarity(content_embedding, existing_emb)

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_id = item_id

        is_duplicate = max_similarity >= self.similarity_threshold

        if is_duplicate:
            logger.info(
                f"Semantic duplicate detected: similarity={max_similarity:.3f}, "
                f"item_id={most_similar_id}"
            )

        return is_duplicate, most_similar_id if is_duplicate else None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimensions")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


def chunk_text(
    text: str, chunk_size: int = 500, overlap: int = 100, min_chunk_size: int = 50
) -> List[str]:
    """
    Smart text chunking with sliding window and sentence-aware overlap.

    Args:
        text: Text to chunk
        chunk_size: Target size of each chunk (characters)
        overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum chunk size to keep

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text] if len(text) >= min_chunk_size else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:]
            if len(chunk) >= min_chunk_size:
                chunks.append(chunk)
            break

        # Find sentence boundary
        chunk_text = text[start:end]
        sentence_ends = [".", "!", "?", "\n"]
        best_break = -1

        for i in range(len(chunk_text) - 1, max(0, len(chunk_text) - 100), -1):
            if chunk_text[i] in sentence_ends:
                best_break = i + 1
                break

        if best_break > 0:
            chunk = text[start : start + best_break]
        else:
            chunk = chunk_text

        if len(chunk) >= min_chunk_size:
            chunks.append(chunk.strip())

        if start + len(chunk) >= len(text):
            break
        start += len(chunk) - overlap

    logger.debug(f"Chunked text into {len(chunks)} chunks")

    return chunks
