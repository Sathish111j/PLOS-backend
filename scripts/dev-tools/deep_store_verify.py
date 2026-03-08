#!/usr/bin/env python3
"""
Deep Data Store Verification for PLOS Knowledge Base.

Verifies consistency and correctness across all four data stores:
  - PostgreSQL (documents, chunks, buckets, integrity chain, entities)
  - Qdrant     (vector embeddings, payload metadata, dimensions)
  - Meilisearch (keyword search, filterable attributes, typo tolerance)
  - Redis       (cache entries, key patterns, TTLs)

The chunk ID mapping works via:
  PG document_chunks.chunk_metadata->>'chunk_id' == Qdrant point_id == Meili doc id

Usage:
    python3 scripts/deep_store_verify.py

Registers a fresh user, uploads diverse docs, then verifies every store.
"""
import subprocess
import json
import time
import sys
import hashlib
import requests

# Configuration
KB = "http://localhost:8003"
QDRANT = "http://localhost:6333"
MEILI = "http://localhost:7700"
MEILI_KEY = "plos_meili_secure_2025"
QDRANT_COLL = "documents_768"
MEILI_IDX = "kb_chunks"
REDIS_PASS = "plos_redis_secure_2025"
PG_CMD = [
    "docker", "exec", "plos-supabase-db",
    "psql", "-U", "postgres", "-d", "plos", "-t", "-A", "-c",
]
REDIS_CMD = ["docker", "exec", "plos-redis", "redis-cli", "-a", REDIS_PASS]

pass_count = 0
fail_count = 0
warn_count = 0


def pg(sql):
    r = subprocess.run(PG_CMD + [sql], capture_output=True, text=True)
    return r.stdout.strip()


def rc(*args):
    r = subprocess.run(
        REDIS_CMD + list(args), capture_output=True, text=True
    )
    # Filter out the auth warning line
    lines = [
        ln
        for ln in r.stdout.strip().split("\n")
        if "Warning:" not in ln and ln.strip()
    ]
    return "\n".join(lines)


def meili(method, path, body=None):
    h = {"Authorization": f"Bearer {MEILI_KEY}"}
    if method == "GET":
        return requests.get(f"{MEILI}{path}", headers=h).json()
    return requests.post(f"{MEILI}{path}", headers=h, json=body).json()


