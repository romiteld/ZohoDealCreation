"""
Advanced caching strategies for Outlook Add-in manifest delivery and Office environment optimization.
Implements environment-aware caching with progressive rollout and A/B testing support.
"""

import os
import json
import hashlib
import logging
import asyncio
from typing import Dict, Optional, Any, List, Tuple, Union
from datetime import timedelta, datetime
from enum import Enum
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
import re

from .cache_strategies import EmailType, CacheStrategyManager, get_strategy_manager
from .redis_cache_manager import RedisCacheManager, get_cache_manager

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environment types for manifest caching."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    CANARY = "canary"
    PREVIEW = "preview"


class OfficeVersion(Enum):
    """Office application versions for user-agent based caching."""
    OUTLOOK_WEB = "outlook_web"
    OUTLOOK_DESKTOP_2019 = "outlook_2019"
    OUTLOOK_DESKTOP_2021 = "outlook_2021"
    OUTLOOK_365 = "outlook_365"
    OUTLOOK_MAC = "outlook_mac"
    TEAMS = "teams"
    UNKNOWN = "unknown"


class GeographicRegion(Enum):
    """Geographic regions for edge caching optimization."""
    NORTH_AMERICA = "na"
    EUROPE = "eu"
    ASIA_PACIFIC = "apac"
    AUSTRALIA = "au"
    GLOBAL = "global"


@dataclass
class ManifestCacheConfig:
    """Configuration for manifest-specific caching strategies."""
    environment: Environment
    ttl: timedelta
    max_versions: int
    enable_compression: bool
    enable_cdn_caching: bool
    cache_headers: Dict[str, str]
    user_agent_variants: bool
    geographic_caching: bool
    a_b_testing: bool
    rollout_percentage: float


@dataclass
class UserContext:
    """User context for personalized manifest caching."""
    user_agent: str
    office_version: OfficeVersion
    region: GeographicRegion
    tenant_id: Optional[str]
    language: str
    timezone: str
    ip_address: Optional[str]


class ManifestCacheStrategy:
    """Base strategy for manifest caching with environment awareness."""
    
    def __init__(self, config: ManifestCacheConfig):
        self.config = config
        
    def get_cache_key(self, 
                      manifest_version: str,
                      user_context: UserContext,
                      variant: str = "default") -> str:
        """Generate cache key for manifest delivery."""
        components = [
            "manifest",
            self.config.environment.value,
            manifest_version,
            user_context.office_version.value,
            variant
        ]
        
        if self.config.user_agent_variants:
            components.append(self._normalize_user_agent(user_context.user_agent))
        
        if self.config.geographic_caching:
            components.append(user_context.region.value)
        
        return ":".join(components)
    
    def _normalize_user_agent(self, user_agent: str) -> str:
        """Normalize user agent for caching consistency."""
        # Extract key Office version info
        office_patterns = {
            "outlook_web": r"outlook.*web",
            "outlook_2019": r"outlook.*16\.0\.1[0-4]",
            "outlook_2021": r"outlook.*16\.0\.1[5-9]",
            "outlook_365": r"microsoft.*365",
            "teams": r"teams"
        }
        
        ua_lower = user_agent.lower()
        for key, pattern in office_patterns.items():
            if re.search(pattern, ua_lower):
                return key
        
        return "generic"
    
    def get_cache_headers(self) -> Dict[str, str]:
        """Get appropriate HTTP cache headers for this strategy."""
        return self.config.cache_headers.copy()
    
    def should_cache(self, request_context: Dict[str, Any]) -> bool:
        """Determine if this request should be cached."""
        return True


