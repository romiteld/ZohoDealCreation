"""
Circuit Breaker Integration Examples
Shows how to integrate circuit breakers into existing services
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

# Import circuit breaker components
from app.services.circuit_breaker import (
    redis_breaker,
    postgresql_breaker,
    zoho_breaker,
    with_fallback,
    redis_fallback_get,
    redis_fallback_set,
    postgresql_fallback_query,
    zoho_fallback_request
)

# Import existing services
from well_shared.cache.redis_manager import RedisCacheManager
from well_shared.database.connection import get_connection_manager
from app.integrations import get_zoho_headers, ZOHO_BASE_URL

import httpx

logger = logging.getLogger(__name__)


class RedisCacheManagerWithCircuitBreaker:
    """
    Enhanced Redis Cache Manager with Circuit Breaker Pattern
    Wraps existing RedisCacheManager with resilience patterns
    """

    def __init__(self, redis_manager: RedisCacheManager):
        self.redis_manager = redis_manager

    async def get_cached_extraction(self,
                                   email_content: str,
                                   extraction_type: str = "full") -> Optional[Dict[str, Any]]:
        """Get cached extraction with circuit breaker protection"""

        async def primary():
            return await self.redis_manager.get_cached_extraction(email_content, extraction_type)

        async def fallback():
            logger.warning("Redis circuit open - cache miss for extraction")
            return None  # Always return cache miss when Redis is down

        return await with_fallback(redis_breaker, primary, fallback)

    async def cache_extraction(self,
                              email_content: str,
                              extraction_result: Dict[str, Any],
                              extraction_type: str = "full",
                              ttl: Optional[timedelta] = None) -> bool:
        """Cache extraction with circuit breaker protection"""

        async def primary():
            return await self.redis_manager.cache_extraction(
                email_content, extraction_result, extraction_type, ttl
            )

        async def fallback():
            logger.warning("Redis circuit open - skipping cache write")
            return False  # Gracefully skip caching when Redis is down

        return await with_fallback(redis_breaker, primary, fallback)

    async def get(self, key: str) -> Optional[str]:
        """Generic get with circuit breaker"""

        async def primary():
            return await self.redis_manager.get(key)

        # Use the fallback function from circuit_breaker module
        return await with_fallback(
            redis_breaker,
            primary,
            lambda: redis_fallback_get(key)
        )

    async def set(self, key: str, value: str, ttl: Optional[timedelta] = None) -> bool:
        """Generic set with circuit breaker"""

        async def primary():
            return await self.redis_manager.set(key, value, ttl)

        # Use the fallback function from circuit_breaker module
        return await with_fallback(
            redis_breaker,
            primary,
            lambda: redis_fallback_set(key, value, ttl)
        )


class DatabaseConnectionWithCircuitBreaker:
    """
    Enhanced Database Connection with Circuit Breaker Pattern
    Wraps existing database operations with resilience patterns
    """

    def __init__(self):
        self.manager = None

    async def initialize(self):
        """Initialize database manager with circuit breaker"""
        self.manager = await get_connection_manager()

    async def execute_query(self, query: str, *args, fetch_mode: str = 'fetchval') -> Any:
        """Execute query with circuit breaker protection"""

        async def primary():
            if not self.manager:
                await self.initialize()
            return await self.manager.execute_query(query, *args, fetch_mode=fetch_mode)

        # Use the fallback function from circuit_breaker module
        return await with_fallback(
            postgresql_breaker,
            primary,
            postgresql_fallback_query
        )

    async def fetch_vault_candidates(self, from_date: str) -> list:
        """Fetch vault candidates with circuit breaker"""

        async def primary():
            if not self.manager:
                await self.initialize()

            query = """
                SELECT * FROM vault_candidates
                WHERE created_at >= $1
                ORDER BY created_at DESC
            """

            async with self.manager.get_connection() as conn:
                return await conn.fetch(query, from_date)

        async def fallback():
            logger.warning("Database circuit open - returning cached vault candidates")
            # Return a minimal cached response
            return [{
                "id": "cached-001",
                "candidate_name": "[Database Unavailable]",
                "cached": True,
                "message": "Database is temporarily unavailable. Showing cached data."
            }]

        return await with_fallback(postgresql_breaker, primary, fallback)


class ZohoAPIWithCircuitBreaker:
    """
    Enhanced Zoho API Client with Circuit Breaker Pattern
    Wraps Zoho API calls with resilience patterns
    """

    def __init__(self):
        self.client = None
        self.headers = None

    async def initialize(self):
        """Initialize Zoho client with circuit breaker"""
        self.headers = await get_zoho_headers()

        # Create HTTP client with timeouts
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Zoho contact with circuit breaker"""

        async def primary():
            if not self.client:
                await self.initialize()

            url = f"{ZOHO_BASE_URL}/v8/Contacts"
            response = await self.client.post(
                url,
                json={"data": [contact_data]},
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

        # Use the fallback function from circuit_breaker module
        return await with_fallback(
            zoho_breaker,
            primary,
            lambda: zoho_fallback_request("/v8/Contacts", contact_data)
        )

    async def update_deal(self, deal_id: str, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update Zoho deal with circuit breaker"""

        async def primary():
            if not self.client:
                await self.initialize()

            url = f"{ZOHO_BASE_URL}/v8/Deals/{deal_id}"
            response = await self.client.put(
                url,
                json={"data": [deal_data]},
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

        # Use the fallback function from circuit_breaker module
        return await with_fallback(
            zoho_breaker,
            primary,
            lambda: zoho_fallback_request(f"/v8/Deals/{deal_id}", deal_data)
        )

    async def search_records(self,
                           module: str,
                           criteria: str,
                           fields: list = None) -> list:
        """Search Zoho records with circuit breaker"""

        async def primary():
            if not self.client:
                await self.initialize()

            url = f"{ZOHO_BASE_URL}/v8/{module}/search"
            params = {"criteria": criteria}
            if fields:
                params["fields"] = ",".join(fields)

            response = await self.client.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            return data.get("data", [])

        async def fallback():
            logger.warning(f"Zoho circuit open - returning empty search results for {module}")
            return []

        return await with_fallback(zoho_breaker, primary, fallback)

    async def cleanup(self):
        """Cleanup HTTP client"""
        if self.client:
            await self.client.aclose()


class TeamsRateLimitWithCircuitBreaker:
    """
    Teams Bot Rate Limiting with Circuit Breaker
    Implements in-memory fallback when Redis is unavailable
    """

    def __init__(self, redis_manager: RedisCacheManager):
        self.redis_manager = redis_manager

    async def check_rate_limit(self, user_id: str, limit: int = 5, window: int = 60) -> bool:
        """Check rate limit with circuit breaker"""

        async def primary():
            key = f"rate_limit:{user_id}"

            # Get current count
            current = await self.redis_manager.get(key)
            if not current:
                # First request in window
                await self.redis_manager.set(key, "1", ttl=timedelta(seconds=window))
                return True

            count = int(current)
            if count >= limit:
                return False

            # Increment counter
            await self.redis_manager.set(key, str(count + 1), ttl=timedelta(seconds=window))
            return True

        async def fallback():
            # Use in-memory rate limiting from circuit breaker module
            from app.services.circuit_breaker import in_memory_sessions, InMemoryRateLimitSession

            if user_id not in in_memory_sessions:
                in_memory_sessions[user_id] = InMemoryRateLimitSession(
                    user_id=user_id,
                    max_clarifications=limit
                )

            session = in_memory_sessions[user_id]
            return session.can_clarify()

        return await with_fallback(redis_breaker, primary, fallback)

    async def use_rate_limit(self, user_id: str) -> bool:
        """Use one rate limit slot with circuit breaker"""

        async def primary():
            key = f"rate_limit:{user_id}"
            current = await self.redis_manager.get(key)

            if current:
                count = int(current) + 1
            else:
                count = 1

            await self.redis_manager.set(key, str(count), ttl=timedelta(seconds=60))
            return True

        async def fallback():
            from app.services.circuit_breaker import in_memory_sessions, InMemoryRateLimitSession

            if user_id not in in_memory_sessions:
                in_memory_sessions[user_id] = InMemoryRateLimitSession(user_id=user_id)

            return in_memory_sessions[user_id].use_clarification()

        return await with_fallback(redis_breaker, primary, fallback)


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

async def example_redis_integration():
    """Example of using Redis with circuit breaker"""
    from well_shared.cache.redis_manager import get_cache_manager

    # Get original Redis manager
    redis_manager = await get_cache_manager()

    # Wrap with circuit breaker
    protected_redis = RedisCacheManagerWithCircuitBreaker(redis_manager)

    # Use as normal - circuit breaker handles failures transparently
    cached_value = await protected_redis.get("test:key")

    if not cached_value:
        # Compute value
        new_value = "computed_value"

        # Cache it (will gracefully fail if Redis is down)
        await protected_redis.set("test:key", new_value, ttl=timedelta(hours=1))

    return cached_value or "computed_value"


async def example_database_integration():
    """Example of using database with circuit breaker"""
    db = DatabaseConnectionWithCircuitBreaker()
    await db.initialize()

    # Query with automatic fallback
    candidates = await db.fetch_vault_candidates(from_date="2025-01-01")

    # Check if we got cached/fallback data
    if candidates and candidates[0].get("cached"):
        logger.info("Using cached vault candidates due to database unavailability")

    return candidates


async def example_zoho_integration():
    """Example of using Zoho API with circuit breaker"""
    zoho = ZohoAPIWithCircuitBreaker()
    await zoho.initialize()

    try:
        # Create contact with automatic queuing if Zoho is down
        result = await zoho.create_contact({
            "First_Name": "John",
            "Last_Name": "Doe",
            "Email": "john.doe@example.com"
        })

        # Check if request was queued
        if result.get("status") == "queued":
            logger.info(f"Contact creation queued: {result['request_id']}")
        else:
            logger.info(f"Contact created: {result}")

    finally:
        await zoho.cleanup()

    return result


async def example_rate_limiting():
    """Example of rate limiting with circuit breaker"""
    from well_shared.cache.redis_manager import get_cache_manager

    redis_manager = await get_cache_manager()
    rate_limiter = TeamsRateLimitWithCircuitBreaker(redis_manager)

    user_id = "user123"

    # Check if user can make request
    if await rate_limiter.check_rate_limit(user_id, limit=5, window=60):
        # Use the rate limit
        await rate_limiter.use_rate_limit(user_id)
        return {"status": "allowed", "message": "Request processed"}
    else:
        return {"status": "rate_limited", "message": "Too many requests"}


# Export integration classes
__all__ = [
    'RedisCacheManagerWithCircuitBreaker',
    'DatabaseConnectionWithCircuitBreaker',
    'ZohoAPIWithCircuitBreaker',
    'TeamsRateLimitWithCircuitBreaker',
    'example_redis_integration',
    'example_database_integration',
    'example_zoho_integration',
    'example_rate_limiting'
]