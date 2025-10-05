"""
Apollo.io Search Cache Management
Handles caching, cleanup, and analytics for Apollo people search results
"""

import os
import json
import logging
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
import asyncpg

logger = logging.getLogger(__name__)

class ApolloCacheManager:
    """Manages Apollo.io search result caching in PostgreSQL and Redis"""

    def __init__(self, postgres_conn: str, redis_client=None):
        self.postgres_conn = postgres_conn
        self.redis_client = redis_client
        self.pool = None

    async def init_pool(self):
        """Initialize PostgreSQL connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.postgres_conn,
                min_size=2,
                max_size=10
            )

    async def ensure_cache_table(self):
        """Ensure the Apollo cache table exists with proper indexes"""
        await self.init_pool()

        async with self.pool.acquire() as conn:
            # Create table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS apollo_search_cache (
                    id SERIAL PRIMARY KEY,
                    search_type VARCHAR(50) NOT NULL,
                    search_params JSONB NOT NULL,
                    result_data JSONB NOT NULL,
                    completeness_score FLOAT,
                    has_linkedin BOOLEAN,
                    has_phone BOOLEAN,
                    has_email BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    hit_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (search_type, search_params)
                )
            """)

            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_apollo_cache_expires ON apollo_search_cache (expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_apollo_cache_search_params ON apollo_search_cache USING GIN (search_params)",
                "CREATE INDEX IF NOT EXISTS idx_apollo_cache_completeness ON apollo_search_cache (completeness_score)",
                "CREATE INDEX IF NOT EXISTS idx_apollo_cache_created ON apollo_search_cache (created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_apollo_cache_hit_count ON apollo_search_cache (hit_count DESC)"
            ]

            for index_sql in indexes:
                await conn.execute(index_sql)

            logger.info("Apollo cache table and indexes ensured")

    async def store_search_result(
        self,
        search_type: str,
        search_params: Dict[str, Any],
        result_data: Dict[str, Any],
        ttl_hours: int = 168  # 7 days default
    ) -> bool:
        """Store a search result in both Redis and PostgreSQL"""
        try:
            # Calculate data quality metrics
            person_data = result_data.get('data', {}).get('person', {})
            completeness_score = result_data.get('data_quality', {}).get('completeness_score', 0)
            has_linkedin = bool(person_data.get('linkedin_url'))
            has_phone = bool(person_data.get('primary_phone') or person_data.get('phone_numbers'))
            has_email = bool(person_data.get('email'))

            # Store in PostgreSQL
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO apollo_search_cache (
                        search_type, search_params, result_data,
                        completeness_score, has_linkedin, has_phone, has_email,
                        created_at, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (search_type, search_params) DO UPDATE
                    SET result_data = $3,
                        completeness_score = $4,
                        has_linkedin = $5,
                        has_phone = $6,
                        has_email = $7,
                        updated_at = CURRENT_TIMESTAMP,
                        expires_at = $9,
                        hit_count = apollo_search_cache.hit_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                """,
                search_type,
                json.dumps(search_params),
                json.dumps(result_data),
                completeness_score,
                has_linkedin,
                has_phone,
                has_email,
                datetime.utcnow(),
                datetime.utcnow() + timedelta(hours=ttl_hours)
                )

            # Store in Redis if available
            if self.redis_client:
                cache_key = self.generate_cache_key(search_type, search_params)
                await self.redis_client.setex(
                    cache_key,
                    ttl_hours * 3600,
                    json.dumps(result_data)
                )

            logger.info(f"Cached Apollo {search_type} search result for {ttl_hours} hours")
            return True

        except Exception as e:
            logger.error(f"Failed to cache Apollo result: {str(e)}")
            return False

    async def get_cached_result(
        self,
        search_type: str,
        search_params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a cached search result"""
        try:
            # Try Redis first (faster)
            if self.redis_client:
                cache_key = self.generate_cache_key(search_type, search_params)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.info(f"Redis cache hit for Apollo {search_type} search")
                    return json.loads(cached)

            # Fallback to PostgreSQL
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow("""
                    UPDATE apollo_search_cache
                    SET hit_count = hit_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE search_type = $1
                    AND search_params = $2
                    AND expires_at > CURRENT_TIMESTAMP
                    RETURNING result_data
                """, search_type, json.dumps(search_params))

                if result:
                    logger.info(f"PostgreSQL cache hit for Apollo {search_type} search")
                    return json.loads(result['result_data'])

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve cached result: {str(e)}")
            return None

    def generate_cache_key(self, search_type: str, search_params: Dict[str, Any]) -> str:
        """Generate a consistent cache key from search parameters"""
        # Sort params for consistency
        sorted_params = json.dumps(search_params, sort_keys=True)
        key_hash = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"apollo:{search_type}:{key_hash}"

    async def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM apollo_search_cache
                    WHERE expires_at < CURRENT_TIMESTAMP
                """)

                deleted_count = int(result.split()[-1]) if result else 0
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired Apollo cache entries")

                return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {str(e)}")
            return 0

    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache usage statistics"""
        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_entries,
                        COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_entries,
                        COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries,
                        AVG(completeness_score) as avg_completeness,
                        SUM(hit_count) as total_hits,
                        AVG(hit_count) as avg_hits,
                        COUNT(CASE WHEN has_linkedin THEN 1 END) as with_linkedin,
                        COUNT(CASE WHEN has_phone THEN 1 END) as with_phone,
                        COUNT(CASE WHEN has_email THEN 1 END) as with_email,
                        MIN(created_at) as oldest_entry,
                        MAX(created_at) as newest_entry,
                        MAX(last_accessed) as last_accessed
                    FROM apollo_search_cache
                """)

                # Get top searched items
                top_searches = await conn.fetch("""
                    SELECT
                        search_type,
                        search_params,
                        hit_count,
                        completeness_score,
                        last_accessed
                    FROM apollo_search_cache
                    WHERE expires_at > CURRENT_TIMESTAMP
                    ORDER BY hit_count DESC
                    LIMIT 10
                """)

                # Get recent high-quality results
                quality_results = await conn.fetch("""
                    SELECT
                        search_type,
                        search_params,
                        completeness_score,
                        has_linkedin,
                        has_phone,
                        has_email
                    FROM apollo_search_cache
                    WHERE completeness_score > 70
                    AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                    LIMIT 10
                """)

                return {
                    "summary": {
                        "total_entries": stats['total_entries'],
                        "active_entries": stats['active_entries'],
                        "expired_entries": stats['expired_entries'],
                        "average_completeness": round(float(stats['avg_completeness'] or 0), 2),
                        "total_cache_hits": stats['total_hits'],
                        "average_hits_per_entry": round(float(stats['avg_hits'] or 0), 2),
                        "with_linkedin": stats['with_linkedin'],
                        "with_phone": stats['with_phone'],
                        "with_email": stats['with_email'],
                        "oldest_entry": stats['oldest_entry'].isoformat() if stats['oldest_entry'] else None,
                        "newest_entry": stats['newest_entry'].isoformat() if stats['newest_entry'] else None,
                        "last_accessed": stats['last_accessed'].isoformat() if stats['last_accessed'] else None
                    },
                    "top_searches": [
                        {
                            "search_type": row['search_type'],
                            "params": json.loads(row['search_params']),
                            "hits": row['hit_count'],
                            "completeness": round(float(row['completeness_score'] or 0), 2),
                            "last_accessed": row['last_accessed'].isoformat() if row['last_accessed'] else None
                        }
                        for row in top_searches
                    ],
                    "high_quality_results": [
                        {
                            "search_type": row['search_type'],
                            "params": json.loads(row['search_params']),
                            "completeness": round(float(row['completeness_score'] or 0), 2),
                            "has_linkedin": row['has_linkedin'],
                            "has_phone": row['has_phone'],
                            "has_email": row['has_email']
                        }
                        for row in quality_results
                    ]
                }

        except Exception as e:
            logger.error(f"Failed to get cache statistics: {str(e)}")
            return {"error": str(e)}

    async def warm_cache_from_recent_searches(self, days: int = 7) -> int:
        """Pre-warm cache by re-running recent popular searches"""
        try:
            async with self.pool.acquire() as conn:
                # Get recent popular searches
                recent_searches = await conn.fetch("""
                    SELECT DISTINCT
                        search_type,
                        search_params
                    FROM apollo_search_cache
                    WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    AND hit_count > 2
                    ORDER BY hit_count DESC
                    LIMIT 50
                """, days)

                warmed_count = 0
                for row in recent_searches:
                    # Check if still cached
                    cached = await self.get_cached_result(
                        row['search_type'],
                        json.loads(row['search_params'])
                    )
                    if not cached:
                        warmed_count += 1
                        # In production, you would trigger a new search here

                logger.info(f"Warmed {warmed_count} cache entries from recent searches")
                return warmed_count

        except Exception as e:
            logger.error(f"Failed to warm cache: {str(e)}")
            return 0

    async def export_high_value_cache(self, min_completeness: float = 80) -> List[Dict[str, Any]]:
        """Export high-value cached results for backup or analysis"""
        try:
            async with self.pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        search_type,
                        search_params,
                        result_data,
                        completeness_score,
                        has_linkedin,
                        has_phone,
                        has_email,
                        hit_count
                    FROM apollo_search_cache
                    WHERE completeness_score >= $1
                    AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY completeness_score DESC, hit_count DESC
                """, min_completeness)

                return [
                    {
                        "search_type": row['search_type'],
                        "params": json.loads(row['search_params']),
                        "data": json.loads(row['result_data']),
                        "quality": {
                            "completeness": float(row['completeness_score']),
                            "has_linkedin": row['has_linkedin'],
                            "has_phone": row['has_phone'],
                            "has_email": row['has_email']
                        },
                        "usage": {
                            "hit_count": row['hit_count']
                        }
                    }
                    for row in results
                ]

        except Exception as e:
            logger.error(f"Failed to export cache: {str(e)}")
            return []