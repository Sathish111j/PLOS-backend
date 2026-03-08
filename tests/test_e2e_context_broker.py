"""
End-to-End Test Suite for Context Broker Service.

Tests context lifecycle: creation via update, retrieval, summary,
invalidation, and admin stats.

Run:
    pytest tests/test_e2e_context_broker.py -v --tb=short -m e2e

Pre-requisites:
    docker compose up -d  (all services healthy)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONTEXT_URL = os.getenv("CONTEXT_URL", "http://localhost:8001")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8002")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared state & helpers
# ---------------------------------------------------------------------------


class _CB_State:
    """Mutable container shared across ordered tests."""

    token: str = ""
    user_id: str = ""


def _h(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def state() -> _CB_State:
    return _CB_State()


@pytest.fixture(scope="module", autouse=True)
def _ensure_healthy() -> None:
    """Skip entire module if context-broker is not healthy."""
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(f"{CONTEXT_URL}/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "healthy":
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    pytest.skip("context-broker not healthy -- skipping")


@pytest.fixture(scope="module", autouse=True)
def _setup_auth_user(state: _CB_State) -> None:
    """Register a unique user for context-broker tests."""
    unique = uuid.uuid4().hex[:8]
    email = f"cb-e2e-{unique}@plos-test.dev"
    password = "E2eTestCB99!!"
    resp = requests.post(
        f"{AUTH_URL}/auth/register",
        json={
            "email": email,
            "username": f"cb_e2e_{unique}",
            "password": password,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert resp.status_code == 201, f"Auth register failed: {resp.text}"
    data = resp.json()
    state.token = data["access_token"]
    state.user_id = data["user"]["user_id"]
    logger.info("[CB-SETUP] Registered user %s (id=%s)", email, state.user_id)


# ===================================================================
# 1. HEALTH & METRICS
# ===================================================================


@pytest.mark.e2e
class TestCBHealth:
    """Health and metrics endpoints."""

    def test_health(self) -> None:
        resp = requests.get(f"{CONTEXT_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "context-broker"

    def test_metrics(self) -> None:
        resp = requests.get(f"{CONTEXT_URL}/metrics", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200


# ===================================================================
# 2. CONTEXT UPDATES
# ===================================================================


@pytest.mark.e2e
class TestContextUpdate:
    """Test posting context updates."""

    def test_mood_update(self, state: _CB_State) -> None:
        """POST a mood update."""
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            headers=_h(state.token),
            json={
                "user_id": state.user_id,
                "update_type": "mood",
                "data": {"mood_score": 7, "mood_label": "good"},
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Mood update failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True or data.get("status") in ("updated", "success", "ok")
        logger.info("[CB] Mood update accepted")

    def test_energy_update(self, state: _CB_State) -> None:
        """POST an energy update."""
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            headers=_h(state.token),
            json={
                "user_id": state.user_id,
                "update_type": "energy",
                "data": {"energy_level": 8},
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Energy update failed: {resp.text}"

    def test_stress_update(self, state: _CB_State) -> None:
        """POST a stress update."""
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            headers=_h(state.token),
            json={
                "user_id": state.user_id,
                "update_type": "stress",
                "data": {"stress_level": 5},
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Stress update failed: {resp.text}"

    def test_journal_context_update(self, state: _CB_State) -> None:
        """POST a journal-type context update with rich data."""
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            headers=_h(state.token),
            json={
                "user_id": state.user_id,
                "update_type": "journal",
                "data": {
                    "mood_score": 7,
                    "energy_level": 8,
                    "stress_level": 5,
                    "sleep_hours": 8,
                    "activities": ["jogging", "coding"],
                    "calories_in": 2100,
                    "water_ml": 1800,
                },
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Journal context update failed: {resp.text}"

    def test_update_missing_fields_rejected(self, state: _CB_State) -> None:
        """Update without required fields should fail with 422."""
        resp = requests.post(
            f"{CONTEXT_URL}/context/update",
            headers=_h(state.token),
            json={"user_id": state.user_id},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 422


# ===================================================================
# 3. CONTEXT RETRIEVAL
# ===================================================================


@pytest.mark.e2e
class TestContextRetrieval:
    """Test retrieving user context after updates."""

    def test_get_context(self, state: _CB_State) -> None:
        """GET /context/{user_id} should return aggregated context."""
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Get context failed: {resp.text}"
        data = resp.json()
        assert data["user_id"] == state.user_id
        logger.info("[CB] Context retrieved: keys=%s", list(data.keys()))

    def test_get_context_summary(self, state: _CB_State) -> None:
        """GET /context/{user_id}/summary should return a concise view."""
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}/summary",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Get summary failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict)
        logger.info("[CB] Summary retrieved: %s", list(data.keys()))

    def test_get_nonexistent_user(self, state: _CB_State) -> None:
        """Getting context for a random user_id should return 403 (IDOR guard)."""
        fake_user = str(uuid.uuid4())
        resp = requests.get(
            f"{CONTEXT_URL}/context/{fake_user}",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        # IDOR ownership check rejects access to another user's context
        assert resp.status_code == 403


# ===================================================================
# 4. CACHE INVALIDATION
# ===================================================================


@pytest.mark.e2e
class TestContextInvalidation:
    """Test cache invalidation flow."""

    def test_invalidate_context(self, state: _CB_State) -> None:
        """Invalidate the cached context for the user."""
        resp = requests.post(
            f"{CONTEXT_URL}/context/{state.user_id}/invalidate",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Invalidate failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True or data.get("status") in ("invalidated", "success", "ok")
        logger.info("[CB] Context invalidated for %s", state.user_id)

    def test_context_still_readable_after_invalidation(self, state: _CB_State) -> None:
        """After invalidation the context should still be retrievable (cold cache)."""
        resp = requests.get(
            f"{CONTEXT_URL}/context/{state.user_id}",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200


# ===================================================================
# 5. ADMIN STATS
# ===================================================================


@pytest.mark.e2e
class TestCBAdminStats:
    """Test admin / diagnostic endpoints."""

    def test_admin_stats(self, state: _CB_State) -> None:
        """GET /admin/stats should return cache and usage information."""
        resp = requests.get(
            f"{CONTEXT_URL}/admin/stats",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Admin stats failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict)
        logger.info("[CB] Admin stats: %s", data)
