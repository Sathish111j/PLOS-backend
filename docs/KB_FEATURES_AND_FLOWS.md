# Knowledge Base -- Features, Flows and Verification Report

> Auto-generated from live system inspection and deep data-store verification.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Data Stores](#data-stores)
3. [API Endpoints](#api-endpoints)
4. [Feature Catalogue](#feature-catalogue)
5. [Data Flows](#data-flows)
6. [Cross-Store Consistency](#cross-store-consistency)
7. [Test Coverage Summary](#test-coverage-summary)

---

## System Overview

The Knowledge Base (KB) is a microservice (port 8003) that provides personal document
management with intelligent search, automatic organisation, and conversational RAG.

### Architecture Layers

```
api/            FastAPI routers, request/response schemas
application/    Use cases, orchestration (KnowledgeService, search, dedup, chunking)
infrastructure/ DB, cache, vector store, graph store adapters
dependencies/   FastAPI dependency injection wiring
core/           Settings, logging, constants
workers/        Background task consumers
```

### Supporting Infrastructure

| Component     | Port  | Purpose                              |
|---------------|-------|--------------------------------------|
| PostgreSQL    | 5432  | Documents, chunks, buckets, entities |
| Qdrant        | 6333  | 768-dim HNSW vector index            |
| Meilisearch   | 7700  | Typo-tolerant full-text index        |
| Redis         | 6379  | Embedding / dedup / search caches    |
| MinIO         | 9000  | Raw document blob storage            |
| Kafka         | 9092  | Async event bus                      |

---

## Data Stores

### PostgreSQL (primary relational store)

| Table                      | Key Columns                                         |
|----------------------------|-----------------------------------------------------|
| `documents`                | id, title, content, checksum, word_count, created_by, bucket_id, status, tsvector |
| `document_chunks`          | id, document_id, chunk_index, total_chunks, text, token_count, chunk_metadata (JSON with `chunk_id` for Qdrant mapping) |
| `document_integrity_chain` | document_id, stage_name (ingestion/chunking/embedding/extraction), chain_hash, verified |
| `buckets`                  | id, name, user_id, parent_bucket_id, is_default, depth |
| `entities`                 | id, document_id, entity_type, value                |
| `chunk_dedup_signatures`   | document_id, signature hash                        |
| `document_dedup_signatures`| document_id, signature hash                        |

### Qdrant (vector store)

- **Collection**: `documents_768` (768 dimensions, cosine distance, HNSW)
- **Fallback collection**: `documents_fallback_384`
- **Payload fields**: `user_id`, `document_id`, `bucket_id`, `chunk_id`, `text`, `content_type`, `created_at`
- **ID mapping**: Qdrant point ID == `document_chunks.chunk_metadata->>'chunk_id'`

### Meilisearch (typo-tolerant search)

- **Index**: `kb_chunks`
- **Filterable**: `user_id`, `bucket_id`, `content_type`
- **Searchable**: `text`, `content_type`
- **Sortable**: `created_at`
- Typo tolerance enabled (handles 1-2 character misspellings)

### Redis (caching layer)

| Key Prefix        | Purpose                | TTL        |
|--------------------|------------------------|------------|
| `kb:search:v2:*`  | Search result cache    | ~1 hour    |
| `kb:embedding:*`  | Embedding vector cache | ~7 days    |
| `kb:dedup:exact:*`| Dedup signature cache  | ~24 hours  |

---

## API Endpoints

### Health and Observability

| Method | Path      | Description          |
|--------|-----------|----------------------|
| GET    | `/health` | Returns `{"status": "healthy"}` |
| GET    | `/metrics`| Prometheus metrics   |
| GET    | `/`       | Root info            |

### Document Management

| Method | Path        | Description                                    |
|--------|-------------|------------------------------------------------|
| POST   | `/upload`   | Upload document (filename + content_base64)    |
| POST   | `/ingest`   | Kafka-triggered ingest (internal)              |
| GET    | `/documents`| List user documents (auth-scoped)              |

### Bucket Organisation

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/buckets`                        | List user buckets                    |
| POST   | `/buckets`                        | Create custom bucket                 |
| GET    | `/buckets/tree`                   | Hierarchical bucket tree             |
| POST   | `/buckets/{id}/move`              | Move bucket under new parent         |
| DELETE | `/buckets/{id}`                   | Delete bucket (requires target_bucket_id body) |
| POST   | `/buckets/bulk-move-documents`    | Move documents between buckets       |
| POST   | `/buckets/route-preview`          | Preview AI-suggested bucket routing  |

### Search and Chat

| Method | Path      | Description                                       |
|--------|-----------|---------------------------------------------------|
| POST   | `/search` | Hybrid search (semantic + full-text + typo-tolerant) |
| POST   | `/chat`   | RAG chat with source attribution (Gemini)         |

### Knowledge Graph

| Method | Path                              | Description                        |
|--------|-----------------------------------|------------------------------------|
| GET    | `/graph/entity/search`            | Search entities by name/type       |
| GET    | `/graph/entity/{id}`              | Get entity details                 |
| GET    | `/graph/document/{doc_id}/entities`| Entities in a document            |
| DELETE | `/graph/document/{doc_id}`        | Remove document from graph         |
| POST   | `/graph/document/{doc_id}/move`   | Move document graph data           |
| GET    | `/graph/related/{entity_id}`      | Related entities                   |
| GET    | `/graph/path`                     | Path between entities              |
| GET    | `/graph/cooccurring`              | Co-occurring entities              |
| GET    | `/graph/centrality`               | Entity centrality rankings         |
| GET    | `/graph/timeline`                 | Entity timeline                    |
| GET    | `/graph/stats`                    | Graph statistics                   |

### Operations / DLQ

| Method | Path                                        | Description                     |
|--------|---------------------------------------------|---------------------------------|
| GET    | `/ops/embedding-dlq/stats`                  | Dead letter queue statistics    |
| POST   | `/ops/embedding-dlq/reprocess-unreplayable` | Retry failed embeddings         |
| POST   | `/ops/embedding-dlq/purge-unreplayable`     | Purge failed embedding entries  |

---

## Feature Catalogue

### 1. Document Ingestion Pipeline

Upload triggers a multi-stage pipeline:

```
POST /upload  -->  decode base64
              -->  compute MD5 checksum
              -->  persist document row (status: processing)
              -->  semantic chunking (sentence boundaries, token limits)
              -->  generate embeddings (Gemini embedding-001, 768-dim)
              -->  store vectors in Qdrant
              -->  index chunks in Meilisearch
              -->  extract entities (NER)
              -->  AI-based bucket routing
              -->  build integrity chain (4 stages)
              -->  mark status: completed
```

Supported formats: plain text via base64 encoding.

### 2. Deduplication

- **Exact dedup**: MD5 checksum matching at document level
- **Near-duplicate detection**: Chunk-level similarity signatures
- Duplicates are stored (tracked) but flagged at the API level
- Cache layer (`kb:dedup:exact:*`) prevents redundant computation

### 3. Hybrid Search

Three-tier search with RRF fusion:

| Tier | Engine          | Default Weight | Strength                     |
|------|-----------------|----------------|------------------------------|
| 1    | Qdrant HNSW     | 60%            | Semantic / conceptual recall |
| 2    | PostgreSQL GIN  | 30%            | Exact phrases / terms        |
| 3    | Meilisearch     | 10%            | Typo-tolerant fuzzy match    |

**Dynamic query intent classification** adjusts weights:
- Conceptual queries: semantic 80%, keyword 15%, typo 5%
- Exact/code-like queries: semantic 30%, keyword 60%, typo 10%
- Typo-likely queries: semantic 55%, keyword 15%, typo 30%

**Cross-encoder reranking** on top candidates (ms-marco-MiniLM-L-6-v2).

**Final score blend**: relevance 60%, recency 15%, engagement 15%, bucket context 10%.

**MMR diversity**: lambda=0.7 to reduce redundancy.

**Two-layer cache**: L1 in-process LRU (1000 entries, 5 min TTL) + L2 Redis (1 hour TTL).

### 4. Bucket Organisation

- Auto-created default buckets on first upload (Research and Reference, Work and Projects, Web and Media Saves, plus Needs Classification)
- AI-powered bucket routing suggests best bucket for new documents
- Hierarchical bucket tree with parent/child relationships
- Bulk document moves between buckets
- Route preview (dry-run bucket assignment)
- Protected default buckets cannot be deleted
- Custom bucket creation and deletion (with document reassignment)

### 5. Knowledge Graph

- Entity extraction from document text (NER pipeline)
- Entity disambiguation and canonical form resolution
- Graph storage (Kuzu-based)
- Entity search, related entities, co-occurrence
- Path finding between entities
- Centrality analysis
- Timeline view
- Per-document entity management

### 6. Chat / RAG

- Retrieval-augmented generation using Gemini
- Searches user documents via hybrid search
- Returns response with source attribution
- Scoped to authenticated user's documents

### 7. Integrity Chain

Every document gets a 4-stage integrity chain:
- `ingestion` -- document received and stored
- `chunking` -- chunks created
- `embedding` -- vectors generated and stored
- `extraction` -- entities extracted

Each stage records a `chain_hash` and `verified` flag for auditability.

### 8. Authentication and Multi-Tenancy

- JWT-based auth (registration via journal-parser service on port 8002)
- All data is scoped by `user_id` / `created_by`
- Graceful degradation: unauthenticated requests operate as `anonymous`
- Qdrant, Meilisearch, and PG all filter by user_id

### 9. Observability

- Prometheus metrics at `/metrics`
- Structured logging via shared logging config
- Health check at `/health`
- DLQ monitoring for failed embedding operations

### 10. Embedding Dead Letter Queue (DLQ)

- Failed embedding operations are tracked
- Stats endpoint for monitoring
- Reprocess endpoint to retry failures
- Purge endpoint to clear unreplayable entries

---

## Data Flows

### Upload Flow

```
Client
  |
  | POST /upload {filename, content_base64}
  v
API Router (auth extract user_id)
  |
  v
KnowledgeService.upload_document()
  |
  |-- decode base64, compute checksum
  |-- INSERT documents (status=processing)
  |-- SemanticChunkingEngine.chunk()
  |-- INSERT document_chunks (with chunk_metadata.chunk_id)
  |-- Gemini embed each chunk (768-dim)
  |-- Qdrant upsert vectors (point_id = chunk_id)
  |-- Meilisearch index chunks (doc id = chunk_id)
  |-- extract_entities() -> INSERT entities
  |-- AI bucket routing -> UPDATE documents.bucket_id
  |-- build_integrity_chain() -> 4 records
  |-- UPDATE documents.status = completed
  |
  v
Response {document_id, title, status, chunks, bucket}
```

### Search Flow

```
Client
  |
  | POST /search {query, filters}
  v
API Router
  |
  v
KnowledgeService.search()
  |
  |-- normalize_query(), query_hash()
  |-- check L1 cache -> check L2 Redis cache
  |
  |-- (cache miss) detect_query_intent_weights()
  |-- Tier 1: Qdrant semantic search (user-scoped)
  |-- Tier 2: PostgreSQL tsvector search
  |-- Tier 3: Meilisearch typo-tolerant search
  |-- reciprocal_rank_fusion(k=60) with intent weights
  |-- cross-encoder reranking
  |-- apply_mmr_diversity(lambda=0.7)
  |-- store in L1 + L2 cache
  |
  v
Response {results[], total_candidates, cache_hit, tiers_matched[], latency_ms}
```

### Cross-Store ID Mapping

```
PG document_chunks.id          -- internal PG row UUID (NOT used externally)
PG chunk_metadata->>'chunk_id' -- the cross-store UUID
Qdrant point_id                -- same UUID as chunk_metadata.chunk_id
Meilisearch doc.id             -- same UUID as chunk_metadata.chunk_id
```

This mapping was verified by the deep store verification script across all 3 stores.

---

## Cross-Store Consistency

Verified by `scripts/deep_store_verify.py` (66 PASS, 0 FAIL, 1 WARN):

| Check                                 | Result |
|---------------------------------------|--------|
| PG document count matches uploads     | PASS   |
| All documents status = completed      | PASS   |
| All documents have checksums          | PASS   |
| Exact duplicate same checksum         | PASS   |
| Near-duplicate different checksum     | PASS   |
| tsvector populated for all docs       | PASS   |
| Chunks created for non-empty docs     | PASS   |
| chunk_metadata has chunk_id           | PASS   |
| Integrity chain (4 stages per doc)    | PASS   |
| Qdrant vectors = PG chunks            | PASS   |
| Qdrant vector dim = 768               | PASS   |
| Meilisearch docs = PG chunks          | PASS   |
| Meilisearch typo tolerance works      | PASS   |
| Redis caches populated                | PASS   |
| PG chunk IDs == Qdrant IDs == Meili IDs | PASS |
| Text content matches PG <-> Qdrant    | PASS   |
| Text content matches PG <-> Meilisearch | PASS |
| Hybrid search returns results         | PASS   |
| Document list API works               | PASS   |
| Bucket list API works                 | PASS   |
| DLQ stats accessible                  | PASS   |
| Health check returns healthy          | PASS   |
| No-auth returns anonymous user        | PASS   |
| Default bucket delete blocked (403)   | PASS   |
| Chat/RAG responds (WARN: empty with test key) | WARN |

---

## Test Coverage Summary

### Automated Test Suites

| Suite                          | Tests | Passed | Failed | Skipped | Notes                          |
|--------------------------------|-------|--------|--------|---------|-------------------------------|
| KB Unit/Integration (pytest)   | 308   | 298    | 2      | 8       | Failures: Gemini key missing + perf threshold |
| E2E Docker (test_e2e_docker.py)| 47    | 47     | 0      | 0       | All endpoints, edge cases      |
| Manual Deep Test               | 108   | 108    | 0      | 0       | Feature coverage via API       |
| Deep Store Verify              | 67    | 66     | 0      | 1 warn  | Cross-store data consistency   |

### Test File Inventory (tests/knowledge_base/)

| File                                    | Focus Area                         |
|-----------------------------------------|------------------------------------|
| test_acceptance_benchmarks.py           | Search quality SLOs                |
| test_api_ingest_endpoint.py             | Upload/ingest API                  |
| test_dedup_acceptance_benchmarks.py     | Dedup quality gates                |
| test_deduplication_algorithms.py        | Dedup logic unit tests             |
| test_document_management_migration.py   | Schema migration validation        |
| test_document_persistence_flow.py       | Full persistence pipeline          |
| test_embedding_provider.py             | Embedding generation               |
| test_hybrid_search.py                  | Hybrid search logic                |
| test_integration_e2e_perf_errors.py    | Integration + performance          |
| test_phase1b_chunk_dedup.py            | Chunk-level dedup                  |
| test_phase2_embedding_search.py        | Embedding + search                 |
| test_phase3_bucket_system.py           | Bucket management                  |
| test_phase4_knowledge_graph.py         | Knowledge graph pipeline           |
