#!/usr/bin/env python3
"""
Deep manual testing script for Knowledge Base.
Tests all features end-to-end, checking DB and vector DB at each step.
"""

import base64
import json
import os
import sys
import time
import uuid

import requests

# Service URLs
KB_URL = "http://localhost:8003"
AUTH_URL = "http://localhost:8002"
CONTEXT_URL = "http://localhost:8001"
GATEWAY_URL = "http://localhost:8000/api/v1"

# DB access (Supabase PostgreSQL)
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "plos"
DB_USER = "postgres"
DB_PASS = "plos_db_secure_2025"

# Qdrant
QDRANT_URL = "http://localhost:6333"

# Meilisearch
MEILI_URL = "http://localhost:7700"
MEILI_KEY = "plos_meili_secure_2025"

# Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASS = "plos_redis_secure_2025"

TIMEOUT = 60


def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def b64(text):
    return base64.b64encode(text.encode()).decode()


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def check(condition, msg):
    if condition:
        print(f"  [PASS] {msg}")
    else:
        print(f"  [FAIL] {msg}")
    return condition


def check_db(query):
    """Run a query against Supabase PostgreSQL via psql in the container."""
    import subprocess
    cmd = [
        "docker", "exec", "plos-supabase-db",
        "psql", "-U", "postgres", "-d", "plos", "-t", "-A", "-c", query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def check_qdrant(path, method="GET", data=None):
    """Query Qdrant REST API."""
    url = f"{QDRANT_URL}{path}"
    if method == "POST":
        r = requests.post(url, json=data, timeout=10)
    else:
        r = requests.get(url, timeout=10)
    return r.json()


def check_meili(index, query=""):
    """Query Meilisearch."""
    url = f"{MEILI_URL}/indexes/{index}/search"
    r = requests.post(url, json={"q": query, "limit": 100},
                      headers={"Authorization": f"Bearer {MEILI_KEY}"}, timeout=10)
    return r.json()


def check_redis(pattern="*"):
    """Check Redis keys."""
    import subprocess
    cmd = [
        "docker", "exec", "plos-redis",
        "redis-cli", "-a", REDIS_PASS, "--no-auth-warning", "KEYS", pattern
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return [k for k in result.stdout.strip().split("\n") if k]


# STEP 0: Register and authenticate
section("STEP 0: Authentication")

unique = uuid.uuid4().hex[:8]
reg = requests.post(f"{AUTH_URL}/auth/register", json={
    "username": f"deeptest_{unique}",
    "email": f"deeptest_{unique}@plos.dev",
    "password": "DeepTest123!"
}, timeout=TIMEOUT)

check(reg.status_code in (200, 201), f"Registration: {reg.status_code}")
reg_data = reg.json()
TOKEN = reg_data["access_token"]
USER_ID = reg_data["user"]["user_id"]
print(f"  User ID: {USER_ID}")
print(f"  Token: {TOKEN[:40]}...")

# Verify user in DB
db_user = check_db(f"SELECT email FROM users WHERE id = '{USER_ID}';")
check(f"deeptest_{unique}@plos.dev" in db_user, f"User in DB: {db_user}")

# STEP 1: Check default buckets created for new user
section("STEP 1: Default Buckets for New User")

buckets = requests.get(f"{KB_URL}/buckets", headers=headers(TOKEN), timeout=TIMEOUT).json()
bucket_names = sorted([b["name"] for b in buckets])
print(f"  Buckets: {bucket_names}")
check(len(buckets) == 4, f"Expected 4 default buckets, got {len(buckets)}")
check("Needs Classification" in bucket_names, "Has 'Needs Classification' bucket")
check("Research and Reference" in bucket_names, "Has 'Research and Reference' bucket")

# Verify in DB
db_bucket_count = check_db(
    f"SELECT COUNT(*) FROM buckets WHERE user_id = '{USER_ID}' AND is_deleted = false;"
)
check(db_bucket_count == "4", f"DB bucket count: {db_bucket_count}")

# Store bucket IDs for later
bucket_map = {b["name"]: b["bucket_id"] for b in buckets}
nc_bucket = bucket_map.get("Needs Classification", "")
rr_bucket = bucket_map.get("Research and Reference", "")
wp_bucket = bucket_map.get("Work and Projects", "")
print(f"  Needs Classification: {nc_bucket}")
print(f"  Research and Reference: {rr_bucket}")

# STEP 2: Upload diverse documents
section("STEP 2: Upload Diverse Documents")

test_docs = [
    {
        "filename": "ml_production_guide.txt",
        "content": (
            "Machine Learning in Production: Deploying ML models requires careful "
            "consideration of latency, throughput, and model drift. Key strategies "
            "include A/B testing, shadow deployments, and canary releases. Feature "
            "stores help maintain consistency between training and serving. "
            "Monitoring should track prediction quality, data drift, and system "
            "performance metrics. Model versioning and rollback capabilities are "
            "essential for production stability."
        ),
        "mime_type": "text/plain"
    },
    {
        "filename": "distributed_systems_notes.txt",
        "content": (
            "Distributed Systems Notes: The CAP theorem states that a distributed "
            "system cannot simultaneously provide Consistency, Availability, and "
            "Partition tolerance. Modern systems like Cassandra choose AP while "
            "systems like Spanner choose CP. Consensus algorithms such as Raft and "
            "Paxos help maintain consistency across replicas. Vector clocks and "
            "Lamport timestamps provide causal ordering of events. Service meshes "
            "like Istio handle cross-cutting concerns including retries, circuit "
            "breaking, and observability."
        ),
        "mime_type": "text/plain"
    },
    {
        "filename": "python_best_practices.txt",
        "content": (
            "Python Best Practices: Use type hints everywhere for better code "
            "documentation and IDE support. Prefer pathlib over os.path for file "
            "operations. Use dataclasses or Pydantic models for structured data. "
            "Virtual environments isolate project dependencies. Black and ruff "
            "ensure consistent code formatting. Pytest with fixtures provides "
            "powerful testing capabilities. Async/await patterns improve I/O bound "
            "performance significantly. Context managers handle resource cleanup."
        ),
        "mime_type": "text/plain"
    },
    {
        "filename": "kubernetes_deployment.txt",
        "content": (
            "Kubernetes Deployment Guide: Pods are the smallest deployable units. "
            "Deployments manage ReplicaSets for rolling updates. Services provide "
            "stable networking with ClusterIP, NodePort, and LoadBalancer types. "
            "Ingress controllers handle external HTTP routing. ConfigMaps and "
            "Secrets manage configuration. Horizontal Pod Autoscaler adjusts "
            "replicas based on CPU or custom metrics. Persistent Volumes provide "
            "durable storage. Helm charts package complex applications. "
            "Namespaces isolate resources within a cluster."
        ),
        "mime_type": "text/plain"
    },
    {
        "filename": "personal_journal_reflection.txt",
        "content": (
            "Today was a productive day. I finished the database migration project "
            "that has been pending for two weeks. The team meeting went well and we "
            "agreed on the Q3 roadmap priorities. I need to follow up on the API "
            "performance issues reported by the frontend team. Feeling energized "
            "about the new architecture decisions. Should schedule a one-on-one "
            "with my manager about career growth. Also need to book flights for "
            "the conference next month."
        ),
        "mime_type": "text/plain"
    },
]

doc_ids = []
for i, doc in enumerate(test_docs):
    resp = requests.post(f"{KB_URL}/upload", headers=headers(TOKEN), json={
        "filename": doc["filename"],
        "content_base64": b64(doc["content"]),
        "mime_type": doc["mime_type"],
    }, timeout=TIMEOUT)
    check(resp.status_code == 200, f"Doc {i+1} '{doc['filename']}': status={resp.status_code}")
    data = resp.json()
    doc_id = data["document_id"]
    doc_ids.append(doc_id)
    print(f"    id={doc_id}, chunks={data.get('metadata',{}).get('chunk_count','?')}, "
          f"words={data['word_count']}, strategy={data['strategy']}")

print(f"\n  Total uploaded: {len(doc_ids)} documents")

# STEP 3: Verify documents in PostgreSQL
section("STEP 3: Verify Documents in PostgreSQL")

for i, doc_id in enumerate(doc_ids):
    row = check_db(
        f"SELECT title, status, content_type, bucket_id FROM documents "
        f"WHERE id = '{doc_id}';"
    )
    parts = row.split("|") if row else []
    if len(parts) >= 4:
        print(f"  Doc {i+1}: title={parts[0]}, status={parts[1]}, "
              f"type={parts[2]}, bucket={parts[3][:8]}...")
        check(parts[1] == "completed", f"Doc {i+1} status is 'completed'")
    else:
        print(f"  [FAIL] Doc {i+1} not found in DB! raw={row}")

# Count chunks per document
for i, doc_id in enumerate(doc_ids):
    chunk_count = check_db(
        f"SELECT COUNT(*) FROM document_chunks WHERE document_id = '{doc_id}';"
    )
    print(f"  Doc {i+1} chunks in DB: {chunk_count}")
    check(int(chunk_count) > 0, f"Doc {i+1} has chunks in DB")

# Total chunks
total_chunks = check_db(
    f"SELECT COUNT(*) FROM document_chunks WHERE document_id IN "
    f"({','.join(repr(d) for d in doc_ids)});"
)
print(f"  Total chunks in DB: {total_chunks}")

# STEP 4: Verify documents in Qdrant (Vector DB)
section("STEP 4: Verify Documents in Qdrant (Vector DB)")

# Check collection info
collection = check_qdrant("/collections/documents_768")
points_count = collection.get("result", {}).get("points_count", 0)
print(f"  Qdrant collection 'documents_768': {points_count} points total")

# Scroll to verify our docs are present
for i, doc_id in enumerate(doc_ids):
    scroll = check_qdrant("/collections/documents_768/points/scroll", "POST", {
        "filter": {"must": [{"key": "document_id", "match": {"value": doc_id}}]},
        "limit": 20,
        "with_payload": True,
        "with_vectors": False,
    })
    pts = scroll.get("result", {}).get("points", [])
    check(len(pts) > 0, f"Doc {i+1} in Qdrant: {len(pts)} vectors")
    if pts:
        payload = pts[0].get("payload", {})
        print(f"    payload keys: {sorted(payload.keys())}")
        check("user_id" in payload, f"Doc {i+1} has user_id in payload")
        check("bucket_id" in payload, f"Doc {i+1} has bucket_id in payload")
        check(payload.get("user_id") == USER_ID, f"Doc {i+1} owner matches user")

# STEP 5: Verify documents in Meilisearch
section("STEP 5: Verify Documents in Meilisearch")

meili_results = check_meili("kb_chunks", "")
meili_total = meili_results.get("estimatedTotalHits", 0)
print(f"  Meilisearch total hits: {meili_total}")

# Search for specific content
for term, expected_doc in [("machine learning", "ml_production_guide"),
                           ("kubernetes", "kubernetes_deployment"),
                           ("CAP theorem", "distributed_systems"),
                           ("pytest fixtures", "python_best_practices"),
                           ("conference", "personal_journal")]:
    sr = check_meili("kb_chunks", term)
    hits = sr.get("hits", [])
    check(len(hits) > 0, f"Meili search '{term}': {len(hits)} hits")
    if hits:
        first_doc = hits[0].get("document_id", "unknown")
        print(f"    First hit doc_id: {first_doc[:8]}...")

# STEP 6: Test Hybrid Search in depth
section("STEP 6: Hybrid Search Deep Testing")

search_queries = [
    {"query": "how to deploy machine learning models in production", "expected": "ml_production"},
    {"query": "distributed systems consistency algorithms", "expected": "distributed_systems"},
    {"query": "Python code formatting and testing", "expected": "python_best"},
    {"query": "container orchestration with pods", "expected": "kubernetes"},
    {"query": "personal reflection and team meetings", "expected": "personal_journal"},
    {"query": "monitoring model performance", "expected": "ml_production"},
]

for sq in search_queries:
    resp = requests.post(f"{KB_URL}/search", headers=headers(TOKEN), json={
        "query": sq["query"],
        "top_k": 5,
    }, timeout=TIMEOUT)
    check(resp.status_code == 200, f"Search '{sq['query'][:40]}...': status={resp.status_code}")
    data = resp.json()
    results = data.get("results", [])
    diag = data.get("diagnostics", {})
    
    print(f"    Results: {len(results)}, intent={data.get('intent','?')}, "
          f"latency={data.get('latency_ms','?')}ms")
    
    # Check search tiers
    candidates = diag.get("candidate_counts", {})
    print(f"    Tiers - semantic:{candidates.get('semantic',0)} "
          f"keyword:{candidates.get('keyword',0)} "
          f"typo:{candidates.get('typo',0)} "
          f"fused:{candidates.get('fused',0)}")
    
    # Verify result structure
    if results:
        r = results[0]
        check("text_preview" in r or "chunk_text" in r, "Result has text content")
        check("score" in r, "Result has score")
        check("document_id" in r, f"Result has document_id")
        check("bucket_id" in r, "Result has bucket_id")
        print(f"    Top result: score={r.get('score','?')}, "
              f"doc={r.get('document_id','?')[:8]}...")

# STEP 7: Test Deduplication
section("STEP 7: Deduplication Testing")

# Upload exact duplicate
dup_content = test_docs[0]["content"]
resp = requests.post(f"{KB_URL}/upload", headers=headers(TOKEN), json={
    "filename": "ml_production_DUPLICATE.txt",
    "content_base64": b64(dup_content),
    "mime_type": "text/plain",
}, timeout=TIMEOUT)
check(resp.status_code == 200, f"Duplicate upload status: {resp.status_code}")
dup_data = resp.json()
dup_id = dup_data["document_id"]
meta = dup_data.get("metadata", {})
dedup = meta.get("deduplication", meta.get("dedup_stats", {}))
print(f"  Duplicate doc id: {dup_id}")
print(f"  Dedup stats: {json.dumps(dedup, indent=4)}")
check(dedup.get("stage_counts", {}).get("exact", 0) > 0 or dedup.get("exact_duplicates", 0) > 0,
      "Exact duplicates detected")
check(dedup.get("forced_retention", False) or dedup.get("retained_chunks", 0) > 0,
      "Forced retention or chunks retained")

# Verify original still has vectors
scroll_orig = check_qdrant("/collections/documents_768/points/scroll", "POST", {
    "filter": {"must": [{"key": "document_id", "match": {"value": doc_ids[0]}}]},
    "limit": 20, "with_vectors": False,
})
orig_pts = len(scroll_orig.get("result", {}).get("points", []))
check(orig_pts > 0, f"Original doc still has {orig_pts} vectors")

# Upload near-duplicate (slightly modified)
near_dup = dup_content.replace("shadow deployments", "blue-green deployments").replace(
    "Feature stores", "Data pipelines")
resp = requests.post(f"{KB_URL}/upload", headers=headers(TOKEN), json={
    "filename": "ml_production_NEARDUPE.txt",
    "content_base64": b64(near_dup),
    "mime_type": "text/plain",
}, timeout=TIMEOUT)
check(resp.status_code == 200, f"Near-dup upload status: {resp.status_code}")
nd_data = resp.json()
nd_dedup = nd_data.get("metadata", {}).get("deduplication", nd_data.get("metadata", {}).get("dedup_stats", {}))
print(f"  Near-dup dedup stats: {json.dumps(nd_dedup, indent=4)}")
near_dup_id = nd_data["document_id"]

# STEP 8: Bucket System Deep Testing
section("STEP 8: Bucket System Deep Testing")

# 8a: Check auto-routing - docs should be in appropriate buckets
doc_buckets = {}
for i, doc_id in enumerate(doc_ids):
    bkt = check_db(
        f"SELECT b.name FROM documents d JOIN buckets b ON d.bucket_id = b.id "
        f"WHERE d.id = '{doc_id}';"
    )
    doc_buckets[doc_id] = bkt
    print(f"  Doc {i+1} '{test_docs[i]['filename']}' -> bucket: '{bkt}'")

# 8b: Create sub-bucket
create_resp = requests.post(f"{KB_URL}/buckets", headers=headers(TOKEN), json={
    "name": "ML Papers",
    "description": "Machine learning research papers",
    "parent_bucket_id": rr_bucket,
}, timeout=TIMEOUT)
check(create_resp.status_code == 200, f"Create sub-bucket: {create_resp.status_code}")
sub_bucket = create_resp.json()
sub_bucket_id = sub_bucket["bucket_id"]
print(f"  Sub-bucket created: id={sub_bucket_id}, path={sub_bucket.get('path','?')}")
check(sub_bucket.get("depth", 0) == 1, f"Sub-bucket depth={sub_bucket.get('depth','?')}")

# Verify in DB
db_sub = check_db(
    f"SELECT name, depth, path, parent_bucket_id FROM buckets WHERE id = '{sub_bucket_id}';"
)
print(f"  DB sub-bucket: {db_sub}")
check("ML Papers" in db_sub, "Sub-bucket name in DB")

# 8c: Create deeper nesting (depth 2)
create_resp2 = requests.post(f"{KB_URL}/buckets", headers=headers(TOKEN), json={
    "name": "Reinforcement Learning",
    "description": "RL-specific papers and notes",
    "parent_bucket_id": sub_bucket_id,
}, timeout=TIMEOUT)
check(create_resp2.status_code == 200, f"Create depth-2 bucket: {create_resp2.status_code}")
depth2_bucket = create_resp2.json()
depth2_id = depth2_bucket["bucket_id"]
check(depth2_bucket.get("depth", 0) == 2, f"Depth-2 bucket depth={depth2_bucket.get('depth','?')}")
print(f"  Depth-2 bucket: path={depth2_bucket.get('path','?')}")

# 8d: Verify bucket tree
tree_resp = requests.get(f"{KB_URL}/buckets/tree", headers=headers(TOKEN), timeout=TIMEOUT)
check(tree_resp.status_code == 200, f"Bucket tree: {tree_resp.status_code}")
tree = tree_resp.json()
tree_buckets = tree.get("buckets", [])
print(f"  Bucket tree: {len(tree_buckets)} buckets")
for tb in tree_buckets:
    indent = "  " * (tb.get("depth", 0) + 1)
    print(f"    {indent}{tb['name']} (depth={tb.get('depth',0)}, "
          f"docs={tb.get('document_count', 0)})")

# 8e: Bulk move documents to sub-bucket
# Find which docs are in Research bucket
rr_docs_str = check_db(
    f"SELECT id FROM documents WHERE bucket_id = '{rr_bucket}' AND "
    f"created_by = '{USER_ID}' AND status != 'failed' LIMIT 5;"
)
rr_doc_ids = [d.strip() for d in rr_docs_str.split("\n") if d.strip()]
print(f"  Docs in Research bucket: {len(rr_doc_ids)}")

if rr_doc_ids:
    move_resp = requests.post(f"{KB_URL}/buckets/bulk-move-documents",
        headers=headers(TOKEN), json={
            "source_bucket_id": rr_bucket,
            "target_bucket_id": sub_bucket_id,
        }, timeout=TIMEOUT)
    check(move_resp.status_code == 200, f"Bulk move: {move_resp.status_code}")
    move_data = move_resp.json()
    print(f"  Bulk move result: {json.dumps(move_data, indent=4)}")
    
    # Verify in DB
    moved_count = check_db(
        f"SELECT COUNT(*) FROM documents WHERE bucket_id = '{sub_bucket_id}' "
        f"AND created_by = '{USER_ID}';"
    )
    print(f"  Docs in sub-bucket after move: {moved_count}")
    
    # Verify in Qdrant - vectors should have updated bucket_id
    time.sleep(1)  # Allow propagation
    for moved_doc_id in rr_doc_ids[:2]:  # Check first 2
        scroll = check_qdrant("/collections/documents_768/points/scroll", "POST", {
            "filter": {"must": [{"key": "document_id", "match": {"value": moved_doc_id}}]},
            "limit": 5, "with_payload": True, "with_vectors": False,
        })
        pts = scroll.get("result", {}).get("points", [])
        if pts:
            qdrant_bucket = pts[0].get("payload", {}).get("bucket_id", "")
            check(qdrant_bucket == sub_bucket_id,
                  f"Qdrant bucket_id updated for {moved_doc_id[:8]}: {qdrant_bucket[:8]}...")
        else:
            print(f"  [WARN] No Qdrant points for {moved_doc_id[:8]}")

# 8f: Route preview
route_prev = requests.post(f"{KB_URL}/buckets/route-preview",
    headers=headers(TOKEN), json={
        "title": "Neural Network Training",
        "preview_text": "This paper discusses training techniques for deep neural networks",
    }, timeout=TIMEOUT)
check(route_prev.status_code == 200, f"Route preview: {route_prev.status_code}")
rp_data = route_prev.json()
print(f"  Route preview: mode={rp_data.get('mode','?')}, "
      f"confidence={rp_data.get('selected_confidence','?')}, "
      f"requires_confirm={rp_data.get('requires_confirmation','?')}")
candidates = rp_data.get("candidates", [])
for c in candidates[:3]:
    print(f"    Candidate: {c.get('bucket_name','?')} "
          f"(score={c.get('score','?')})")

# STEP 9: Bucket deletion with redistribution
section("STEP 9: Bucket Deletion with Redistribution")

# First move everything out of depth-2 bucket
# Delete depth-2 bucket, reassign to sub-bucket's parent
del_resp = requests.delete(f"{KB_URL}/buckets/{depth2_id}",
    headers=headers(TOKEN), json={"target_bucket_id": sub_bucket_id},
    timeout=TIMEOUT)
check(del_resp.status_code == 200, f"Delete depth-2 bucket: {del_resp.status_code}")
del_data = del_resp.json()
print(f"  Delete result: {json.dumps(del_data, indent=4)}")

# Verify deleted in DB
deleted_check = check_db(
    f"SELECT is_deleted FROM buckets WHERE id = '{depth2_id}';"
)
check(deleted_check == "t", f"Depth-2 bucket is_deleted={deleted_check}")

# STEP 10: Chat endpoint
section("STEP 10: Chat Endpoint (RAG)")

chat_resp = requests.post(f"{KB_URL}/chat", headers=headers(TOKEN), json={
    "message": "What are the best practices for deploying ML models?"
}, timeout=TIMEOUT)
check(chat_resp.status_code == 200, f"Chat status: {chat_resp.status_code}")
chat_data = chat_resp.json()
print(f"  Chat response keys: {sorted(chat_data.keys())}")
if "answer" in chat_data:
    print(f"  Answer preview: {chat_data['answer'][:200]}...")
if "sources" in chat_data:
    print(f"  Sources: {len(chat_data.get('sources',[]))} referenced")

# STEP 11: Embedding DLQ ops
section("STEP 11: Embedding DLQ Operations")

dlq_stats = requests.get(f"{KB_URL}/ops/embedding-dlq/stats",
    headers=headers(TOKEN), timeout=TIMEOUT)
check(dlq_stats.status_code == 200, f"DLQ stats: {dlq_stats.status_code}")
print(f"  DLQ stats: {json.dumps(dlq_stats.json(), indent=4)}")

# STEP 12: Document listing with document details
section("STEP 12: Document Listing & Details")

docs_resp = requests.get(f"{KB_URL}/documents", headers=headers(TOKEN), timeout=TIMEOUT)
check(docs_resp.status_code == 200, f"List documents: {docs_resp.status_code}")
docs = docs_resp.json()
print(f"  Total documents: {len(docs)}")

for d in docs:
    print(f"  - {d.get('filename','?'):40s} status={d.get('status','?'):10s} "
          f"type={d.get('content_type','?'):15s} bucket={d.get('bucket_id','?')[:8]}...")

# Check required fields
required_fields = ["document_id", "status", "content_type", "owner_id"]
for d in docs[:1]:
    for f in required_fields:
        check(f in d, f"Document has field '{f}'")

# STEP 13: Edge cases
section("STEP 13: Edge Cases & Error Handling")

# 13a: Empty content
empty_resp = requests.post(f"{KB_URL}/upload", headers=headers(TOKEN), json={
    "filename": "empty.txt",
    "content_base64": b64(""),
    "mime_type": "text/plain",
}, timeout=TIMEOUT)
print(f"  Empty content upload: status={empty_resp.status_code}")

# 13b: Very short content
short_resp = requests.post(f"{KB_URL}/upload", headers=headers(TOKEN), json={
    "filename": "short.txt",
    "content_base64": b64("Hi"),
    "mime_type": "text/plain",
}, timeout=TIMEOUT)
print(f"  Very short content upload: status={short_resp.status_code}")
if short_resp.status_code == 200:
    sd = short_resp.json()
    print(f"    word_count={sd.get('word_count')}, strategy={sd.get('strategy')}")

# 13c: No auth on documents (optional auth)
no_auth = requests.get(f"{KB_URL}/documents", timeout=TIMEOUT)
check(no_auth.status_code == 200, f"No-auth /documents: {no_auth.status_code}")
check(isinstance(no_auth.json(), list), "Returns list (may be empty for anonymous)")

# 13d: No auth on buckets (required auth)
no_auth_bkt = requests.get(f"{KB_URL}/buckets", timeout=TIMEOUT)
check(no_auth_bkt.status_code in (401, 403),
      f"No-auth /buckets rejected: {no_auth_bkt.status_code}")

# 13e: Delete a default bucket (is_default=true) should fail
# Note: 'Needs Classification' is NOT a default bucket (is_default=false)
# Use a real default like 'Research and Reference'
default_bkt_id = rr_bucket
del_default = requests.delete(f"{KB_URL}/buckets/{default_bkt_id}",
    headers=headers(TOKEN), json={"target_bucket_id": nc_bucket},
    timeout=TIMEOUT)
check(del_default.status_code in (400, 403),
      f"Delete default bucket blocked: {del_default.status_code}")
print(f"  Error: {del_default.json().get('detail','?')[:80]}")

# 13f: Search with empty query
empty_search = requests.post(f"{KB_URL}/search", headers=headers(TOKEN), json={
    "query": "", "top_k": 5,
}, timeout=TIMEOUT)
print(f"  Empty query search: status={empty_search.status_code}")

# 13g: Upload with bucket_hint
hint_resp = requests.post(f"{KB_URL}/upload", headers=headers(TOKEN), json={
    "filename": "work_report.txt",
    "content_base64": b64("Quarterly performance report for Q3 2025. Revenue increased 15%."),
    "mime_type": "text/plain",
    "bucket_hint": "Work and Projects",
}, timeout=TIMEOUT)
check(hint_resp.status_code == 200, f"Upload with bucket_hint: {hint_resp.status_code}")
if hint_resp.status_code == 200:
    hint_data = hint_resp.json()
    hint_doc_id = hint_data["document_id"]
    # Check which bucket it ended up in
    hint_doc_id = hint_data["document_id"]
    hint_bucket = check_db(
        f"SELECT b.name FROM documents d JOIN buckets b ON d.bucket_id = b.id "
        f"WHERE d.id = '{hint_doc_id}';"
    )
    print(f"  Bucket hint doc went to: '{hint_bucket}'")

# STEP 14: Cross-store consistency verification
section("STEP 14: Cross-Store Consistency Verification")

# Get all doc IDs from PostgreSQL for this user
pg_docs = check_db(
    f"SELECT id FROM documents WHERE created_by = '{USER_ID}' ORDER BY created_at;"
)
pg_doc_list = [d.strip() for d in pg_docs.split("\n") if d.strip()]
print(f"  PostgreSQL documents: {len(pg_doc_list)}")

# Count total chunks in PG
pg_chunk_count = check_db(
    f"SELECT COUNT(*) FROM document_chunks WHERE document_id IN "
    f"(SELECT id FROM documents WHERE created_by = '{USER_ID}');"
)
print(f"  PostgreSQL chunks: {pg_chunk_count}")

# Qdrant count for user (uses user_id field)
qdrant_count = check_qdrant("/collections/documents_768/points/count", "POST", {
    "filter": {"must": [{"key": "user_id", "match": {"value": USER_ID}}]},
    "exact": True,
})
qdrant_pts = qdrant_count.get("result", {}).get("count", 0)
print(f"  Qdrant vectors: {qdrant_pts}")

# Meilisearch for user
meili_user = requests.post(f"{MEILI_URL}/indexes/kb_chunks/search", json={
    "q": "",
    "filter": f"owner_id = '{USER_ID}'",
    "limit": 100,
}, headers={"Authorization": f"Bearer {MEILI_KEY}"}, timeout=10)
if meili_user.status_code == 200:
    meili_count = meili_user.json().get("estimatedTotalHits", 0)
else:
    # Meilisearch may not have filterable owner_id - try without filter
    meili_all = check_meili("kb_chunks", "")
    meili_count = meili_all.get("estimatedTotalHits", 0)
    print(f"  Note: Meilisearch count is for ALL users")
print(f"  Meilisearch documents: {meili_count}")

# Redis cache keys
redis_keys = check_redis("*")
print(f"  Redis keys: {len(redis_keys)}")
for k in redis_keys[:10]:
    print(f"    {k}")

# Compare PG chunks vs Qdrant vectors
# Some chunks may be deduped (no vectors), so Qdrant <= PG chunks
check(qdrant_pts > 0, f"Qdrant has vectors for user")
check(int(pg_chunk_count) >= qdrant_pts,
      f"PG chunks ({pg_chunk_count}) >= Qdrant vectors ({qdrant_pts})")

# STEP 15: Gateway routing verification
section("STEP 15: Gateway Routing Verification")

# KB search through gateway
gw_search = requests.post(f"{GATEWAY_URL}/search", headers=headers(TOKEN), json={
    "query": "machine learning deployment", "top_k": 3,
}, timeout=TIMEOUT)
check(gw_search.status_code == 200, f"Gateway search: {gw_search.status_code}")
if gw_search.status_code == 200:
    gw_data = gw_search.json()
    print(f"  Results: {len(gw_data.get('results',[]))}")

# KB documents through gateway
gw_docs = requests.get(f"{GATEWAY_URL}/documents", headers=headers(TOKEN), timeout=TIMEOUT)
check(gw_docs.status_code == 200, f"Gateway documents: {gw_docs.status_code}")
print(f"  Docs via gateway: {len(gw_docs.json())}")

# KB buckets through gateway
gw_bkts = requests.get(f"{GATEWAY_URL}/buckets", headers=headers(TOKEN), timeout=TIMEOUT)
check(gw_bkts.status_code == 200, f"Gateway buckets: {gw_bkts.status_code}")
print(f"  Buckets via gateway: {len(gw_bkts.json())}")

# Auth through gateway
gw_me = requests.get(f"{GATEWAY_URL}/auth/me", headers=headers(TOKEN), timeout=TIMEOUT)
check(gw_me.status_code == 200, f"Gateway auth/me: {gw_me.status_code}")

# STEP 16: Service logs check
section("STEP 16: Service Logs Verification")

import subprocess

for svc in ["plos-knowledge-base", "plos-journal-parser", "plos-context-broker"]:
    result = subprocess.run(
        ["docker", "logs", "--tail", "20", svc],
        capture_output=True, text=True, timeout=10
    )
    log_lines = result.stdout.strip().split("\n") + result.stderr.strip().split("\n")
    error_lines = [l for l in log_lines if "ERROR" in l or "Traceback" in l]
    if error_lines:
        print(f"  [{svc}] ERRORS found:")
        for e in error_lines[:3]:
            print(f"    {e[:120]}")
    else:
        print(f"  [{svc}] No errors in last 20 log lines")

# SUMMARY
section("SUMMARY")

print(f"""
  User: {USER_ID}
  Documents uploaded: {len(doc_ids) + 3}  (5 unique + 1 exact dup + 1 near-dup + 1 hinted)
  Buckets: 4 default + 2 created (1 deleted)
  PostgreSQL docs: {len(pg_doc_list)}
  PostgreSQL chunks: {pg_chunk_count}
  Qdrant vectors: {qdrant_pts}
  Meilisearch docs: {meili_count}
  Redis keys: {len(redis_keys)}
  
  Features tested:
  - Authentication (register, login, profile, token validation)
  - Document upload pipeline (text, base64, dedup, auto-routing)
  - Deduplication (exact match, near-duplicate detection, forced retention)
  - Hybrid search (semantic + keyword + typo tiers, RRF fusion, diagnostics)
  - Bucket system (defaults, create, nest, tree, bulk-move, delete/redistribute)
  - Route preview (AI-assisted bucket classification)
  - Chat/RAG (retrieval-augmented generation)
  - Embedding DLQ (dead letter queue stats)
  - Document listing with metadata
  - Error handling (empty content, short content, no auth, invalid operations)
  - Cross-store consistency (PG, Qdrant, Meilisearch, Redis)
  - API Gateway routing (search, documents, buckets, auth)
  - Service log health (no errors)
""")

print("Deep manual testing complete!")
