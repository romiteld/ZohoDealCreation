"""
Azure Maps geocoding client with Key Vault integration and Redis caching.
Provides forward and reverse geocoding capabilities for location enrichment.
"""

import os
import json
import hashlib
import asyncio
import logging
from typing import Dict, Optional, List, Any, Tuple
from datetime import timedelta

import httpx
from pydantic import BaseModel

from well_shared.cache.redis_manager import get_cache_manager
from app.config_manager import get_extraction_config
from app.security_config import SecurityConfig

logger = logging.getLogger(__name__)


class AzureMapsClient:
    """Azure Maps client with caching and retry logic."""

    def __init__(self):
        self.config = get_extraction_config()
        self.security = SecurityConfig()
        self.base_url = self.config.azure_maps_base_url
        self.api_version = self.config.azure_maps_api_version
        self.timeout = 6.0
        self.max_retries = 2
        self.cache_ttl = timedelta(seconds=self.config.azure_maps_cache_ttl_sec)
        self._api_key: Optional[str] = None
        self._key_loaded = False

    async def _ensure_api_key(self) -> Optional[str]:
        """Load API key from Key Vault once."""
        if not self._key_loaded:
            self._key_loaded = True
            if not self.config.enable_azure_maps:
                logger.info("Azure Maps is disabled in configuration")
                return None

            try:
                # Try Key Vault first
                self._api_key = await self.security.get_secret(
                    self.config.azure_maps_key_secret_name
                )
                if not self._api_key:
                    # Fallback to environment variable
                    self._api_key = os.getenv('AZURE_MAPS_KEY')

                if not self._api_key:
                    logger.warning("Azure Maps API key not found in Key Vault or environment")
                else:
                    logger.info("Azure Maps API key loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Azure Maps API key: {e}")

        return self._api_key

    def _cache_key(self, prefix: str, params: Dict) -> str:
        """Generate deterministic cache key."""
        key_data = json.dumps(params, sort_keys=True)
        hash_val = hashlib.sha256(key_data.encode()).hexdigest()
        return f"azure_maps:{prefix}:{hash_val}"

    async def _http_get(
        self,
        path: str,
        params: Dict[str, Any],
        api_key: str
    ) -> Optional[Dict]:
        """Execute HTTP GET with retries."""
        # Azure Maps uses subscription-key as query parameter
        params['subscription-key'] = api_key
        url = f"{self.base_url}{path}"

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException:
                if attempt == self.max_retries:
                    logger.error(f"Azure Maps timeout after {self.max_retries + 1} attempts")
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"Azure Maps request failed: {e}")
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

        return None

    async def geocode_address(
        self,
        query: str,
        country_filter: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_m: Optional[int] = None
    ) -> Optional[List[Dict]]:
        """
        Forward geocode an address or location query.

        Args:
            query: Address or place name to geocode
            country_filter: ISO country code(s) to filter results (e.g., "US,CA")
            lat: Latitude for location bias
            lon: Longitude for location bias
            radius_m: Radius in meters for location bias

        Returns:
            List of geocoding results with lat/lon and address components
        """
        api_key = await self._ensure_api_key()
        if not api_key:
            return None

        # Skip if query looks like a URL
        if query and ('http://' in query or 'https://' in query or '.com' in query):
            logger.debug(f"Skipping geocoding for URL-like query: {query}")
            return None

        # Check cache
        cache_params = {
            "q": query,
            "country": country_filter,
            "lat": lat,
            "lon": lon,
            "radius": radius_m
        }
        cache_key = self._cache_key("geocode", cache_params)

        cache_manager = await get_cache_manager()
        if cache_manager:
            cached = await cache_manager.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for geocode query: {query}")
                return json.loads(cached)

        # Determine endpoint and params
        if lat is not None and lon is not None:
            # Use fuzzy search with location bias
            endpoint = "/search/fuzzy/json"
            params = {
                "api-version": self.api_version,
                "query": query,
                "lat": lat,
                "lon": lon
            }
            if radius_m:
                params["radius"] = radius_m
        else:
            # Use standard address search
            endpoint = "/search/address/json"
            params = {
                "api-version": self.api_version,
                "query": query
            }

        if country_filter:
            params["countrySet"] = country_filter or self.config.azure_maps_default_country

        # Make request
        try:
            data = await self._http_get(endpoint, params, api_key)
            if not data:
                return None

            # Parse results
            results = []
            for item in data.get("results", []):
                position = item.get("position", {})
                results.append({
                    "latitude": position.get("lat"),
                    "longitude": position.get("lon"),
                    "address": item.get("address", {}),
                    "confidence": item.get("confidence") or item.get("score"),
                    "type": item.get("type"),
                    "poi": item.get("poi", {})
                })

            # Cache results
            if cache_manager and results:
                await cache_manager.set(
                    cache_key,
                    json.dumps(results),
                    ttl=self.cache_ttl
                )

            return results

        except Exception as e:
            logger.error(f"Geocoding failed for '{query}': {e}")
            return None

    async def reverse_geocode(
        self,
        lat: float,
        lon: float
    ) -> Optional[Dict]:
        """
        Reverse geocode coordinates to address.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Address components and formatted address
        """
        api_key = await self._ensure_api_key()
        if not api_key:
            return None

        # Check cache
        cache_params = {"lat": lat, "lon": lon}
        cache_key = self._cache_key("reverse", cache_params)

        cache_manager = await get_cache_manager()
        if cache_manager:
            cached = await cache_manager.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for reverse geocode: {lat},{lon}")
                return json.loads(cached)

        # Make request
        params = {
            "api-version": self.api_version,
            "query": f"{lat},{lon}"
        }

        try:
            data = await self._http_get(
                "/search/address/reverse/json",
                params,
                api_key
            )

            if not data or not data.get("addresses"):
                return None

            address = data["addresses"][0].get("address", {})
            result = {
                "latitude": lat,
                "longitude": lon,
                "address": address,
                "formatted_address": address.get("freeformAddress")
            }

            # Cache result
            if cache_manager:
                await cache_manager.set(
                    cache_key,
                    json.dumps(result),
                    ttl=self.cache_ttl
                )

            return result

        except Exception as e:
            logger.error(f"Reverse geocoding failed for {lat},{lon}: {e}")
            return None


# Singleton instance
_client: Optional[AzureMapsClient] = None


async def get_azure_maps_client() -> AzureMapsClient:
    """Get or create Azure Maps client instance."""
    global _client
    if _client is None:
        _client = AzureMapsClient()
    return _client