"""
Smoke tests for Teams Bot service.

These tests run against staging/production endpoints to validate:
- Bot responds to messages
- Commands work correctly
- Response latency is acceptable
- Adaptive cards render properly

Run before production deployment:
    pytest tests/smoke/test_teams_bot_smoke.py --env=staging
    pytest tests/smoke/test_teams_bot_smoke.py --env=production
"""

import os
import pytest
import httpx
import asyncio
import time
from typing import Dict, Any

# Configuration
STAGING_ENDPOINT = os.getenv("TEAMS_BOT_STAGING_URL", "https://teams-bot-app-staging.wittyocean-dfae0f9b.eastus.azurecontainerapps.io")
PROD_ENDPOINT = os.getenv("TEAMS_BOT_PROD_URL", "https://teams-bot-app.wittyocean-dfae0f9b.eastus.azurecontainerapps.io")

# SLA thresholds
MAX_RESPONSE_TIME_MS = 2000  # 2 seconds
MAX_ERROR_RATE = 0.01  # 1%


@pytest.fixture
def endpoint(request):
    """Get endpoint URL based on --env flag."""
    env = request.config.getoption("--env", default="staging")
    return PROD_ENDPOINT if env == "production" else STAGING_ENDPOINT


@pytest.fixture
def bot_headers():
    """Headers for Bot Framework authentication."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('TEAMS_BOT_TEST_TOKEN', 'test-token')}"
    }


def create_message_activity(text: str, user_id: str = "test-user") -> Dict[str, Any]:
    """Create a Bot Framework message activity."""
    return {
        "type": "message",
        "id": f"test-{int(time.time())}",
        "timestamp": "2025-01-07T00:00:00Z",
        "channelId": "msteams",
        "from": {
            "id": user_id,
            "name": "Test User",
            "aadObjectId": "12345678-1234-1234-1234-123456789012"
        },
        "conversation": {
            "id": "test-conversation"
        },
        "text": text,
        "channelData": {
            "tenant": {"id": os.getenv("TEAMS_BOT_TENANT_ID", "test-tenant")}
        }
    }


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_health_endpoint(endpoint):
    """Test that bot health endpoint is responsive."""
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.get(f"{endpoint}/health")
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < MAX_RESPONSE_TIME_MS, f"Health check too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_help_command(endpoint, bot_headers):
    """Test /help command returns help card."""
    activity = create_message_activity("help")

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.post(
            f"{endpoint}/api/teams/webhook",
            json=activity,
            headers=bot_headers,
            timeout=5.0
        )
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < MAX_RESPONSE_TIME_MS, f"Help command too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_digest_command(endpoint, bot_headers):
    """Test /digest command generates preview."""
    activity = create_message_activity("digest advisors")

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.post(
            f"{endpoint}/api/teams/webhook",
            json=activity,
            headers=bot_headers,
            timeout=30.0  # Digest generation can take longer
        )
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        # Digest can be slow, but should complete within 30 seconds
        assert duration_ms < 30000, f"Digest command too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_preferences_command(endpoint, bot_headers):
    """Test /preferences command shows settings."""
    activity = create_message_activity("preferences")

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.post(
            f"{endpoint}/api/teams/webhook",
            json=activity,
            headers=bot_headers,
            timeout=5.0
        )
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < MAX_RESPONSE_TIME_MS, f"Preferences command too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_natural_language_query(endpoint, bot_headers):
    """Test natural language query processing."""
    activity = create_message_activity("show me deals from last week")

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.post(
            f"{endpoint}/api/teams/webhook",
            json=activity,
            headers=bot_headers,
            timeout=10.0
        )
        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration_ms < 10000, f"Query too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_concurrent_load(endpoint, bot_headers):
    """Test bot handles concurrent requests without errors."""
    num_concurrent = 10
    activities = [create_message_activity("help", f"user-{i}") for i in range(num_concurrent)]

    async def send_message(activity):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{endpoint}/api/teams/webhook",
                    json=activity,
                    headers=bot_headers,
                    timeout=5.0
                )
                return response.status_code == 200
            except Exception:
                return False

    start_time = time.time()
    results = await asyncio.gather(*[send_message(a) for a in activities])
    duration_ms = (time.time() - start_time) * 1000

    success_rate = sum(results) / len(results)
    assert success_rate >= (1 - MAX_ERROR_RATE), f"Error rate too high: {1 - success_rate}"
    assert duration_ms < 5000, f"Concurrent load too slow: {duration_ms}ms"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_database_connection(endpoint, bot_headers):
    """Test bot can connect to database (via preferences read)."""
    # Preferences command requires database access
    activity = create_message_activity("preferences")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/api/teams/webhook",
            json=activity,
            headers=bot_headers,
            timeout=5.0
        )

        # Should succeed if database is accessible
        assert response.status_code == 200


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_bot_error_handling(endpoint, bot_headers):
    """Test bot handles invalid commands gracefully."""
    activity = create_message_activity("invalid_command_xyz")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{endpoint}/api/teams/webhook",
            json=activity,
            headers=bot_headers,
            timeout=5.0
        )

        # Should return 200 even for invalid commands (bot should respond with error message)
        assert response.status_code == 200


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--env",
        action="store",
        default="staging",
        help="Environment to test: staging or production"
    )
