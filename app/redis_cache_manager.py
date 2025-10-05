"""
Azure Cache for Redis manager for optimizing GPT-5-mini token usage.
Implements prompt/response caching with intelligent key generation.
"""

import os
import json
import hashlib
import logging
import asyncio
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class RedisHealthStatus(Enum):
    """Redis connection health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking."""
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_retry_time: Optional[datetime] = None


@dataclass
class RedisMetrics:
    """Enhanced Redis metrics with failure tracking."""
    hits: int = 0
    misses: int = 0
    errors: int = 0
    connection_failures: int = 0
    timeout_failures: int = 0
    fallback_activations: int = 0
    savings: float = 0.0
    last_connection_attempt: Optional[datetime] = None
    last_successful_operation: Optional[datetime] = None
    health_status: RedisHealthStatus = RedisHealthStatus.UNKNOWN


class RedisCacheManager:
    """Manages Azure Cache for Redis connections and operations for GPT-5-mini caching."""
    
    def __init__(self, connection_string: str = None):
        """
        Initialize Redis cache manager.
        
        Args:
            connection_string: Azure Cache for Redis connection string
                              Format: "rediss://:password@hostname:port"
        """
        self.connection_string = connection_string or os.getenv("AZURE_REDIS_CONNECTION_STRING")
        self.client: Optional[Redis] = None
        self._connected = False
        
        # Cache configuration
        self.default_ttl = timedelta(hours=24)  # 24-hour TTL for email patterns
        self.batch_ttl = timedelta(hours=48)    # 48-hour TTL for batch processing
        self.pattern_ttl = timedelta(days=90)   # 90-day TTL for common patterns
        
        # Enhanced metrics tracking
        self.metrics = RedisMetrics()
        
        # Circuit breaker configuration
        self.circuit_breaker = CircuitBreakerState()
        self.max_failures = 5
        self.failure_timeout = timedelta(minutes=5)  # Wait 5 minutes before retry
        self.connection_timeout = 10  # seconds
        self.operation_timeout = 5    # seconds
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 0.1  # seconds
        self.max_delay = 2.0   # seconds
        
        # Fallback mode tracking
        self.fallback_mode = False
        self.fallback_reason = None
    
    async def cache_domain_info(self, domain: str, company_info: Dict[str, Any]) -> bool:
        """
        Cache company information for a domain.
        
        Args:
            domain: Email domain (e.g., "example.com")
            company_info: Company information to cache
            
        Returns:
            Success status
        """
        if not self._connected or not self.client:
            await self.connect()
            if not self._connected:
                return False
        
        try:
            key = f"domain::{domain.lower()}"
            value = json.dumps({
                "company_info": company_info,
                "cached_at": datetime.utcnow().isoformat()
            })
            
            # Cache for 7 days - domains are relatively stable
            await self.client.setex(
                key,
                timedelta(days=7),
                value
            )
            
            logger.info(f"Cached domain info for: {domain}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching domain info: {e}")
            return False
    
    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached company information for a domain.
        
        Args:
            domain: Email domain (e.g., "example.com")
            
        Returns:
            Cached company info or None
        """
        if not self._connected or not self.client:
            await self.connect()
            if not self._connected:
                return None
        
        try:
            key = f"domain::{domain.lower()}"
            cached = await self.client.get(key)
            
            if cached:
                data = json.loads(cached)
                logger.info(f"Domain cache hit for: {domain}")
                return data.get("company_info")
            
            logger.debug(f"Domain cache miss for: {domain}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving domain info: {e}")
            return None
    
    async def connect(self) -> bool:
        """Establish connection to Azure Cache for Redis with circuit breaker and fallback."""
        # Check if already connected
        if self._connected and self.client:
            return True
        
        # Check circuit breaker state
        if self._is_circuit_breaker_open():
            logger.debug(f"Circuit breaker is open, skipping connection attempt. Next retry: {self.circuit_breaker.next_retry_time}")
            self._activate_fallback_mode("Circuit breaker open")
            return False
        
        # Check if Redis is configured
        if not self.connection_string:
            logger.warning("No Redis connection string provided. Operating in fallback mode.")
            self._activate_fallback_mode("No connection string configured")
            return False
        
        self.metrics.last_connection_attempt = datetime.now()
        
        for attempt in range(self.max_retries + 1):
            try:
                # Create Redis client with timeouts
                client_config = {
                    "decode_responses": True,
                    "socket_connect_timeout": self.connection_timeout,
                    "socket_timeout": self.operation_timeout,
                    "retry_on_timeout": True,
                    "retry_on_error": [RedisError],
                    "max_connections": 10,
                    "health_check_interval": 30
                }
                
                if self.connection_string.startswith("rediss://"):
                    # Azure Cache for Redis uses SSL
                    self.client = redis.from_url(self.connection_string, **client_config)
                else:
                    # Local Redis or non-SSL connection
                    self.client = redis.from_url(self.connection_string, **client_config)
                
                # Test connection with timeout
                await asyncio.wait_for(self.client.ping(), timeout=self.operation_timeout)
                
                # Connection successful
                self._connected = True
                self.fallback_mode = False
                self.fallback_reason = None
                self._reset_circuit_breaker()
                self.metrics.health_status = RedisHealthStatus.HEALTHY
                self.metrics.last_successful_operation = datetime.now()
                
                logger.info(f"Successfully connected to Redis (attempt {attempt + 1}/{self.max_retries + 1})")
                return True
                
            except (ConnectionError, TimeoutError) as e:
                self.metrics.connection_failures += 1
                self.metrics.timeout_failures += 1 if isinstance(e, TimeoutError) else 0
                
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to connect to Redis after {self.max_retries + 1} attempts: {e}")
                    self._record_circuit_breaker_failure()
                    self._activate_fallback_mode(f"Connection failed: {str(e)}")
                    
            except Exception as e:
                self.metrics.errors += 1
                logger.error(f"Unexpected Redis connection error: {e}")
                self._record_circuit_breaker_failure()
                self._activate_fallback_mode(f"Unexpected error: {str(e)}")
                break
        
        # Cleanup on failure
        if self.client:
            try:
                await self.client.close()
            except:
                pass
            self.client = None
        
        self._connected = False
        self.metrics.health_status = RedisHealthStatus.UNHEALTHY
        return False
    
    async def disconnect(self):
        """Close Redis connection gracefully."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.warning(f"Error during Redis disconnect: {e}")
            finally:
                self.client = None
                self._connected = False
                self.metrics.health_status = RedisHealthStatus.UNKNOWN
    
    def generate_cache_key(self, 
                          email_content: str, 
                          extraction_type: str = "full") -> str:
        """
        Generate a deterministic cache key from email content.
        
        Args:
            email_content: The email body content
            extraction_type: Type of extraction (full, simple, pattern)
        
        Returns:
            A unique cache key based on email content hash
        """
        # Normalize email content for consistent hashing
        normalized = self._normalize_email(email_content)
        
        # Create hash
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        
        # Create namespaced key
        key = f"well:email:{extraction_type}:{content_hash}"
        
        return key
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open (preventing Redis operations)."""
        if not self.circuit_breaker.is_open:
            return False
        
        # Check if it's time to retry
        if (self.circuit_breaker.next_retry_time and 
            datetime.now() >= self.circuit_breaker.next_retry_time):
            logger.info("Circuit breaker retry window opened")
            self.circuit_breaker.is_open = False
            return False
        
        return True
    
    def _record_circuit_breaker_failure(self):
        """Record a failure for circuit breaker logic."""
        self.circuit_breaker.failure_count += 1
        self.circuit_breaker.last_failure_time = datetime.now()
        
        if self.circuit_breaker.failure_count >= self.max_failures:
            self.circuit_breaker.is_open = True
            self.circuit_breaker.next_retry_time = datetime.now() + self.failure_timeout
            logger.warning(f"Circuit breaker opened after {self.circuit_breaker.failure_count} failures. Next retry: {self.circuit_breaker.next_retry_time}")
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker after successful operation."""
        self.circuit_breaker.is_open = False
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.last_failure_time = None
        self.circuit_breaker.next_retry_time = None
    
    def _activate_fallback_mode(self, reason: str):
        """Activate fallback mode and record reason."""
        if not self.fallback_mode:
            self.fallback_mode = True
            self.fallback_reason = reason
            self.metrics.fallback_activations += 1
            logger.warning(f"Activated fallback mode: {reason}")
    
    async def _execute_with_fallback(self, operation_name: str, redis_operation, fallback_value=None):
        """Execute Redis operation with comprehensive error handling and fallback."""
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.debug(f"{operation_name}: Circuit breaker open, using fallback")
            self.metrics.fallback_activations += 1
            return fallback_value
        
        # Try to connect if not connected
        if not self._connected:
            if not await self.connect():
                logger.debug(f"{operation_name}: Connection failed, using fallback")
                return fallback_value
        
        try:
            # Execute operation with timeout
            result = await asyncio.wait_for(redis_operation(), timeout=self.operation_timeout)
            
            # Record successful operation
            self.metrics.last_successful_operation = datetime.now()
            if self.metrics.health_status != RedisHealthStatus.HEALTHY:
                self.metrics.health_status = RedisHealthStatus.HEALTHY
                logger.info(f"Redis health restored for {operation_name}")
            
            return result
            
        except (ConnectionError, TimeoutError) as e:
            self.metrics.connection_failures += 1
            self.metrics.timeout_failures += 1 if isinstance(e, TimeoutError) else 0
            self._record_circuit_breaker_failure()
            self._activate_fallback_mode(f"{operation_name} failed: {str(e)}")
            logger.warning(f"{operation_name} connection/timeout error: {e}, using fallback")
            
            # Mark as disconnected
            self._connected = False
            self.metrics.health_status = RedisHealthStatus.UNHEALTHY
            
        except Exception as e:
            self.metrics.errors += 1
            self._record_circuit_breaker_failure()
            logger.error(f"{operation_name} unexpected error: {e}, using fallback")
            self.metrics.health_status = RedisHealthStatus.DEGRADED
        
        return fallback_value
    
    def _normalize_email(self, content: str) -> str:
        """
        Normalize email content for consistent cache key generation.
        Removes variable elements like timestamps, preserves structure.
        """
        import re
        
        # Remove common variable elements
        normalized = content.lower().strip()
        
        # Remove timestamps (various formats)
        normalized = re.sub(r'\d{1,2}[:/]\d{1,2}[:/]\d{2,4}', '', normalized)
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '', normalized)
        normalized = re.sub(r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}', '', normalized)
        
        # Remove email addresses (but keep domain patterns)
        normalized = re.sub(r'[a-zA-Z0-9._%+-]+@', '@', normalized)
        
        # Remove phone numbers
        normalized = re.sub(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{3,5}[-\s\.]?[0-9]{3,5}', 'PHONE', normalized)
        
        # Remove excess whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    async def get_cached_extraction(self, 
                                   email_content: str,
                                   extraction_type: str = "full") -> Optional[Dict[str, Any]]:
        """
        Retrieve cached extraction result if available with fallback handling.
        
        Args:
            email_content: The email to check cache for
            extraction_type: Type of extraction
        
        Returns:
            Cached extraction result or None if not found/Redis unavailable
        """
        key = self.generate_cache_key(email_content, extraction_type)
        
        async def redis_get_operation():
            cached_data = await self.client.get(key)
            if cached_data:
                self.metrics.hits += 1
                # Calculate cost savings (cached: $0.025/1M vs new: $0.25/1M)
                tokens_saved = 500  # Average tokens per extraction
                cost_saved = (tokens_saved / 1_000_000) * (0.25 - 0.025)
                self.metrics.savings += cost_saved
                
                logger.info(f"Cache HIT for key: {key} (saved ${cost_saved:.6f})")
                return json.loads(cached_data)
            else:
                self.metrics.misses += 1
                logger.debug(f"Cache MISS for key: {key}")
                return None
        
        result = await self._execute_with_fallback(
            "get_cached_extraction", 
            redis_get_operation, 
            fallback_value=None
        )
        
        # Always count as miss if fallback was used
        if result is None and self.fallback_mode:
            self.metrics.misses += 1
        
        return result
    
    async def cache_extraction(self,
                              email_content: str,
                              extraction_result: Dict[str, Any],
                              extraction_type: str = "full",
                              ttl: Optional[timedelta] = None) -> bool:
        """
        Cache extraction result with appropriate TTL and fallback handling.
        
        Args:
            email_content: The original email content
            extraction_result: The extraction result to cache
            extraction_type: Type of extraction
            ttl: Time to live (defaults to 24 hours)
        
        Returns:
            True if successfully cached, False if Redis unavailable (graceful degradation)
        """
        key = self.generate_cache_key(email_content, extraction_type)
        ttl = ttl or self.default_ttl
        
        async def redis_set_operation():
            # Add metadata to cached result
            cache_data = {
                "result": extraction_result,
                "cached_at": asyncio.get_event_loop().time(),
                "extraction_type": extraction_type
            }
            
            # Store in Redis with TTL
            await self.client.setex(
                key,
                int(ttl.total_seconds()),
                json.dumps(cache_data)
            )
            
            logger.info(f"Cached extraction for key: {key} with TTL: {ttl}")
            return True
        
        result = await self._execute_with_fallback(
            "cache_extraction", 
            redis_set_operation, 
            fallback_value=False
        )
        
        return result if result is not None else False
    
    async def invalidate_cache(self, pattern: str = None) -> int:
        """
        Invalidate cache entries matching a pattern with fallback handling.
        
        Args:
            pattern: Redis pattern to match keys (e.g., "well:email:*")
                    If None, invalidates all email caches
        
        Returns:
            Number of keys deleted (0 if Redis unavailable)
        """
        async def redis_invalidate_operation():
            search_pattern = pattern or "well:email:*"
            
            # Find all matching keys
            keys = []
            async for key in self.client.scan_iter(match=search_pattern):
                keys.append(key)
            
            if keys:
                # Delete all matching keys
                deleted = await self.client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries matching pattern: {search_pattern}")
                return deleted
            
            return 0
        
        result = await self._execute_with_fallback(
            "invalidate_cache", 
            redis_invalidate_operation, 
            fallback_value=0
        )
        
        return result if result is not None else 0
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache performance metrics with fallback information.
        
        Returns:
            Dictionary with cache statistics, Redis health, and fallback status
        """
        total_requests = self.metrics.hits + self.metrics.misses
        hit_rate = (self.metrics.hits / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate uptime percentage
        uptime_pct = 0.0
        if total_requests > 0:
            failed_requests = self.metrics.connection_failures + self.metrics.timeout_failures
            uptime_pct = ((total_requests - failed_requests) / total_requests * 100)
        
        metrics = {
            # Core metrics
            "hits": self.metrics.hits,
            "misses": self.metrics.misses,
            "errors": self.metrics.errors,
            "savings": self.metrics.savings,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
            "estimated_monthly_savings": self.metrics.savings * 30,
            
            # Health and reliability metrics
            "health_status": self.metrics.health_status.value,
            "connection_failures": self.metrics.connection_failures,
            "timeout_failures": self.metrics.timeout_failures,
            "fallback_activations": self.metrics.fallback_activations,
            "uptime_percentage": f"{uptime_pct:.2f}%",
            "is_connected": self._connected,
            "fallback_mode": self.fallback_mode,
            "fallback_reason": self.fallback_reason,
            
            # Circuit breaker status
            "circuit_breaker_open": self.circuit_breaker.is_open,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "last_failure_time": self.circuit_breaker.last_failure_time.isoformat() if self.circuit_breaker.last_failure_time else None,
            "next_retry_time": self.circuit_breaker.next_retry_time.isoformat() if self.circuit_breaker.next_retry_time else None,
            
            # Timestamps
            "last_connection_attempt": self.metrics.last_connection_attempt.isoformat() if self.metrics.last_connection_attempt else None,
            "last_successful_operation": self.metrics.last_successful_operation.isoformat() if self.metrics.last_successful_operation else None
        }
        
        # Get Redis server info if connected (with fallback)
        if self._connected and self.client:
            async def redis_info_operation():
                info = await self.client.info()
                return {
                    "redis_memory_used": info.get("used_memory_human", "N/A"),
                    "redis_connected_clients": info.get("connected_clients", 0),
                    "redis_uptime_seconds": info.get("uptime_in_seconds", 0),
                    "redis_version": info.get("redis_version", "Unknown")
                }
            
            redis_info = await self._execute_with_fallback(
                "get_redis_info", 
                redis_info_operation, 
                fallback_value={
                    "redis_memory_used": "N/A (Disconnected)",
                    "redis_connected_clients": 0,
                    "redis_uptime_seconds": 0,
                    "redis_version": "N/A (Disconnected)"
                }
            )
            
            metrics.update(redis_info)
        else:
            metrics.update({
                "redis_memory_used": "N/A (Disconnected)",
                "redis_connected_clients": 0,
                "redis_uptime_seconds": 0,
                "redis_version": "N/A (Disconnected)"
            })
        
        return metrics
    
    def get_health_summary(self) -> str:
        """
        Get a simple health status summary for monitoring.

        Returns:
            Human-readable health status
        """
        if not self.connection_string:
            return "not_configured"
        elif self._is_circuit_breaker_open():
            return "circuit_breaker_open"
        elif self.fallback_mode:
            return "fallback_mode"
        elif self._connected:
            return "healthy"
        else:
            return "disconnected"

    async def get(self, key: str) -> Optional[str]:
        """
        Generic get method for retrieving cached values.

        Args:
            key: Cache key

        Returns:
            Cached value as string or None if not found
        """
        if not self._connected or not self.client:
            await self.connect()
            if not self._connected:
                return None

        try:
            value = await self.client.get(key)
            if value:
                self.metrics.hits += 1
                logger.debug(f"Cache hit for key: {key}")
            else:
                self.metrics.misses += 1
                logger.debug(f"Cache miss for key: {key}")
            return value
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            self.metrics.errors += 1
            return None

    async def set(self, key: str, value: str, ttl: Optional[timedelta] = None, expire: Optional[int] = None) -> bool:
        """
        Generic set method for caching values.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live as timedelta (preferred)
            expire: TTL in seconds (backward compatibility)

        Returns:
            Success status
        """
        if not self._connected or not self.client:
            await self.connect()
            if not self._connected:
                return False

        try:
            # Determine TTL
            if ttl:
                expire_seconds = int(ttl.total_seconds())
            elif expire:
                expire_seconds = expire
            else:
                expire_seconds = int(self.default_ttl.total_seconds())

            await self.client.setex(
                key,
                expire_seconds,
                value
            )
            logger.debug(f"Cached key: {key} with TTL: {expire_seconds}s")
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            self.metrics.errors += 1
            return False


# Singleton instance
_cache_manager: Optional[RedisCacheManager] = None


async def get_cache_manager() -> RedisCacheManager:
    """Get or create the singleton cache manager instance."""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = RedisCacheManager()
        
        # Attempt initial connection
        await _cache_manager.connect()
        
        logger.info("Redis Cache Manager initialized with fallback mechanisms")
    
    return _cache_manager


# Health check helper for FastAPI endpoints
async def get_redis_health_status() -> Dict[str, Any]:
    """Get Redis health status for API endpoints."""
    try:
        cache_manager = await get_cache_manager()
        return {
            "status": cache_manager.get_health_summary(),
            "timestamp": datetime.now().isoformat(),
            "connection_status": "connected" if cache_manager._connected else "disconnected",
            "fallback_mode": cache_manager.fallback_mode,
            "fallback_reason": cache_manager.fallback_reason,
            "circuit_breaker_open": cache_manager.circuit_breaker.is_open
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "connection_status": "unknown",
            "error": f"Failed to get Redis health status: {str(e)}"
        }