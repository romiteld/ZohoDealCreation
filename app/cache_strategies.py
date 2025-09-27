"""
Smart caching strategies for different email types to maximize cache hit rates.
Implements intelligent pattern recognition and cache invalidation logic.
"""

import re
import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class EmailType(Enum):
    """Classification of email types for caching strategies."""
    REFERRAL = "referral"           # Standard referral emails
    RECRUITER = "recruiter"         # Recruiter outreach
    APPLICATION = "application"      # Direct applications
    FOLLOWUP = "followup"           # Follow-up emails
    BATCH = "batch"                 # Batch recruitment emails
    UNKNOWN = "unknown"             # Unclassified


class CacheStrategy:
    """Base class for cache strategies."""
    
    def __init__(self):
        self.ttl = timedelta(hours=24)  # Default TTL
        self.pattern_key = None
        
    def should_cache(self, extraction_result: Dict[str, Any]) -> bool:
        """Determine if this extraction should be cached."""
        # Don't cache empty or error results
        if not extraction_result:
            return False
        
        # Don't cache if no meaningful data extracted
        has_data = any([
            extraction_result.get("candidate_name"),
            extraction_result.get("job_title"),
            extraction_result.get("company_name")
        ])
        
        return has_data
    
    def get_ttl(self) -> timedelta:
        """Get the TTL for this strategy."""
        return self.ttl
    
    def generate_pattern_key(self, email_content: str) -> Optional[str]:
        """Generate a pattern key for common email formats."""
        return self.pattern_key


class ReferralStrategy(CacheStrategy):
    """Caching strategy for referral emails."""
    
    def __init__(self):
        super().__init__()
        self.ttl = timedelta(hours=48)  # Longer TTL for referrals
        
    def should_cache(self, extraction_result: Dict[str, Any]) -> bool:
        """Referrals should always be cached if they have a referrer."""
        if not super().should_cache(extraction_result):
            return False
        
        # Cache if has referrer information
        return bool(extraction_result.get("referrer_name"))
    
    def generate_pattern_key(self, email_content: str) -> Optional[str]:
        """Generate pattern key for common referral formats."""
        content_lower = email_content.lower()
        
        # Check for common referral patterns
        if "i would like to refer" in content_lower:
            return "referral:standard_intro"
        elif "referred by" in content_lower:
            return "referral:referred_by"
        elif "recommendation" in content_lower:
            return "referral:recommendation"
        
        return None


class RecruiterStrategy(CacheStrategy):
    """Caching strategy for recruiter emails."""
    
    def __init__(self):
        super().__init__()
        self.ttl = timedelta(days=7)  # Long TTL for recruiter templates
        
    def generate_pattern_key(self, email_content: str) -> Optional[str]:
        """Identify common recruiter email templates."""
        content_lower = email_content.lower()
        
        # Common recruiter domains and patterns
        recruiter_patterns = [
            ("linkedin", "recruiter:linkedin"),
            ("indeed", "recruiter:indeed"),
            ("ziprecruiter", "recruiter:ziprecruiter"),
            ("opportunity", "recruiter:opportunity"),
            ("your profile", "recruiter:profile_match"),
            ("perfect fit", "recruiter:perfect_fit")
        ]
        
        for pattern, key in recruiter_patterns:
            if pattern in content_lower:
                return key
        
        return None


class BatchStrategy(CacheStrategy):
    """Caching strategy for batch recruitment emails."""
    
    def __init__(self):
        super().__init__()
        self.ttl = timedelta(days=30)  # Very long TTL for batch emails
        
    def should_cache(self, extraction_result: Dict[str, Any]) -> bool:
        """Batch emails are highly cacheable."""
        return super().should_cache(extraction_result)
    
    def identify_batch_pattern(self, email_content: str) -> bool:
        """Identify if this is a batch recruitment email."""
        indicators = [
            r"multiple\s+candidates",
            r"bulk\s+recruitment",
            r"candidates?\s+list",
            r"recruitment\s+drive",
            r"talent\s+pool"
        ]
        
        content_lower = email_content.lower()
        for pattern in indicators:
            if re.search(pattern, content_lower):
                return True
        
        return False


