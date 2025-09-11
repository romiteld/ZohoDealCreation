"""
Policy loader for loading seed data into Redis at startup.
Enhanced to support database fallbacks and reload functionality.
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from app.redis_cache_manager import get_cache_manager
from app.integrations import PostgreSQLClient

# Load environment variables
load_dotenv('.env.local')

logger = logging.getLogger(__name__)


class PolicyLoader:
    """Load policy seeds into Redis with database fallback support"""
    
    def __init__(self, seed_dir: str = "app/policy/seed"):
        self.seed_dir = Path(seed_dir)
        self.cache_mgr = None
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required for policy loader")
        self.postgres_client = PostgreSQLClient(database_url)
        
    async def initialize(self):
        """Initialize async components."""
        if not self.cache_mgr:
            self.cache_mgr = await get_cache_manager()
        
    async def load_employers_from_db(self) -> Dict[str, str]:
        """Load employer classifications from database."""
        await self.postgres_client.init_pool()
        data = {}
        
        try:
            async with self.postgres_client.pool.acquire() as conn:
                rows = await conn.fetch("SELECT company_name, firm_type FROM policy_employers")
                data = {row['company_name']: row['firm_type'] for row in rows}
        except Exception as e:
            logger.warning(f"Failed to load employers from database: {e}")
        
        return data
    
    async def load_employers(self, data: Dict[str, str] = None):
        """Load employer classifications into Redis with database fallback"""
        await self.initialize()
        
        # Use provided data or fall back to database
        if data is None:
            data = await self.load_employers_from_db()
        
        if not data:
            logger.warning("No employer data available")
            return
        
        if not self.cache_mgr or not self.cache_mgr.client:
            logger.warning("Redis not available, skipping employer policy load")
            return
        
        for company, firm_type in data.items():
            key = f"policy:employers:{company.lower().replace(' ', '_')}"
            await self.cache_mgr.client.setex(key, 86400 * 30, firm_type)  # 30 day TTL
        
        logger.info(f"Loaded {len(data)} employer policies")
    
    async def load_city_context_from_db(self) -> Dict[str, str]:
        """Load city context from database."""
        await self.postgres_client.init_pool()
        data = {}
        
        try:
            async with self.postgres_client.pool.acquire() as conn:
                rows = await conn.fetch("SELECT city, metro_area FROM policy_city_context")
                data = {row['city']: row['metro_area'] for row in rows}
        except Exception as e:
            logger.warning(f"Failed to load city context from database: {e}")
        
        return data

    async def load_city_context(self, data: Dict[str, str] = None):
        """Load city to metro mappings into Redis with database fallback"""
        await self.initialize()
        
        # Use provided data or fall back to database
        if data is None:
            data = await self.load_city_context_from_db()
        
        if not data:
            logger.warning("No city context data available")
            return
        
        if not self.cache_mgr or not self.cache_mgr.client:
            logger.warning("Redis not available, skipping city context load")
            return
        
        for city, metro in data.items():
            key = f"geo:metro:{city.lower().replace(' ', '_')}"
            await self.cache_mgr.client.setex(key, 86400 * 30, metro)  # 30 day TTL
        
        logger.info(f"Loaded {len(data)} city-metro mappings")
    
    async def load_subjects_from_db(self) -> List[Dict]:
        """Load subject line bandit priors from database."""
        await self.postgres_client.init_pool()
        data = []
        
        try:
            async with self.postgres_client.pool.acquire() as conn:
                rows = await conn.fetch("SELECT id, text, alpha, beta FROM policy_subject_priors")
                data = [{'id': row['id'], 'text': row['text'], 'alpha': row['alpha'], 'beta': row['beta']} for row in rows]
        except Exception as e:
            logger.warning(f"Failed to load subject priors from database: {e}")
        
        return data

    async def load_subjects(self, data: List[Dict] = None):
        """Load subject line bandit priors into Redis with database fallback"""
        await self.initialize()
        
        # Use provided data or fall back to database
        if data is None:
            data = await self.load_subjects_from_db()
        
        if not data:
            logger.warning("No subject priors data available")
            return
        
        if not self.cache_mgr or not self.cache_mgr.client:
            logger.warning("Redis not available, skipping subject priors load")
            return
        
        for subject in data:
            key = f"bandit:subjects:steve_perry:{subject['id']}"
            value = json.dumps({
                'text': subject['text'],
                'alpha': subject['alpha'],
                'beta': subject['beta']
            })
            await self.cache_mgr.client.set(key, value)
            await self.cache_mgr.client.expire(key, 86400 * 7)  # 7 day TTL
        
        # Store list of variant IDs
        variants_key = "bandit:subjects:steve_perry:variants"
        variant_ids = [s['id'] for s in data]
        await self.cache_mgr.client.set(variants_key, json.dumps(variant_ids))
        await self.cache_mgr.client.expire(variants_key, 86400 * 7)
        
        logger.info(f"Loaded {len(data)} subject line variants")
    
    async def load_selector_priors_from_db(self) -> Dict[str, Dict]:
        """Load selector-specific C³ and BDAT parameters from database."""
        await self.postgres_client.init_pool()
        data = {}
        
        try:
            async with self.postgres_client.pool.acquire() as conn:
                rows = await conn.fetch("SELECT selector, tau_delta, bdat_alpha, bdat_beta FROM policy_selector_priors")
                data = {
                    row['selector']: {
                        'tau_delta': row['tau_delta'],
                        'bdat_alpha': row['bdat_alpha'], 
                        'bdat_beta': row['bdat_beta']
                    } for row in rows
                }
        except Exception as e:
            logger.warning(f"Failed to load selector priors from database: {e}")
        
        return data

    async def load_selector_priors(self, data: Dict[str, Dict] = None):
        """Load selector-specific C³ and BDAT parameters into Redis with database fallback"""
        await self.initialize()
        
        # Use provided data or fall back to database
        if data is None:
            data = await self.load_selector_priors_from_db()
        
        if not data:
            logger.warning("No selector priors data available")
            return
        
        if not self.cache_mgr or not self.cache_mgr.client:
            logger.warning("Redis not available, skipping selector priors load")
            return
        
        for selector, params in data.items():
            # Store tau_delta for C³
            tau_key = f"c3:tau:{selector}"
            await self.cache_mgr.client.setex(tau_key, 86400 * 30, str(params['tau_delta']))
            
            # Store BDAT parameters for TTL
            ttl_key = f"ttl:{selector}"
            ttl_value = json.dumps({
                'alpha': params['bdat_alpha'],
                'beta': params['bdat_beta']
            })
            await self.cache_mgr.client.setex(ttl_key, 86400 * 30, ttl_value)
        
        logger.info(f"Loaded {len(data)} selector configurations")
    
    async def load_all_policies(self) -> Dict[str, int]:
        """Load all policy seeds from files into Redis"""
        loaded_counts = {}
        
        # Check if seed directory exists
        if not self.seed_dir.exists():
            logger.warning(f"Seed directory not found: {self.seed_dir}")
            return loaded_counts
        
        # Load employers.json
        employers_file = self.seed_dir / "employers.json"
        if employers_file.exists():
            try:
                with open(employers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    await self.load_employers(data)
                    loaded_counts['employers'] = len(data)
            except Exception as e:
                logger.error(f"Failed to load employers.json: {e}")
        
        # Load city_context.json
        city_file = self.seed_dir / "city_context.json"
        if city_file.exists():
            try:
                with open(city_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    await self.load_city_context(data)
                    loaded_counts['city_context'] = len(data)
            except Exception as e:
                logger.error(f"Failed to load city_context.json: {e}")
        
        # Load subjects.json
        subjects_file = self.seed_dir / "subjects.json"
        if subjects_file.exists():
            try:
                with open(subjects_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    await self.load_subjects(data)
                    loaded_counts['subjects'] = len(data)
            except Exception as e:
                logger.error(f"Failed to load subjects.json: {e}")
        
        # Load selector_priors.json
        selectors_file = self.seed_dir / "selector_priors.json"
        if selectors_file.exists():
            try:
                with open(selectors_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    await self.load_selector_priors(data)
                    loaded_counts['selector_priors'] = len(data)
            except Exception as e:
                logger.error(f"Failed to load selector_priors.json: {e}")
        
        logger.info(f"Policy loading complete: {loaded_counts}")
        return loaded_counts
    
    async def get_employer_type(self, company_name: str) -> str:
        """Get employer type from Redis"""
        if not self.cache_mgr or not self.cache_mgr.client:
            return "Independent firm"  # Default
        
        key = f"policy:employers:{company_name.lower().replace(' ', '_')}"
        value = await self.cache_mgr.client.get(key)
        return value.decode() if value else "Independent firm"
    
    async def get_metro_area(self, city: str) -> str:
        """Get metro area from Redis"""
        if not self.cache_mgr or not self.cache_mgr.client:
            return city  # Return original city if not found
        
        key = f"geo:metro:{city.lower().replace(' ', '_')}"
        value = await self.cache_mgr.client.get(key)
        return value.decode() if value else city
    
    async def get_selector_tau(self, selector: str) -> float:
        """Get selector-specific tau_delta from Redis"""
        if not self.cache_mgr or not self.cache_mgr.client:
            return 0.01  # Default tau_delta
        
        key = f"c3:tau:{selector}"
        value = await self.cache_mgr.client.get(key)
        return float(value.decode()) if value else 0.01
    
    async def get_selector_ttl_params(self, selector: str) -> Dict[str, int]:
        """Get selector-specific BDAT parameters from Redis"""
        if not self.cache_mgr or not self.cache_mgr.client:
            return {'alpha': 3, 'beta': 7}  # Default BDAT params
        
        key = f"ttl:{selector}"
        value = await self.cache_mgr.client.get(key)
        if value:
            return json.loads(value.decode())
        return {'alpha': 3, 'beta': 7}


# Singleton instance
_policy_loader: Optional[PolicyLoader] = None


def get_policy_loader() -> PolicyLoader:
    """Get singleton policy loader instance"""
    global _policy_loader
    if _policy_loader is None:
        _policy_loader = PolicyLoader()
    return _policy_loader


async def initialize_policies():
    """Initialize policies at application startup"""
    loader = get_policy_loader()
    result = await loader.load_all_policies()
    logger.info(f"Policies initialized: {result}")
    return result