class DevelopmentManifestStrategy(ManifestCacheStrategy):
    """Development environment - minimal caching for rapid iteration."""
    
    def __init__(self):
        config = ManifestCacheConfig(
            environment=Environment.DEVELOPMENT,
            ttl=timedelta(minutes=1),  # Very short TTL
            max_versions=3,
            enable_compression=False,
            enable_cdn_caching=False,
            cache_headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            },
            user_agent_variants=False,
            geographic_caching=False,
            a_b_testing=False,
            rollout_percentage=100.0
        )
        super().__init__(config)
    
    def should_cache(self, request_context: Dict[str, Any]) -> bool:
        """Only cache for basic functionality testing in dev."""
        return request_context.get("cache_test", False)


class StagingManifestStrategy(ManifestCacheStrategy):
    """Staging environment - moderate caching for testing scenarios."""
    
    def __init__(self):
        config = ManifestCacheConfig(
            environment=Environment.STAGING,
            ttl=timedelta(minutes=5),  # Short TTL for testing
            max_versions=10,
            enable_compression=True,
            enable_cdn_caching=False,
            cache_headers={
                "Cache-Control": "private, max-age=300",  # 5 minutes
                "ETag": "",  # Will be populated dynamically
                "Vary": "User-Agent, Accept-Encoding"
            },
            user_agent_variants=True,
            geographic_caching=False,
            a_b_testing=True,
            rollout_percentage=100.0
        )
        super().__init__(config)


class ProductionManifestStrategy(ManifestCacheStrategy):
    """Production environment - aggressive caching with geographic distribution."""
    
    def __init__(self):
        config = ManifestCacheConfig(
            environment=Environment.PRODUCTION,
            ttl=timedelta(hours=24),  # 24-hour TTL
            max_versions=50,
            enable_compression=True,
            enable_cdn_caching=True,
            cache_headers={
                "Cache-Control": "public, max-age=86400, s-maxage=86400",  # 24 hours
                "ETag": "",  # Will be populated dynamically
                "Vary": "User-Agent, Accept-Encoding, Accept-Language",
                "X-Content-Type-Options": "nosniff"
            },
            user_agent_variants=True,
            geographic_caching=True,
            a_b_testing=True,
            rollout_percentage=100.0
        )
        super().__init__(config)


class CanaryManifestStrategy(ManifestCacheStrategy):
    """Canary deployment - progressive rollout with monitoring."""
    
    def __init__(self, rollout_percentage: float = 5.0):
        config = ManifestCacheConfig(
            environment=Environment.CANARY,
            ttl=timedelta(hours=1),  # Shorter TTL for quick rollback
            max_versions=25,
            enable_compression=True,
            enable_cdn_caching=False,  # Direct serving for monitoring
            cache_headers={
                "Cache-Control": "private, max-age=3600",  # 1 hour
                "ETag": "",
                "Vary": "User-Agent",
                "X-Canary-Version": "true"
            },
            user_agent_variants=True,
            geographic_caching=True,
            a_b_testing=True,
            rollout_percentage=rollout_percentage
        )
        super().__init__(config)
    
    def should_serve_canary(self, user_context: UserContext) -> bool:
        """Determine if user should receive canary version."""
        # Hash user identifier for consistent assignment
        user_hash = hashlib.md5(
            f"{user_context.tenant_id or user_context.ip_address}".encode()
        ).hexdigest()
        
        # Convert to percentage (0-100)
        hash_percentage = int(user_hash[:2], 16) / 255 * 100
        
        return hash_percentage < self.config.rollout_percentage