class CacheStrategyManager:
    """Manages cache strategies and email classification."""
    
    def __init__(self):
        self.strategies = {
            EmailType.REFERRAL: ReferralStrategy(),
            EmailType.RECRUITER: RecruiterStrategy(),
            EmailType.BATCH: BatchStrategy(),
            EmailType.APPLICATION: CacheStrategy(),  # Use base strategy
            EmailType.FOLLOWUP: CacheStrategy(),     # Use base strategy
            EmailType.UNKNOWN: CacheStrategy()       # Use base strategy
        }
        
        # Track patterns for optimization
        self.pattern_stats = {}
        
    def classify_email(self, email_content: str, sender_domain: str) -> EmailType:
        """
        Classify email type based on content and sender.
        
        Args:
            email_content: The email body
            sender_domain: The sender's domain
        
        Returns:
            EmailType classification
        """
        content_lower = email_content.lower()
        
        # Check for referral indicators
        referral_keywords = ["refer", "referred by", "recommendation", "suggested", "introduce"]
        if any(keyword in content_lower for keyword in referral_keywords):
            return EmailType.REFERRAL
        
        # Check for recruiter indicators
        recruiter_domains = ["linkedin.com", "indeed.com", "ziprecruiter.com", "glassdoor.com"]
        if sender_domain in recruiter_domains:
            return EmailType.RECRUITER
        
        recruiter_keywords = ["opportunity", "position", "opening", "role", "your profile", "perfect fit"]
        if any(keyword in content_lower for keyword in recruiter_keywords):
            return EmailType.RECRUITER
        
        # Check for batch recruitment
        batch_strategy = BatchStrategy()
        if batch_strategy.identify_batch_pattern(email_content):
            return EmailType.BATCH
        
        # Check for application
        if "application" in content_lower or "apply" in content_lower:
            return EmailType.APPLICATION
        
        # Check for follow-up
        if "follow up" in content_lower or "following up" in content_lower:
            return EmailType.FOLLOWUP
        
        return EmailType.UNKNOWN
    
    def get_strategy(self, email_type: EmailType) -> CacheStrategy:
        """Get the appropriate cache strategy for an email type."""
        return self.strategies.get(email_type, self.strategies[EmailType.UNKNOWN])
    
    def should_cache(self, 
                    email_content: str,
                    sender_domain: str,
                    extraction_result: Dict[str, Any]) -> Tuple[bool, timedelta, Optional[str]]:
        """
        Determine if extraction should be cached and with what parameters.
        
        Args:
            email_content: The email body
            sender_domain: The sender's domain
            extraction_result: The extraction result
        
        Returns:
            Tuple of (should_cache, ttl, pattern_key)
        """
        # Classify email
        email_type = self.classify_email(email_content, sender_domain)
        logger.info(f"Email classified as: {email_type.value}")
        
        # Get appropriate strategy
        strategy = self.get_strategy(email_type)
        
        # Check if should cache
        should_cache = strategy.should_cache(extraction_result)
        
        # Get TTL
        ttl = strategy.get_ttl()
        
        # Get pattern key if applicable
        pattern_key = strategy.generate_pattern_key(email_content)
        
        # Track pattern usage
        if pattern_key:
            self.pattern_stats[pattern_key] = self.pattern_stats.get(pattern_key, 0) + 1
        
        return should_cache, ttl, pattern_key
    
    def get_invalidation_patterns(self, email_type: EmailType) -> List[str]:
        """
        Get cache invalidation patterns for an email type.
        
        Args:
            email_type: The email type
        
        Returns:
            List of Redis key patterns to invalidate
        """
        base_patterns = ["well:email:full:*"]
        
        if email_type == EmailType.REFERRAL:
            base_patterns.extend([
                "well:pattern:referral:*",
                "well:email:*:referral:*"
            ])
        elif email_type == EmailType.RECRUITER:
            base_patterns.extend([
                "well:pattern:recruiter:*",
                "well:email:*:recruiter:*"
            ])
        elif email_type == EmailType.BATCH:
            base_patterns.extend([
                "well:pattern:batch:*",
                "well:email:*:batch:*"
            ])
        
        return base_patterns
    
    def should_invalidate(self, 
                         old_result: Dict[str, Any],
                         new_result: Dict[str, Any]) -> bool:
        """
        Determine if cache should be invalidated based on result changes.
        
        Args:
            old_result: Previous extraction result
            new_result: New extraction result
        
        Returns:
            True if cache should be invalidated
        """
        # Check for significant changes
        critical_fields = ["candidate_name", "job_title", "company_name", "referrer_name"]
        
        for field in critical_fields:
            old_value = old_result.get(field)
            new_value = new_result.get(field)
            
            # If values differ significantly, invalidate
            if old_value != new_value:
                # Check if it's a meaningful change (not just formatting)
                if old_value and new_value:
                    # Normalize for comparison
                    old_normalized = str(old_value).lower().strip()
                    new_normalized = str(new_value).lower().strip()
                    
                    # If substantially different, invalidate
                    if old_normalized != new_normalized:
                        logger.info(f"Cache invalidation triggered: {field} changed from '{old_value}' to '{new_value}'")
                        return True
                elif old_value or new_value:
                    # One is None, the other isn't
                    logger.info(f"Cache invalidation triggered: {field} changed from '{old_value}' to '{new_value}'")
                    return True
        
        return False
    
    def get_common_patterns(self) -> List[Dict[str, Any]]:
        """
        Get common email patterns for cache warming.
        
        Returns:
            List of pattern dictionaries for pre-warming cache
        """
        common_patterns = [
            {
                "key": "referral:standard_intro",
                "data": {
                    "template": "I would like to refer {candidate_name} for the {job_title} position",
                    "fields": ["candidate_name", "job_title", "referrer_name"],
                    "type": "referral"
                }
            },
            {
                "key": "recruiter:linkedin",
                "data": {
                    "template": "LinkedIn recruiter message about {job_title} opportunity",
                    "fields": ["job_title", "location", "company_name"],
                    "type": "recruiter"
                }
            },
            {
                "key": "recruiter:opportunity",
                "data": {
                    "template": "Exciting opportunity for {job_title} at {company_name}",
                    "fields": ["job_title", "company_name", "location"],
                    "type": "recruiter"
                }
            },
            {
                "key": "application:direct",
                "data": {
                    "template": "Application for {job_title} position",
                    "fields": ["candidate_name", "job_title", "email", "phone"],
                    "type": "application"
                }
            }
        ]
        
        return common_patterns
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache strategy metrics.
        
        Returns:
            Dictionary with strategy performance metrics
        """
        # Sort patterns by usage
        top_patterns = sorted(
            self.pattern_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Calculate email type distribution
        total_emails = sum(self.pattern_stats.values())
        
        return {
            "top_patterns": dict(top_patterns),
            "total_patterns_tracked": len(self.pattern_stats),
            "total_emails_processed": total_emails,
            "average_pattern_reuse": total_emails / len(self.pattern_stats) if self.pattern_stats else 0
        }
    
    def optimize_cache_strategy(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize cache strategies based on metrics.
        
        Args:
            metrics: Current cache metrics
        
        Returns:
            Dictionary with optimization recommendations
        """
        recommendations = []
        
        # Check hit rate
        hit_rate = float(metrics.get("hit_rate", "0").replace("%", ""))
        
        if hit_rate < 50:
            recommendations.append({
                "issue": "Low cache hit rate",
                "recommendation": "Consider increasing TTL for common patterns",
                "impact": "high"
            })
        
        # Check for underutilized patterns
        if self.pattern_stats:
            low_usage_patterns = [k for k, v in self.pattern_stats.items() if v < 5]
            if len(low_usage_patterns) > len(self.pattern_stats) * 0.3:
                recommendations.append({
                    "issue": "Many underutilized patterns",
                    "recommendation": "Review and consolidate pattern definitions",
                    "impact": "medium"
                })
        
        # Check error rate
        errors = metrics.get("errors", 0)
        total_requests = metrics.get("total_requests", 1)
        error_rate = (errors / total_requests * 100) if total_requests > 0 else 0
        
        if error_rate > 5:
            recommendations.append({
                "issue": "High cache error rate",
                "recommendation": "Check Redis connection and capacity",
                "impact": "high"
            })
        
        # Suggest cache warming
        if hit_rate < 70 and total_requests > 100:
            recommendations.append({
                "issue": "Suboptimal hit rate with sufficient traffic",
                "recommendation": "Implement cache warming for top patterns",
                "impact": "medium"
            })
        
        return {
            "optimizations": recommendations,
            "current_hit_rate": f"{hit_rate:.2f}%",
            "potential_savings": f"${metrics.get('estimated_monthly_savings', 0):.2f}",
            "recommendations_count": len(recommendations)
        }


# Singleton instance
_strategy_manager: Optional[CacheStrategyManager] = None


def get_strategy_manager() -> CacheStrategyManager:
    """Get or create the singleton strategy manager instance."""
    global _strategy_manager
    
    if _strategy_manager is None:
        _strategy_manager = CacheStrategyManager()
    
    return _strategy_manager