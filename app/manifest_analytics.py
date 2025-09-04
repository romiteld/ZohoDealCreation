"""
Manifest analytics and monitoring module for tracking Outlook add-in usage.
Monitors manifest request patterns, cache performance, version adoption,
and provides cost optimization recommendations.
"""

import os
import json
import hashlib
import logging
import asyncio
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics
from opentelemetry.metrics import get_meter
from opentelemetry.trace import get_tracer
from fastapi import Request
from user_agents import parse

# Import existing monitoring infrastructure
from .monitoring import MonitoringService
from .redis_cache_manager import RedisCacheManager

logger = logging.getLogger(__name__)


@dataclass
class ManifestRequest:
    """Data class for tracking manifest requests."""
    timestamp: datetime
    user_agent: str
    client_ip: str
    office_version: Optional[str] = None
    office_platform: Optional[str] = None
    cache_hit: bool = False
    response_time_ms: int = 0
    manifest_version: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CachePerformance:
    """Data class for cache performance metrics."""
    hit_rate: float
    avg_response_time_cached: float
    avg_response_time_uncached: float
    redis_hits: int
    file_system_hits: int
    total_requests: int
    cost_savings_usd: float


@dataclass
class VersionAdoption:
    """Data class for version adoption metrics."""
    version: str
    request_count: int
    unique_clients: int
    first_seen: datetime
    last_seen: datetime
    adoption_percentage: float


