"""
Company Location Enrichment Service using Azure Maps
Enriches missing company locations by geocoding company names
"""

import os
import logging
from typing import Optional, Dict
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LocationEnrichmentService:
    """Enrich missing company locations using Azure Maps geocoding."""

    def __init__(self):
        self.base_url = "https://atlas.microsoft.com"
        self.api_version = "1.0"
        self.timeout = 6.0
        self.max_retries = 2
        # In-memory cache for session duration
        self._location_cache: Dict[str, Optional[str]] = {}

    async def _get_api_key(self) -> Optional[str]:
        """Get Azure Maps API key from environment."""
        api_key = os.getenv('AZURE_MAPS_KEY')
        if not api_key:
            logger.warning("Azure Maps API key not found in environment")
        return api_key

    async def enrich_company_location(self, company_name: str) -> Optional[str]:
        """
        Enrich company location by geocoding company headquarters.

        Args:
            company_name: Name of the company

        Returns:
            Formatted location as "City, State" or None if not found

        Examples:
            "Microsoft" → "Redmond, WA"
            "Tesla" → "Austin, TX"
            "Stripe" → "San Francisco, CA"
        """
        if not company_name or not company_name.strip():
            return None

        # Normalize company name for caching
        cache_key = company_name.lower().strip()

        # Check cache first
        if cache_key in self._location_cache:
            logger.debug(f"Cache hit for {company_name}")
            return self._location_cache[cache_key]

        # Get API key
        api_key = await self._get_api_key()
        if not api_key:
            self._location_cache[cache_key] = None
            return None

        try:
            # Query: "Company Name headquarters"
            query = f"{company_name} headquarters"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/search/address/json",
                    params={
                        "api-version": self.api_version,
                        "query": query,
                        "subscription-key": api_key,
                        "countrySet": "US",  # Focus on US companies
                        "limit": 1  # Only need best match
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])

                    if results:
                        address = results[0].get("address", {})
                        city = address.get("municipality") or address.get("localName")
                        state = address.get("countrySubdivision")

                        if city and state:
                            location = f"{city}, {state}"
                            logger.info(f"Enriched {company_name}: {location}")
                            self._location_cache[cache_key] = location
                            return location

            # No location found
            logger.debug(f"No location found for {company_name}")
            self._location_cache[cache_key] = None
            return None

        except Exception as e:
            logger.error(f"Failed to enrich location for {company_name}: {e}")
            self._location_cache[cache_key] = None
            return None

    async def enrich_job_locations(self, jobs: list) -> list:
        """
        Enrich missing locations for a list of jobs.

        Args:
            jobs: List of job dictionaries with 'company' and 'location' fields

        Returns:
            Same list with enriched locations where possible
        """
        for job in jobs:
            company = job.get("company")
            location = job.get("location", "").strip()

            # Only enrich if location is missing
            if company and not location:
                enriched_location = await self.enrich_company_location(company)
                if enriched_location:
                    job["location"] = enriched_location
                    logger.info(f"Enriched {company} → {enriched_location}")

        return jobs