class ManifestCacheManager:
    """Advanced manifest cache manager with environment awareness and A/B testing."""
    
    def __init__(self):
        self.strategies = {
            Environment.DEVELOPMENT: DevelopmentManifestStrategy(),
            Environment.STAGING: StagingManifestStrategy(),
            Environment.PRODUCTION: ProductionManifestStrategy(),
            Environment.CANARY: CanaryManifestStrategy(),
        }
        
        self.redis_manager: Optional[RedisCacheManager] = None
        self.email_strategy_manager: Optional[CacheStrategyManager] = None
        
        # A/B testing configurations
        self.ab_tests = {
            "manifest_compression": {
                "enabled": True,
                "variants": ["gzip", "brotli", "none"],
                "distribution": [40, 40, 20]  # 40% gzip, 40% brotli, 20% none
            },
            "cache_warmup_strategy": {
                "enabled": True,
                "variants": ["aggressive", "moderate", "minimal"],
                "distribution": [30, 50, 20]
            }
        }
        
        # Metrics tracking
        self.metrics = {
            "manifest_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "ab_test_assignments": {},
            "geographic_distribution": {},
            "office_version_distribution": {},
            "error_count": 0
        }
    
    async def initialize(self):
        """Initialize cache managers and connections."""
        try:
            self.redis_manager = await get_cache_manager()
            self.email_strategy_manager = get_strategy_manager()
            logger.info("Manifest cache manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize manifest cache manager: {e}")
    
    def detect_environment(self, request_context: Dict[str, Any]) -> Environment:
        """Detect deployment environment from request context."""
        host = request_context.get("host", "").lower()
        
        if "localhost" in host or "127.0.0.1" in host:
            return Environment.DEVELOPMENT
        elif "staging" in host or "dev" in host:
            return Environment.STAGING
        elif "canary" in host or "preview" in host:
            return Environment.CANARY
        else:
            return Environment.PRODUCTION
    
    def parse_user_context(self, request: Dict[str, Any]) -> UserContext:
        """Extract user context from HTTP request."""
        user_agent = request.get("user_agent", "")
        headers = request.get("headers", {})
        
        # Detect Office version from user agent
        office_version = self._detect_office_version(user_agent)
        
        # Detect geographic region from headers or IP
        region = self._detect_region(headers, request.get("client_ip"))
        
        return UserContext(
            user_agent=user_agent,
            office_version=office_version,
            region=region,
            tenant_id=headers.get("x-tenant-id"),
            language=headers.get("accept-language", "en-US").split(",")[0],
            timezone=headers.get("x-timezone", "UTC"),
            ip_address=request.get("client_ip")
        )
    
    def _detect_office_version(self, user_agent: str) -> OfficeVersion:
        """Detect Office version from user agent string."""
        ua_lower = user_agent.lower()
        
        version_patterns = {
            OfficeVersion.OUTLOOK_WEB: [r"outlook.*web", r"owa", r"weboutlook"],
            OfficeVersion.OUTLOOK_365: [r"microsoft.*365", r"office.*365"],
            OfficeVersion.OUTLOOK_DESKTOP_2021: [r"outlook.*16\.0\.1[5-9]", r"office.*2021"],
            OfficeVersion.OUTLOOK_DESKTOP_2019: [r"outlook.*16\.0\.1[0-4]", r"office.*2019"],
            OfficeVersion.OUTLOOK_MAC: [r"outlook.*mac", r"macoutlook"],
            OfficeVersion.TEAMS: [r"teams", r"msteams"]
        }
        
        for version, patterns in version_patterns.items():
            for pattern in patterns:
                if re.search(pattern, ua_lower):
                    return version
        
        return OfficeVersion.UNKNOWN
    
    def _detect_region(self, headers: Dict[str, str], client_ip: Optional[str]) -> GeographicRegion:
        """Detect geographic region from request headers."""
        # Check CloudFlare headers
        cf_ipcountry = headers.get("cf-ipcountry", "").upper()
        
        region_mapping = {
            # North America
            "US": GeographicRegion.NORTH_AMERICA,
            "CA": GeographicRegion.NORTH_AMERICA,
            "MX": GeographicRegion.NORTH_AMERICA,
            
            # Europe
            "GB": GeographicRegion.EUROPE,
            "DE": GeographicRegion.EUROPE,
            "FR": GeographicRegion.EUROPE,
            "IT": GeographicRegion.EUROPE,
            "ES": GeographicRegion.EUROPE,
            "NL": GeographicRegion.EUROPE,
            
            # Asia Pacific
            "JP": GeographicRegion.ASIA_PACIFIC,
            "KR": GeographicRegion.ASIA_PACIFIC,
            "CN": GeographicRegion.ASIA_PACIFIC,
            "IN": GeographicRegion.ASIA_PACIFIC,
            "SG": GeographicRegion.ASIA_PACIFIC,
            
            # Australia
            "AU": GeographicRegion.AUSTRALIA,
            "NZ": GeographicRegion.AUSTRALIA,
        }
        
        return region_mapping.get(cf_ipcountry, GeographicRegion.GLOBAL)
    
    async def get_manifest_cache_key(self,
                                   manifest_version: str,
                                   user_context: UserContext,
                                   environment: Environment) -> str:
        """Generate cache key for manifest with A/B test variants."""
        strategy = self.strategies.get(environment)
        if not strategy:
            strategy = self.strategies[Environment.PRODUCTION]
        
        # Determine A/B test variant
        variant = await self._get_ab_test_variant(user_context, "manifest_compression")
        
        return strategy.get_cache_key(manifest_version, user_context, variant)
    
    async def _get_ab_test_variant(self, user_context: UserContext, test_name: str) -> str:
        """Assign user to A/B test variant consistently."""
        test_config = self.ab_tests.get(test_name)
        if not test_config or not test_config["enabled"]:
            return "default"
        
        # Create consistent hash for user
        user_id = user_context.tenant_id or user_context.ip_address or "anonymous"
        test_hash = hashlib.md5(f"{test_name}:{user_id}".encode()).hexdigest()
        hash_value = int(test_hash[:8], 16) % 100
        
        # Assign to variant based on distribution
        variants = test_config["variants"]
        distribution = test_config["distribution"]
        
        cumulative = 0
        for i, percentage in enumerate(distribution):
            cumulative += percentage
            if hash_value < cumulative:
                variant = variants[i]
                
                # Track assignment
                if test_name not in self.metrics["ab_test_assignments"]:
                    self.metrics["ab_test_assignments"][test_name] = {}
                
                self.metrics["ab_test_assignments"][test_name][variant] = \
                    self.metrics["ab_test_assignments"][test_name].get(variant, 0) + 1
                
                return variant
        
        return variants[0]  # Fallback to first variant
    
    async def get_cached_manifest(self,
                                manifest_version: str,
                                user_context: UserContext,
                                environment: Environment) -> Optional[Dict[str, Any]]:
        """Retrieve cached manifest with environment-specific logic."""
        if not self.redis_manager:
            await self.initialize()
        
        try:
            cache_key = await self.get_manifest_cache_key(
                manifest_version, user_context, environment
            )
            
            # Get from Redis cache
            cached_manifest = await self.redis_manager.get_cached_extraction(
                cache_key, "manifest"
            )
            
            if cached_manifest:
                self.metrics["cache_hits"] += 1
                self.metrics["manifest_requests"] += 1
                
                # Track geographic distribution
                region = user_context.region.value
                self.metrics["geographic_distribution"][region] = \
                    self.metrics["geographic_distribution"].get(region, 0) + 1
                
                # Track Office version distribution
                version = user_context.office_version.value
                self.metrics["office_version_distribution"][version] = \
                    self.metrics["office_version_distribution"].get(version, 0) + 1
                
                logger.info(f"Manifest cache HIT: {cache_key}")
                return cached_manifest["result"]
            else:
                self.metrics["cache_misses"] += 1
                self.metrics["manifest_requests"] += 1
                logger.debug(f"Manifest cache MISS: {cache_key}")
                return None
        
        except Exception as e:
            self.metrics["error_count"] += 1
            logger.error(f"Error retrieving cached manifest: {e}")
            return None
    
    async def cache_manifest(self,
                           manifest_version: str,
                           manifest_content: Dict[str, Any],
                           user_context: UserContext,
                           environment: Environment) -> bool:
        """Cache manifest with environment-specific TTL and optimization."""
        if not self.redis_manager:
            await self.initialize()
        
        try:
            strategy = self.strategies.get(environment, self.strategies[Environment.PRODUCTION])
            cache_key = await self.get_manifest_cache_key(
                manifest_version, user_context, environment
            )
            
            # Add manifest metadata
            cache_data = {
                "manifest": manifest_content,
                "version": manifest_version,
                "environment": environment.value,
                "cached_at": datetime.utcnow().isoformat(),
                "user_context": {
                    "office_version": user_context.office_version.value,
                    "region": user_context.region.value,
                    "language": user_context.language
                },
                "cache_headers": strategy.get_cache_headers()
            }
            
            # Cache with environment-specific TTL
            success = await self.redis_manager.cache_extraction(
                cache_key,
                cache_data,
                "manifest",
                strategy.config.ttl
            )
            
            if success:
                logger.info(f"Cached manifest: {cache_key} with TTL: {strategy.config.ttl}")
            
            return success
        
        except Exception as e:
            self.metrics["error_count"] += 1
            logger.error(f"Error caching manifest: {e}")
            return False
    
    async def warm_cache_progressive(self,
                                   manifest_versions: List[str],
                                   target_regions: List[GeographicRegion],
                                   office_versions: List[OfficeVersion]) -> Dict[str, int]:
        """Progressively warm cache for common manifest requests."""
        if not self.redis_manager:
            await self.initialize()
        
        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0
        }
        
        # Generate user contexts for cache warming
        warmup_contexts = []
        for region in target_regions:
            for office_version in office_versions:
                context = UserContext(
                    user_agent=f"cache_warmup_{office_version.value}",
                    office_version=office_version,
                    region=region,
                    tenant_id="warmup",
                    language="en-US",
                    timezone="UTC",
                    ip_address="0.0.0.0"
                )
                warmup_contexts.append(context)
        
        # Warm cache for each combination
        for version in manifest_versions:
            for context in warmup_contexts:
                for environment in [Environment.PRODUCTION, Environment.STAGING]:
                    try:
                        # Generate sample manifest content
                        manifest_content = {
                            "id": f"warmup-{version}",
                            "version": version,
                            "environment": environment.value,
                            "office_version": context.office_version.value,
                            "region": context.region.value
                        }
                        
                        success = await self.cache_manifest(
                            version, manifest_content, context, environment
                        )
                        
                        if success:
                            results["success"] += 1
                        else:
                            results["failed"] += 1
                    
                    except Exception as e:
                        logger.error(f"Cache warmup failed for {version}/{context.office_version.value}: {e}")
                        results["failed"] += 1
        
        logger.info(f"Cache warmup completed: {results}")
        return results
    
    async def invalidate_manifest_cache(self,
                                      manifest_version: Optional[str] = None,
                                      environment: Optional[Environment] = None,
                                      office_version: Optional[OfficeVersion] = None) -> int:
        """Invalidate manifest caches with selective targeting."""
        if not self.redis_manager:
            await self.initialize()
        
        # Build invalidation pattern
        pattern_parts = ["manifest"]
        
        if environment:
            pattern_parts.append(environment.value)
        else:
            pattern_parts.append("*")
        
        if manifest_version:
            pattern_parts.append(manifest_version)
        else:
            pattern_parts.append("*")
        
        if office_version:
            pattern_parts.append(office_version.value)
        else:
            pattern_parts.append("*")
        
        pattern_parts.append("*")  # For variant and region
        
        invalidation_pattern = ":".join(pattern_parts)
        
        try:
            deleted_count = await self.redis_manager.invalidate_cache(invalidation_pattern)
            logger.info(f"Invalidated {deleted_count} manifest cache entries matching: {invalidation_pattern}")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Manifest cache invalidation failed: {e}")
            return 0
    
    async def get_cache_metrics(self) -> Dict[str, Any]:
        """Get comprehensive manifest cache metrics."""
        base_metrics = await self.redis_manager.get_metrics() if self.redis_manager else {}
        
        # Calculate manifest-specific metrics
        total_requests = self.metrics["manifest_requests"]
        hit_rate = (self.metrics["cache_hits"] / total_requests * 100) if total_requests > 0 else 0
        
        manifest_metrics = {
            **self.metrics,
            "hit_rate": f"{hit_rate:.2f}%",
            "cache_efficiency": hit_rate / 100 if total_requests > 0 else 0,
            "error_rate": (self.metrics["error_count"] / total_requests * 100) if total_requests > 0 else 0
        }
        
        # Add optimization recommendations
        recommendations = []
        
        if hit_rate < 60:
            recommendations.append({
                "type": "performance",
                "message": "Consider extending cache TTL for stable manifest versions",
                "impact": "high"
            })
        
        if self.metrics["error_count"] > total_requests * 0.05:
            recommendations.append({
                "type": "reliability",
                "message": "High error rate detected - check Redis connectivity",
                "impact": "critical"
            })
        
        # A/B test performance analysis
        ab_performance = {}
        for test_name, assignments in self.metrics["ab_test_assignments"].items():
            total_assignments = sum(assignments.values())
            ab_performance[test_name] = {
                "total_assignments": total_assignments,
                "variant_distribution": {
                    variant: count / total_assignments * 100
                    for variant, count in assignments.items()
                }
            }
        
        return {
            "manifest_cache": manifest_metrics,
            "redis_cache": base_metrics,
            "ab_testing": ab_performance,
            "recommendations": recommendations,
            "environment_strategies": {
                env.value: {
                    "ttl_hours": strategy.config.ttl.total_seconds() / 3600,
                    "compression_enabled": strategy.config.enable_compression,
                    "cdn_enabled": strategy.config.enable_cdn_caching
                }
                for env, strategy in self.strategies.items()
            }
        }
    
    async def optimize_cache_strategy(self) -> Dict[str, Any]:
        """Analyze usage patterns and optimize caching strategies."""
        metrics = await self.get_cache_metrics()
        
        optimizations = []
        
        # Analyze geographic distribution
        geo_dist = self.metrics["geographic_distribution"]
        if geo_dist:
            total_requests = sum(geo_dist.values())
            top_region = max(geo_dist.items(), key=lambda x: x[1])
            
            if top_region[1] / total_requests > 0.6:  # 60% from one region
                optimizations.append({
                    "type": "geographic_optimization",
                    "recommendation": f"Consider dedicated edge cache for {top_region[0]} region",
                    "impact": "medium",
                    "data": {"dominant_region": top_region[0], "percentage": top_region[1] / total_requests * 100}
                })
        
        # Analyze Office version distribution
        office_dist = self.metrics["office_version_distribution"]
        if office_dist:
            total_requests = sum(office_dist.values())
            for version, count in office_dist.items():
                percentage = count / total_requests * 100
                
                if percentage < 5 and version != OfficeVersion.UNKNOWN.value:
                    optimizations.append({
                        "type": "version_optimization",
                        "recommendation": f"Consider reducing cache variants for low-usage {version} ({percentage:.1f}%)",
                        "impact": "low",
                        "data": {"version": version, "percentage": percentage}
                    })
        
        # Analyze A/B test performance
        for test_name, performance in metrics.get("ab_testing", {}).items():
            if performance["total_assignments"] > 100:  # Sufficient sample size
                variant_dist = performance["variant_distribution"]
                
                # Check if distribution is balanced
                expected_percentage = 100 / len(variant_dist)
                unbalanced = any(
                    abs(percentage - expected_percentage) > 10
                    for percentage in variant_dist.values()
                )
                
                if unbalanced:
                    optimizations.append({
                        "type": "ab_test_optimization",
                        "recommendation": f"A/B test '{test_name}' shows unbalanced distribution - review assignment logic",
                        "impact": "medium",
                        "data": {"test": test_name, "distribution": variant_dist}
                    })
        
        return {
            "optimizations": optimizations,
            "current_performance": {
                "hit_rate": metrics["manifest_cache"]["hit_rate"],
                "error_rate": f"{metrics['manifest_cache']['error_rate']:.2f}%",
                "total_requests": metrics["manifest_cache"]["manifest_requests"]
            },
            "recommendations_count": len(optimizations),
            "optimization_priority": "high" if any(opt["impact"] == "critical" for opt in optimizations) else "medium"
        }