class ManifestAnalyticsService:
    """Analytics service for monitoring Outlook add-in manifest requests."""
    
    def __init__(self, monitoring_service: MonitoringService = None, cache_manager: RedisCacheManager = None):
        """Initialize manifest analytics service."""
        self.monitoring = monitoring_service
        self.cache_manager = cache_manager
        
        # Initialize OpenTelemetry
        self.tracer = get_tracer("manifest-analytics", "1.0.0")
        self.meter = get_meter("manifest-analytics", "1.0.0")
        
        # Create custom metrics
        self._create_custom_metrics()
        
        # In-memory storage for real-time analytics
        # In production, this would be backed by a database
        self.request_history: List[ManifestRequest] = []
        self.version_stats: Dict[str, Dict] = defaultdict(dict)
        self.client_stats: Dict[str, Dict] = defaultdict(dict)
        
        # Configuration
        self.max_history_size = 10000
        self.cache_ttl_hours = 24
        
    def _create_custom_metrics(self):
        """Create custom OpenTelemetry metrics for manifest monitoring."""
        # Request metrics
        self.manifest_requests_counter = self.meter.create_counter(
            "manifest_requests_total",
            description="Total number of manifest requests",
            unit="requests"
        )
        
        self.manifest_response_time = self.meter.create_histogram(
            "manifest_response_time_seconds",
            description="Manifest response time",
            unit="seconds"
        )
        
        # Cache metrics
        self.manifest_cache_hits = self.meter.create_counter(
            "manifest_cache_hits_total",
            description="Total manifest cache hits",
            unit="hits"
        )
        
        self.manifest_cache_misses = self.meter.create_counter(
            "manifest_cache_misses_total",
            description="Total manifest cache misses",
            unit="misses"
        )
        
        # Version metrics
        self.manifest_version_requests = self.meter.create_counter(
            "manifest_version_requests_total",
            description="Total requests by manifest version",
            unit="requests"
        )
        
        # Client metrics
        self.unique_clients_gauge = self.meter.create_up_down_counter(
            "manifest_unique_clients",
            description="Number of unique clients accessing manifest",
            unit="clients"
        )
        
        # Error metrics
        self.manifest_errors = self.meter.create_counter(
            "manifest_errors_total",
            description="Total manifest serving errors",
            unit="errors"
        )
    
    def parse_user_agent(self, user_agent: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse User-Agent string to extract Office version and platform.
        
        Args:
            user_agent: HTTP User-Agent header value
            
        Returns:
            Tuple of (office_version, platform)
        """
        try:
            parsed = parse(user_agent)
            
            # Extract Office version from User-Agent
            office_version = None
            office_platform = None
            
            # Look for Office-specific patterns
            ua_lower = user_agent.lower()
            
            # Office version detection
            if 'microsoft office' in ua_lower:
                # Extract version like "Microsoft Office/16.0"
                import re
                version_match = re.search(r'microsoft office/(\d+\.\d+)', ua_lower)
                if version_match:
                    office_version = version_match.group(1)
            elif 'outlook' in ua_lower:
                # Extract Outlook version
                version_match = re.search(r'outlook[/\s](\d+\.\d+)', ua_lower)
                if version_match:
                    office_version = f"Outlook {version_match.group(1)}"
            
            # Platform detection
            if parsed.os.family:
                office_platform = f"{parsed.os.family} {parsed.os.version_string}".strip()
            
            return office_version, office_platform
            
        except Exception as e:
            logger.warning(f"Failed to parse user agent: {e}")
            return None, None
    
    def extract_manifest_version(self, manifest_path: str) -> Optional[str]:
        """
        Extract version from manifest XML file.
        
        Args:
            manifest_path: Path to the manifest.xml file
            
        Returns:
            Version string or None if not found
        """
        try:
            if not os.path.exists(manifest_path):
                return None
                
            tree = ET.parse(manifest_path)
            root = tree.getroot()
            
            # Find the Version element
            # Handle namespace properly
            for elem in root.iter():
                if elem.tag.endswith('Version'):
                    return elem.text
                    
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract manifest version: {e}")
            return None
    
    async def track_manifest_request(self, 
                                   request: Request,
                                   response_time_ms: int,
                                   cache_hit: bool = False,
                                   error: Optional[str] = None) -> ManifestRequest:
        """
        Track a manifest request with full context.
        
        Args:
            request: FastAPI request object
            response_time_ms: Response time in milliseconds
            cache_hit: Whether the request was served from cache
            error: Error message if request failed
            
        Returns:
            ManifestRequest object for the tracked request
        """
        with self.tracer.start_as_current_span("track_manifest_request") as span:
            # Extract request details
            user_agent = request.headers.get("User-Agent", "")
            client_ip = request.client.host if request.client else "unknown"
            
            # Parse user agent for Office details
            office_version, office_platform = self.parse_user_agent(user_agent)
            
            # Get manifest version
            manifest_path = os.path.join(os.path.dirname(__file__), "..", "addin", "manifest.xml")
            manifest_version = self.extract_manifest_version(manifest_path)
            
            # Create request record
            manifest_request = ManifestRequest(
                timestamp=datetime.utcnow(),
                user_agent=user_agent,
                client_ip=client_ip,
                office_version=office_version,
                office_platform=office_platform,
                cache_hit=cache_hit,
                response_time_ms=response_time_ms,
                manifest_version=manifest_version,
                error=error
            )
            
            # Record metrics
            await self._record_metrics(manifest_request)
            
            # Store in history (with size limit)
            self.request_history.append(manifest_request)
            if len(self.request_history) > self.max_history_size:
                self.request_history.pop(0)
            
            # Update version and client statistics
            self._update_stats(manifest_request)
            
            # Set span attributes
            span.set_attribute("office_version", office_version or "unknown")
            span.set_attribute("office_platform", office_platform or "unknown")
            span.set_attribute("cache_hit", cache_hit)
            span.set_attribute("response_time_ms", response_time_ms)
            span.set_attribute("manifest_version", manifest_version or "unknown")
            
            if error:
                span.set_attribute("error", error)
                span.set_status(trace.Status(trace.StatusCode.ERROR, error))
            else:
                span.set_status(trace.Status(trace.StatusCode.OK))
            
            return manifest_request
    
    async def _record_metrics(self, request: ManifestRequest):
        """Record OpenTelemetry metrics for the request."""
        # Request counter
        labels = {
            "office_version": request.office_version or "unknown",
            "office_platform": request.office_platform or "unknown",
            "cache_hit": str(request.cache_hit).lower()
        }
        
        if request.error:
            labels["status"] = "error"
            self.manifest_errors.add(1, {"error_type": request.error})
        else:
            labels["status"] = "success"
        
        self.manifest_requests_counter.add(1, labels)
        
        # Response time
        self.manifest_response_time.record(
            request.response_time_ms / 1000,
            {"cache_hit": str(request.cache_hit).lower()}
        )
        
        # Cache metrics
        if request.cache_hit:
            self.manifest_cache_hits.add(1, {"source": "redis"})  # Assume Redis for now
        else:
            self.manifest_cache_misses.add(1)
        
        # Version metrics
        if request.manifest_version:
            self.manifest_version_requests.add(1, {"version": request.manifest_version})
    
    def _update_stats(self, request: ManifestRequest):
        """Update internal statistics for version and client tracking."""
        # Update version statistics
        if request.manifest_version:
            version_key = request.manifest_version
            if version_key not in self.version_stats:
                self.version_stats[version_key] = {
                    "request_count": 0,
                    "unique_clients": set(),
                    "first_seen": request.timestamp,
                    "last_seen": request.timestamp
                }
            
            stats = self.version_stats[version_key]
            stats["request_count"] += 1
            stats["unique_clients"].add(request.client_ip)
            stats["last_seen"] = request.timestamp
            
            if request.timestamp < stats["first_seen"]:
                stats["first_seen"] = request.timestamp
        
        # Update client statistics
        client_key = f"{request.client_ip}:{request.office_version or 'unknown'}"
        if client_key not in self.client_stats:
            self.client_stats[client_key] = {
                "first_seen": request.timestamp,
                "last_seen": request.timestamp,
                "request_count": 0,
                "office_version": request.office_version,
                "office_platform": request.office_platform
            }
        
        client_stats = self.client_stats[client_key]
        client_stats["request_count"] += 1
        client_stats["last_seen"] = request.timestamp
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """
        Get current cache status and performance metrics.
        
        Returns:
            Dictionary with cache performance data
        """
        # Get recent requests (last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        recent_requests = [
            req for req in self.request_history
            if req.timestamp >= cutoff_time and not req.error
        ]
        
        if not recent_requests:
            return {
                "status": "no_data",
                "message": "No requests in the last 24 hours",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Calculate cache performance
        total_requests = len(recent_requests)
        cache_hits = sum(1 for req in recent_requests if req.cache_hit)
        cache_misses = total_requests - cache_hits
        
        hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate average response times
        cached_times = [req.response_time_ms for req in recent_requests if req.cache_hit]
        uncached_times = [req.response_time_ms for req in recent_requests if not req.cache_hit]
        
        avg_cached = sum(cached_times) / len(cached_times) if cached_times else 0
        avg_uncached = sum(uncached_times) / len(uncached_times) if uncached_times else 0
        
        # Estimate cost savings (manifest requests are low cost, but still trackable)
        # Assume ~0.1ms of compute time saved per cached request
        compute_savings = cache_hits * 0.0001  # Very rough estimate in USD
        
        performance = CachePerformance(
            hit_rate=round(hit_rate, 2),
            avg_response_time_cached=round(avg_cached, 2),
            avg_response_time_uncached=round(avg_uncached, 2),
            redis_hits=cache_hits,  # Assuming all cache hits are Redis
            file_system_hits=0,     # File system fallback not implemented yet
            total_requests=total_requests,
            cost_savings_usd=round(compute_savings, 6)
        )
        
        # Get Redis cache metrics if available
        redis_metrics = {}
        if self.cache_manager:
            try:
                redis_metrics = await self.cache_manager.get_metrics()
            except Exception as e:
                logger.warning(f"Failed to get Redis metrics: {e}")
        
        return {
            "cache_performance": asdict(performance),
            "redis_metrics": redis_metrics,
            "recommendations": self._get_cache_recommendations(performance),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _get_cache_recommendations(self, performance: CachePerformance) -> List[str]:
        """Generate cache optimization recommendations based on performance."""
        recommendations = []
        
        if performance.hit_rate < 50:
            recommendations.append(
                "Low cache hit rate detected. Consider implementing file system fallback cache."
            )
        
        if performance.avg_response_time_cached > 100:
            recommendations.append(
                "Cached responses are slower than expected. Check Redis latency and connection."
            )
        
        if performance.total_requests > 1000 and performance.hit_rate > 80:
            recommendations.append(
                "High traffic with good cache performance. Consider increasing cache TTL."
            )
        
        if performance.avg_response_time_uncached > 500:
            recommendations.append(
                "Uncached responses are slow. Implement aggressive caching strategy."
            )
        
        if not recommendations:
            recommendations.append("Cache performance is optimal. No immediate action required.")
        
        return recommendations
    
    async def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get detailed performance analytics for the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with comprehensive performance metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_requests = [
            req for req in self.request_history
            if req.timestamp >= cutoff_time
        ]
        
        if not recent_requests:
            return {"error": "No data available for the specified time period"}
        
        # Basic statistics
        total_requests = len(recent_requests)
        successful_requests = [req for req in recent_requests if not req.error]
        error_requests = [req for req in recent_requests if req.error]
        
        # Response time statistics
        response_times = [req.response_time_ms for req in successful_requests]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
            p99_response_time = sorted(response_times)[int(len(response_times) * 0.99)]
        else:
            avg_response_time = p95_response_time = p99_response_time = 0
        
        # Cache statistics
        cache_hits = sum(1 for req in successful_requests if req.cache_hit)
        cache_hit_rate = (cache_hits / len(successful_requests) * 100) if successful_requests else 0
        
        # Error analysis
        error_types = Counter(req.error for req in error_requests if req.error)
        error_rate = (len(error_requests) / total_requests * 100) if total_requests > 0 else 0
        
        # Office version distribution
        office_versions = Counter(
            req.office_version or "Unknown" 
            for req in successful_requests
        )
        
        # Platform distribution
        platforms = Counter(
            req.office_platform or "Unknown"
            for req in successful_requests
        )
        
        # Hourly distribution
        hourly_stats = defaultdict(int)
        for req in recent_requests:
            hour_key = req.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_stats[hour_key] += 1
        
        return {
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
            "request_stats": {
                "total_requests": total_requests,
                "successful_requests": len(successful_requests),
                "error_requests": len(error_requests),
                "error_rate_percent": round(error_rate, 2)
            },
            "response_time_stats": {
                "avg_ms": round(avg_response_time, 2),
                "p95_ms": round(p95_response_time, 2),
                "p99_ms": round(p99_response_time, 2)
            },
            "cache_stats": {
                "hit_rate_percent": round(cache_hit_rate, 2),
                "total_hits": cache_hits,
                "total_misses": len(successful_requests) - cache_hits
            },
            "error_analysis": dict(error_types),
            "office_versions": dict(office_versions.most_common(10)),
            "platforms": dict(platforms.most_common(10)),
            "hourly_distribution": dict(sorted(hourly_stats.items()))
        }
    
    async def get_version_adoption(self) -> Dict[str, Any]:
        """
        Get version adoption metrics across all tracked clients.
        
        Returns:
            Dictionary with version adoption statistics
        """
        if not self.version_stats:
            return {"error": "No version data available"}
        
        total_requests = sum(
            stats["request_count"] for stats in self.version_stats.values()
        )
        
        adoption_metrics = []
        for version, stats in self.version_stats.items():
            adoption_percentage = (stats["request_count"] / total_requests * 100) if total_requests > 0 else 0
            
            adoption_metrics.append(VersionAdoption(
                version=version,
                request_count=stats["request_count"],
                unique_clients=len(stats["unique_clients"]),
                first_seen=stats["first_seen"],
                last_seen=stats["last_seen"],
                adoption_percentage=round(adoption_percentage, 2)
            ))
        
        # Sort by adoption percentage
        adoption_metrics.sort(key=lambda x: x.adoption_percentage, reverse=True)
        
        # Get unique client count
        all_clients = set()
        for stats in self.version_stats.values():
            all_clients.update(stats["unique_clients"])
        
        return {
            "total_unique_clients": len(all_clients),
            "total_requests": total_requests,
            "version_adoption": [asdict(adoption) for adoption in adoption_metrics],
            "most_popular_version": adoption_metrics[0].version if adoption_metrics else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def invalidate_manifest_cache(self, pattern: str = None) -> Dict[str, Any]:
        """
        Invalidate manifest cache entries.
        
        Args:
            pattern: Optional pattern to match cache keys
            
        Returns:
            Dictionary with invalidation results
        """
        if not self.cache_manager:
            return {"error": "Cache manager not available"}
        
        try:
            # Use manifest-specific cache pattern
            cache_pattern = pattern or "well:manifest:*"
            deleted_count = await self.cache_manager.invalidate_cache(cache_pattern)
            
            logger.info(f"Invalidated {deleted_count} manifest cache entries")
            
            return {
                "status": "success",
                "deleted_entries": deleted_count,
                "pattern": cache_pattern,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Singleton instance
_manifest_analytics: Optional[ManifestAnalyticsService] = None


async def get_manifest_analytics() -> ManifestAnalyticsService:
    """Get or create the singleton manifest analytics instance."""
    global _manifest_analytics
    
    if _manifest_analytics is None:
        # Import here to avoid circular dependencies
        from .monitoring import monitoring
        from .redis_cache_manager import get_cache_manager
        
        cache_manager = await get_cache_manager()
        _manifest_analytics = ManifestAnalyticsService(monitoring, cache_manager)
    
    return _manifest_analytics


# Export commonly used functions
track_manifest_request = lambda *args, **kwargs: asyncio.create_task(
    get_manifest_analytics().then(lambda service: service.track_manifest_request(*args, **kwargs))
)