"""
Circuit Breaker Pattern Implementation for Resilient Microservices
Provides automatic fallback strategies when dependencies fail (Redis, PostgreSQL, Zoho API)
Follows 2025 best practices for distributed systems resilience
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional, List, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import json

from pybreaker import CircuitBreaker, CircuitBreakerError, STATE_OPEN, STATE_CLOSED, STATE_HALF_OPEN

# Application Insights for monitoring (if available)
try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry import trace
    TELEMETRY_AVAILABLE = True
    tracer = trace.get_tracer(__name__)
except ImportError:
    TELEMETRY_AVAILABLE = False
    tracer = None

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, using fallback
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class FallbackMetrics:
    """Metrics for fallback strategy performance"""
    total_fallbacks: int = 0
    successful_fallbacks: int = 0
    failed_fallbacks: int = 0
    last_fallback_time: Optional[datetime] = None
    fallback_latencies: deque = field(default_factory=lambda: deque(maxlen=100))

    def record_fallback(self, success: bool, latency_ms: float):
        """Record a fallback execution"""
        self.total_fallbacks += 1
        if success:
            self.successful_fallbacks += 1
        else:
            self.failed_fallbacks += 1
        self.last_fallback_time = datetime.now()
        self.fallback_latencies.append(latency_ms)

    def get_avg_latency(self) -> float:
        """Get average fallback latency"""
        if not self.fallback_latencies:
            return 0.0
        return sum(self.fallback_latencies) / len(self.fallback_latencies)

    def get_success_rate(self) -> float:
        """Get fallback success rate"""
        if self.total_fallbacks == 0:
            return 0.0
        return (self.successful_fallbacks / self.total_fallbacks) * 100


@dataclass
class InMemoryRateLimitSession:
    """In-memory rate limiting session for Redis fallback"""
    user_id: str
    clarifications_used: int = 0
    max_clarifications: int = 1
    last_reset: datetime = field(default_factory=datetime.now)
    session_timeout: timedelta = field(default_factory=lambda: timedelta(hours=1))

    def can_clarify(self) -> bool:
        """Check if user can make another clarification"""
        # Reset if session expired
        if datetime.now() - self.last_reset > self.session_timeout:
            self.clarifications_used = 0
            self.last_reset = datetime.now()

        return self.clarifications_used < self.max_clarifications

    def use_clarification(self) -> bool:
        """Use a clarification if available"""
        if self.can_clarify():
            self.clarifications_used += 1
            return True
        return False


class EnhancedCircuitBreaker:
    """Enhanced circuit breaker with telemetry and fallback metrics"""

    def __init__(self,
                 name: str,
                 fail_max: int = 5,
                 timeout_duration: int = 60,
                 expected_exception: type = Exception,
                 fallback_fn: Optional[Callable] = None):
        """
        Initialize enhanced circuit breaker

        Args:
            name: Breaker identifier
            fail_max: Number of failures before opening
            timeout_duration: Seconds to stay open
            expected_exception: Exception types to catch
            fallback_fn: Default fallback function
        """
        self.name = name
        self.breaker = CircuitBreaker(
            fail_max=fail_max,
            timeout_duration=timeout_duration,
            expected_exception=expected_exception,
            name=name
        )
        self.fallback_fn = fallback_fn
        self.metrics = FallbackMetrics()

        # Register listeners for state changes
        self.breaker.add_listeners(self._on_state_change)

        logger.info(f"Circuit breaker '{name}' initialized: fail_max={fail_max}, timeout={timeout_duration}s")

    def _on_state_change(self, breaker, old_state, new_state):
        """Handle circuit breaker state changes"""
        logger.warning(f"Circuit breaker '{self.name}' state changed: {old_state} -> {new_state}")

        # Emit telemetry if available
        if TELEMETRY_AVAILABLE and tracer:
            with tracer.start_as_current_span(f"circuit_breaker.{self.name}.state_change") as span:
                span.set_attribute("old_state", str(old_state))
                span.set_attribute("new_state", str(new_state))
                span.set_attribute("failure_count", breaker.failure_count)

        # Log to Application Insights
        telemetry_event = {
            "name": f"CircuitBreakerStateChange",
            "properties": {
                "breaker_name": self.name,
                "old_state": str(old_state),
                "new_state": str(new_state),
                "failure_count": breaker.failure_count,
                "timestamp": datetime.now().isoformat()
            }
        }
        logger.info(f"Telemetry: {json.dumps(telemetry_event)}")

    async def call_with_fallback(self,
                                 primary_fn: Callable,
                                 fallback_fn: Optional[Callable] = None,
                                 *args, **kwargs) -> Any:
        """
        Execute primary function with circuit breaker and fallback

        Args:
            primary_fn: Primary function to execute
            fallback_fn: Fallback function (overrides default)
            *args, **kwargs: Arguments for functions

        Returns:
            Result from primary or fallback function
        """
        start_time = time.time()
        use_fallback = fallback_fn or self.fallback_fn

        try:
            # Try primary function through circuit breaker
            if asyncio.iscoroutinefunction(primary_fn):
                result = await self.breaker(primary_fn)(*args, **kwargs)
            else:
                result = self.breaker(primary_fn)(*args, **kwargs)

            return result

        except CircuitBreakerError as e:
            # Circuit is open, use fallback
            logger.warning(f"Circuit breaker '{self.name}' is open, using fallback")

            if use_fallback:
                try:
                    fallback_start = time.time()

                    if asyncio.iscoroutinefunction(use_fallback):
                        result = await use_fallback(*args, **kwargs)
                    else:
                        result = use_fallback(*args, **kwargs)

                    # Record successful fallback
                    latency = (time.time() - fallback_start) * 1000
                    self.metrics.record_fallback(True, latency)

                    return result

                except Exception as fallback_error:
                    # Fallback also failed
                    logger.error(f"Fallback for '{self.name}' failed: {fallback_error}")
                    self.metrics.record_fallback(False, 0)
                    raise
            else:
                # No fallback available
                logger.error(f"No fallback available for '{self.name}'")
                raise

        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error in circuit breaker '{self.name}': {e}")
            raise

    def get_state(self) -> BreakerState:
        """Get current breaker state"""
        if self.breaker.state == STATE_CLOSED:
            return BreakerState.CLOSED
        elif self.breaker.state == STATE_OPEN:
            return BreakerState.OPEN
        else:
            return BreakerState.HALF_OPEN

    def get_metrics(self) -> Dict[str, Any]:
        """Get breaker metrics"""
        return {
            "name": self.name,
            "state": self.get_state().value,
            "failure_count": self.breaker.failure_count,
            "success_count": self.breaker.success_count,
            "fallback_metrics": {
                "total": self.metrics.total_fallbacks,
                "successful": self.metrics.successful_fallbacks,
                "failed": self.metrics.failed_fallbacks,
                "success_rate": f"{self.metrics.get_success_rate():.2f}%",
                "avg_latency_ms": self.metrics.get_avg_latency()
            }
        }

    def reset(self):
        """Manually reset the circuit breaker"""
        self.breaker.reset()
        logger.info(f"Circuit breaker '{self.name}' manually reset")


# =============================================================================
# DEPENDENCY-SPECIFIC CIRCUIT BREAKERS
# =============================================================================

# Redis Circuit Breaker
redis_breaker = EnhancedCircuitBreaker(
    name="redis_breaker",
    fail_max=5,              # Open after 5 failures
    timeout_duration=60,     # Stay open for 60 seconds
    expected_exception=Exception
)

# PostgreSQL Circuit Breaker
postgresql_breaker = EnhancedCircuitBreaker(
    name="postgresql_breaker",
    fail_max=3,              # Open after 3 failures (more critical)
    timeout_duration=120,    # Stay open for 2 minutes
    expected_exception=Exception
)

# Zoho API Circuit Breaker
zoho_breaker = EnhancedCircuitBreaker(
    name="zoho_api_breaker",
    fail_max=10,             # Open after 10 failures (API can be flaky)
    timeout_duration=300,    # Stay open for 5 minutes
    expected_exception=Exception
)

# Apollo API Circuit Breaker
apollo_breaker = EnhancedCircuitBreaker(
    name="apollo_api_breaker",
    fail_max=5,
    timeout_duration=180,
    expected_exception=Exception
)

# Firecrawl API Circuit Breaker
firecrawl_breaker = EnhancedCircuitBreaker(
    name="firecrawl_api_breaker",
    fail_max=5,
    timeout_duration=180,
    expected_exception=Exception
)


# =============================================================================
# FALLBACK STRATEGIES
# =============================================================================

# In-memory session storage for Redis fallback
in_memory_sessions: Dict[str, InMemoryRateLimitSession] = {}

async def redis_fallback_get(key: str, *args, **kwargs) -> Optional[Any]:
    """Fallback for Redis GET operations"""
    logger.warning(f"Using in-memory fallback for Redis GET: {key}")

    # For rate limiting keys
    if key.startswith("session:"):
        user_id = key.split(":")[-1]
        session = in_memory_sessions.get(user_id)
        if session:
            return {
                "user_id": session.user_id,
                "clarifications_used": session.clarifications_used,
                "can_clarify": session.can_clarify()
            }

    # For other keys, return None (cache miss)
    return None


async def redis_fallback_set(key: str, value: Any, ttl: Optional[int] = None, *args, **kwargs) -> bool:
    """Fallback for Redis SET operations"""
    logger.warning(f"Using in-memory fallback for Redis SET: {key}")

    # For rate limiting keys
    if key.startswith("session:"):
        user_id = key.split(":")[-1]

        # Create or update session
        if user_id not in in_memory_sessions:
            in_memory_sessions[user_id] = InMemoryRateLimitSession(user_id=user_id)

        # Update session data if value is dict
        if isinstance(value, dict):
            session = in_memory_sessions[user_id]
            session.clarifications_used = value.get("clarifications_used", 0)

        return True

    # For other keys, just log and return success
    return True


async def postgresql_fallback_query(*args, **kwargs) -> Optional[Any]:
    """Fallback for PostgreSQL queries"""
    logger.warning("Using PostgreSQL fallback - returning cached/default response")

    # Return a help card as fallback
    return {
        "type": "help",
        "title": "Database Temporarily Unavailable",
        "content": "The database is temporarily unavailable. Please try again in a few moments.",
        "actions": [
            {"type": "retry", "title": "Retry", "value": "retry"},
            {"type": "help", "title": "Get Help", "value": "help"}
        ],
        "cached": True,
        "timestamp": datetime.now().isoformat()
    }


async def zoho_fallback_request(*args, **kwargs) -> Dict[str, Any]:
    """Fallback for Zoho API requests"""
    logger.warning("Using Zoho API fallback - queueing request for retry")

    # Queue to Azure Service Bus or local queue for later processing
    request_id = str(datetime.now().timestamp())

    # In production, this would queue to Service Bus
    # For now, return a placeholder response
    return {
        "status": "queued",
        "request_id": request_id,
        "message": "Request queued for processing when Zoho API is available",
        "retry_after": 300,  # 5 minutes
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def with_fallback(breaker: EnhancedCircuitBreaker,
                        primary_fn: Callable,
                        fallback_fn: Callable,
                        *args, **kwargs) -> Any:
    """
    Execute function with circuit breaker and fallback

    Args:
        breaker: Circuit breaker to use
        primary_fn: Primary function to execute
        fallback_fn: Fallback function
        *args, **kwargs: Arguments for functions

    Returns:
        Result from primary or fallback function
    """
    return await breaker.call_with_fallback(primary_fn, fallback_fn, *args, **kwargs)


def get_breaker_status(breaker_name: str) -> Dict[str, Any]:
    """
    Get status of a specific circuit breaker

    Args:
        breaker_name: Name of the breaker

    Returns:
        Breaker status and metrics
    """
    breakers = {
        "redis_breaker": redis_breaker,
        "postgresql_breaker": postgresql_breaker,
        "zoho_api_breaker": zoho_breaker,
        "apollo_api_breaker": apollo_breaker,
        "firecrawl_api_breaker": firecrawl_breaker
    }

    breaker = breakers.get(breaker_name)
    if not breaker:
        return {"error": f"Unknown breaker: {breaker_name}"}

    return breaker.get_metrics()


def get_all_breaker_status() -> Dict[str, Any]:
    """Get status of all circuit breakers"""
    return {
        "redis": redis_breaker.get_metrics(),
        "postgresql": postgresql_breaker.get_metrics(),
        "zoho_api": zoho_breaker.get_metrics(),
        "apollo_api": apollo_breaker.get_metrics(),
        "firecrawl_api": firecrawl_breaker.get_metrics(),
        "timestamp": datetime.now().isoformat()
    }


def reset_all_breakers():
    """Reset all circuit breakers (admin function)"""
    breakers = [
        redis_breaker,
        postgresql_breaker,
        zoho_breaker,
        apollo_breaker,
        firecrawl_breaker
    ]

    for breaker in breakers:
        breaker.reset()

    logger.info("All circuit breakers reset")


def reset_breaker(breaker_name: str) -> bool:
    """Reset a specific circuit breaker"""
    breakers = {
        "redis_breaker": redis_breaker,
        "postgresql_breaker": postgresql_breaker,
        "zoho_api_breaker": zoho_breaker,
        "apollo_api_breaker": apollo_breaker,
        "firecrawl_api_breaker": firecrawl_breaker
    }

    breaker = breakers.get(breaker_name)
    if breaker:
        breaker.reset()
        return True
    return False


# =============================================================================
# HEALTH CHECK ENDPOINT DATA
# =============================================================================

async def get_circuit_breaker_health() -> Dict[str, Any]:
    """Get health status for all circuit breakers"""
    all_status = get_all_breaker_status()

    # Determine overall health
    any_open = any(
        breaker["state"] == "open"
        for breaker in all_status.values()
        if isinstance(breaker, dict) and "state" in breaker
    )

    any_half_open = any(
        breaker["state"] == "half_open"
        for breaker in all_status.values()
        if isinstance(breaker, dict) and "state" in breaker
    )

    if any_open:
        overall_status = "degraded"
    elif any_half_open:
        overall_status = "recovering"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "breakers": all_status,
        "in_memory_sessions": len(in_memory_sessions),
        "recommendations": _get_health_recommendations(all_status)
    }


def _get_health_recommendations(status: Dict[str, Any]) -> List[str]:
    """Generate health recommendations based on breaker status"""
    recommendations = []

    for name, breaker in status.items():
        if isinstance(breaker, dict) and "state" in breaker:
            if breaker["state"] == "open":
                recommendations.append(f"Investigate {name} failures - breaker is open")
            elif breaker["state"] == "half_open":
                recommendations.append(f"Monitor {name} - breaker is testing recovery")

            # Check fallback metrics
            if "fallback_metrics" in breaker:
                metrics = breaker["fallback_metrics"]
                if metrics["failed"] > metrics["successful"]:
                    recommendations.append(f"Review {name} fallback strategy - high failure rate")

    return recommendations


# =============================================================================
# INTEGRATION EXAMPLES
# =============================================================================

class CircuitBreakerExamples:
    """Examples of how to integrate circuit breakers into existing code"""

    @staticmethod
    async def redis_with_circuit_breaker(redis_client, key: str) -> Optional[str]:
        """Example: Redis GET with circuit breaker"""
        async def primary():
            return await redis_client.get(key)

        return await with_fallback(
            redis_breaker,
            primary,
            lambda: redis_fallback_get(key)
        )

    @staticmethod
    async def postgresql_with_circuit_breaker(conn, query: str, *args) -> Any:
        """Example: PostgreSQL query with circuit breaker"""
        async def primary():
            return await conn.fetchval(query, *args)

        return await with_fallback(
            postgresql_breaker,
            primary,
            postgresql_fallback_query
        )

    @staticmethod
    async def zoho_api_with_circuit_breaker(client, endpoint: str, data: Dict) -> Dict:
        """Example: Zoho API call with circuit breaker"""
        async def primary():
            return await client.post(endpoint, json=data)

        return await with_fallback(
            zoho_breaker,
            primary,
            lambda: zoho_fallback_request(endpoint, data)
        )


# Export main components
__all__ = [
    # Circuit breakers
    'redis_breaker',
    'postgresql_breaker',
    'zoho_breaker',
    'apollo_breaker',
    'firecrawl_breaker',

    # Helper functions
    'with_fallback',
    'get_breaker_status',
    'get_all_breaker_status',
    'reset_all_breakers',
    'reset_breaker',
    'get_circuit_breaker_health',

    # Fallback functions
    'redis_fallback_get',
    'redis_fallback_set',
    'postgresql_fallback_query',
    'zoho_fallback_request',

    # Classes
    'EnhancedCircuitBreaker',
    'InMemoryRateLimitSession',
    'CircuitBreakerExamples'
]