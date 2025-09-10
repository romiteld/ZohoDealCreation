"""
Policy loader for loading seed data into Redis at startup.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from app.redis_cache_manager import get_cache_manager

logger = logging.getLogger(__name__)


class PolicyLoader:
    """Load policy seeds into Redis"""
    
    def __init__(self, seed_dir: str = "app/policy/seed"):
        self.seed_dir = Path(seed_dir)
        self.cache_mgr = get_cache_manager()
        
    async def load_employers(self, data: Dict[str, str]):
        """Load employer classifications into Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            logger.warning("Redis not available, skipping employer policy load")
            return
        
        for company, firm_type in data.items():
            key = f"policy:employers:{company.lower().replace(' ', '_')}"
            await self.cache_mgr.redis_client.set(key, firm_type)
            await self.cache_mgr.redis_client.expire(key, 86400 * 30)  # 30 day TTL
        
        logger.info(f"Loaded {len(data)} employer policies")
    
    async def load_city_context(self, data: Dict[str, str]):
        """Load city to metro mappings into Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            logger.warning("Redis not available, skipping city context load")
            return
        
        for city, metro in data.items():
            key = f"geo:metro:{city.lower().replace(' ', '_')}"
            await self.cache_mgr.redis_client.set(key, metro)
            await self.cache_mgr.redis_client.expire(key, 86400 * 30)  # 30 day TTL
        
        logger.info(f"Loaded {len(data)} city-metro mappings")
    
    async def load_subjects(self, data: list):
        """Load subject line bandit priors into Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            logger.warning("Redis not available, skipping subject priors load")
            return
        
        for subject in data:
            key = f"bandit:subjects:steve_perry:{subject['id']}"
            value = json.dumps({
                'text': subject['text'],
                'alpha': subject['alpha'],
                'beta': subject['beta']
            })
            await self.cache_mgr.redis_client.set(key, value)
            await self.cache_mgr.redis_client.expire(key, 86400 * 7)  # 7 day TTL
        
        # Store list of variant IDs
        variants_key = "bandit:subjects:steve_perry:variants"
        variant_ids = [s['id'] for s in data]
        await self.cache_mgr.redis_client.set(variants_key, json.dumps(variant_ids))
        await self.cache_mgr.redis_client.expire(variants_key, 86400 * 7)
        
        logger.info(f"Loaded {len(data)} subject line variants")
    
    async def load_selector_priors(self, data: Dict[str, Dict]):
        """Load selector-specific C³ and BDAT parameters into Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            logger.warning("Redis not available, skipping selector priors load")
            return
        
        for selector, params in data.items():
            # Store tau_delta for C³
            tau_key = f"c3:tau:{selector}"
            await self.cache_mgr.redis_client.set(tau_key, str(params['tau_delta']))
            await self.cache_mgr.redis_client.expire(tau_key, 86400 * 30)
            
            # Store BDAT parameters for TTL
            ttl_key = f"ttl:{selector}"
            ttl_value = json.dumps({
                'alpha': params['bdat_alpha'],
                'beta': params['bdat_beta']
            })
            await self.cache_mgr.redis_client.set(ttl_key, ttl_value)
            await self.cache_mgr.redis_client.expire(ttl_key, 86400 * 30)
        
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
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            return "Independent firm"  # Default
        
        key = f"policy:employers:{company_name.lower().replace(' ', '_')}"
        value = await self.cache_mgr.redis_client.get(key)
        return value.decode() if value else "Independent firm"
    
    async def get_metro_area(self, city: str) -> str:
        """Get metro area from Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            return city  # Return original city if not found
        
        key = f"geo:metro:{city.lower().replace(' ', '_')}"
        value = await self.cache_mgr.redis_client.get(key)
        return value.decode() if value else city
    
    async def get_selector_tau(self, selector: str) -> float:
        """Get selector-specific tau_delta from Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            return 0.01  # Default tau_delta
        
        key = f"c3:tau:{selector}"
        value = await self.cache_mgr.redis_client.get(key)
        return float(value.decode()) if value else 0.01
    
    async def get_selector_ttl_params(self, selector: str) -> Dict[str, int]:
        """Get selector-specific BDAT parameters from Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            return {'alpha': 3, 'beta': 7}  # Default BDAT params
        
        key = f"ttl:{selector}"
        value = await self.cache_mgr.redis_client.get(key)
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