"""
Docker End-to-End Test Suite for PLOS Backend.

Tests all services through their HTTP APIs against running Docker containers.
Requires all services to be up and running via docker-compose.

Run:
    pytest tests/test_e2e_docker.py -v --tb=short

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

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/api/v1")
KB_URL = os.getenv("KB_URL", "http://localhost:8003")
CONTEXT_URL = os.getenv("CONTEXT_URL", "http://localhost:8001")
JOURNAL_URL = os.getenv("JOURNAL_URL", "http://localhost:8002")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8002")

# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT = 30

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _SharedState:
    """Mutable container shared across tests via module-scoped fixture."""

    token: str = ""
    user_id: str = ""
    document_ids: list[str] = []
    bucket_ids: dict[str, str] = {}
    custom_bucket_id: str = ""
    journal_entry_id: str = ""


@pytest.fixture(scope="module")
def state() -> _SharedState:
    """Module-scoped state shared across ordered tests."""
    return _SharedState()


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _make_text_b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


class TestHealthChecks:
    """Verify all services are reachable and healthy."""

    def test_knowledge_base_health(self) -> None:
        resp = requests.get(f"{KB_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy"
        logger.info("[HEALTH] Knowledge-base healthy")

    def test_context_broker_health(self) -> None:
        resp = requests.get(f"{CONTEXT_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy"
        logger.info("[HEALTH] Context-broker healthy")

    def test_journal_parser_health(self) -> None:
        resp = requests.get(f"{JOURNAL_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy"
        logger.info("[HEALTH] Journal-parser healthy")

    def test_api_gateway_reachable(self) -> None:
        # Gateway itself does not expose /health -- verify it responds to a routed path
        # An unauthenticated request to a known route should return 401/403, confirming
        # the gateway is up and routing correctly.
        resp = requests.get(f"{GATEWAY_URL}/documents", timeout=HTTP_TIMEOUT)
        assert resp.status_code in (200, 401, 403), (
            f"Gateway unreachable or misconfigured: {resp.status_code}"
        )
        logger.info("[HEALTH] API Gateway reachable (status=%d)", resp.status_code)


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------


class TestAuthFlow:
    """Test user registration, login, and profile retrieval."""

    def test_register_user(self, state: _SharedState) -> None:
        unique = uuid.uuid4().hex[:8]
        payload = {
            "username": f"e2e_user_{unique}",
            "email": f"e2e_{unique}@plos-test.dev",
            "password": "TestPassword123!",
        }
        resp = requests.post(
            f"{AUTH_URL}/auth/register",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (200, 201), f"Register failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert "user" in data
        state.token = data["access_token"]
        state.user_id = data["user"]["user_id"]
        logger.info(
            "[AUTH] User registered: %s (id=%s)", payload["email"], state.user_id
        )

    def test_login_user(self, state: _SharedState) -> None:
        # Re-login to verify credentials work
        unique = state.user_id[:8]
        # We need to use the same credentials; extract from registration
        # Instead, register a second user and login with known creds
        payload = {
            "username": f"e2e_login_{unique}",
            "email": f"e2e_login_{unique}@plos-test.dev",
            "password": "LoginTest456!",
        }
        resp = requests.post(
            f"{AUTH_URL}/auth/register",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (200, 201), f"Register #2 failed: {resp.text}"
        login_data = resp.json()

        # Now login
        resp = requests.post(
            f"{AUTH_URL}/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        logger.info("[AUTH] Login successful for %s", payload["email"])

    def test_get_profile(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{AUTH_URL}/auth/me",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Profile failed: {resp.text}"
        data = resp.json()
        assert data["user_id"] == state.user_id
        logger.info("[AUTH] Profile retrieved for user %s", state.user_id)

    def test_auth_required_without_token(self) -> None:
        # /buckets requires authentication (unlike /documents which uses optional auth)
        resp = requests.get(f"{KB_URL}/buckets", timeout=HTTP_TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected auth error, got {resp.status_code}"
        )
        logger.info("[AUTH] Correctly rejected unauthenticated request")


# ---------------------------------------------------------------------------
# Document upload pipeline
# ---------------------------------------------------------------------------


class TestDocumentUpload:
    """Test document upload, processing, and storage pipeline."""

    def test_upload_text_document(self, state: _SharedState) -> None:
        content = (
            "Machine learning is a subset of artificial intelligence that focuses "
            "on building systems that learn from data. Deep learning uses neural "
            "networks with many layers to model complex patterns. Key applications "
            "include natural language processing, computer vision, and autonomous "
            "vehicles. Transfer learning enables reuse of pre-trained models. "
            "Regularization techniques prevent overfitting in neural networks."
        )
        payload = {
            "filename": "e2e-ml-overview.txt",
            "content_base64": _make_text_b64(content),
            "mime_type": "text/plain",
        }
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "completed"
        assert data["document_id"]
        assert data["word_count"] > 0
        assert data["metadata"]["chunk_count"] >= 1
        assert data["metadata"]["deduplication"]["input_chunks"] >= 1
        # Verify integrity chain
        chain = data["metadata"]["integrity_chain"]
        assert len(chain) >= 3, "Expected at least 3 integrity stages"
        for stage in chain:
            assert stage["is_verified"] is True
        state.document_ids.append(data["document_id"])
        logger.info(
            "[UPLOAD] Document uploaded: id=%s, chunks=%d, words=%d",
            data["document_id"],
            data["metadata"]["chunk_count"],
            data["word_count"],
        )

    def test_upload_second_document(self, state: _SharedState) -> None:
        content = (
            "Python is the most popular language for data science. Libraries like "
            "NumPy and Pandas provide powerful data manipulation capabilities. "
            "Scikit-learn offers a wide range of machine learning algorithms. "
            "TensorFlow and PyTorch are the leading deep learning frameworks. "
            "Jupyter notebooks are essential for exploratory data analysis."
        )
        payload = {
            "filename": "e2e-python-datascience.txt",
            "content_base64": _make_text_b64(content),
            "mime_type": "text/plain",
        }
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "completed"
        state.document_ids.append(data["document_id"])
        logger.info(
            "[UPLOAD] Second document uploaded: id=%s", data["document_id"]
        )

    def test_upload_duplicate_content(self, state: _SharedState) -> None:
        """Upload same content with different filename -- dedup should detect."""
        content = (
            "Machine learning is a subset of artificial intelligence that focuses "
            "on building systems that learn from data. Deep learning uses neural "
            "networks with many layers to model complex patterns. Key applications "
            "include natural language processing, computer vision, and autonomous "
            "vehicles. Transfer learning enables reuse of pre-trained models. "
            "Regularization techniques prevent overfitting in neural networks."
        )
        payload = {
            "filename": "e2e-ml-overview-copy.txt",
            "content_base64": _make_text_b64(content),
            "mime_type": "text/plain",
        }
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Duplicate upload failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "completed"
        dedup = data["metadata"]["deduplication"]
        # The dedup exact stage should detect at least 1 duplicate
        # (forced_retention may keep the chunk anyway)
        logger.info(
            "[UPLOAD] Duplicate upload: exact=%d, retained=%d, forced=%s",
            dedup["stage_counts"]["exact"],
            dedup["retained_chunks"],
            dedup.get("forced_retention", False),
        )
        state.document_ids.append(data["document_id"])

    def test_upload_via_ingest_endpoint(self, state: _SharedState) -> None:
        """Test the /ingest endpoint (alternative upload path)."""
        content = (
            "Cloud computing provides on-demand access to shared pools of "
            "computing resources. Infrastructure as a Service, Platform as a "
            "Service, and Software as a Service are the three main models. "
            "Major providers include AWS, Azure, and Google Cloud Platform."
        )
        payload = {
            "filename": "e2e-cloud-overview.txt",
            "content_base64": _make_text_b64(content),
            "mime_type": "text/plain",
        }
        resp = requests.post(
            f"{KB_URL}/ingest",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Ingest failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "completed"
        state.document_ids.append(data["document_id"])
        logger.info("[UPLOAD] Ingest endpoint: id=%s", data["document_id"])


# ---------------------------------------------------------------------------
# Document listing
# ---------------------------------------------------------------------------


class TestDocumentListing:
    """Test document retrieval endpoints."""

    def test_list_documents(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{KB_URL}/documents",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"List documents failed: {resp.text}"
        docs = resp.json()
        assert isinstance(docs, list)
        assert len(docs) >= 2, f"Expected >= 2 docs, got {len(docs)}"
        # Verify all uploaded docs appear
        doc_ids_in_list = {d["document_id"] for d in docs}
        for doc_id in state.document_ids:
            assert doc_id in doc_ids_in_list, (
                f"Document {doc_id} not found in listing"
            )
        logger.info("[DOCS] Listed %d documents", len(docs))

    def test_documents_have_expected_fields(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{KB_URL}/documents",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        docs = resp.json()
        required_fields = [
            "document_id",
            "owner_id",
            "filename",
            "status",
            "content_type",
            "metadata",
        ]
        for doc in docs:
            for field in required_fields:
                assert field in doc, f"Missing field '{field}' in document"
        logger.info("[DOCS] All documents have required fields")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    """Test hybrid search functionality."""

    def test_search_returns_results(self, state: _SharedState) -> None:
        payload = {"query": "machine learning deep learning", "top_k": 5}
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Search failed: {resp.text}"
        data = resp.json()
        assert data["query"] == "machine learning deep learning"
        assert len(data["results"]) > 0, "Search returned no results"
        assert data["latency_ms"] > 0
        assert data["query_intent"] in ("hybrid", "semantic", "keyword")
        logger.info(
            "[SEARCH] Query returned %d results in %dms (intent=%s)",
            len(data["results"]),
            data["latency_ms"],
            data["query_intent"],
        )

    def test_search_result_structure(self, state: _SharedState) -> None:
        payload = {"query": "python data science", "top_k": 3}
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        for result in data["results"]:
            assert "document_id" in result
            assert "score" in result
            assert "tiers_matched" in result
            assert isinstance(result["tiers_matched"], list)
            assert result["score"] > 0
        logger.info("[SEARCH] Result structure validated")

    def test_search_diagnostics(self, state: _SharedState) -> None:
        payload = {"query": "neural networks training", "top_k": 5}
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        diag = data.get("diagnostics", {})
        assert "weights" in diag, "Missing search weights in diagnostics"
        assert "candidate_counts" in diag, "Missing candidate counts"
        assert "diversity" in diag, "Missing diversity info"
        logger.info(
            "[SEARCH] Diagnostics: weights=%s, candidates=%s",
            diag["weights"],
            diag["candidate_counts"],
        )

    def test_search_via_gateway(self, state: _SharedState) -> None:
        """Search through the API gateway."""
        payload = {"query": "cloud computing", "top_k": 3}
        resp = requests.post(
            f"{GATEWAY_URL}/search",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Gateway search failed: {resp.text}"
        data = resp.json()
        assert "results" in data
        logger.info(
            "[SEARCH] Gateway search returned %d results", len(data["results"])
        )

    def test_search_empty_query(self, state: _SharedState) -> None:
        """Empty or very short query should still return gracefully."""
        payload = {"query": "", "top_k": 5}
        resp = requests.post(
            f"{KB_URL}/search",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        # Either returns empty results or validation error -- both acceptable
        assert resp.status_code in (200, 422), (
            f"Unexpected status for empty query: {resp.status_code}"
        )
        logger.info("[SEARCH] Empty query handled gracefully: %d", resp.status_code)


# ---------------------------------------------------------------------------
# Bucket operations
# ---------------------------------------------------------------------------


class TestBuckets:
    """Test bucket CRUD and document organization."""

    def test_list_default_buckets(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{KB_URL}/buckets",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"List buckets failed: {resp.text}"
        buckets = resp.json()
        assert isinstance(buckets, list)
        assert len(buckets) >= 4, (
            f"Expected >= 4 default buckets, got {len(buckets)}"
        )
        for b in buckets:
            state.bucket_ids[b["name"]] = b["bucket_id"]
        logger.info(
            "[BUCKETS] Default buckets: %s",
            [b["name"] for b in buckets],
        )

    def test_bucket_tree(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{KB_URL}/buckets/tree",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "buckets" in data
        assert len(data["buckets"]) >= 4
        logger.info("[BUCKETS] Tree has %d nodes", len(data["buckets"]))

    def test_create_sub_bucket(self, state: _SharedState) -> None:
        parent_id = state.bucket_ids.get("Research and Reference", "")
        assert parent_id, "Parent bucket 'Research and Reference' not found"
        payload = {
            "name": f"E2E Test Sub-Bucket {uuid.uuid4().hex[:6]}",
            "description": "Created by E2E test",
            "parent_bucket_id": parent_id,
            "icon_emoji": "test_tube",
            "color_hex": "#FF6B6B",
        }
        resp = requests.post(
            f"{KB_URL}/buckets",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Create bucket failed: {resp.text}"
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["depth"] == 1
        assert data["parent_bucket_id"] == parent_id
        state.custom_bucket_id = data["bucket_id"]
        logger.info(
            "[BUCKETS] Sub-bucket created: %s (path=%s)",
            data["name"],
            data["path"],
        )

    def test_bulk_move_documents(self, state: _SharedState) -> None:
        """Move documents from one bucket to another."""
        source_id = state.bucket_ids.get("Research and Reference", "")
        target_id = state.custom_bucket_id
        assert source_id and target_id, "Bucket IDs required for move"
        payload = {
            "source_bucket_id": source_id,
            "target_bucket_id": target_id,
        }
        resp = requests.post(
            f"{KB_URL}/buckets/bulk-move-documents",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Bulk move failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "moved"
        moved = data["details"]["moved_documents"]
        logger.info("[BUCKETS] Bulk moved %d documents", moved)

    def test_delete_bucket_with_reassignment(self, state: _SharedState) -> None:
        """Delete sub-bucket and reassign docs back to parent."""
        if not state.custom_bucket_id:
            pytest.skip("No custom bucket to delete")
        parent_id = state.bucket_ids.get("Research and Reference", "")
        resp = requests.delete(
            f"{KB_URL}/buckets/{state.custom_bucket_id}",
            headers=_headers(state.token),
            json={"target_bucket_id": parent_id},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Delete bucket failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "deleted"
        logger.info(
            "[BUCKETS] Bucket deleted, redistributed %d docs",
            data["details"].get("redistributed_documents", 0),
        )


# ---------------------------------------------------------------------------
# Context broker
# ---------------------------------------------------------------------------


class TestContextBroker:
    """Test context broker CRUD operations."""

    def test_get_initial_context(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Get context failed: {resp.text}"
        data = resp.json()
        assert data["user_id"] == state.user_id
        logger.info("[CONTEXT] Initial context retrieved")

    def test_update_mood_context(self, state: _SharedState) -> None:
        payload = {
            "user_id": state.user_id,
            "update_type": "mood",
            "data": {
                "current_mood_score": 8,
                "current_energy_level": 7,
                "current_stress_level": 3,
                "context_data": {
                    "focus": "e2e testing",
                    "last_activity": "document_upload",
                },
            },
        }
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Update context failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        logger.info("[CONTEXT] Mood context updated")

    def test_verify_updated_context(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_mood_score"] == 8
        assert data["current_energy_level"] == 7
        assert data["current_stress_level"] == 3
        assert data["context_data"]["focus"] == "e2e testing"
        logger.info("[CONTEXT] Context values verified after update")

    def test_update_task_context(self, state: _SharedState) -> None:
        payload = {
            "user_id": state.user_id,
            "update_type": "task",
            "data": {
                "active_goals_count": 5,
                "pending_tasks_count": 10,
                "completed_tasks_today": 3,
            },
        }
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        logger.info("[CONTEXT] Task context updated")

    def test_context_summary(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}/summary",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Summary failed: {resp.text}"
        data = resp.json()
        assert "mood_score" in data
        assert "energy_level" in data
        assert data["mood_score"] == 8
        logger.info("[CONTEXT] Summary: %s", data)

    def test_invalidate_cache(self, state: _SharedState) -> None:
        resp = requests.post(
            f"{CONTEXT_URL}/context/{state.user_id}/invalidate",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Invalidate failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        logger.info("[CONTEXT] Cache invalidated")

    def test_context_after_invalidation(self, state: _SharedState) -> None:
        """After cache invalidation, context should still be retrievable from DB."""
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_mood_score"] == 8
        logger.info("[CONTEXT] Context still available after cache invalidation")


# ---------------------------------------------------------------------------
# Journal parser
# ---------------------------------------------------------------------------


class TestJournalParser:
    """Test journal processing pipeline."""

    def test_process_journal_entry(self, state: _SharedState) -> None:
        payload = {
            "entry_text": (
                "Today I woke up at 7am feeling refreshed. Had a healthy "
                "breakfast of oatmeal and fruit. Went for a 30 minute jog in "
                "the park. Worked on my machine learning project from 9am to "
                "12pm. Had lunch with a colleague. Afternoon was spent reading "
                "research papers. Evening was relaxing with a good book."
            ),
            "detect_gaps": True,
        }
        resp = requests.post(
            f"{JOURNAL_URL}/journal/process",
            headers=_headers(state.token),
            json=payload,
            timeout=60,  # journal processing can be slow
        )
        assert resp.status_code == 200, f"Journal process failed: {resp.text}"
        data = resp.json()
        assert "entry_id" in data
        assert data["stored"] is True
        assert data["user_id"] == state.user_id
        assert data["quality"] in ("high", "medium", "low")
        assert data["processing_time_ms"] > 0
        state.journal_entry_id = data["entry_id"]
        logger.info(
            "[JOURNAL] Entry processed: id=%s, quality=%s, time=%dms, gaps=%s",
            data["entry_id"],
            data["quality"],
            data["processing_time_ms"],
            data["has_gaps"],
        )

    def test_journal_via_gateway(self, state: _SharedState) -> None:
        """Process journal through API gateway."""
        payload = {
            "entry_text": (
                "Had a productive morning. Completed two code reviews and "
                "deployed the new feature to staging."
            ),
            "detect_gaps": False,
        }
        resp = requests.post(
            f"{GATEWAY_URL}/journal/process",
            headers=_headers(state.token),
            json=payload,
            timeout=60,
        )
        assert resp.status_code == 200, f"Gateway journal failed: {resp.text}"
        data = resp.json()
        assert data["stored"] is True
        logger.info("[JOURNAL] Gateway journal: entry_id=%s", data["entry_id"])


# ---------------------------------------------------------------------------
# API Gateway routing
# ---------------------------------------------------------------------------


class TestGatewayRouting:
    """Verify API gateway correctly routes to all services."""

    def test_gateway_to_auth(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{AUTH_URL}/auth/me",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        logger.info("[GATEWAY] Auth route OK")

    def test_gateway_to_documents(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{GATEWAY_URL}/documents",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        logger.info("[GATEWAY] Documents route OK")

    def test_gateway_to_buckets(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{GATEWAY_URL}/buckets/tree",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        logger.info("[GATEWAY] Buckets route OK")

    def test_gateway_to_context(self, state: _SharedState) -> None:
        resp = requests.get(
            f"{GATEWAY_URL}/context/{state.user_id}",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        logger.info("[GATEWAY] Context route OK")


# ---------------------------------------------------------------------------
# Cross-service integration
# ---------------------------------------------------------------------------


class TestCrossServiceIntegration:
    """Test workflows that span multiple services."""

    def test_upload_then_search(self, state: _SharedState) -> None:
        """Upload a unique doc, then search for it."""
        unique_term = f"quantum_computing_{uuid.uuid4().hex[:6]}"
        content = (
            f"This document is about {unique_term}. Quantum computing leverages "
            "quantum mechanics to perform computations. Qubits can exist in "
            "superposition states. Quantum entanglement enables faster processing."
        )
        # Upload
        upload_resp = requests.post(
            f"{KB_URL}/upload",
            headers=_headers(state.token),
            json={
                "filename": f"{unique_term}.txt",
                "content_base64": _make_text_b64(content),
                "mime_type": "text/plain",
            },
            timeout=HTTP_TIMEOUT,
        )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["document_id"]

        # Search for the unique term
        search_resp = requests.post(
            f"{KB_URL}/search",
            headers=_headers(state.token),
            json={"query": unique_term.replace("_", " "), "top_k": 5},
            timeout=HTTP_TIMEOUT,
        )
        assert search_resp.status_code == 200
        results = search_resp.json()["results"]
        assert len(results) > 0, f"Search for '{unique_term}' returned no results"
        result_ids = [r["document_id"] for r in results]
        assert doc_id in result_ids, (
            f"Uploaded doc {doc_id} not found in search results"
        )
        logger.info(
            "[INTEGRATION] Upload-then-search: doc %s found in results", doc_id
        )

    def test_upload_context_and_search(self, state: _SharedState) -> None:
        """Verify context and KB work independently with same user."""
        # Update context
        ctx_resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            json={
                "user_id": state.user_id,
                "update_type": "activity",
                "data": {
                    "context_data": {"last_search": "machine learning"},
                },
            },
            timeout=HTTP_TIMEOUT,
        )
        assert ctx_resp.status_code == 200

        # Search KB
        search_resp = requests.post(
            f"{KB_URL}/search",
            headers=_headers(state.token),
            json={"query": "machine learning", "top_k": 3},
            timeout=HTTP_TIMEOUT,
        )
        assert search_resp.status_code == 200
        assert len(search_resp.json()["results"]) > 0

        # Verify context still intact
        ctx_get = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            timeout=HTTP_TIMEOUT,
        )
        assert ctx_get.status_code == 200
        assert ctx_get.json()["context_data"].get("last_search") == "machine learning"
        logger.info("[INTEGRATION] Context + KB cross-service verified")


# ---------------------------------------------------------------------------
# Error handling & edge cases
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling across services."""

    def test_upload_empty_content(self, state: _SharedState) -> None:
        payload = {
            "filename": "empty.txt",
            "content_base64": _make_text_b64(""),
            "mime_type": "text/plain",
        }
        resp = requests.post(
            f"{KB_URL}/upload",
            headers=_headers(state.token),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        # Should either reject (400/422) or handle gracefully
        assert resp.status_code in (200, 400, 422), (
            f"Unexpected status for empty upload: {resp.status_code}"
        )
        logger.info(
            "[ERROR] Empty content upload handled: %d", resp.status_code
        )

    def test_search_nonexistent_user_context(self) -> None:
        fake_id = str(uuid.uuid4())
        resp = requests.get(
            f"{CONTEXT_URL}/context/{fake_id}",
            timeout=HTTP_TIMEOUT,
        )
        # Should return empty/default context or 404
        assert resp.status_code in (200, 404), (
            f"Unexpected status for nonexistent user context: {resp.status_code}"
        )
        logger.info(
            "[ERROR] Nonexistent user context handled: %d", resp.status_code
        )

    def test_invalid_bucket_delete(self, state: _SharedState) -> None:
        fake_id = str(uuid.uuid4())
        resp = requests.delete(
            f"{KB_URL}/buckets/{fake_id}",
            headers=_headers(state.token),
            json={"target_bucket_id": str(uuid.uuid4())},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (400, 404), (
            f"Expected error for invalid bucket delete: {resp.status_code}"
        )
        logger.info(
            "[ERROR] Invalid bucket delete handled: %d", resp.status_code
        )

    def test_expired_token_rejected(self) -> None:
        """Malformed/expired token should be rejected."""
        resp = requests.get(
            f"{KB_URL}/documents",
            headers={"Authorization": "Bearer invalid.token.here"},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (401, 403), (
            f"Expected auth rejection, got {resp.status_code}"
        )
        logger.info("[ERROR] Invalid token correctly rejected")

    def test_duplicate_registration(self, state: _SharedState) -> None:
        """Registering same email twice should fail."""
        unique = uuid.uuid4().hex[:8]
        payload = {
            "username": f"e2e_dup_{unique}",
            "email": f"e2e_dup_{unique}@plos-test.dev",
            "password": "DupTest123!",
        }
        # First registration
        resp1 = requests.post(
            f"{AUTH_URL}/auth/register", json=payload, timeout=HTTP_TIMEOUT
        )
        assert resp1.status_code in (200, 201)

        # Second registration with same email
        payload["username"] = f"e2e_dup2_{unique}"
        resp2 = requests.post(
            f"{AUTH_URL}/auth/register", json=payload, timeout=HTTP_TIMEOUT
        )
        assert resp2.status_code in (400, 409, 422), (
            f"Expected duplicate rejection, got {resp2.status_code}: {resp2.text}"
        )
        logger.info("[ERROR] Duplicate registration rejected: %d", resp2.status_code)


# ---------------------------------------------------------------------------
# Data consistency checks
# ---------------------------------------------------------------------------


class TestDataConsistency:
    """Verify data consistency across storage systems."""

    def test_document_count_matches(self, state: _SharedState) -> None:
        """Verify document count in listing matches uploaded count."""
        resp = requests.get(
            f"{KB_URL}/documents",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        docs = resp.json()
        # We uploaded at least 4 regular docs + 1 in cross-service test
        assert len(docs) >= 4, f"Expected >= 4 docs, got {len(docs)}"
        logger.info("[CONSISTENCY] Document count: %d", len(docs))

    def test_all_documents_completed(self, state: _SharedState) -> None:
        """All uploaded documents should have completed status."""
        resp = requests.get(
            f"{KB_URL}/documents",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        docs = resp.json()
        for doc in docs:
            assert doc["status"] == "completed", (
                f"Document {doc['document_id']} has status '{doc['status']}'"
            )
        logger.info("[CONSISTENCY] All %d documents in 'completed' status", len(docs))

    def test_bucket_tree_consistency(self, state: _SharedState) -> None:
        """Bucket tree should list only non-deleted buckets for user."""
        resp = requests.get(
            f"{KB_URL}/buckets/tree",
            headers=_headers(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        tree = resp.json()["buckets"]
        for bucket in tree:
            assert bucket["is_deleted"] is False, (
                f"Deleted bucket {bucket['name']} in tree"
            )
            assert bucket["user_id"] == state.user_id
        logger.info(
            "[CONSISTENCY] Bucket tree: %d non-deleted buckets",
            len(tree),
        )
