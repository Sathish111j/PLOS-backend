"""
Shared test fixtures for PLOS E2E testing.

Provides reusable fixtures for auth, HTTP clients, service URLs,
and Docker health checks used across all service test suites.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

import pytest
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service URL configuration
# ---------------------------------------------------------------------------

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/api/v1")
KB_URL = os.getenv("KB_URL", "http://localhost:8003")
CONTEXT_URL = os.getenv("CONTEXT_URL", "http://localhost:8001")
JOURNAL_URL = os.getenv("JOURNAL_URL", "http://localhost:8002")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8002")

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))


@dataclass
class ServiceURLs:
    """Container for all service URLs."""
    gateway: str = GATEWAY_URL
    kb: str = KB_URL
    context: str = CONTEXT_URL
    journal: str = JOURNAL_URL
    auth: str = AUTH_URL


@dataclass
class AuthState:
    """Holds authentication state for test sessions."""
    token: str = ""
    user_id: str = ""
    email: str = ""
    password: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_auth_headers(token: str) -> Dict[str, str]:
    """Build Authorization + Content-Type headers for a JWT token."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def wait_for_health(url: str, timeout: int = 60, interval: int = 2) -> bool:
    """
    Poll a health endpoint until it returns 200 or timeout is reached.
    Returns True if healthy, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "healthy":
                    return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def urls() -> ServiceURLs:
    """Service URL configuration -- available to all tests."""
    return ServiceURLs()


@pytest.fixture(scope="session")
def http_client() -> requests.Session:
    """
    Shared HTTP session with default timeout and retry configuration.
    Session-scoped so connection pooling is reused across tests.
    """
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        max_retries=requests.adapters.Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
        )
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@pytest.fixture(scope="session")
def docker_healthy(urls: ServiceURLs) -> bool:
    """
    Verify all Docker services are healthy before running tests.
    Skips entire test session if services are unreachable.
    """
    health_endpoints = [
        (f"{urls.journal}/health", "journal-parser"),
        (f"{urls.context}/health", "context-broker"),
        (f"{urls.kb}/health", "knowledge-base"),
    ]

    all_healthy = True
    for endpoint, name in health_endpoints:
        healthy = wait_for_health(endpoint, timeout=60)
        if healthy:
            logger.info(f"[HEALTH] {name} is healthy")
        else:
            logger.error(f"[HEALTH] {name} is NOT healthy at {endpoint}")
            all_healthy = False

    if not all_healthy:
        pytest.skip("Not all Docker services are healthy -- skipping tests")

    return True


@pytest.fixture(scope="session")
def auth_state(urls: ServiceURLs, http_client: requests.Session) -> AuthState:
    """
    Register a unique test user and log in.
    Returns AuthState with token, user_id, email, password.
    Session-scoped so the same user is reused across all tests.
    """
    unique = uuid.uuid4().hex[:8]
    email = f"e2e-test-{unique}@plos-test.dev"
    username = f"e2e_test_{unique}"
    password = "TestPass123!@#"

    # Register
    resp = http_client.post(
        f"{urls.auth}/auth/register",
        json={"email": email, "username": username, "password": password},
        timeout=HTTP_TIMEOUT,
    )
    assert resp.status_code in (200, 201), (
        f"Registration failed: {resp.status_code} {resp.text}"
    )

    # Login
    resp = http_client.post(
        f"{urls.auth}/auth/login",
        json={"email": email, "password": password},
        timeout=HTTP_TIMEOUT,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()

    user_info = data.get("user", {})
    state = AuthState(
        token=data["access_token"],
        user_id=user_info.get("user_id", data.get("user_id", "")),
        email=email,
        password=password,
    )
    logger.info(f"[AUTH] Test user created: {email} (user_id={state.user_id})")
    return state
