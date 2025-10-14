"""
Integration tests for circuit breaker pattern implementation.
Tests failure detection, circuit opening/closing, and fallback mechanisms.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import redis.exceptions


class CircuitBreakerState:
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple circuit breaker implementation for testing."""

    def __init__(self, failure_threshold=5, timeout=60, fallback_func=None):
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # Seconds before attempting to close
        self.fallback_func = fallback_func
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0

    async def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker."""
        # Check if circuit should be half-open
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            elif self.fallback_func:
                return await self.fallback_func(*args, **kwargs)
            else:
                raise Exception("Circuit breaker is open")

        try:
            # Attempt the call
            result = await func(*args, **kwargs)

            # Success - update state
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0

            self.success_count += 1
            return result

        except Exception as e:
            # Failure - update state
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN

            if self.state == CircuitBreakerState.OPEN and self.fallback_func:
                return await self.fallback_func(*args, **kwargs)

            raise e

    def _should_attempt_reset(self):
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        return (datetime.utcnow() - self.last_failure_time).seconds >= self.timeout

    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


@pytest.mark.asyncio
class TestRedisCircuitBreaker:
    """Test Redis circuit breaker functionality."""

    async def test_circuit_opens_after_failures(self):
        """Test that circuit breaker opens after 5 consecutive failures."""
        # Arrange
        async def failing_redis_operation():
            raise redis.exceptions.ConnectionError("Redis connection failed")

        async def fallback_operation():
            return {"source": "fallback", "data": "cached_value"}

        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            fallback_func=fallback_operation
        )

        # Act - Fail 5 times
        for i in range(5):
            try:
                await breaker.call(failing_redis_operation)
            except redis.exceptions.ConnectionError:
                pass

        # Assert - Circuit should be open
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.failure_count == 5

        # Further calls should use fallback
        result = await breaker.call(failing_redis_operation)
        assert result["source"] == "fallback"

    async def test_fallback_function_called_when_open(self):
        """Test that fallback function is called when circuit is open."""
        # Arrange
        call_count = 0
        fallback_count = 0

        async def unreliable_operation():
            nonlocal call_count
            call_count += 1
            raise Exception("Operation failed")

        async def fallback_operation():
            nonlocal fallback_count
            fallback_count += 1
            return "fallback_result"

        breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=60,
            fallback_func=fallback_operation
        )

        # Act - Trigger circuit opening
        for i in range(3):
            try:
                await breaker.call(unreliable_operation)
            except Exception:
                pass

        # Circuit is now open, next calls should use fallback
        results = []
        for i in range(5):
            result = await breaker.call(unreliable_operation)
            results.append(result)

        # Assert
        assert breaker.state == CircuitBreakerState.OPEN
        assert all(r == "fallback_result" for r in results)
        assert fallback_count == 5
        assert call_count == 3  # Only the initial failures

    async def test_circuit_auto_closes_after_timeout(self):
        """Test that circuit automatically attempts to close after timeout."""
        # Arrange
        async def sometimes_failing_operation():
            # Will succeed when called after circuit reset
            return "success"

        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=1  # 1 second timeout for testing
        )

        # Force circuit open
        breaker.state = CircuitBreakerState.OPEN
        breaker.failure_count = 2
        breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=2)

        # Act - Call after timeout period
        result = await breaker.call(sometimes_failing_operation)

        # Assert
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0

    async def test_half_open_state_transition(self):
        """Test half-open state transitions correctly."""
        # Arrange
        attempt_count = 0

        async def recovering_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 3:
                raise Exception("Still failing")
            return "recovered"

        breaker = CircuitBreaker(failure_threshold=2, timeout=0)

        # Act - Open the circuit
        for i in range(2):
            try:
                await breaker.call(recovering_operation)
            except Exception:
                pass

        assert breaker.state == CircuitBreakerState.OPEN

        # Wait and try again (should go to half-open)
        breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=1)

        try:
            await breaker.call(recovering_operation)
        except Exception:
            pass

        # Should be open again due to failure in half-open
        assert breaker.state == CircuitBreakerState.OPEN

        # Try once more after recovery
        breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=1)
        result = await breaker.call(recovering_operation)

        # Assert - Should be closed after success in half-open
        assert result == "recovered"
        assert breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
class TestZohoAPICircuitBreaker:
    """Test Zoho API circuit breaker functionality."""

    async def test_zoho_circuit_breaker_opens_on_api_errors(self):
        """Test circuit breaker for Zoho API failures."""
        # Arrange
        async def failing_zoho_call():
            raise Exception("Zoho API rate limit exceeded")

        async def fallback_zoho_call():
            return {"status": "queued", "message": "Request queued for retry"}

        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=300,  # 5 minutes for API rate limits
            fallback_func=fallback_zoho_call
        )

        # Act - Simulate API failures
        results = []
        for i in range(10):
            try:
                result = await breaker.call(failing_zoho_call)
                results.append(result)
            except Exception as e:
                if i < 5:
                    # First 5 should fail normally
                    assert str(e) == "Zoho API rate limit exceeded"
                results.append({"status": "error", "message": str(e)})

        # Assert
        assert breaker.state == CircuitBreakerState.OPEN
        # After opening, should get fallback responses
        fallback_results = [r for r in results if r.get("status") == "queued"]
        assert len(fallback_results) == 5


@pytest.mark.asyncio
class TestOpenAICircuitBreaker:
    """Test OpenAI/GPT-5 circuit breaker functionality."""

    async def test_gpt5_circuit_breaker_with_model_fallback(self):
        """Test circuit breaker with GPT-5 model fallback to mini."""
        # Arrange
        async def gpt5_full_call(prompt, model="gpt-5"):
            if model == "gpt-5":
                raise Exception("GPT-5 rate limit exceeded")
            return {"model": model, "response": "Generated text"}

        async def fallback_to_mini(prompt, model="gpt-5"):
            # Fallback to GPT-5-mini
            return await gpt5_full_call(prompt, model="gpt-5-mini")

        breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=60,
            fallback_func=fallback_to_mini
        )

        # Act
        results = []
        for i in range(5):
            try:
                result = await breaker.call(gpt5_full_call, "Test prompt")
                results.append(result)
            except Exception:
                pass

        # Assert
        assert breaker.state == CircuitBreakerState.OPEN
        # Should have fallback results
        assert len(results) == 2  # Last 2 calls after circuit opened
        assert all(r["model"] == "gpt-5-mini" for r in results)


@pytest.mark.asyncio
class TestCascadingCircuitBreakers:
    """Test cascading failure scenarios with multiple circuit breakers."""

    async def test_cascading_failure_handling(self):
        """Test handling cascading failures across multiple services."""
        # Arrange
        redis_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
        zoho_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        gpt_breaker = CircuitBreaker(failure_threshold=2, timeout=10)

        service_states = {
            "redis": "healthy",
            "zoho": "healthy",
            "gpt": "healthy"
        }

        async def redis_operation():
            if service_states["redis"] == "failed":
                raise redis.exceptions.ConnectionError("Redis down")
            return "redis_data"

        async def zoho_operation():
            if service_states["zoho"] == "failed":
                raise Exception("Zoho API error")
            return "zoho_data"

        async def gpt_operation():
            if service_states["gpt"] == "failed":
                raise Exception("GPT-5 error")
            return "gpt_data"

        # Act - Simulate cascading failures
        results = []

        # Phase 1: All healthy
        try:
            r1 = await redis_breaker.call(redis_operation)
            r2 = await zoho_breaker.call(zoho_operation)
            r3 = await gpt_breaker.call(gpt_operation)
            results.append(("healthy", r1, r2, r3))
        except Exception:
            pass

        # Phase 2: Redis fails
        service_states["redis"] = "failed"
        for i in range(3):
            try:
                await redis_breaker.call(redis_operation)
            except Exception:
                pass

        # Phase 3: Zoho fails (while Redis is down)
        service_states["zoho"] = "failed"
        for i in range(5):
            try:
                await zoho_breaker.call(zoho_operation)
            except Exception:
                pass

        # Phase 4: GPT fails (cascade complete)
        service_states["gpt"] = "failed"
        for i in range(2):
            try:
                await gpt_breaker.call(gpt_operation)
            except Exception:
                pass

        # Assert - All circuits should be open
        assert redis_breaker.state == CircuitBreakerState.OPEN
        assert zoho_breaker.state == CircuitBreakerState.OPEN
        assert gpt_breaker.state == CircuitBreakerState.OPEN

        # Recovery test
        service_states["redis"] = "healthy"
        service_states["zoho"] = "healthy"
        service_states["gpt"] = "healthy"

        # Reset timeouts
        redis_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=31)
        zoho_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=61)
        gpt_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=11)

        # All should recover
        r1 = await redis_breaker.call(redis_operation)
        r2 = await zoho_breaker.call(zoho_operation)
        r3 = await gpt_breaker.call(gpt_operation)

        assert r1 == "redis_data"
        assert r2 == "zoho_data"
        assert r3 == "gpt_data"
        assert redis_breaker.state == CircuitBreakerState.CLOSED
        assert zoho_breaker.state == CircuitBreakerState.CLOSED
        assert gpt_breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics and monitoring."""

    async def test_circuit_breaker_metrics_collection(self):
        """Test collection of circuit breaker metrics."""
        # Arrange
        metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "fallback_calls": 0,
            "circuit_opens": 0,
            "circuit_closes": 0
        }

        async def monitored_operation():
            metrics["total_calls"] += 1
            if metrics["total_calls"] % 3 == 0:
                metrics["failed_calls"] += 1
                raise Exception("Periodic failure")
            metrics["successful_calls"] += 1
            return "success"

        async def fallback_operation():
            metrics["fallback_calls"] += 1
            return "fallback"

        class MonitoredCircuitBreaker(CircuitBreaker):
            async def call(self, func, *args, **kwargs):
                old_state = self.state
                result = await super().call(func, *args, **kwargs)
                new_state = self.state

                if old_state == CircuitBreakerState.CLOSED and new_state == CircuitBreakerState.OPEN:
                    metrics["circuit_opens"] += 1
                elif old_state == CircuitBreakerState.OPEN and new_state == CircuitBreakerState.CLOSED:
                    metrics["circuit_closes"] += 1

                return result

        breaker = MonitoredCircuitBreaker(
            failure_threshold=2,
            timeout=1,
            fallback_func=fallback_operation
        )

        # Act - Run multiple operations
        for i in range(20):
            try:
                await breaker.call(monitored_operation)
                await asyncio.sleep(0.1)  # Small delay
            except Exception:
                pass

            # Reset circuit periodically
            if i == 10:
                breaker.reset()
                metrics["circuit_closes"] += 1

        # Assert - Verify metrics
        assert metrics["total_calls"] == 20
        assert metrics["successful_calls"] > 0
        assert metrics["failed_calls"] > 0
        assert metrics["fallback_calls"] > 0
        assert metrics["circuit_opens"] > 0