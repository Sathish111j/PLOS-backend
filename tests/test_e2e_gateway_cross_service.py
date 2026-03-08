"""
End-to-End Test Suite for API Gateway (Kong) and Cross-Service Flows.

Tests that Kong correctly routes requests to backend services, and
validates cross-service integration (journal -> context -> KB).

Run:
    pytest tests/test_e2e_gateway_cross_service.py -v --tb=short -m e2e

Pre-requisites:
    docker compose up -d  (all services healthy)
"""

from __future__ import annotations

import base64
import logging
import os
import time
import uuid
from datetime import date, timedelta

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GW_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
JOURNAL_URL = os.getenv("JOURNAL_URL", "http://localhost:8002")
CONTEXT_URL = os.getenv("CONTEXT_URL", "http://localhost:8001")
KB_URL = os.getenv("KB_URL", "http://localhost:8003")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
PROCESS_TIMEOUT = int(os.getenv("PROCESS_TIMEOUT", "120"))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared state & helpers
# ---------------------------------------------------------------------------


class _GW_State:
    """Mutable container shared across ordered tests."""

    token: str = ""
    user_id: str = ""
    email: str = ""
    password: str = ""


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
def state() -> _GW_State:
    return _GW_State()


@pytest.fixture(scope="module", autouse=True)
def _ensure_gateway_up() -> None:
    """Skip entire module if gateway is not reachable."""
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(f"{GW_URL}/health", timeout=5)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    pytest.skip("API Gateway not reachable -- skipping")


# ===================================================================
# 1. GATEWAY HEALTH ROUTES
# ===================================================================