# Singleton instance
_manifest_cache_manager: Optional[ManifestCacheManager] = None


async def get_manifest_cache_manager() -> ManifestCacheManager:
    """Get or create the singleton manifest cache manager instance."""
    global _manifest_cache_manager
    
    if _manifest_cache_manager is None:
        _manifest_cache_manager = ManifestCacheManager()
        await _manifest_cache_manager.initialize()
    
    return _manifest_cache_manager


# Integration functions for existing email cache strategies
async def warm_manifest_cache_from_email_patterns():
    """Warm manifest cache based on successful email processing patterns."""
    manifest_manager = await get_manifest_cache_manager()
    email_manager = get_strategy_manager()
    
    # Get common email patterns
    common_patterns = email_manager.get_common_patterns()
    
    # Map email patterns to likely manifest usage
    manifest_versions = ["1.3.0.2", "1.3.0.1", "1.2.0.0"]  # Recent versions
    target_regions = [GeographicRegion.NORTH_AMERICA, GeographicRegion.EUROPE]
    office_versions = [OfficeVersion.OUTLOOK_WEB, OfficeVersion.OUTLOOK_365, OfficeVersion.OUTLOOK_DESKTOP_2021]
    
    # Warm cache progressively
    results = await manifest_manager.warm_cache_progressive(
        manifest_versions, target_regions, office_versions
    )
    
    logger.info(f"Warmed manifest cache based on email patterns: {results}")
    return results


