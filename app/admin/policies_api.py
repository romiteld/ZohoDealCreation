"""
FastAPI endpoints for policy management and seeding
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from datetime import datetime

from .seed_policies_v2 import PolicySeeder

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/admin/policies", tags=["Policy Management"])


class PolicySeedRequest(BaseModel):
    """Request model for policy seeding."""
    clear_existing: bool = Field(False, description="Clear existing Redis policies before seeding")
    seed_employers: bool = Field(True, description="Seed employer normalization policies")
    seed_cities: bool = Field(True, description="Seed city context policies")
    seed_subjects: bool = Field(True, description="Seed subject line bandit priors")
    seed_selectors: bool = Field(True, description="Seed selector C³/TTL priors")


class PolicySeedResponse(BaseModel):
    """Response model for policy seeding."""
    success: bool
    employers: int = Field(0, description="Number of employer policies seeded")
    cities: int = Field(0, description="Number of city policies seeded")
    subjects: int = Field(0, description="Number of subject variants seeded")
    selectors: int = Field(0, description="Number of selector priors seeded")
    message: str = Field("", description="Status message")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PolicyReloadResponse(BaseModel):
    """Response model for policy reload."""
    success: bool
    employers: int = Field(0, description="Number of employer policies reloaded")
    cities: int = Field(0, description="Number of city policies reloaded")
    subjects: int = Field(0, description="Number of subject variants reloaded")
    selectors: int = Field(0, description="Number of selector priors reloaded")
    message: str = Field("", description="Status message")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PolicyQueryRequest(BaseModel):
    """Request model for policy queries."""
    policy_type: str = Field(..., description="Type of policy: employer, city, subject, or selector")
    key: str = Field(..., description="Key to query (e.g., company name, city name, variant ID)")


class PolicyQueryResponse(BaseModel):
    """Response model for policy queries."""
    found: bool
    policy_type: str
    key: str
    value: Optional[Dict[str, Any]] = None
    source: str = Field("", description="Data source: redis, database, or not_found")


def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """Verify API key for admin endpoints."""
    expected_key = os.getenv("API_KEY", "")
    admin_key = os.getenv("ADMIN_API_KEY", expected_key)  # Allow separate admin key
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    if x_api_key not in [expected_key, admin_key]:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return True


@router.post("/seed", response_model=PolicySeedResponse)
async def seed_policies(
    request: PolicySeedRequest,
    authorized: bool = Depends(verify_api_key)
) -> PolicySeedResponse:
    """
    Seed policy data to database and Redis.
    
    This endpoint generates and stores critical policy data including:
    - Employer normalization (National vs Independent firms)
    - City to metro area mappings
    - Subject line bandit priors
    - Selector C³/TTL parameters
    """
    seeder = PolicySeeder()
    
    try:
        await seeder.initialize()
        
        # Clear existing if requested
        if request.clear_existing:
            await seeder.clear_redis_policies()
        
        results = {
            'employers': 0,
            'cities': 0,
            'subjects': 0,
            'selectors': 0
        }
        
        # Seed requested policy types
        if request.seed_employers:
            results['employers'] = await seeder.seed_employer_policies()
            
        if request.seed_cities:
            results['cities'] = await seeder.seed_city_policies()
            
        if request.seed_subjects:
            results['subjects'] = await seeder.seed_subject_priors()
            
        if request.seed_selectors:
            results['selectors'] = await seeder.seed_selector_priors()
        
        await seeder.close()
        
        return PolicySeedResponse(
            success=True,
            **results,
            message=f"Successfully seeded {sum(results.values())} policies"
        )
        
    except Exception as e:
        logger.error(f"Policy seeding failed: {e}")
        await seeder.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload", response_model=PolicyReloadResponse)
async def reload_policies(
    authorized: bool = Depends(verify_api_key)
) -> PolicyReloadResponse:
    """
    Reload all policies from database to Redis.
    
    This endpoint:
    1. Clears existing Redis policy keys
    2. Loads all policies from PostgreSQL
    3. Pushes them to Redis with no TTL
    """
    seeder = PolicySeeder()
    
    try:
        await seeder.initialize()
        
        # Reload from database
        results = await seeder.reload_from_database()
        
        await seeder.close()
        
        return PolicyReloadResponse(
            success=True,
            **results,
            message=f"Successfully reloaded {sum(results.values())} policies from database"
        )
        
    except Exception as e:
        logger.error(f"Policy reload failed: {e}")
        await seeder.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_policies(
    authorized: bool = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Clear all policy keys from Redis.
    
    WARNING: This removes all cached policies. Use reload endpoint to restore.
    """
    seeder = PolicySeeder()
    
    try:
        await seeder.initialize()
        
        count = await seeder.clear_redis_policies()
        
        await seeder.close()
        
        return {
            "success": True,
            "cleared_keys": count,
            "message": f"Cleared {count} policy keys from Redis",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Policy clear failed: {e}")
        await seeder.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=PolicyQueryResponse)
