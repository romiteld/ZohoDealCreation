"""
Smoke tests for Vault Agent service.

These tests run against staging/production endpoints to validate:
- Digest generation works
- Email delivery succeeds
- Database operations complete
- Performance meets SLAs

Run before production deployment:
    pytest tests/smoke/test_vault_agent_smoke.py --env=staging
    pytest tests/smoke/test_vault_agent_smoke.py --env=production
"""

import os
import pytest
import httpx
import time
from typing import Dict, Any

# Configuration
STAGING_ENDPOINT = os.getenv("VAULT_AGENT_STAGING_URL", "https://vault-agent-http-staging.wittyocean-dfae0f9b.eastus.azurecontainerapps.io")
PROD_ENDPOINT = os.getenv("VAULT_AGENT_PROD_URL", "https://vault-agent-http.wittyocean-dfae0f9b.eastus.azurecontainerapps.io")

# SLA thresholds
MAX_DIGEST_GENERATION_TIME_MS = 30000  # 30 seconds
MAX_EMAIL_DELIVERY_TIME_MS = 10000  # 10 seconds


@pytest.fixture
def endpoint(request):
    """Get endpoint URL based on --env flag."""
    env = request.config.getoption("--env", default="staging")
    return PROD_ENDPOINT if env == "production" else STAGING_ENDPOINT


@pytest.fixture
def api_key():
    """API key for vault agent endpoints."""
    return os.getenv("API_KEY", "test-api-key")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_vault_agent_health(endpoint):
    """Test that vault agent health endpoint is responsive."""
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.get(f"{endpoint}/health")
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < 2000, f"Health check too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_generation_advisors(endpoint, api_key):
    """Test digest generation for advisors audience."""
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.post(
            f"{endpoint}/digest/advisors",
            headers={"X-API-Key": api_key},
            params={"max_cards": 5},
            timeout=60.0  # Digest generation can take time
        )
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < MAX_DIGEST_GENERATION_TIME_MS, f"Digest generation too slow: {duration_ms}ms"

        # Validate response structure
        data = response.json()
        assert data["status"] == "preview"
        assert "html" in data
        assert len(data["html"]) > 100, "Digest HTML too short"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_generation_c_suite(endpoint, api_key):
    """Test digest generation for c_suite audience."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/digest/c_suite",
            headers={"X-API-Key": api_key},
            params={"max_cards": 5},
            timeout=60.0
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preview"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_generation_global(endpoint, api_key):
    """Test digest generation for global audience."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/digest/global",
            headers={"X-API-Key": api_key},
            params={"max_cards": 5},
            timeout=60.0
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preview"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_email_delivery(endpoint, api_key):
    """Test digest email delivery to test address."""
    test_email = os.getenv("DIGEST_TEST_EMAIL", "daniel.romitelli@emailthewell.com")

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.post(
            f"{endpoint}/digest/advisors",
            headers={"X-API-Key": api_key},
            params={"test_email": test_email, "max_cards": 3},
            timeout=60.0
        )
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < (MAX_DIGEST_GENERATION_TIME_MS + MAX_EMAIL_DELIVERY_TIME_MS)

        # Validate response
        data = response.json()
        assert data["status"] == "sent"
        assert data["recipient"] == test_email


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_privacy_mode_enabled(endpoint, api_key):
    """Test that privacy mode is enabled (company anonymization)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/digest/advisors",
            headers={"X-API-Key": api_key},
            params={"max_cards": 5},
            timeout=60.0
        )

        assert response.status_code == 200
        data = response.json()
        html = data["html"]

        # Privacy mode should NOT contain actual company names
        # Check for generic descriptors instead
        forbidden_patterns = [
            "Morgan Stanley",  # Should be "Major wirehouse"
            "Merrill Lynch",   # Should be "Major wirehouse"
            "Wells Fargo",     # Should be "National bank"
        ]

        for pattern in forbidden_patterns:
            assert pattern not in html, f"Privacy mode failed: '{pattern}' found in digest"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_database_connection(endpoint, api_key):
    """Test vault agent can connect to database."""
    # Digest generation requires database access to fetch candidates
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/digest/advisors",
            headers={"X-API-Key": api_key},
            params={"max_cards": 1},
            timeout=60.0
        )

        # Should succeed if database is accessible
        assert response.status_code == 200


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_digest_error_handling(endpoint, api_key):
    """Test vault agent handles invalid audience gracefully."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/digest/invalid_audience",
            headers={"X-API-Key": api_key},
            timeout=10.0
        )

        # Should return error response (4xx or 5xx)
        assert response.status_code >= 400


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--env",
        action="store",
        default="staging",
        help="Environment to test: staging or production"
    )
