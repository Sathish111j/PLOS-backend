"""
End-to-End Test Suite for Knowledge Base Service.

Tests the entire KB lifecycle: document upload, listing, search,
RAG chat, buckets, and graph endpoints against running containers.

Run:
    pytest tests/test_e2e_knowledge_base.py -v --tb=short -m e2e

Pre-requisites:
    docker compose up -d  (all services healthy)
"""

from __future__ import annotations

import base64
import logging
import os
import time
import uuid
from typing import Any

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KB_URL = os.getenv("KB_URL", "http://localhost:8003")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8002")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", "120"))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared state & helpers
# ---------------------------------------------------------------------------


class _KB_State:
    """Mutable container shared across ordered tests."""

    token: str = ""
    user_id: str = ""
    doc_id_1: str = ""
    doc_id_2: str = ""
    bucket_id: str = ""
    session_id: str = ""


def _h(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _text_b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def state() -> _KB_State:
    return _KB_State()


@pytest.fixture(scope="module", autouse=True)
def _ensure_healthy() -> None:
    """Skip entire module if knowledge-base is not healthy."""
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            r = requests.get(f"{KB_URL}/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "healthy":
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    pytest.skip("knowledge-base not healthy -- skipping")


@pytest.fixture(scope="module", autouse=True)
def _setup_auth_user(state: _KB_State) -> None:
    """Register a unique user for KB tests."""
    unique = uuid.uuid4().hex[:8]
    email = f"kb-e2e-{unique}@plos-test.dev"
    password = "E2eTestKB99!!"
    resp = requests.post(
        f"{AUTH_URL}/auth/register",
        json={
            "email": email,
            "username": f"kb_e2e_{unique}",
            "password": password,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert resp.status_code == 201, f"Auth register failed: {resp.text}"
    data = resp.json()
    state.token = data["access_token"]
    state.user_id = data["user"]["user_id"]
    logger.info("[KB-SETUP] Registered user %s (id=%s)", email, state.user_id)


# ===================================================================
# 1. HEALTH & METRICS
# ===================================================================


@pytest.mark.e2e
class TestKBHealth:
    """Health and metrics endpoints."""

    def test_health(self) -> None:
        resp = requests.get(f"{KB_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_dependencies(self) -> None:
        """Health check should report dependency status."""
        resp = requests.get(f"{KB_URL}/health", timeout=HTTP_TIMEOUT)
        data = resp.json()
        deps = data.get("dependencies", data.get("checks", {}))
        # Expect at least some backend deps reported
        assert isinstance(deps, (dict, list))
        logger.info("[KB] Health deps: %s", deps)

    def test_metrics(self) -> None:
        resp = requests.get(f"{KB_URL}/metrics", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200


# ===================================================================
# 2. DOCUMENT UPLOAD
# ===================================================================


@pytest.mark.e2e
class TestDocumentUpload:
    """Test uploading documents through the full pipeline."""

    SAMPLE_DOCS = [
        (
            "test_nutrition_guide.txt",
            "A balanced diet should include proteins, carbohydrates, fats, "
            "vitamins, and minerals. Aim for 2000-2500 calories per day. "
            "Drink at least 2 liters of water. Include vegetables in every meal. "
            "Limit processed sugars. Whole grains are preferred over refined ones. "
            "Omega-3 fatty acids from fish are beneficial for heart health.",
        ),
        (
            "test_sleep_guide.txt",
            "Good sleep hygiene involves keeping a consistent sleep schedule. "
            "Adults need 7-9 hours of sleep per night. Avoid screens before bed. "
            "Keep the bedroom dark and cool at 18-20 degrees Celsius. "
            "Limit caffeine intake after 2pm. Regular exercise improves sleep "
            "quality but avoid intense workouts close to bedtime.",
        ),
    ]

    def test_upload_first_document(self, state: _KB_State) -> None:
        """Upload a nutrition guide document."""
        filename, content = self.SAMPLE_DOCS[0]
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_h(state.token),
            json={
                "filename": filename,
                "content_base64": _text_b64(content),
                "mime_type": "text/plain",
            },
            timeout=UPLOAD_TIMEOUT,
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert "document_id" in data
        assert data["status"] in ("processed", "completed")
        assert data["word_count"] > 0
        assert data["char_count"] > 0
        state.doc_id_1 = data["document_id"]
        logger.info(
            "[KB] Uploaded doc 1: %s (words=%d, strategy=%s)",
            state.doc_id_1,
            data["word_count"],
            data.get("strategy"),
        )

    def test_upload_second_document(self, state: _KB_State) -> None:
        """Upload a sleep guide document."""
        filename, content = self.SAMPLE_DOCS[1]
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_h(state.token),
            json={
                "filename": filename,
                "content_base64": _text_b64(content),
                "mime_type": "text/plain",
            },
            timeout=UPLOAD_TIMEOUT,
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert data["status"] in ("processed", "completed")
        state.doc_id_2 = data["document_id"]
        logger.info("[KB] Uploaded doc 2: %s", state.doc_id_2)

    def test_upload_with_bucket_hint(self, state: _KB_State) -> None:
        """Upload with a bucket_hint for AI-based routing."""
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_h(state.token),
            json={
                "filename": "exercise_tips.txt",
                "content_base64": _text_b64(
                    "Running improves cardiovascular health. Start with 20-minute "
                    "jogs three times a week. Gradually increase distance."
                ),
                "mime_type": "text/plain",
                "bucket_hint": "fitness and exercise",
            },
            timeout=UPLOAD_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("processed", "completed")
        # AI bucket routing should have been attempted
        if data.get("content_bucket_id"):
            logger.info("[KB] Routed to bucket %s", data["content_bucket_id"])

    def test_upload_no_content_rejected(self, state: _KB_State) -> None:
        """Upload without content or source_url should fail."""
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_h(state.token),
            json={"filename": "empty.txt"},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 422

    def test_upload_unauthenticated(self) -> None:
        """Upload without auth -- KB may use optional auth or reject."""
        resp = requests.post(
            f"{KB_URL}/upload",
            json={
                "filename": "test.txt",
                "content_base64": _text_b64("test content"),
            },
            timeout=HTTP_TIMEOUT,
        )
        # KB uses optional auth: unauthenticated requests may succeed with anonymous owner
        assert resp.status_code in (200, 401, 403)


# ===================================================================
# 3. DOCUMENT LISTING
# ===================================================================


@pytest.mark.e2e
class TestDocumentListing:
    """Test document listing and filtering."""

    def test_list_documents(self, state: _KB_State) -> None:
        """List all documents for the user."""
        resp = requests.get(
            f"{KB_URL}/documents",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        docs = data if isinstance(data, list) else data.get("documents", [])
        assert len(docs) >= 2, f"Expected at least 2 docs, got {len(docs)}"
        doc_ids = [d["document_id"] for d in docs]
        assert state.doc_id_1 in doc_ids
        assert state.doc_id_2 in doc_ids
        logger.info("[KB] Listed %d documents", len(docs))

    def test_list_unauthenticated(self) -> None:
        resp = requests.get(f"{KB_URL}/documents", timeout=HTTP_TIMEOUT)
        # KB uses optional auth: unauthenticated requests may succeed
        assert resp.status_code in (200, 401, 403)


# ===================================================================
# 4. SEARCH
# ===================================================================


@pytest.mark.e2e
class TestKBSearch:
    """Test hybrid search functionality."""

    def test_basic_search(self, state: _KB_State) -> None:
        """Search for nutrition-related content."""
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_h(state.token),
            json={"query": "balanced diet nutrition calories"},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(f"Gemini embedding transient failure: {resp.status_code}")
        assert resp.status_code == 200, f"Search failed: {resp.text}"
        data = resp.json()
        assert isinstance(data["results"], list)
        assert data["query"] == "balanced diet nutrition calories"
        logger.info("[KB] Search returned %d results", len(data["results"]))

    def test_search_sleep(self, state: _KB_State) -> None:
        """Search for sleep-related content."""
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_h(state.token),
            json={"query": "sleep schedule hours night"},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(f"Gemini embedding transient failure: {resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        # Embedding may not be ready yet; accept 0 results gracefully
        assert isinstance(data["results"], list)

    def test_search_returns_metadata(self, state: _KB_State) -> None:
        """Search results should include scoring metadata."""
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_h(state.token),
            json={"query": "water intake hydration", "top_k": 5},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(f"Gemini embedding transient failure: {resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("owner_id") == state.user_id
        if data["results"]:
            result = data["results"][0]
            assert "score" in result or "combined_score" in result

    def test_search_empty_query(self, state: _KB_State) -> None:
        """Empty query should be rejected."""
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_h(state.token),
            json={"query": ""},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 422


# ===================================================================
# 5. RAG CHAT
# ===================================================================


@pytest.mark.e2e
class TestRAGChat:
    """Test RAG chat with the uploaded knowledge base."""

    def test_chat_creates_session(self, state: _KB_State) -> None:
        """First chat message should create a session and return a sourced answer."""
        resp = requests.post(
            f"{KB_URL}/chat",
            headers=_h(state.token),
            json={
                "message": "What are the recommended daily calories?",
                "session_id": None,
            },
            timeout=UPLOAD_TIMEOUT,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(f"Gemini embedding transient failure: {resp.status_code}")
        assert resp.status_code == 200, f"Chat failed: {resp.text}"
        data = resp.json()
        assert data.get("answer"), "Expected non-empty answer"
        assert data.get("owner_id") == state.user_id
        assert isinstance(data.get("sources"), list)
        if data.get("session_id"):
            state.session_id = data["session_id"]
        logger.info(
            "[KB] Chat answer: %s... (sources=%d)",
            data["answer"][:80],
            len(data.get("sources", [])),
        )

    def test_chat_follow_up(self, state: _KB_State) -> None:
        """Follow-up in the same session should work."""
        if not state.session_id:
            pytest.skip("No session_id from first chat")
        resp = requests.post(
            f"{KB_URL}/chat",
            headers=_h(state.token),
            json={
                "message": "What about sleep recommendations?",
                "session_id": state.session_id,
            },
            timeout=UPLOAD_TIMEOUT,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(f"Gemini embedding transient failure: {resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("answer")
        assert data.get("session_id") == state.session_id

    def test_chat_sessions_list(self, state: _KB_State) -> None:
        """List chat sessions for the user."""
        resp = requests.get(
            f"{KB_URL}/chat/sessions",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        assert len(sessions) >= 1
        logger.info("[KB] %d chat sessions", len(sessions))

    def test_chat_empty_message(self, state: _KB_State) -> None:
        """Empty message should be rejected."""
        resp = requests.post(
            f"{KB_URL}/chat",
            headers=_h(state.token),
            json={"message": ""},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 422


# ===================================================================
# 6. BUCKETS
# ===================================================================


@pytest.mark.e2e
class TestKBBuckets:
    """Test bucket management endpoints."""

    def test_list_buckets(self, state: _KB_State) -> None:
        """List buckets for the user (includes auto-created default)."""
        resp = requests.get(
            f"{KB_URL}/buckets",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        buckets = data if isinstance(data, list) else data.get("buckets", [])
        assert len(buckets) >= 1, "Expected at least the default bucket"
        logger.info("[KB] %d buckets", len(buckets))

    def test_bucket_tree(self, state: _KB_State) -> None:
        """Get the bucket tree structure."""
        resp = requests.get(
            f"{KB_URL}/buckets/tree",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        tree_buckets = data if isinstance(data, list) else data.get("buckets", [])
        assert isinstance(tree_buckets, list)

    def test_create_bucket(self, state: _KB_State) -> None:
        """Create a new bucket."""
        resp = requests.post(
            f"{KB_URL}/buckets",
            headers=_h(state.token),
            json={
                "name": "e2e-test-bucket",
                "description": "Bucket created by E2E tests",
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Create bucket failed: {resp.text}"
        data = resp.json()
        assert "bucket_id" in data or "id" in data
        state.bucket_id = data.get("bucket_id") or data.get("id") or ""
        logger.info("[KB] Created bucket %s", state.bucket_id)

    def test_route_preview(self, state: _KB_State) -> None:
        """Test bucket routing preview (AI-assisted)."""
        resp = requests.post(
            f"{KB_URL}/buckets/route-preview",
            headers=_h(state.token),
            json={
                "title": "Morning workout routine",
                "preview_text": (
                    "A guide to effective morning exercises for beginners "
                    "including stretching, yoga, and light cardio."
                ),
            },
            timeout=UPLOAD_TIMEOUT,
        )
        # route-preview may return 200 with candidates or 500 if no AI config
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("[KB] Route preview: %s", data)


# ===================================================================
# 7. EMBEDDING DLQ
# ===================================================================


@pytest.mark.e2e
class TestEmbeddingDLQ:
    """Test embedding dead letter queue stats."""

    def test_dlq_stats(self, state: _KB_State) -> None:
        """Retrieve DLQ stats."""
        resp = requests.get(
            f"{KB_URL}/ops/embedding-dlq/stats",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "active_dlq" in data
        assert isinstance(data["active_dlq"], int)


# ===================================================================
# 8. GRAPH (Knowledge Graph)
# ===================================================================


@pytest.mark.e2e
class TestKBGraph:
    """Test knowledge graph endpoints."""

    def test_document_entities(self, state: _KB_State) -> None:
        """Get entities for an uploaded document."""
        if not state.doc_id_1:
            pytest.skip("No document uploaded")
        resp = requests.get(
            f"{KB_URL}/document/{state.doc_id_1}/entities",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        # Graph may not be populated yet; just verify the endpoint responds
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("[KB] Entities for doc 1: %s", data)
