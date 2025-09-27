"""
Thompson Sampling bandit for subject line optimization.
"""

import json
import logging
import random
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from app.redis_cache_manager import get_cache_manager

logger = logging.getLogger(__name__)


class SubjectLineBandit:
    """Thompson Sampling for email subject line optimization"""
    
    def __init__(self, audience: str = "steve_perry"):
        self.audience = audience
        self.cache_mgr = get_cache_manager()
        self.variants = []
        self.current_week = self._get_week_number()
        
    def _get_week_number(self) -> str:
        """Get current week number in YYYY-WW format"""
        now = datetime.now()
        week_num = now.isocalendar()[1]
        return f"{now.year}-{week_num:02d}"
    
    async def load_variants(self) -> List[Dict]:
        """Load subject line variants from Redis"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            logger.warning("Redis not available, using default variants")
            return self._get_default_variants()
        
        # Get list of variant IDs
        variants_key = f"bandit:subjects:{self.audience}:variants"
        variant_ids_raw = await self.cache_mgr.redis_client.get(variants_key)
        
        if not variant_ids_raw:
            logger.info("No variants in Redis, using defaults")
            return self._get_default_variants()
        
        variant_ids = json.loads(variant_ids_raw.decode())
        variants = []
        
        for variant_id in variant_ids:
            key = f"bandit:subjects:{self.audience}:{variant_id}"
            data_raw = await self.cache_mgr.redis_client.get(key)
            
            if data_raw:
                data = json.loads(data_raw.decode())
                variants.append({
                    'id': variant_id,
                    'text': data['text'],
                    'alpha': data.get('alpha', 1),
                    'beta': data.get('beta', 1)
                })
        
        self.variants = variants
        return variants
    
    def _get_default_variants(self) -> List[Dict]:
        """Get default subject line variants"""
        return [
            {
                'id': 'v1',
                'text': '🎯 Weekly Talent Update - {date}',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v2',
                'text': 'Your Curated Candidates - {date}',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v3',
                'text': '📊 TalentWell Weekly Digest',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v4',
                'text': 'Steve - New Talent Matches Available',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v5',
                'text': 'Weekly Recruiting Pipeline Update',
                'alpha': 1,
                'beta': 1
            }
        ]
    
    def thompson_sample(self) -> Tuple[str, str]:
        """Select variant using Thompson Sampling"""
        if not self.variants:
            self.variants = self._get_default_variants()
        
        # Sample from each variant's Beta distribution
        samples = []
        for variant in self.variants:
            # Sample from Beta(alpha, beta)
            sample_value = np.random.beta(variant['alpha'], variant['beta'])
            samples.append((sample_value, variant))
        
        # Select variant with highest sampled value
        samples.sort(reverse=True, key=lambda x: x[0])
        selected_variant = samples[0][1]
        
        # Format subject line with current date
        subject = selected_variant['text'].format(
            date=datetime.now().strftime('%b %d, %Y')
        )
        
        logger.info(f"Selected variant {selected_variant['id']} with sample value {samples[0][0]:.3f}")
        
        return selected_variant['id'], subject
    
    async def select_variant(self, audience: str = None) -> Dict:
        """Select subject line variant using Thompson Sampling"""
        if audience:
            self.audience = audience
            
        # Use existing thompson_sample method
        variant_id, subject_text = self.thompson_sample()
        
        # Find the selected variant details
        selected = None
        for v in self.variants:
            if v['id'] == variant_id:
                selected = v
                break
        
        if not selected:
            selected = {
                'id': 'default',
                'text': 'Weekly Digest',
                'alpha': 1,
                'beta': 1
            }
        
        # Calculate probability for transparency
        total_samples = selected.get('alpha', 1) + selected.get('beta', 1)
        probability = selected.get('alpha', 1) / total_samples if total_samples > 0 else 0.5
        
        return {
            'variant_id': variant_id,
            'text': subject_text,
            'probability': probability
        }
    
    async def update_variant(self, audience: str, variant_id: str, opened: bool = False, clicked: bool = False):
        """Update variant with engagement outcome"""
        outcome = 'click' if clicked else 'open' if opened else 'no_open'
        await self.update_priors(variant_id, outcome)
    
    async def update_priors(self, variant_id: str, outcome: str, 
                           value: float = 1.0):
        """
        Update Beta priors based on outcome.
        
        outcome types:
        - 'open': Email was opened
        - 'click': Link was clicked
        - 'meeting': Meeting was scheduled
        - 'no_open': Email not opened after 48 hours
        """
        # Find variant
        variant = None
        for v in self.variants:
            if v['id'] == variant_id:
                variant = v
                break
        
        if not variant:
            logger.warning(f"Variant {variant_id} not found")
            return
        
        # Update based on outcome
        if outcome in ['open', 'click', 'meeting']:
            # Success - increase alpha
            weight = {'open': 1.0, 'click': 2.0, 'meeting': 3.0}.get(outcome, 1.0)
            variant['alpha'] += weight * value
            logger.info(f"Positive update for {variant_id}: α+={weight * value}")
        elif outcome == 'no_open':
            # Failure - increase beta
            variant['beta'] += value
            logger.info(f"Negative update for {variant_id}: β+={value}")
        
        # Save updated priors to Redis
        if self.cache_mgr and self.cache_mgr.redis_client:
            key = f"bandit:subjects:{self.audience}:{variant_id}"
            data = {
                'text': variant['text'],
                'alpha': variant['alpha'],
                'beta': variant['beta']
            }
            await self.cache_mgr.redis_client.set(key, json.dumps(data))
            await self.cache_mgr.redis_client.expire(key, 86400 * 30)  # 30 day TTL
    
    async def log_selection(self, variant_id: str, subject: str, 
                           recipients: List[str]):
        """Log subject line selection for tracking"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            return
        
        # Create log entry
        log_entry = {
            'variant_id': variant_id,
            'subject': subject,
            'recipients': recipients,
            'timestamp': datetime.now().isoformat(),
            'week': self.current_week
        }
        
        # Store in Redis list
        log_key = f"bandit:log:{self.audience}:{self.current_week}"
        await self.cache_mgr.redis_client.lpush(log_key, json.dumps(log_entry))
        await self.cache_mgr.redis_client.expire(log_key, 86400 * 90)  # 90 day TTL
        
        # Update selection count
        count_key = f"bandit:count:{self.audience}:{variant_id}:{self.current_week}"
        await self.cache_mgr.redis_client.incr(count_key)
        await self.cache_mgr.redis_client.expire(count_key, 86400 * 90)
    
    async def get_performance_stats(self) -> Dict:
        """Get performance statistics for all variants"""
        stats = {}
        
        for variant in self.variants:
            # Calculate expected value (mean of Beta distribution)
            expected_value = variant['alpha'] / (variant['alpha'] + variant['beta'])
            
            # Calculate confidence interval (95%)
            samples = np.random.beta(variant['alpha'], variant['beta'], 10000)
            ci_lower = np.percentile(samples, 2.5)
            ci_upper = np.percentile(samples, 97.5)
            
            stats[variant['id']] = {
                'text': variant['text'],
                'alpha': variant['alpha'],
                'beta': variant['beta'],
                'expected_value': expected_value,
                'confidence_interval': (ci_lower, ci_upper),
                'samples_seen': variant['alpha'] + variant['beta'] - 2  # Subtract initial priors
            }
        
        return stats
    
    async def get_weekly_stats(self, week: Optional[str] = None) -> Dict:
        """Get selection stats for a specific week"""
        if not self.cache_mgr or not self.cache_mgr.redis_client:
            return {}
        
        week = week or self.current_week
        stats = {}
        
        for variant in self.variants:
            count_key = f"bandit:count:{self.audience}:{variant['id']}:{week}"
            count = await self.cache_mgr.redis_client.get(count_key)
            stats[variant['id']] = int(count.decode()) if count else 0
        
        return stats
    
    def calculate_regret(self) -> float:
        """Calculate cumulative regret (for analysis)"""
        if not self.variants:
            return 0.0
        
        # Find best arm (highest true mean)
        best_mean = max(v['alpha'] / (v['alpha'] + v['beta']) for v in self.variants)
        
        # Calculate total regret
        total_regret = 0.0
        total_pulls = 0
        
        for variant in self.variants:
            pulls = variant['alpha'] + variant['beta'] - 2  # Subtract initial priors
            mean = variant['alpha'] / (variant['alpha'] + variant['beta'])
            regret = (best_mean - mean) * pulls
            total_regret += regret
            total_pulls += pulls
        
        return total_regret / max(total_pulls, 1)
    
    async def run_ab_test_analysis(self) -> Dict:
        """Analyze A/B test results with statistical significance"""
        stats = await self.get_performance_stats()
        
        # Find best performing variant
        best_variant = max(stats.items(), key=lambda x: x[1]['expected_value'])
        
        analysis = {
            'best_variant': best_variant[0],
            'best_performance': best_variant[1]['expected_value'],
            'variants': {}
        }
        
        # Compare each variant to the best
        for variant_id, variant_stats in stats.items():
            if variant_id == best_variant[0]:
                analysis['variants'][variant_id] = {
                    'status': 'best',
                    'lift': 0.0,
                    'significant': True
                }
            else:
                # Calculate lift
                lift = (best_variant[1]['expected_value'] - variant_stats['expected_value']) / variant_stats['expected_value']
                
                # Check if confidence intervals overlap
                best_ci = best_variant[1]['confidence_interval']
                variant_ci = variant_stats['confidence_interval']
                significant = best_ci[0] > variant_ci[1]  # Best lower bound > variant upper bound
                
                analysis['variants'][variant_id] = {
                    'status': 'challenger',
                    'lift': lift,
                    'significant': significant
                }
        
        return analysis


# Factory function
def create_subject_bandit(audience: str = "steve_perry") -> SubjectLineBandit:
    """Create a subject line bandit for the specified audience"""
    return SubjectLineBandit(audience)