def ok(name, condition, detail=""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {name}")
    else:
        fail_count += 1
        print(f"  [FAIL] {name} -- {detail}")


def info(name, value):
    print(f"  [INFO] {name}: {value}")


def warn(name, detail):
    global warn_count
    warn_count += 1
    print(f"  [WARN] {name} -- {detail}")


def section(title):
    print(f"\n--- {title} ---")


# Helper: register + get token
def setup_user():
    """Register a fresh test user and return (user_id, token).

    Auth lives on journal-parser (port 8002), not on KB service.
    """
    AUTH = "http://localhost:8002"
    tag = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    username = f"dsv_{tag}"
    email = f"{username}@plos-test.dev"
    password = "TestPass123!"

    r = requests.post(
        f"{AUTH}/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    if r.status_code not in (200, 201):
        print(f"[FATAL] Registration failed: {r.status_code} {r.text}")
        sys.exit(1)
    data = r.json()
    user_id = data["user"]["user_id"]
    token = data["access_token"]
    print(f"  User: {username} ({user_id})")
    return user_id, token


def upload(token, title, text, bucket_hint=None):
    """Upload a document and wait for completion.

    API expects 'filename' and 'content_base64' (base64-encoded text).
    """
    import base64

    h = {"Authorization": f"Bearer {token}"}
    body = {
        "filename": title,
        "content_base64": base64.b64encode(text.encode()).decode() if text else None,
    }
    if bucket_hint:
        body["bucket_hint"] = bucket_hint
    r = requests.post(f"{KB}/upload", headers=h, json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  [FAIL] Upload '{title}': {r.status_code} {r.text[:100]}")
        return None
    return r.json()


DOCS = [
    (
        "ml_production_guide",
        (
            "Machine Learning in Production: Deploying ML models requires "
            "careful consideration of model versioning, feature stores, "
            "A/B testing frameworks, and monitoring for data drift. "
            "Key practices include model registry management, automated "
            "retraining pipelines, shadow deployments, and canary releases. "
            "Infrastructure typically involves Kubernetes, TensorFlow Serving "
            "or TorchServe, MLflow, and custom inference endpoints."
        ),
    ),
    (
        "distributed_systems",
        (
            "Distributed Systems Design Patterns: Building reliable distributed "
            "systems requires understanding CAP theorem, consensus algorithms "
            "like Raft and Paxos, eventual consistency models, and partition "
            "tolerance strategies. Common patterns include saga pattern for "
            "distributed transactions, circuit breaker for fault tolerance, "
            "event sourcing for state management, and CQRS for read/write "
            "separation. Technologies like Apache Kafka enable event-driven "
            "architectures."
        ),
    ),
    (
        "python_best_practices",
        (
            "Python Development Best Practices: Modern Python development "
            "emphasizes type hints, dataclasses, and async/await patterns. "
            "Use virtual environments with poetry or pip-tools for dependency "
            "management. Code quality tools include ruff for linting, black "
            "for formatting, mypy for type checking, and pytest for testing. "
            "Design patterns like dependency injection and repository pattern "
            "improve testability."
        ),
    ),
    (
        "kubernetes_deployment",
        (
            "Kubernetes Deployment Guide: Production Kubernetes clusters "
            "require proper resource requests/limits, horizontal pod "
            "autoscaling, pod disruption budgets, and network policies. "
            "Use Helm charts for templating, ArgoCD for GitOps workflows, "
            "and Istio service mesh for traffic management. Storage "
            "considerations include persistent volumes with CSI drivers "
            "and StatefulSets for databases."
        ),
    ),
    (
        "personal_reflection",
        (
            "Today was a productive day. I finished the database migration "
            "project that has been pending for two weeks. The team is "
            "excited about the new schema design with its improved indexing "
            "strategy. Tomorrow, I plan to start on the API refactoring "
            "task. Need to schedule a code review session with Sarah and "
            "prepare the architecture decision record for the caching layer "
            "redesign. Also, the quarterly goals document is due Friday."
        ),
    ),
]


# ====================================================================
print("=" * 64)
print("DEEP DATA STORE VERIFICATION")
print("=" * 64)

# Setup
section("0. Setup")
user_id, token = setup_user()
headers = {"Authorization": f"Bearer {token}"}

# Upload 5 diverse docs + 1 exact duplicate + 1 near-duplicate
for title, text in DOCS:
    r = upload(token, title, text)
    ok(f"Upload '{title}'", r and r.get("status") == "completed")

# Exact duplicate
dup_r = upload(token, "ml_EXACT_DUP", DOCS[0][1])
ok("Upload exact duplicate", dup_r is not None)

# Near-duplicate (slightly modified)
near_text = DOCS[0][1].replace("Deploying ML", "Deploying machine learning")
near_r = upload(token, "ml_NEAR_DUP", near_text)
ok("Upload near-duplicate", near_r is not None)

# Empty + short docs
upload(token, "empty_doc", "")
upload(token, "short_doc", "Hi")

info("Total uploads", "9 (5 unique + dup + near-dup + empty + short)")
time.sleep(2)  # let async processing finish

# ====================================================================
section("1. PostgreSQL - Documents")
dc = int(pg(f"SELECT count(*) FROM documents WHERE created_by='{user_id}'"))
ok(f"Document count = 9", dc == 9, f"got {dc}")

comp = int(
    pg(
        f"SELECT count(*) FROM documents WHERE created_by='{user_id}' "
        "AND status='completed'"
    )
)
ok("All completed", comp == dc, f"{comp}/{dc}")

null_ck = int(
    pg(
        f"SELECT count(*) FROM documents WHERE created_by='{user_id}' "
        "AND checksum IS NULL"
    )
)
ok("All have checksums", null_ck == 0)

# Dup detection: same content = same checksum
dup_same = pg(
    f"SELECT d1.checksum = d2.checksum FROM documents d1, documents d2 "
    f"WHERE d1.created_by='{user_id}' AND d2.created_by='{user_id}' "
    "AND d1.title='ml_production_guide' AND d2.title='ml_EXACT_DUP'"
)
ok("Exact dup same checksum", "t" in dup_same)

near_diff = pg(
    f"SELECT d1.checksum != d2.checksum FROM documents d1, documents d2 "
    f"WHERE d1.created_by='{user_id}' AND d2.created_by='{user_id}' "
    "AND d1.title='ml_production_guide' AND d2.title='ml_NEAR_DUP'"
)
ok("Near-dup diff checksum", "t" in near_diff)

# Word count sanity
zero_w = pg(
    f"SELECT title FROM documents WHERE created_by='{user_id}' AND word_count=0"
)
ok("Only empty_doc has 0 words", zero_w.strip() == "empty_doc", f"got: {zero_w}")

# tsvector
tsv = int(
    pg(
        f"SELECT count(*) FROM documents WHERE created_by='{user_id}' "
        "AND search_vector IS NOT NULL"
    )
)
ok(f"tsvector populated ({tsv}/{dc})", tsv >= 5)

# ====================================================================
section("2. PostgreSQL - Chunks")
cc = int(
    pg(
        f"SELECT count(*) FROM document_chunks dc "
        f"JOIN documents d ON dc.document_id=d.id "
        f"WHERE d.created_by='{user_id}'"
    )
)
info("Total chunks", cc)
# At least 7 chunks (5 unique + near-dup + short, empty may or may not have chunk)
ok(f"Chunks >= 7", cc >= 7, f"got {cc}")

per_doc = pg(
    f"SELECT d.title || '=' || count(dc.id) "
    f"FROM documents d LEFT JOIN document_chunks dc ON dc.document_id=d.id "
    f"WHERE d.created_by='{user_id}' GROUP BY d.title ORDER BY d.title"
)
info("Chunks per doc", per_doc.replace("\n", ", "))

bad_idx = int(
    pg(
        f"SELECT count(*) FROM document_chunks dc "
        f"JOIN documents d ON dc.document_id=d.id "
        f"WHERE d.created_by='{user_id}' AND dc.chunk_index >= dc.total_chunks"
    )
)
ok("chunk_index < total_chunks", bad_idx == 0)

zero_tk = int(
    pg(
        f"SELECT count(*) FROM document_chunks dc "
        f"JOIN documents d ON dc.document_id=d.id "
        f"WHERE d.created_by='{user_id}' AND dc.token_count=0 "
        "AND d.title NOT IN ('empty_doc', 'short_doc')"
    )
)
ok("Token count > 0 for real docs", zero_tk == 0, f"{zero_tk}")

# Chunk metadata stores qdrant chunk_id
has_meta_cid = int(
    pg(
        f"SELECT count(*) FROM document_chunks dc "
        f"JOIN documents d ON dc.document_id=d.id "
        f"WHERE d.created_by='{user_id}' "
        "AND dc.chunk_metadata->>'chunk_id' IS NOT NULL"
    )
)
ok(f"chunk_metadata has chunk_id ({has_meta_cid}/{cc})", has_meta_cid == cc)

# ====================================================================
section("3. Integrity Chain")
ic = int(
    pg(
        f"SELECT count(*) FROM document_integrity_checks "
        f"WHERE document_id IN (SELECT id FROM documents WHERE created_by='{user_id}')"
    )
)
info("Integrity records", ic)

if ic > 0:
    ok("Integrity records exist", True)
    stages = pg(
        f"SELECT DISTINCT stage_name FROM document_integrity_checks "
        f"WHERE document_id IN (SELECT id FROM documents WHERE created_by='{user_id}') "
        "ORDER BY stage_name"
    )
    info("Stages", stages)
    for s in ["chunking", "embedding", "extraction", "ingestion"]:
        ok(f"Stage '{s}'", s in stages, f"found: {stages}")

    unverified = int(
        pg(
            f"SELECT count(*) FROM document_integrity_checks "
            f"WHERE document_id IN "
            f"(SELECT id FROM documents WHERE created_by='{user_id}') "
            "AND is_verified=false"
        )
    )
    ok("All verified", unverified == 0, f"{unverified} unverified")

    chain_nulls = int(
        pg(
            f"SELECT count(*) FROM document_integrity_checks "
            f"WHERE document_id IN "
            f"(SELECT id FROM documents WHERE created_by='{user_id}') "
            "AND chain_hash_sha256 IS NULL"
        )
    )
    ok("All have chain hashes", chain_nulls == 0, f"{chain_nulls} null")
else:
    warn("No integrity records", "May not be enabled")

# ====================================================================
section("4. Buckets")
bkts = pg(
    f"SELECT name || ' | d=' || depth || ' | def=' || is_default "
    f"|| ' | del=' || is_deleted || ' | docs=' || document_count "
    f"FROM buckets WHERE user_id='{user_id}' ORDER BY path"
)
info("Buckets", "\n    " + bkts.replace("\n", "\n    "))

active_b = int(
    pg(f"SELECT count(*) FROM buckets WHERE user_id='{user_id}' AND is_deleted=false")
)
ok(f"Active buckets >= 4", active_b >= 4, f"got {active_b}")

defaults_csv = pg(
    f"SELECT name FROM buckets WHERE user_id='{user_id}' AND is_default=true "
    "ORDER BY name"
)
ok("Default 'Research and Reference'", "Research and Reference" in defaults_csv)
ok("Default 'Work and Projects'", "Work and Projects" in defaults_csv)

# ====================================================================
section("5. Entities")
ents = int(
    pg(
        f"SELECT count(*) FROM document_entities "
        f"WHERE document_id IN (SELECT id FROM documents WHERE created_by='{user_id}')"
    )
)
info("Entity records", ents)
if ents > 0:
    ok("Entities extracted", True)
    sample = pg(
        f"SELECT entity_type || ': ' || entity_value "
        f"FROM document_entities "
        f"WHERE document_id IN (SELECT id FROM documents WHERE created_by='{user_id}') "
        "LIMIT 8"
    )
    info("Sample", sample.replace("\n", " | "))
else:
    warn("No entities", "May run asynchronously")

# ====================================================================
section("6. Qdrant Vector Store")

r = requests.get(f"{QDRANT}/collections/{QDRANT_COLL}")
coll = r.json().get("result", {})
ok("Collection green", coll.get("status") == "green")
cfg = coll.get("config", {}).get("params", {}).get("vectors", {})
ok("Vector size = 768", cfg.get("size") == 768, f"got {cfg.get('size')}")
info("Total points (all users)", coll.get("points_count"))

# Get user's points
r = requests.post(
    f"{QDRANT}/collections/{QDRANT_COLL}/points/scroll",
    json={
        "filter": {"must": [{"key": "user_id", "match": {"value": user_id}}]},
        "limit": 100,
        "with_payload": True,
        "with_vectors": False,
    },
)
pts = r.json().get("result", {}).get("points", [])
info("User vectors", len(pts))
ok(f"Qdrant vectors >= 7", len(pts) >= 7, f"got {len(pts)}")

if pts:
    p0 = pts[0]["payload"]
    req_fields = [
        "user_id",
        "bucket_id",
        "document_id",
        "chunk_id",
        "text",
        "text_preview",
        "token_count",
        "content_type",
    ]
    missing = [fi for fi in req_fields if fi not in p0]
    ok("Payload has all fields", len(missing) == 0, f"missing: {missing}")
    ok("user_id correct", p0.get("user_id") == user_id)

    # Vector dimensions
    r2 = requests.post(
        f"{QDRANT}/collections/{QDRANT_COLL}/points/scroll",
        json={
            "filter": {
                "must": [{"key": "user_id", "match": {"value": user_id}}]
            },
            "limit": 1,
            "with_payload": False,
            "with_vectors": True,
        },
    )
    vpts = r2.json().get("result", {}).get("points", [])
    if vpts and "vector" in vpts[0]:
        vec = vpts[0]["vector"]
        vlen = len(vec) if isinstance(vec, list) else 0
        ok("Vector dim = 768", vlen == 768, f"got {vlen}")

    # Cross-check: PG chunk_metadata->>'chunk_id' == Qdrant point_id
    pg_qdrant_ids = set(
        pg(
            f"SELECT dc.chunk_metadata->>'chunk_id' "
            f"FROM document_chunks dc "
            f"JOIN documents d ON dc.document_id=d.id "
            f"WHERE d.created_by='{user_id}' "
            "AND dc.chunk_metadata->>'chunk_id' IS NOT NULL"
        ).split("\n")
    )
    q_ids = set(pt["id"] for pt in pts)
    pg_not_q = pg_qdrant_ids - q_ids
    q_not_pg = q_ids - pg_qdrant_ids
    ok(
        "PG chunk_metadata IDs in Qdrant",
        len(pg_not_q) == 0,
        f"{len(pg_not_q)} missing",
    )
    ok(
        "Qdrant IDs in PG metadata",
        len(q_not_pg) == 0,
        f"{len(q_not_pg)} orphaned",
    )

    # Text content match (spot check 3)
    mismatches = 0
    for pt in pts[:3]:
        cid = pt["payload"].get("chunk_id", "")
        qt = pt["payload"].get("text", "")[:80]
        # Look up by the metada chunk_id in PG
        pgt = pg(
            f"SELECT left(dc.content, 80) FROM document_chunks dc "
            f"WHERE dc.chunk_metadata->>'chunk_id' = '{cid}'"
        )
        if not pgt or pgt.strip() != qt.strip():
            mismatches += 1
    ok(f"Text matches PG<->Qdrant (3 samples)", mismatches == 0, f"{mismatches}")

    # Verify bucket_ids reference valid buckets
    q_bucket_ids = set(pt["payload"]["bucket_id"] for pt in pts)
    for bid in q_bucket_ids:
        exists = pg(
            f"SELECT count(*) FROM buckets WHERE id='{bid}' AND user_id='{user_id}'"
        )
        ok(f"Qdrant bucket {bid[:8]} valid in PG", int(exists) == 1)

# ====================================================================
section("7. Meilisearch")

ms = meili("GET", f"/indexes/{MEILI_IDX}/stats")
info("Total docs (all users)", ms.get("numberOfDocuments"))
ok("Has documents", ms.get("numberOfDocuments", 0) > 0)
ok("Not indexing", ms.get("isIndexing") is False)

st = meili("GET", f"/indexes/{MEILI_IDX}/settings")
filterable = st.get("filterableAttributes", [])
searchable = st.get("searchableAttributes", [])
ok("user_id filterable", "user_id" in filterable)
ok("bucket_id filterable", "bucket_id" in filterable)
ok("text searchable", "text" in searchable)

# User-filtered searches
for term in ["kubernetes", "machine learning", "python", "distributed", "productive"]:
    r = meili(
        "POST",
        f"/indexes/{MEILI_IDX}/search",
        {"q": term, "limit": 10, "filter": f"user_id = '{user_id}'"},
    )
    hits = r.get("hits", [])
    ok(f"Meili '{term}' ({len(hits)} hits)", len(hits) > 0, "0 hits")

# Typo tolerance
r = meili(
    "POST",
    f"/indexes/{MEILI_IDX}/search",
    {"q": "kuberntes", "limit": 5, "filter": f"user_id = '{user_id}'"},
)
ok(f"Typo 'kuberntes' ({len(r.get('hits', []))} hits)", len(r.get("hits", [])) > 0)

# Cross-check Meilisearch doc content vs PG
r = meili(
    "POST",
    f"/indexes/{MEILI_IDX}/search",
    {"q": "kubernetes", "limit": 1, "filter": f"user_id = '{user_id}'"},
)
if r.get("hits"):
    hit = r["hits"][0]
    meili_cid = hit.get("id", "")
    meili_text = hit.get("text", "")[:80]
    pg_text = pg(
        f"SELECT left(dc.content, 80) FROM document_chunks dc "
        f"WHERE dc.chunk_metadata->>'chunk_id' = '{meili_cid}'"
    )
    ok(
        "Text matches PG<->Meili",
        pg_text.strip() == meili_text.strip(),
        f"M='{meili_text[:40]}' PG='{pg_text[:40]}'",
    )

# Get all user docs from Meili for cross-store check
r = meili(
    "POST",
    f"/indexes/{MEILI_IDX}/search",
    {"q": "", "limit": 100, "filter": f"user_id = '{user_id}'"},
)
meili_hits = r.get("hits", [])
meili_count = len(meili_hits)

# ====================================================================
section("8. Redis Cache")

dbsize_raw = rc("DBSIZE")
# Parse the number from DBSIZE output
dbsize_str = dbsize_raw.split(":")[-1].strip() if ":" in dbsize_raw else dbsize_raw
try:
    total_keys = int(dbsize_str)
except ValueError:
    total_keys = 0
info("Total keys", total_keys)
ok("Redis has cached data", total_keys > 0, f"total={total_keys}")

# Key pattern breakdown
keys_raw = rc("KEYS", "*")
keys = [k for k in keys_raw.split("\n") if k.strip()]
patterns = {}
for k in keys[:500]:
    parts = k.split(":")
    if len(parts) >= 2:
        pref = parts[0] + ":" + parts[1]
    else:
        pref = k
    patterns[pref] = patterns.get(pref, 0) + 1
info("Key prefixes", json.dumps(patterns, indent=2))

# Check for embedding cache
emb_keys = [k for k in keys if "embedding" in k.lower()]
info("Embedding cache keys", len(emb_keys))
ok("Embedding cache exists", len(emb_keys) > 0)

# Check for dedup cache
dedup_keys = [k for k in keys if "dedup" in k.lower()]
info("Dedup cache keys", len(dedup_keys))

# Check for search cache
search_keys = [k for k in keys if "search" in k.lower()]
info("Search cache keys", len(search_keys))

# TTL on sample keys
for k in keys[:3]:
    ttl = rc("TTL", k)
    ktype = rc("TYPE", k)
    info(f"'{k[:60]}' type={ktype}", f"TTL={ttl}s")

# ====================================================================
section("9. Cross-Store Consistency")

qdrant_count = len(pts) if pts else 0

info("PG chunks", cc)
info("Qdrant vectors", qdrant_count)
info("Meilisearch docs (user)", meili_count)

ok(f"PG ({cc}) == Qdrant ({qdrant_count})", cc == qdrant_count)
ok(
    f"PG ({cc}) == Meili ({meili_count})",
    cc == meili_count,
    "Index may differ for empty/short docs",
)

if pts and meili_hits:
    q_ids = set(pt["id"] for pt in pts)
    m_ids = set(h["id"] for h in meili_hits)
    ok("Qdrant IDs == Meili IDs", q_ids == m_ids, f"diff={q_ids.symmetric_difference(m_ids)}")

# ====================================================================
section("10. API-Level Verification")

# Search should return results using hybrid search
r = requests.post(
    f"{KB}/search",
    headers=headers,
    json={"query": "Kubernetes deployment production"},
)
ok("Hybrid search returns results", r.status_code == 200 and len(r.json().get("results", [])) > 0)
if r.status_code == 200:
    sr = r.json()
    info("Search latency", f"{sr.get('latency_ms', '?')}ms")
    info("Candidates", sr.get("total_candidates"))
    info("Cache hit", sr.get("cache_hit"))
    if sr.get("results"):
        res = sr["results"][0]
        info("Top result score", res.get("score"))
        info("Tiers matched", res.get("tiers_matched"))

# Document listing
r = requests.get(f"{KB}/documents", headers=headers)
ok("Document list works", r.status_code == 200)
if r.status_code == 200:
    docs_list = r.json()
    ok(
        f"Lists all 9 docs",
        len(docs_list) == 9,
        f"got {len(docs_list)}",
    )

# Bucket listing
r = requests.get(f"{KB}/buckets", headers=headers)
ok("Bucket list works", r.status_code == 200)
if r.status_code == 200:
    buckets_list = r.json()
    info("Buckets returned", len(buckets_list))
    ok("At least 4 buckets", len(buckets_list) >= 4)

# Chat/RAG
r = requests.post(
    f"{KB}/chat",
    headers=headers,
    json={"message": "What are the best practices for deploying ML models?"},
)
ok("Chat/RAG returns 200", r.status_code == 200)
if r.status_code == 200:
    chat = r.json()
    # Chat may return empty response if Gemini API key is test/dummy
    has_resp = len(chat.get("response", "")) > 20
    if has_resp:
        ok("Chat has response", True)
    else:
        warn("Chat response empty", "Expected with test Gemini key (429 rate limit)")
    info("Sources", len(chat.get("sources", [])))

# DLQ stats
r = requests.get(f"{KB}/ops/embedding-dlq/stats", headers=headers)
ok("DLQ stats accessible", r.status_code == 200)

# Health
r = requests.get(f"{KB}/health")
ok("Health check OK", r.status_code == 200 and r.json().get("status") == "healthy")

# ====================================================================
section("11. Edge Cases")

# Unauthenticated access - returns 200 with anonymous owner (graceful degradation)
r = requests.post(f"{KB}/search", json={"query": "test"})
anon = r.json().get("owner_id") == "anonymous" if r.status_code == 200 else False
ok("No-auth returns anonymous", r.status_code == 200 and anon)

# Default bucket delete protection
default_bid = pg(
    f"SELECT id FROM buckets WHERE user_id='{user_id}' "
    "AND is_default=true LIMIT 1"
)
if default_bid:
    r = requests.delete(
        f"{KB}/buckets/{default_bid}",
        headers=headers,
        json={"target_bucket_id": None},
    )
    ok(
        "Default bucket delete blocked (403)",
        r.status_code == 403,
        f"got {r.status_code}: {r.text[:80]}",
    )

# ====================================================================
print("\n" + "=" * 64)
print(f"FINAL: {pass_count} PASS | {fail_count} FAIL | {warn_count} WARN")
print("=" * 64)
sys.exit(1 if fail_count > 0 else 0)
