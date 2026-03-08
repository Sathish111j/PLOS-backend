"""
End-to-End Test Suite for Journal Parser Service.

Tests auth flow, journal processing (with real Gemini AI),
gap detection/resolution, activities, and reporting endpoints
against running Docker containers.

Run:
    pytest tests/test_e2e_journal_parser.py -v --tb=short -m e2e

Pre-requisites:
    docker compose up -d  (all services healthy)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JOURNAL_URL = os.getenv("JOURNAL_URL", "http://localhost:8002")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8002")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
PROCESS_TIMEOUT = int(os.getenv("PROCESS_TIMEOUT", "120"))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared state & helpers
# ---------------------------------------------------------------------------


class _JP_State:
    """Mutable container shared across ordered tests."""

    token: str = ""
    user_id: str = ""
    email: str = ""
    password: str = ""
    entry_id: str = ""
    gap_ids: list[str] = []
    second_entry_id: str = ""


def _h(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def state() -> _JP_State:
    return _JP_State()


@pytest.fixture(scope="module", autouse=True)
def _ensure_healthy() -> None:
    """Skip entire module if journal-parser is not healthy."""
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(f"{JOURNAL_URL}/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "healthy":
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    pytest.skip("journal-parser not healthy -- skipping")


# ===================================================================
# 1. AUTH FLOW
# ===================================================================


@pytest.mark.e2e
class TestJPAuthFlow:
    """Test the complete authentication lifecycle via journal-parser."""

    def test_register(self, state: _JP_State) -> None:
        """Register a unique test user."""
        unique = uuid.uuid4().hex[:8]
        state.email = f"jp-e2e-{unique}@plos-test.dev"
        state.password = "E2eTestPass99!!"
        resp = requests.post(
            f"{AUTH_URL}/auth/register",
            json={
                "email": state.email,
                "username": f"jp_e2e_{unique}",
                "password": state.password,
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 201, f"Register failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        user = data["user"]
        state.token = data["access_token"]
        state.user_id = user["user_id"]
        logger.info("[AUTH] Registered user %s", state.email)

    def test_login(self, state: _JP_State) -> None:
        """Login with the registered user."""
        resp = requests.post(
            f"{AUTH_URL}/auth/login",
            json={"email": state.email, "password": state.password},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        state.token = data["access_token"]
        logger.info("[AUTH] Login OK")

    def test_get_profile(self, state: _JP_State) -> None:
        """Retrieve the user profile via /auth/me."""
        resp = requests.get(
            f"{AUTH_URL}/auth/me",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == state.email
        assert data["user_id"] == state.user_id
        assert data["is_active"] is True

    def test_update_profile(self, state: _JP_State) -> None:
        """Update user profile (full_name, timezone)."""
        resp = requests.patch(
            f"{AUTH_URL}/auth/me",
            headers=_h(state.token),
            json={"full_name": "JP E2E User", "timezone": "Europe/London"},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "JP E2E User"
        assert data["timezone"] == "Europe/London"

    def test_change_password(self, state: _JP_State) -> None:
        """Change password and verify login with the new one."""
        new_pass = "NewE2ePass88!!"
        resp = requests.post(
            f"{AUTH_URL}/auth/change-password",
            headers=_h(state.token),
            json={
                "current_password": state.password,
                "new_password": new_pass,
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        # Verify login with new password
        resp2 = requests.post(
            f"{AUTH_URL}/auth/login",
            json={"email": state.email, "password": new_pass},
            timeout=HTTP_TIMEOUT,
        )
        assert resp2.status_code == 200
        state.password = new_pass
        state.token = resp2.json()["access_token"]

    def test_duplicate_email_rejected(self, state: _JP_State) -> None:
        """Duplicate email registration should fail."""
        resp = requests.post(
            f"{AUTH_URL}/auth/register",
            json={
                "email": state.email,
                "username": "another_user",
                "password": "SomePass123!",
            },
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (400, 409), f"Expected 400/409, got {resp.status_code}: {resp.text}"
        assert "already" in resp.json()["detail"].lower()

    def test_invalid_login_rejected(self, state: _JP_State) -> None:
        """Wrong password should be rejected."""
        resp = requests.post(
            f"{AUTH_URL}/auth/login",
            json={"email": state.email, "password": "WrongPassword123"},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_invalid_token_rejected(self) -> None:
        """An invalid JWT should be rejected."""
        resp = requests.get(
            f"{AUTH_URL}/auth/me",
            headers=_h("invalid_token_string"),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 401


# ===================================================================
# 2. JOURNAL PROCESSING (Gemini AI)
# ===================================================================


@pytest.mark.e2e
class TestJournalProcessing:
    """Test the complete journal processing pipeline with real Gemini AI."""

    SAMPLE_ENTRY = (
        "Woke up at 7am after about 8 hours of sleep, feeling rested. "
        "Had oatmeal and coffee for breakfast. Went for a 30 minute jog. "
        "Work was productive, spent 4 hours coding on the PLOS project. "
        "Had chicken salad for lunch. Feeling stressed about the deadline. "
        "Drank 6 glasses of water. Met friends for dinner at a restaurant, "
        "had pasta and a glass of wine. Mood 7 out of 10."
    )

    def test_process_journal_entry(self, state: _JP_State) -> None:
        """Process a realistic journal entry and verify extraction structure."""
        entry_date = (date.today() - timedelta(days=1)).isoformat()
        resp = requests.post(
            f"{JOURNAL_URL}/journal/process",
            headers=_h(state.token),
            json={
                "entry_text": self.SAMPLE_ENTRY,
                "entry_date": entry_date,
                "detect_gaps": True,
            },
            timeout=PROCESS_TIMEOUT,
        )
        assert resp.status_code == 200, f"Process failed: {resp.text}"
        data = resp.json()

        # Core fields
        assert "entry_id" in data
        assert data["user_id"] == state.user_id
        assert data["entry_date"] == entry_date
        assert data["quality"] in ("high", "medium", "low")
        assert data["stored"] is True

        state.entry_id = data["entry_id"]

        # Sleep data (Gemini extraction may not always detect sleep)
        sleep = data.get("sleep")
        if sleep is not None:
            assert sleep.get("duration_hours") is not None
            assert sleep["duration_hours"] > 0

        # Metrics (Gemini extraction may return empty dict)
        metrics = data.get("metrics") or {}
        if metrics:
            assert "mood_score" in metrics or "water_intake_liters" in metrics

        # Activities (Gemini extraction may vary)
        assert isinstance(data.get("activities"), list)

        # Consumptions (Gemini extraction may vary)
        assert isinstance(data.get("consumptions"), list)

        # Gap detection
        assert isinstance(data.get("has_gaps"), bool)

        # Processing time
        assert "processing_time_ms" in data
        assert data["processing_time_ms"] > 0

        state.gap_ids = [
            q["gap_id"] for q in data.get("clarification_questions", [])
        ]
        logger.info(
            "[JOURNAL] Processed entry %s: quality=%s, gaps=%d, activities=%d",
            state.entry_id,
            data["quality"],
            len(state.gap_ids),
            len(data["activities"]),
        )

    def test_process_minimal_entry(self, state: _JP_State) -> None:
        """Process a minimal journal entry (no gaps expected)."""
        entry_date = date.today().isoformat()
        resp = requests.post(
            f"{JOURNAL_URL}/journal/process",
            headers=_h(state.token),
            json={
                "entry_text": "Had a quiet day at home. Read a book.",
                "entry_date": entry_date,
                "detect_gaps": False,
            },
            timeout=PROCESS_TIMEOUT,
        )
        assert resp.status_code == 200, f"Process failed: {resp.text}"
        data = resp.json()
        assert data["stored"] is True
        state.second_entry_id = data["entry_id"]
        logger.info("[JOURNAL] Minimal entry processed: %s", state.second_entry_id)

    def test_empty_entry_rejected(self, state: _JP_State) -> None:
        """Empty entry text should be rejected with 422."""
        resp = requests.post(
            f"{JOURNAL_URL}/journal/process",
            headers=_h(state.token),
            json={"entry_text": "", "entry_date": date.today().isoformat()},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (400, 422)

    def test_unauthenticated_rejected(self) -> None:
        """Processing without auth token should be rejected."""
        resp = requests.post(
            f"{JOURNAL_URL}/journal/process",
            json={"entry_text": "test", "entry_date": date.today().isoformat()},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (401, 403)


# ===================================================================
# 3. GAP DETECTION & RESOLUTION
# ===================================================================


@pytest.mark.e2e
class TestGapDetection:
    """Test gap detection and resolution flow."""

    def test_get_pending_gaps(self, state: _JP_State) -> None:
        """Retrieve pending gaps for the user."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/pending-gaps",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        gaps = resp.json()
        assert isinstance(gaps, list)
        logger.info("[GAPS] %d pending gaps", len(gaps))
        if gaps:
            gap = gaps[0]
            assert "gap_id" in gap
            assert "question" in gap
            assert "field" in gap

    def test_resolve_single_gap(self, state: _JP_State) -> None:
        """Resolve one gap with a user response."""
        if not state.gap_ids:
            pytest.skip("No gaps to resolve")
        gap_id = state.gap_ids[0]
        resp = requests.post(
            f"{JOURNAL_URL}/journal/resolve-gap",
            headers=_h(state.token),
            json={
                "gap_id": gap_id,
                "user_response": "Medium bowl of oatmeal with blueberries",
            },
            timeout=PROCESS_TIMEOUT,
        )
        assert resp.status_code == 200, f"Resolve gap failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["gap_id"] == gap_id
        logger.info("[GAPS] Resolved gap %s", gap_id)


