# Hybrid Search System (Section 2.3–2.5)

## 2.3 Hybrid Search Architecture

PLOS knowledge-base uses a three-tier hybrid search pipeline and fuses ranked lists with Reciprocal Rank Fusion (RRF).

| Tier | Engine | Target Weight | Strength |
|---|---|---:|---|
| Tier 1: Semantic | Qdrant HNSW | 60% | Concepts, paraphrases, semantic recall |
| Tier 2: Full-Text | PostgreSQL tsvector + GIN | 30% | Exact phrases and technical terms |
| Tier 3: Typo-Tolerant | Typo similarity layer | 10% | Misspellings and noisy user input |

### RRF Formula

For each document and source list:

`RRF += source_weight * (1 / (k + rank))`, with `k = 60`.

Documents are sorted by fused score descending.

### Dynamic Query Intent Classification

The query intent classifier adjusts tier weights using lightweight query signals:

- Conceptual: `semantic=0.80`, `keyword=0.15`, `typo=0.05`
- Exact phrase / code-like: `semantic=0.30`, `keyword=0.60`, `typo=0.10`
- Navigational: `semantic=0.60`, `keyword=0.30`, `typo=0.10`
- Typo-likely: `semantic=0.55`, `keyword=0.15`, `typo=0.30`
- Filter-heavy: default fusion weights with filters applied first

### Caching Strategy

Two-layer cache:

- L1: in-process LRU, 1000 entries, TTL 5 minutes
- L2: Redis, query-keyed, TTL 1 hour for larger result sets (shorter for sparse sets)

Cache key includes normalized query hash, user id, filter fingerprint, and relevant request knobs.

## 2.4 Cross-Encoder Reranking

After hybrid fusion, reranking runs on top candidates:

- CPU default model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- GPU preferred model: `BAAI/bge-reranker-base` (if CUDA is available)
- Default batch size: `32`

Final ranking score blend:

- Cross-encoder relevance: `60%`
- Recency: `15%`
- Engagement: `15%`
- Bucket context: `10%`

Post-rerank diversity uses MMR with `lambda=0.7`.

## 2.5 Acceptance Criteria

These are treated as production SLO/quality gates and should be measured in dedicated benchmark runs:

- Qdrant latency p50/p95/p99
- Recall@10 and semantic NDCG@10
- Exact phrase precision
- Typo recovery
- End-to-end latency and index freshness
- Reranking uplift and diversity targets
- L1/L2 cache hit rates

## Current Implementation Notes

- Semantic tier: implemented via Qdrant HNSW.
- Full-text tier: implemented via PostgreSQL `tsvector` search.
- Typo tier: implemented with PostgreSQL similarity-based fallback.
- RRF (`k=60`), dynamic intent weighting, reranking, and MMR diversity are implemented.
- L1 + L2 cache layers are implemented.

If strict Meilisearch integration is required for typo tier, add a dedicated Meilisearch index service and swap the typo tier adapter to Meilisearch queries.
