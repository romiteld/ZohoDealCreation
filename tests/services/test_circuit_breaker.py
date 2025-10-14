"""
Comprehensive tests for Circuit Breaker implementation
Tests resilience patterns, fallback strategies, and state management
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

# Import circuit breaker components
from teams_bot.app.services.circuit_breaker import (
    EnhancedCircuitBreaker,
    redis_breaker,
    postgresql_breaker,
    zoho_breaker,
    with_fallback,
    get_breaker_status,
    get_all_breaker_status,
    reset_all_breakers,
    get_circuit_breaker_health,
    redis_fallback_get,
    redis_fallback_set,
    postgresql_fallback_query,
    zoho_fallback_request,
    InMemoryRateLimitSession,
    BreakerState,
    in_memory_sessions
)

from pybreaker import CircuitBreakerError


class TestEnhancedCircuitBreaker:
    """Test EnhancedCircuitBreaker functionality"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization"""
        breaker = EnhancedCircuitBreaker(
            name="test_breaker",
            fail_max=3,
            timeout_duration=30
        )

        assert breaker.name == "test_breaker"
        assert breaker.get_state() == BreakerState.CLOSED
        assert breaker.metrics.total_fallbacks == 0

    @pytest.mark.asyncio
    async def test_successful_primary_function(self):
        """Test successful execution of primary function"""
        breaker = EnhancedCircuitBreaker(
            name="test_success",
            fail_max=3
        )

        async def primary_fn(value):
            return f"Success: {value}"

        result = await breaker.call_with_fallback(
            primary_fn,
            None,
            "test_value"
        )

        assert result == "Success: test_value"
        assert breaker.get_state() == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test circuit breaker opens after max failures"""
        breaker = EnhancedCircuitBreaker(
            name="test_failure",
            fail_max=3,
            timeout_duration=1
        )

        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise Exception("Simulated failure")

        async def fallback_fn():
            return "Fallback response"

        # Make calls until circuit opens
        for i in range(5):
            try:
                result = await breaker.call_with_fallback(
                    failing_fn,
                    fallback_fn
                )
                # After circuit opens, should get fallback
                assert result == "Fallback response"
            except Exception:
                # First 3 calls will fail before circuit opens
                pass

        # Circuit should be open after 3 failures
        assert breaker.get_state() == BreakerState.OPEN
        # Primary function should only be called 3 times
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_recovers_after_timeout(self):
        """Test circuit breaker recovers after timeout period"""
        breaker = EnhancedCircuitBreaker(
            name="test_recovery",
            fail_max=2,
            timeout_duration=1  # 1 second timeout
        )

        async def failing_then_succeeding_fn():
            if breaker.breaker.failure_count < 2:
                raise Exception("Still failing")
            return "Recovered!"

        async def fallback_fn():
            return "Fallback"

        # Cause failures to open circuit
        for _ in range(2):
            try:
                await breaker.call_with_fallback(failing_then_succeeding_fn, fallback_fn)
            except:
                pass

        assert breaker.get_state() == BreakerState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.5)

        # Reset failure count for recovery test
        breaker.breaker.failure_count = 0

        # Should try primary again after timeout
        async def success_fn():
            return "Success after recovery"

        result = await breaker.call_with_fallback(success_fn, fallback_fn)
        assert result == "Success after recovery"

    @pytest.mark.asyncio
    async def test_fallback_metrics_tracking(self):
        """Test fallback metrics are tracked correctly"""
        breaker = EnhancedCircuitBreaker(
            name="test_metrics",
            fail_max=1,
            timeout_duration=60
        )

        async def failing_fn():
            raise Exception("Fail")

        async def fallback_fn():
            await asyncio.sleep(0.01)  # Simulate some processing
            return "Fallback"

        # Trigger circuit to open
        try:
            await breaker.call_with_fallback(failing_fn, fallback_fn)
        except:
            pass

        # Now circuit is open, use fallback
        result = await breaker.call_with_fallback(failing_fn, fallback_fn)

        assert result == "Fallback"
        assert breaker.metrics.total_fallbacks == 1
        assert breaker.metrics.successful_fallbacks == 1
        assert breaker.metrics.get_success_rate() == 100.0

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        """Test manual circuit breaker reset"""
        breaker = EnhancedCircuitBreaker(
            name="test_reset",
            fail_max=1,
            timeout_duration=3600  # Long timeout
        )

        async def failing_fn():
            raise Exception("Fail")

        # Open the circuit
        try:
            await breaker.call_with_fallback(failing_fn, None)
        except:
            pass

        assert breaker.get_state() == BreakerState.OPEN

        # Manual reset
        breaker.reset()

        assert breaker.get_state() == BreakerState.CLOSED
        assert breaker.breaker.failure_count == 0


class TestRedisFallback:
    """Test Redis fallback strategies"""

    @pytest.mark.asyncio
    async def test_redis_fallback_get_session(self):
        """Test Redis GET fallback for session data"""
        # Clear in-memory sessions
        in_memory_sessions.clear()

        # Create a test session
        in_memory_sessions["user123"] = InMemoryRateLimitSession(
            user_id="user123",
            clarifications_used=1
        )

        result = await redis_fallback_get("session:user123")

        assert result is not None
        assert result["user_id"] == "user123"
        assert result["clarifications_used"] == 1
        assert "can_clarify" in result

    @pytest.mark.asyncio
    async def test_redis_fallback_get_missing_key(self):
        """Test Redis GET fallback for missing key"""
        result = await redis_fallback_get("nonexistent:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_fallback_set_session(self):
        """Test Redis SET fallback for session data"""
        # Clear in-memory sessions
        in_memory_sessions.clear()

        session_data = {
            "user_id": "user456",
            "clarifications_used": 2
        }

        result = await redis_fallback_set("session:user456", session_data)

        assert result is True
        assert "user456" in in_memory_sessions
        assert in_memory_sessions["user456"].clarifications_used == 2


class TestPostgreSQLFallback:
    """Test PostgreSQL fallback strategies"""

    @pytest.mark.asyncio
    async def test_postgresql_fallback_returns_help_card(self):
        """Test PostgreSQL fallback returns help card"""
        result = await postgresql_fallback_query("SELECT * FROM users")

        assert result is not None
        assert result["type"] == "help"
        assert result["title"] == "Database Temporarily Unavailable"
        assert result["cached"] is True
        assert "timestamp" in result


class TestZohoFallback:
    """Test Zoho API fallback strategies"""

    @pytest.mark.asyncio
    async def test_zoho_fallback_queues_request(self):
        """Test Zoho API fallback queues request"""
        result = await zoho_fallback_request(
            endpoint="/api/v2/Contacts",
            data={"name": "Test Contact"}
        )

        assert result["status"] == "queued"
        assert "request_id" in result
        assert result["retry_after"] == 300


class TestInMemoryRateLimitSession:
    """Test in-memory rate limiting session"""

    def test_session_initialization(self):
        """Test session initialization"""
        session = InMemoryRateLimitSession(user_id="user789")

        assert session.user_id == "user789"
        assert session.clarifications_used == 0
        assert session.max_clarifications == 1

    def test_can_clarify_within_limit(self):
        """Test user can clarify within limit"""
        session = InMemoryRateLimitSession(user_id="user789")

        assert session.can_clarify() is True

        session.use_clarification()
        assert session.clarifications_used == 1
        assert session.can_clarify() is False

    def test_session_reset_after_timeout(self):
        """Test session resets after timeout"""
        session = InMemoryRateLimitSession(user_id="user789")
        session.use_clarification()

        # Simulate timeout
        session.last_reset = datetime.now() - timedelta(hours=2)

        assert session.can_clarify() is True
        assert session.clarifications_used == 1  # Not reset yet

        # Use clarification triggers reset
        session.use_clarification()
        assert session.clarifications_used == 1  # Reset and incremented


class TestCircuitBreakerHelpers:
    """Test helper functions"""

    def test_get_breaker_status(self):
        """Test getting individual breaker status"""
        status = get_breaker_status("redis_breaker")

        assert "name" in status
        assert status["name"] == "redis_breaker"
        assert "state" in status
        assert "failure_count" in status

    def test_get_unknown_breaker_status(self):
        """Test getting status of unknown breaker"""
        status = get_breaker_status("unknown_breaker")
        assert "error" in status

    def test_get_all_breaker_status(self):
        """Test getting all breaker statuses"""
        status = get_all_breaker_status()

        assert "redis" in status
        assert "postgresql" in status
        assert "zoho_api" in status
        assert "timestamp" in status

    def test_reset_all_breakers(self):
        """Test resetting all breakers"""
        # No exceptions should be raised
        reset_all_breakers()

        # Verify all breakers are closed
        status = get_all_breaker_status()
        for name, breaker_status in status.items():
            if isinstance(breaker_status, dict) and "state" in breaker_status:
                assert breaker_status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_health(self):
        """Test getting overall circuit breaker health"""
        health = await get_circuit_breaker_health()

        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "recovering"]
        assert "breakers" in health
        assert "in_memory_sessions" in health
        assert "recommendations" in health


class TestIntegrationExamples:
    """Test integration with existing services"""

    @pytest.mark.asyncio
    async def test_with_fallback_helper(self):
        """Test with_fallback helper function"""
        async def primary():
            return "Primary result"

        async def fallback():
            return "Fallback result"

        # Test successful primary
        result = await with_fallback(
            redis_breaker,
            primary,
            fallback
        )
        assert result == "Primary result"

        # Test with failing primary
        async def failing_primary():
            raise Exception("Primary failed")

        # Open circuit first
        redis_breaker.breaker.fail_max = 1
        try:
            await redis_breaker.call_with_fallback(failing_primary, None)
        except:
            pass

        # Now should use fallback
        result = await with_fallback(
            redis_breaker,
            failing_primary,
            fallback
        )
        assert result == "Fallback result"

        # Reset for other tests
        redis_breaker.reset()

    @pytest.mark.asyncio
    async def test_redis_integration_example(self):
        """Test Redis integration example"""
        from teams_bot.app.services.circuit_breaker import CircuitBreakerExamples

        # Mock Redis client
        redis_client = AsyncMock()
        redis_client.get.return_value = "cached_value"

        result = await CircuitBreakerExamples.redis_with_circuit_breaker(
            redis_client,
            "test:key"
        )

        assert result == "cached_value"
        redis_client.get.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_postgresql_integration_example(self):
        """Test PostgreSQL integration example"""
        from teams_bot.app.services.circuit_breaker import CircuitBreakerExamples

        # Mock database connection
        conn = AsyncMock()
        conn.fetchval.return_value = 42

        result = await CircuitBreakerExamples.postgresql_with_circuit_breaker(
            conn,
            "SELECT COUNT(*) FROM users"
        )

        assert result == 42
        conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_zoho_integration_example(self):
        """Test Zoho API integration example"""
        from teams_bot.app.services.circuit_breaker import CircuitBreakerExamples

        # Mock Zoho client
        client = AsyncMock()
        client.post.return_value = {"id": "123", "status": "created"}

        result = await CircuitBreakerExamples.zoho_api_with_circuit_breaker(
            client,
            "/api/v2/Contacts",
            {"name": "Test"}
        )

        assert result["id"] == "123"
        client.post.assert_called_once()


class TestMetricsAndTelemetry:
    """Test metrics and telemetry functionality"""

    @pytest.mark.asyncio
    async def test_fallback_metrics_accumulation(self):
        """Test fallback metrics accumulate correctly"""
        breaker = EnhancedCircuitBreaker(
            name="test_metrics_accumulation",
            fail_max=1,
            timeout_duration=60
        )

        async def failing_fn():
            raise Exception("Fail")

        async def success_fallback():
            return "Success"

        async def failing_fallback():
            raise Exception("Fallback fail")

        # Open circuit
        try:
            await breaker.call_with_fallback(failing_fn, None)
        except:
            pass

        # Successful fallback
        await breaker.call_with_fallback(failing_fn, success_fallback)

        # Failed fallback
        try:
            await breaker.call_with_fallback(failing_fn, failing_fallback)
        except:
            pass

        metrics = breaker.get_metrics()
        assert metrics["fallback_metrics"]["total"] == 2
        assert metrics["fallback_metrics"]["successful"] == 1
        assert metrics["fallback_metrics"]["failed"] == 1
        assert metrics["fallback_metrics"]["success_rate"] == "50.00%"

    @pytest.mark.asyncio
    async def test_health_recommendations(self):
        """Test health recommendations generation"""
        # Open redis breaker
        redis_breaker.breaker.fail_max = 1
        async def fail():
            raise Exception("Fail")

        try:
            await redis_breaker.call_with_fallback(fail, None)
        except:
            pass

        health = await get_circuit_breaker_health()

        assert health["status"] == "degraded"
        assert len(health["recommendations"]) > 0
        assert any("redis" in rec.lower() for rec in health["recommendations"])

        # Reset for other tests
        redis_breaker.reset()
        redis_breaker.breaker.fail_max = 5


# Fixtures for test isolation
@pytest.fixture(autouse=True)
def clear_in_memory_sessions():
    """Clear in-memory sessions before each test"""
    in_memory_sessions.clear()
    yield
    in_memory_sessions.clear()


@pytest.fixture(autouse=True)
def reset_breakers():
    """Reset all breakers after each test"""
    yield
    reset_all_breakers()