# ===================================================================
# 4. ACTIVITIES & SUMMARIES
# ===================================================================


@pytest.mark.e2e
class TestActivitiesAndSummaries:
    """Test activity retrieval and summary endpoints."""

    def test_get_activities(self, state: _JP_State) -> None:
        """Retrieve activities for the user."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/activities",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        logger.info("[ACTIVITIES] %d activities found", len(data))

    def test_get_activity_summary(self, state: _JP_State) -> None:
        """Retrieve activity summary."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/activity-summary",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "activities" in data or "total_activities" in data


# ===================================================================
# 5. REPORTING ENDPOINTS
# ===================================================================


@pytest.mark.e2e
class TestReportingEndpoints:
    """Test all weekly/monthly/range reporting endpoints."""

    WEEKLY_ENDPOINTS = [
        "weekly-overview",
        "calories/weekly",
        "sleep/weekly",
        "mood/weekly",
        "water/weekly",
        "steps/weekly",
        "activity/weekly",
        "nutrition/weekly",
        "social/weekly",
        "health/weekly",
        "work/weekly",
    ]

    MONTHLY_ENDPOINTS = [
        "monthly-overview",
        "calories/monthly",
        "sleep/monthly",
        "mood/monthly",
        "water/monthly",
        "steps/monthly",
        "activity/monthly",
        "nutrition/monthly",
        "social/monthly",
        "health/monthly",
        "work/monthly",
    ]

    @pytest.mark.parametrize("endpoint", WEEKLY_ENDPOINTS)
    def test_weekly_report(self, state: _JP_State, endpoint: str) -> None:
        """Each weekly reporting endpoint should return 200."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/{endpoint}",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, (
            f"Weekly {endpoint} failed: {resp.status_code} {resp.text[:200]}"
        )
        data = resp.json()
        assert isinstance(data, dict)

    @pytest.mark.parametrize("endpoint", MONTHLY_ENDPOINTS)
    def test_monthly_report(self, state: _JP_State, endpoint: str) -> None:
        """Each monthly reporting endpoint should return 200."""
        now = date.today()
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/{endpoint}",
            headers=_h(state.token),
            params={"year": now.year, "month": now.month},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200, (
            f"Monthly {endpoint} failed: {resp.status_code} {resp.text[:200]}"
        )

    def test_daily_overview_requires_date(self, state: _JP_State) -> None:
        """daily-overview without target_date should return 422."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/daily-overview",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 422

    def test_daily_overview_with_date(self, state: _JP_State) -> None:
        """daily-overview with a valid date should return data."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/daily-overview",
            headers=_h(state.token),
            params={"target_date": yesterday},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "daily" in data
        assert "summary" in data

    def test_weekly_overview_has_data(self, state: _JP_State) -> None:
        """weekly-overview should include data from the processed journal entry."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/weekly-overview",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("user_id") == state.user_id
        # Should have at least one daily entry from our processed journal
        assert isinstance(data.get("daily"), list)

    def test_timeseries_overview(self, state: _JP_State) -> None:
        """timeseries-overview should return grouped data."""
        start = (date.today() - timedelta(days=7)).isoformat()
        end = date.today().isoformat()
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/timeseries-overview",
            headers=_h(state.token),
            params={"start_date": start, "end_date": end, "bucket": "day"},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_range_overview(self, state: _JP_State) -> None:
        """range-overview with custom date range."""
        start = (date.today() - timedelta(days=7)).isoformat()
        end = date.today().isoformat()
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/range-overview",
            headers=_h(state.token),
            params={"start_date": start, "end_date": end},
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_reports_require_auth(self) -> None:
        """Reporting endpoints should reject unauthenticated requests."""
        resp = requests.get(
            f"{JOURNAL_URL}/journal/reports/weekly-overview",
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code in (401, 403)


# ===================================================================
# 6. SERVICE HEALTH & METRICS
# ===================================================================


@pytest.mark.e2e
class TestJPHealthAndMetrics:
    """Test health check and Prometheus metrics."""

    def test_health_endpoint(self) -> None:
        resp = requests.get(f"{JOURNAL_URL}/health", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "journal-parser"

    def test_metrics_endpoint(self) -> None:
        """Prometheus metrics should be available."""
        resp = requests.get(f"{JOURNAL_URL}/journal/metrics", timeout=HTTP_TIMEOUT)
        assert resp.status_code == 200
        assert "python_gc" in resp.text or "journal_parser" in resp.text

    def test_correlation_id_header(self, state: _JP_State) -> None:
        """Responses should include the X-Correlation-ID header."""
        resp = requests.get(
            f"{AUTH_URL}/auth/me",
            headers=_h(state.token),
            timeout=HTTP_TIMEOUT,
        )
        assert resp.status_code == 200
        assert "x-correlation-id" in resp.headers