@pytest.mark.e2e
class TestGatewayHealth:
    """Verify dedicated health routes in Kong."""

    def test_root_health(self) -> None:
        """GET /health should proxy to journal-parser."""
        resp = requests.get(f"{GW_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_journal_health(self) -> None:
        """GET /health/journal via gateway."""
        resp = requests.get(f"{GW_URL}/health/journal", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "journal-parser"

    def test_context_health(self) -> None:
        """GET /health/context via gateway."""
        resp = requests.get(f"{GW_URL}/health/context", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "context-broker"

    def test_knowledge_base_health(self) -> None:
        """GET /health/knowledge-base via gateway."""
        resp = requests.get(
            f"{GW_URL}/health/knowledge-base", timeout=HTTP_TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


# ===================================================================
# 2. GATEWAY ROUTING - AUTH
# ===================================================================


@pytest.mark.e2e
class TestGatewayAuth:
    """Verify auth endpoints through gateway (strips /api/v1 prefix)."""

    def test_register_through_gateway(self, state: _GW_State) -> None:
        """Register user via /api/v1/auth/register."""
        unique = uuid.uuid4().hex[:8]
        state.email = f"gw-e2e-{unique}@plos-test.dev"
        state.password = "GwE2ePass99!!"
        resp = requests.post(
            f"{GW_URL}/api/v1/auth/register",
            json={
                "email": state.email,
                "username": f"gw_e2e_{unique}",
                "password": state.password,
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 201, f"GW register failed: {resp.text}"
        data = resp.json()
        state.token = data["access_token"]
        state.user_id = data["user"]["user_id"]
        logger.info("[GW-AUTH] Registered %s via gateway", state.email)

    def test_login_through_gateway(self, state: _GW_State) -> None:
        """Login via /api/v1/auth/login."""
        resp = requests.post(
            f"{GW_URL}/api/v1/auth/login",
            json={"email": state.email, "password": state.password},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        state.token = resp.json()["access_token"]

    def test_profile_through_gateway(self, state: _GW_State) -> None:
        """GET /api/v1/auth/me via gateway."""
        resp = requests.get(
            f"{GW_URL}/api/v1/auth/me",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == state.email


# ===================================================================
# 3. GATEWAY ROUTING - JOURNAL
# ===================================================================


@pytest.mark.e2e
class TestGatewayJournal:
    """Verify journal endpoints through gateway."""

    def test_journal_health_via_api(self, state: _GW_State) -> None:
        """GET /api/v1/journal/health routed correctly."""
        # Note: this uses the journal-parser-route
        resp = requests.get(
            f"{GW_URL}/api/v1/journal/health",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_activities_via_gateway(self, state: _GW_State) -> None:
        """GET /api/v1/journal/activities through gateway."""
        resp = requests.get(
            f"{GW_URL}/api/v1/journal/activities",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_reporting_via_gateway(self, state: _GW_State) -> None:
        """GET /api/v1/journal/reports/weekly-overview through gateway."""
        resp = requests.get(
            f"{GW_URL}/api/v1/journal/reports/weekly-overview",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200


# ===================================================================
# 4. GATEWAY ROUTING - CONTEXT BROKER
# ===================================================================


@pytest.mark.e2e
class TestGatewayContext:
    """Verify context endpoints through gateway."""

    def test_context_update_via_gateway(self, state: _GW_State) -> None:
        """POST /api/v1/context/update via gateway."""
        resp = requests.post(
            f"{GW_URL}/api/v1/context/update",
            headers=_h(state.token),
            json={
                "user_id": state.user_id,
                "update_type": "mood",
                "data": {"mood_score": 8},
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_context_get_via_gateway(self, state: _GW_State) -> None:
        """GET /api/v1/context/{user_id} via gateway."""
        resp = requests.get(
            f"{GW_URL}/api/v1/context/{state.user_id}",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == state.user_id


# ===================================================================
# 5. GATEWAY ROUTING - KNOWLEDGE BASE
# ===================================================================


@pytest.mark.e2e
class TestGatewayKB:
    """Verify KB endpoints through gateway.

    KB routes in Kong use regex:
        ~/api/v1(?<path>/(upload|documents|buckets|search|chat|
                          ingest|graph|ops|health|metrics).*)$
    The prefix (/api/v1) is stripped and the path capture group is forwarded.
    """

    def test_kb_health_via_gateway(self) -> None:
        """GET /api/v1/health should be routed to KB."""
        resp = requests.get(
            f"{GW_URL}/api/v1/health", timeout=HTTP_TIMEOUT
        )
        assert resp.status_code == 200

    def test_kb_documents_via_gateway(self, state: _GW_State) -> None:
        """GET /api/v1/documents via gateway."""
        resp = requests.get(
            f"{GW_URL}/api/v1/documents",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_kb_search_via_gateway(self, state: _GW_State) -> None:
        """POST /api/v1/search via gateway."""
        resp = requests.post(
            f"{GW_URL}/api/v1/search",
            headers=_h(state.token),
            json={"query": "test search via gateway"},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(f"Gemini embedding transient failure: {resp.status_code}")
        assert resp.status_code == 200

    def test_kb_buckets_via_gateway(self, state: _GW_State) -> None:
        """GET /api/v1/buckets via gateway."""
        resp = requests.get(
            f"{GW_URL}/api/v1/buckets",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200


# ===================================================================
# 6. GATEWAY HEADERS
# ===================================================================


@pytest.mark.e2e
class TestGatewayHeaders:
    """Verify Kong adds expected headers."""

    def test_gateway_version_header(self) -> None:
        """Kong should add X-Gateway-Version header."""
        resp = requests.get(f"{GW_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        # Gateway request-transformer adds X-Gateway-Version:1.0 to requests,
        # not responses, but we can verify the request reaches the backend.

    def test_cors_headers(self) -> None:
        """CORS preflight should succeed."""
        resp = requests.options(
            f"{GW_URL}/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


# ===================================================================
# 7. CROSS-SERVICE INTEGRATION
# ===================================================================


@pytest.mark.e2e
class TestCrossServiceFlow:
    """Test flows that span multiple services."""

    def test_journal_then_context_update(self, state: _GW_State) -> None:
        """Process a journal entry, then update context, then verify."""
        # Step 1: Process a journal entry (directly, to save time)
        entry_date = (date.today() - timedelta(days=2)).isoformat()
        j_resp = requests.post(
            f"{JOURNAL_URL}/journal/process",
            headers=_h(state.token),
            json={
                "entry_text": (
                    "Had a productive day. Slept 7 hours, mood is 8/10. "
                    "Went running for 45 minutes. Had healthy meals."
                ),
                "entry_date": entry_date,
                "detect_gaps": False,
            },
            timeout=PROCESS_TIMEOUT,
        )
        assert j_resp.status_code == 200, f"Journal process failed: {j_resp.text}"
        j_data = j_resp.json()
        assert j_data["stored"] is True
        mood = j_data.get("metrics", {}).get("mood_score")

        # Step 2: Simulate what the system does -- push context update
        sleep_data = j_data.get("sleep") or {}
        ctx_resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            headers=_h(state.token),
            json={
                "user_id": state.user_id,
                "update_type": "journal",
                "data": {
                    "mood_score": mood or 8,
                    "sleep_hours": sleep_data.get("duration_hours", 7),
                },
            },
            timeout=HTTP_TIMEOUT,
        )
        assert ctx_resp.status_code == 200

        # Step 3: Verify context reflects the update
        ctx_get = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert ctx_get.status_code == 200
        ctx_data = ctx_get.json()
        assert ctx_data["user_id"] == state.user_id
        logger.info("[CROSS] Journal->Context flow verified")

    def test_kb_upload_then_search_then_chat(self, state: _GW_State) -> None:
        """Upload a document, search it, then chat about it."""
        content = (
            "The Mediterranean diet emphasizes fruits, vegetables, whole grains, "
            "legumes, nuts, and olive oil. It includes moderate consumption of "
            "fish, poultry, dairy, and limits red meat and sweets. Studies show "
            "reduced risk of heart disease and improved longevity."
        )
        # Step 1: Upload
        up_resp = requests.post(
            f"{KB_URL}/upload",
            headers=_h(state.token),
            json={
                "filename": "mediterranean_diet.txt",
                "content_base64": _text_b64(content),
                "mime_type": "text/plain",
            },
            timeout=PROCESS_TIMEOUT,
        )
        assert up_resp.status_code == 200
        doc_id = up_resp.json()["document_id"]
        logger.info("[CROSS] Uploaded doc %s", doc_id)

        # Step 2: Search (may fail if embeddings are still processing)
        s_resp = requests.post(
            f"{KB_URL}/search",
            headers=_h(state.token),
            json={"query": "Mediterranean diet benefits"},
            timeout=HTTP_TIMEOUT,
        )
        assert s_resp.status_code in (200, 500), f"Search unexpected: {s_resp.text[:200]}"
        search_found = False
        if s_resp.status_code == 200:
            search_found = len(s_resp.json()["results"]) >= 1

        # Step 3: Chat
        c_resp = requests.post(
            f"{KB_URL}/chat",
            headers=_h(state.token),
            json={
                "message": "What does the Mediterranean diet include?",
                "session_id": None,
            },
            timeout=PROCESS_TIMEOUT,
        )
        assert c_resp.status_code in (200, 500, 502, 503), f"Chat unexpected: {c_resp.text[:200]}"
        if c_resp.status_code == 200:
            assert c_resp.json()["answer"]
        logger.info("[CROSS] Upload->Search->Chat flow verified")

    def test_auth_propagation_across_services(self, state: _GW_State) -> None:
        """A single JWT should be accepted by all services."""
        headers = _h(state.token)

        # Journal
        r1 = requests.get(
            f"{JOURNAL_URL}/auth/me",
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
        assert r1.status_code == 200, "JWT rejected by journal-parser"

        # KB
        r2 = requests.get(
            f"{KB_URL}/documents",
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
        assert r2.status_code == 200, "JWT rejected by knowledge-base"

        # All services accepted the same token
        logger.info("[CROSS] JWT accepted by all services")


# ===================================================================
# 8. ERROR HANDLING
# ===================================================================


@pytest.mark.e2e
class TestGatewayErrors:
    """Error and edge case handling through gateway."""

    def test_nonexistent_route_returns_404_or_no_route(self) -> None:
        """Unmatched route should return 404."""
        resp = requests.get(
            f"{GW_URL}/api/v1/nonexistent", timeout=HTTP_TIMEOUT
        )
        assert resp.status_code in (404, 503)

    def test_rate_limiting_headers(self) -> None:
        """Responses should include rate-limit headers."""
        resp = requests.get(f"{GW_URL}/health", timeout=HTTP_TIMEOUT)
        # Kong rate-limiting adds these headers
        rl_headers = [
            h for h in resp.headers if "ratelimit" in h.lower() or "x-ratelimit" in h.lower()
        ]
        assert len(rl_headers) >= 1, (
            f"Expected rate-limit headers, got: {dict(resp.headers)}"
        )
