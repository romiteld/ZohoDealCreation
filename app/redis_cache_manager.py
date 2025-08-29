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
from datetime import timedelta
import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


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
        
        # Metrics tracking
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "savings": 0.0  # Cost savings in USD
        }
    
    async def connect(self) -> bool:
        """Establish connection to Azure Cache for Redis."""
        if self._connected and self.client:
            return True
        
        if not self.connection_string:
            logger.warning("No Redis connection string provided. Cache disabled.")
            return False
        
        try:
            # Parse connection string
            if self.connection_string.startswith("rediss://"):
                # Azure Cache for Redis uses SSL
                self.client = redis.from_url(
                    self.connection_string,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    retry_on_error=[RedisError],
                    max_connections=10
                )
            else:
                # Local Redis or non-SSL connection
                self.client = redis.from_url(
                    self.connection_string,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # Test connection
            await self.client.ping()
            self._connected = True
            logger.info("Successfully connected to Azure Cache for Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
            self._connected = False
            return False
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("Disconnected from Redis")
    
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
        Retrieve cached extraction result if available.
        
        Args:
            email_content: The email to check cache for
            extraction_type: Type of extraction
        
        Returns:
            Cached extraction result or None if not found
        """
        if not self._connected:
            if not await self.connect():
                return None
        
        try:
            key = self.generate_cache_key(email_content, extraction_type)
            
            # Get from cache
            cached_data = await self.client.get(key)
            
            if cached_data:
                self.metrics["hits"] += 1
                # Calculate cost savings (cached: $0.025/1M vs new: $0.25/1M)
                # Assume average 500 tokens per extraction
                tokens_saved = 500
                cost_saved = (tokens_saved / 1_000_000) * (0.25 - 0.025)
                self.metrics["savings"] += cost_saved
                
                logger.info(f"Cache HIT for key: {key} (saved ${cost_saved:.6f})")
                
                # Parse and return cached data
                return json.loads(cached_data)
            else:
                self.metrics["misses"] += 1
                logger.debug(f"Cache MISS for key: {key}")
                return None
                
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Cache retrieval error: {e}")
            return None
    
    async def cache_extraction(self,
                              email_content: str,
                              extraction_result: Dict[str, Any],
                              extraction_type: str = "full",
                              ttl: Optional[timedelta] = None) -> bool:
        """
        Cache extraction result with appropriate TTL.
        
        Args:
            email_content: The original email content
            extraction_result: The extraction result to cache
            extraction_type: Type of extraction
            ttl: Time to live (defaults to 24 hours)
        
        Returns:
            True if successfully cached, False otherwise
        """
        if not self._connected:
            if not await self.connect():
                return False
        
        try:
            key = self.generate_cache_key(email_content, extraction_type)
            ttl = ttl or self.default_ttl
            
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
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Cache storage error: {e}")
            return False
    
    async def get_pattern_cache(self, pattern_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached pattern extraction template.
        Used for common email patterns (e.g., specific recruiter formats).
        
        Args:
            pattern_key: The pattern identifier
        
        Returns:
            Cached pattern template or None
        """
        if not self._connected:
            if not await self.connect():
                return None
        
        try:
            key = f"well:pattern:{pattern_key}"
            cached_pattern = await self.client.get(key)
            
            if cached_pattern:
                logger.info(f"Pattern cache HIT: {pattern_key}")
                return json.loads(cached_pattern)
            
            return None
            
        except Exception as e:
            logger.error(f"Pattern cache error: {e}")
            return None
    
    async def cache_pattern(self,
                           pattern_key: str,
                           pattern_data: Dict[str, Any],
                           ttl: Optional[timedelta] = None) -> bool:
        """
        Cache a common email pattern for reuse.
        
        Args:
            pattern_key: The pattern identifier
            pattern_data: The pattern template data
            ttl: Time to live (defaults to 90 days)
        
        Returns:
            True if successfully cached
        """
        if not self._connected:
            if not await self.connect():
                return False
        
        try:
            key = f"well:pattern:{pattern_key}"
            ttl = ttl or self.pattern_ttl
            
            await self.client.setex(
                key,
                int(ttl.total_seconds()),
                json.dumps(pattern_data)
            )
            
            logger.info(f"Cached pattern: {pattern_key}")
            return True
            
        except Exception as e:
            logger.error(f"Pattern cache storage error: {e}")
            return False
    
    async def batch_get(self, email_contents: list) -> Dict[str, Optional[Dict]]:
        """
        Batch retrieve multiple cached extractions.
        Optimized for processing multiple emails at once.
        
        Args:
            email_contents: List of email contents to check
        
        Returns:
            Dictionary mapping email content to cached results
        """
        if not self._connected:
            if not await self.connect():
                return {content: None for content in email_contents}
        
        try:
            # Generate all keys
            keys = [self.generate_cache_key(content, "full") for content in email_contents]
            
            # Batch get from Redis
            results = await self.client.mget(keys)
            
            # Map results back to email contents
            cached_results = {}
            for content, key, result in zip(email_contents, keys, results):
                if result:
                    self.metrics["hits"] += 1
                    cached_results[content] = json.loads(result)
                else:
                    self.metrics["misses"] += 1
                    cached_results[content] = None
            
            # Calculate batch savings
            hits = sum(1 for r in cached_results.values() if r is not None)
            if hits > 0:
                tokens_saved = hits * 500  # Average tokens per extraction
                cost_saved = (tokens_saved / 1_000_000) * (0.25 - 0.025)
                self.metrics["savings"] += cost_saved
                logger.info(f"Batch cache: {hits}/{len(email_contents)} hits, saved ${cost_saved:.6f}")
            
            return cached_results
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Batch cache error: {e}")
            return {content: None for content in email_contents}
    
    async def batch_set(self, 
                       cache_items: Dict[str, Dict[str, Any]],
                       ttl: Optional[timedelta] = None) -> int:
        """
        Batch cache multiple extraction results.
        
        Args:
            cache_items: Dictionary of email_content -> extraction_result
            ttl: Time to live for all items
        
        Returns:
            Number of successfully cached items
        """
        if not self._connected:
            if not await self.connect():
                return 0
        
        ttl = ttl or self.batch_ttl
        success_count = 0
        
        try:
            # Use pipeline for atomic batch operation
            pipe = self.client.pipeline()
            
            for email_content, extraction_result in cache_items.items():
                key = self.generate_cache_key(email_content, "full")
                cache_data = {
                    "result": extraction_result,
                    "cached_at": asyncio.get_event_loop().time(),
                    "extraction_type": "full"
                }
                pipe.setex(key, int(ttl.total_seconds()), json.dumps(cache_data))
            
            # Execute pipeline
            results = await pipe.execute()
            success_count = sum(1 for r in results if r)
            
            logger.info(f"Batch cached {success_count}/{len(cache_items)} items")
            return success_count
            
        except Exception as e:
            logger.error(f"Batch cache storage error: {e}")
            return success_count
    
    async def invalidate_cache(self, pattern: str = None) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Redis pattern to match keys (e.g., "well:email:*")
                    If None, invalidates all email caches
        
        Returns:
            Number of keys deleted
        """
        if not self._connected:
            if not await self.connect():
                return 0
        
        try:
            pattern = pattern or "well:email:*"
            
            # Find all matching keys
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                # Delete all matching keys
                deleted = await self.client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries matching pattern: {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.metrics["hits"] + self.metrics["misses"]
        hit_rate = (self.metrics["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        metrics = {
            **self.metrics,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
            "estimated_monthly_savings": self.metrics["savings"] * 30  # Rough estimate
        }
        
        # Get Redis server info if connected
        if self._connected and self.client:
            try:
                info = await self.client.info()
                metrics["redis_memory_used"] = info.get("used_memory_human", "N/A")
                metrics["redis_connected_clients"] = info.get("connected_clients", 0)
            except:
                pass
        
        return metrics
    
    async def warmup_cache(self, common_patterns: list) -> int:
        """
        Pre-warm cache with common email patterns.
        
        Args:
            common_patterns: List of common email pattern dictionaries
        
        Returns:
            Number of patterns cached
        """
        if not self._connected:
            if not await self.connect():
                return 0
        
        cached_count = 0
        
        for pattern in common_patterns:
            pattern_key = pattern.get("key")
            pattern_data = pattern.get("data")
            
            if pattern_key and pattern_data:
                success = await self.cache_pattern(pattern_key, pattern_data)
                if success:
                    cached_count += 1
        
        logger.info(f"Cache warmup completed: {cached_count} patterns cached")
        return cached_count


# Singleton instance
_cache_manager: Optional[RedisCacheManager] = None


async def get_cache_manager() -> RedisCacheManager:
    """Get or create the singleton cache manager instance."""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = RedisCacheManager()
        await _cache_manager.connect()
    
    return _cache_manager