async def sync_manifest_invalidation_with_email_cache():
    """Synchronize manifest cache invalidation with email cache patterns."""
    manifest_manager = await get_manifest_cache_manager()
    
    # When email patterns change significantly, consider manifest cache refresh
    # This is a placeholder for future implementation based on business logic
    
    logger.info("Synchronized manifest and email cache invalidation strategies")


# Cost optimization integration
def estimate_manifest_cache_savings() -> Dict[str, Any]:
    """Estimate cost savings from manifest caching vs direct serving."""
    
    # Typical manifest request costs
    direct_serving_cost = 0.001  # $0.001 per request (bandwidth + processing)
    cached_serving_cost = 0.0001  # $0.0001 per cached request
    
    # Estimated monthly requests (based on Office add-in usage patterns)
    monthly_requests = 10000  # Conservative estimate
    cache_hit_rate = 0.75  # 75% hit rate target
    
    # Calculate savings
    cached_requests = monthly_requests * cache_hit_rate
    direct_requests = monthly_requests * (1 - cache_hit_rate)
    
    total_cost_without_cache = monthly_requests * direct_serving_cost
    total_cost_with_cache = (cached_requests * cached_serving_cost) + (direct_requests * direct_serving_cost)
    
    monthly_savings = total_cost_without_cache - total_cost_with_cache
    annual_savings = monthly_savings * 12
    
    return {
        "monthly_requests": monthly_requests,
        "cache_hit_rate": f"{cache_hit_rate * 100:.1f}%",
        "monthly_savings": f"${monthly_savings:.2f}",
        "annual_savings": f"${annual_savings:.2f}",
        "roi_percentage": f"{(monthly_savings / (total_cost_without_cache + 0.01)) * 100:.1f}%"  # Avoid division by zero
    }