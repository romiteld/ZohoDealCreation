"""
Database repository for zoho_leads table queries.

This module provides a clean data access layer for querying synced Zoho leads
from PostgreSQL, with Redis caching for performance optimization.

Author: Teams Bot AI Enhancement
Date: 2025-10-17
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import asyncpg
from pydantic import BaseModel, Field
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class VaultCandidate(BaseModel):
    """Typed model for vault candidate with all essential fields."""

    id: str
    zoho_id: str
    full_name: str
    candidate_locator: Optional[str] = None
    employer: Optional[str] = None
    current_location: Optional[str] = None
    designation: Optional[str] = None
    book_size_aum: Optional[str] = None
    production_l12mo: Optional[str] = None
    desired_comp: Optional[str] = None
    when_available: Optional[str] = None
    transferrable_book_of_business: Optional[str] = None
    licenses_and_exams: Optional[str] = None
    professional_designations: Optional[str] = None
    specialty_area_expertise: Optional[str] = None
    is_mobile: Optional[bool] = None
    remote: Optional[bool] = None
    open_to_hybrid: Optional[bool] = None
    in_office: Optional[bool] = None
    owner_email: Optional[str] = None
    created_time: datetime
    modified_time: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ZohoLeadsRepository:
    """
    Repository for zoho_leads table queries with Redis caching.

    Features:
    - Async PostgreSQL queries via asyncpg
    - Redis caching with 5-minute TTL
    - Cache bypass logging for ops monitoring
    - Composable filters for flexible queries
    - Centralized JSONB parsing
    """

    def __init__(self, db: asyncpg.Connection, redis_client: Optional[redis.Redis] = None):
        """
        Initialize repository with database connection and optional Redis cache.

        Args:
            db: Active asyncpg connection
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.redis = redis_client
        self.cache_ttl = 300  # 5 minutes (balance freshness vs performance)

    async def get_vault_candidates(
        self,
        limit: int = 500,
        candidate_locator: Optional[str] = None,
        location: Optional[str] = None,
        min_production: Optional[float] = None,
        after_date: Optional[datetime] = None,
        use_cache: bool = True
    ) -> List[VaultCandidate]:
        """
        Query vault candidates with composable filters and Redis caching.

        Args:
            limit: Maximum number of results (default: 500)
            candidate_locator: Filter by specific candidate locator
            location: Filter by location (fuzzy match on Current_Location)
            min_production: Minimum production value (filters Production_L12Mo)
            after_date: Filter candidates modified after this date
            use_cache: Enable Redis caching (default: True)

        Returns:
            List of VaultCandidate models

        Performance:
        - Cached queries: <100ms
        - Uncached queries: ~500-1000ms (depending on filters)
        """
        start_time = datetime.now()

        # Build cache key from filters
        cache_key = self._build_cache_key("vault_candidates", {
            "limit": limit,
            "candidate_locator": candidate_locator,
            "location": location,
            "min_production": min_production,
            "after_date": after_date.isoformat() if after_date else None
        })

        # Try cache first
        if use_cache and self.redis:
            try:
                cached_str = await self.redis.get(cache_key)
                if cached_str:
                    cached = json.loads(cached_str)
                    cache_time = (datetime.now() - start_time).total_seconds() * 1000
                    logger.info(
                        f"✅ Cache HIT for vault candidates query ({len(cached)} results, {cache_time:.1f}ms)"
                    )
                    return [VaultCandidate(**c) for c in cached]
            except Exception as e:
                logger.warning(f"Cache read failed: {str(e)}")

        # Cache miss - query database
        logger.info(f"❌ Cache MISS for vault candidates query - querying database")

        # Build dynamic WHERE clause
        where_clauses = ["is_vault_candidate = true"]
        params = []
        param_idx = 1

        if candidate_locator:
            where_clauses.append(f"data_payload->>'Candidate_Locator' = ${param_idx}")
            params.append(candidate_locator)
            param_idx += 1

        if location:
            where_clauses.append(f"data_payload->>'Current_Location' ILIKE ${param_idx}")
            params.append(f"%{location}%")
            param_idx += 1

        if min_production:
            # Handle production as text, convert to float for comparison
            where_clauses.append(
                f"(data_payload->>'Production_L12Mo')::FLOAT >= ${param_idx}"
            )
            params.append(min_production)
            param_idx += 1

        if after_date:
            where_clauses.append(f"modified_time > ${param_idx}")
            params.append(after_date)
            param_idx += 1

        where_sql = " AND ".join(where_clauses)

        # Execute query
        query = f"""
            SELECT
                id,
                zoho_id,
                owner_email,
                created_time,
                modified_time,
                data_payload
            FROM zoho_leads
            WHERE {where_sql}
            ORDER BY modified_time DESC
            LIMIT ${param_idx}
        """
        params.append(limit)

        try:
            rows = await self.db.fetch(query, *params)
            candidates = [self._parse_candidate(row) for row in rows]

            # Cache results
            if use_cache and self.redis and candidates:
                try:
                    await self.redis.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps([c.dict() for c in candidates])
                    )
                except Exception as e:
                    logger.warning(f"Cache write failed: {str(e)}")

            query_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(
                f"✅ Database query complete ({len(candidates)} results, {query_time:.1f}ms)"
            )

            return candidates

        except Exception as e:
            logger.error(f"Failed to query vault candidates: {str(e)}", exc_info=True)
            raise

    async def search_candidates(
        self,
        query: str,
        limit: int = 100,
        vault_only: bool = False,
        use_cache: bool = True
    ) -> List[VaultCandidate]:
        """
        Full-text search on JSONB fields.

        Searches across:
        - Full_Name
        - Employer
        - Current_Location
        - Designation
        - Specialty_Area_Expertise

        Args:
            query: Search query string
            limit: Maximum results
            vault_only: Only search vault candidates (default: False)
            use_cache: Enable Redis caching

        Returns:
            List of matching VaultCandidate models
        """
        start_time = datetime.now()

        # Build cache key
        cache_key = self._build_cache_key("search", {
            "query": query,
            "limit": limit,
            "vault_only": vault_only
        })

        # Try cache
        if use_cache and self.redis:
            try:
                cached_str = await self.redis.get(cache_key)
                if cached_str:
                    cached = json.loads(cached_str)
                    cache_time = (datetime.now() - start_time).total_seconds() * 1000
                    logger.info(f"✅ Cache HIT for search '{query}' ({cache_time:.1f}ms)")
                    return [VaultCandidate(**c) for c in cached]
            except Exception as e:
                logger.warning(f"Cache read failed: {str(e)}")

        logger.info(f"❌ Cache MISS for search '{query}' - querying database")

        # Build WHERE clause
        where_clauses = []
        if vault_only:
            where_clauses.append("is_vault_candidate = true")

        # Full-text search across multiple fields
        search_pattern = f"%{query}%"
        where_clauses.append("""(
            data_payload->>'Full_Name' ILIKE $1
            OR data_payload->>'Employer' ILIKE $1
            OR data_payload->>'Current_Location' ILIKE $1
            OR data_payload->>'Designation' ILIKE $1
            OR data_payload->>'Specialty_Area_Expertise' ILIKE $1
        )""")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                id,
                zoho_id,
                owner_email,
                created_time,
                modified_time,
                data_payload
            FROM zoho_leads
            WHERE {where_sql}
            ORDER BY modified_time DESC
            LIMIT $2
        """

        try:
            rows = await self.db.fetch(sql, search_pattern, limit)
            candidates = [self._parse_candidate(row) for row in rows]

            # Cache results
            if use_cache and self.redis and candidates:
                try:
                    await self.redis.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps([c.dict() for c in candidates])
                    )
                except Exception as e:
                    logger.warning(f"Cache write failed: {str(e)}")

            query_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"✅ Search complete ({len(candidates)} results, {query_time:.1f}ms)")

            return candidates

        except Exception as e:
            logger.error(f"Search failed for '{query}': {str(e)}", exc_info=True)
            raise

    def _parse_candidate(self, row: asyncpg.Record) -> VaultCandidate:
        """
        Centralized JSONB serializer - single source of truth for data_payload → model conversion.

        Args:
            row: Database row with data_payload JSONB column

        Returns:
            VaultCandidate model
        """
        payload = row['data_payload']

        return VaultCandidate(
            id=str(row['id']),
            zoho_id=row['zoho_id'],
            full_name=payload.get('Full_Name', 'Unknown'),
            candidate_locator=payload.get('Candidate_Locator'),
            employer=payload.get('Employer'),
            current_location=payload.get('Current_Location'),
            designation=payload.get('Designation'),
            book_size_aum=payload.get('Book_Size_AUM'),
            production_l12mo=payload.get('Production_L12Mo'),
            desired_comp=payload.get('Desired_Comp'),
            when_available=payload.get('When_Available'),
            transferrable_book_of_business=payload.get('Transferrable_Book_of_Business'),
            licenses_and_exams=payload.get('Licenses_and_Exams'),
            professional_designations=payload.get('Professional_Designations'),
            specialty_area_expertise=payload.get('Specialty_Area_Expertise'),
            is_mobile=payload.get('Is_Mobile'),
            remote=payload.get('Remote'),
            open_to_hybrid=payload.get('Open_to_Hybrid'),
            in_office=payload.get('In_Office'),
            owner_email=row.get('owner_email'),
            created_time=row['created_time'],
            modified_time=row['modified_time']
        )

    def _build_cache_key(self, operation: str, filters: Dict[str, Any]) -> str:
        """
        Build deterministic cache key from operation and filters.

        Args:
            operation: Operation name (e.g., 'vault_candidates', 'search')
            filters: Filter dictionary

        Returns:
            Redis cache key (e.g., 'vault:query:abc123def')
        """
        # Sort filters for deterministic hashing
        filter_json = json.dumps(filters, sort_keys=True, default=str)
        filter_hash = hashlib.md5(filter_json.encode()).hexdigest()[:12]

        return f"vault:query:{operation}:{filter_hash}"

    async def invalidate_cache(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries matching pattern.

        Args:
            pattern: Redis key pattern (default: 'vault:query:*')

        Usage:
            # Invalidate all vault queries
            await repo.invalidate_cache()

            # Invalidate specific operation
            await repo.invalidate_cache('vault:query:search:*')
        """
        if not self.redis:
            return

        pattern = pattern or "vault:query:*"

        try:
            # Use SCAN to find matching keys
            cursor = '0'
            deleted = 0
            while cursor != 0:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted += await self.redis.delete(*keys)

            logger.info(f"Invalidated {deleted} cache entries matching '{pattern}'")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {str(e)}")