async def query_policy(
    request: PolicyQueryRequest,
    authorized: bool = Depends(verify_api_key)
) -> PolicyQueryResponse:
    """
    Query a specific policy value.
    
    Checks Redis first for fast access, falls back to database if not cached.
    """
    seeder = PolicySeeder()
    
    try:
        await seeder.initialize()
        
        policy_type = request.policy_type.lower()
        key = request.key.lower()
        value = None
        source = "not_found"
        
        # Try Redis first
        if seeder.redis_client and seeder.redis_client.is_connected():
            redis_key = None
            
            if policy_type == "employer":
                redis_key = f"policy:employers:{key}"
            elif policy_type == "city":
                redis_key = f"geo:metro:{key}"
            elif policy_type == "subject":
                redis_key = f"bandit:subjects:global:{key}"
            elif policy_type == "selector":
                # Check both C³ and TTL keys
                tau_key = f"c3:tau:{key}"
                ttl_key = f"ttl:{key}"
                
                tau_value = await seeder.redis_client.client.get(tau_key)
                ttl_value = await seeder.redis_client.client.get(ttl_key)
                
                if tau_value or ttl_value:
                    value = {}
                    if tau_value:
                        value['tau_delta'] = float(tau_value)
                    if ttl_value:
                        ttl_data = json.loads(ttl_value)
                        value.update(ttl_data)
                    source = "redis"
                    
            if redis_key and not value:
                redis_value = await seeder.redis_client.client.get(redis_key)
                if redis_value:
                    try:
                        value = json.loads(redis_value) if redis_value.startswith('{') else {"value": redis_value}
                    except:
                        value = {"value": redis_value}
                    source = "redis"
        
        # Fallback to database if not in Redis
        if not value:
            async with seeder.pg_client.pool.acquire() as conn:
                if policy_type == "employer":
                    query = "SELECT firm_type FROM policy_employers WHERE LOWER(company_name) = $1"
                    row = await conn.fetchrow(query, key)
                    if row:
                        value = {"firm_type": row['firm_type']}
                        source = "database"
                        
                elif policy_type == "city":
                    query = "SELECT metro_area FROM policy_city_context WHERE LOWER(city) = $1"
                    row = await conn.fetchrow(query, key)
                    if row:
                        value = {"metro_area": row['metro_area']}
                        source = "database"
                        
                elif policy_type == "subject":
                    query = """
                    SELECT text_template, alpha, beta 
                    FROM policy_subject_priors 
                    WHERE variant_id = $1 AND audience = 'global'
                    """
                    row = await conn.fetchrow(query, key)
                    if row:
                        value = {
                            "template": row['text_template'],
                            "alpha": row['alpha'],
                            "beta": row['beta']
                        }
                        source = "database"
                        
                elif policy_type == "selector":
                    query = """
                    SELECT tau_delta, bdat_alpha, bdat_beta 
                    FROM policy_selector_priors 
                    WHERE selector = $1
                    """
                    row = await conn.fetchrow(query, key)
                    if row:
                        value = {
                            "tau_delta": float(row['tau_delta']),
                            "alpha": row['bdat_alpha'],
                            "beta": row['bdat_beta']
                        }
                        source = "database"
        
        await seeder.close()
        
        return PolicyQueryResponse(
            found=value is not None,
            policy_type=policy_type,
            key=key,
            value=value,
            source=source
        )
        
    except Exception as e:
        logger.error(f"Policy query failed: {e}")
        await seeder.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_policy_stats(
    authorized: bool = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Get statistics about stored policies.
    
    Returns counts and metadata for all policy types.
    """
    seeder = PolicySeeder()
    
    try:
        await seeder.initialize()
        
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": {},
            "redis": {}
        }
        
        # Get database counts
        async with seeder.pg_client.pool.acquire() as conn:
            # Employers
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM policy_employers")
            stats["database"]["employers"] = row['count']
            
            # Cities
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM policy_city_context")
            stats["database"]["cities"] = row['count']
            
            # Subjects
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM policy_subject_priors")
            stats["database"]["subjects"] = row['count']
            
            # Selectors
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM policy_selector_priors")
            stats["database"]["selectors"] = row['count']
        
        # Get Redis counts if available
        if seeder.redis_client and seeder.redis_client.is_connected():
            patterns = {
                "employers": "policy:employers:*",
                "cities": "geo:metro:*",
                "subjects": "bandit:subjects:global:*",
                "selectors": "c3:tau:*"
            }
            
            for key, pattern in patterns.items():
                count = 0
                cursor = 0
                while True:
                    cursor, keys = await seeder.redis_client.client.scan(
                        cursor, match=pattern, count=100
                    )
                    count += len(keys)
                    if cursor == 0:
                        break
                stats["redis"][key] = count
        else:
            stats["redis"] = {"status": "not_connected"}
        
        await seeder.close()
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get policy stats: {e}")
        await seeder.close()
        raise HTTPException(status_code=500, detail=str(e))