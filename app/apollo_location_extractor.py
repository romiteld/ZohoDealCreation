"""
Apollo.io Location and Website Extraction Service

Specialized module for extracting comprehensive location data and website information
from Apollo.io, including multi-location support, geocoding, and timezone data.
"""

import os
import logging
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime
import httpx
import asyncio

from app.config_manager import get_extraction_config
from app.apollo_service_manager import ApolloServiceManager

logger = logging.getLogger(__name__)


class LocationData:
    """Structure for location information."""

    def __init__(self, data: Dict[str, Any] = None):
        if data is None:
            data = {}

        self.street_address = data.get("street_address", "")
        self.city = data.get("city", "")
        self.state = data.get("state", "")
        self.postal_code = data.get("postal_code", "")
        self.country = data.get("country", "")
        self.country_code = data.get("country_code", "")
        self.timezone = data.get("timezone", "")
        self.latitude = data.get("latitude")
        self.longitude = data.get("longitude")
        self.location_type = data.get("location_type", "office")  # headquarters, office, branch
        self.is_primary = data.get("is_primary", False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "street_address": self.street_address,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "country_code": self.country_code,
            "timezone": self.timezone,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_type": self.location_type,
            "is_primary": self.is_primary,
            "full_address": self.get_full_address(),
            "formatted_address": self.get_formatted_address()
        }

    def get_full_address(self) -> str:
        """Get complete address as a single string."""
        parts = [
            self.street_address,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ", ".join(filter(None, parts))

    def get_formatted_address(self) -> str:
        """Get nicely formatted multi-line address."""
        lines = []
        if self.street_address:
            lines.append(self.street_address)

        city_state_zip = []
        if self.city:
            city_state_zip.append(self.city)
        if self.state:
            city_state_zip.append(self.state)
        if city_state_zip:
            city_line = ", ".join(city_state_zip)
            if self.postal_code:
                city_line += f" {self.postal_code}"
            lines.append(city_line)

        if self.country:
            lines.append(self.country)

        return "\n".join(lines)

    def has_coordinates(self) -> bool:
        """Check if geographic coordinates are available."""
        return self.latitude is not None and self.longitude is not None


class CompanyWebsiteData:
    """Structure for company website and online presence."""

    def __init__(self, data: Dict[str, Any] = None):
        if data is None:
            data = {}

        self.primary_website = data.get("primary_website", "")
        self.primary_domain = data.get("primary_domain", "")
        self.blog_url = data.get("blog_url", "")
        self.careers_page = data.get("careers_page", "")

        # Social media profiles
        self.linkedin_url = data.get("linkedin_url", "")
        self.twitter_url = data.get("twitter_url", "")
        self.facebook_url = data.get("facebook_url", "")
        self.youtube_url = data.get("youtube_url", "")
        self.instagram_url = data.get("instagram_url", "")

        # Additional web properties
        self.subdomains = data.get("subdomains", [])
        self.alternative_domains = data.get("alternative_domains", [])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_website": self.primary_website,
            "primary_domain": self.primary_domain,
            "blog_url": self.blog_url,
            "careers_page": self.careers_page,
            "social_profiles": {
                "linkedin": self.linkedin_url,
                "twitter": self.twitter_url,
                "facebook": self.facebook_url,
                "youtube": self.youtube_url,
                "instagram": self.instagram_url
            },
            "subdomains": self.subdomains,
            "alternative_domains": self.alternative_domains,
            "all_urls": self.get_all_urls()
        }

    def get_all_urls(self) -> List[str]:
        """Get all unique URLs for the company."""
        urls = []

        # Add primary sites
        for url in [self.primary_website, self.blog_url, self.careers_page]:
            if url and url not in urls:
                urls.append(url)

        # Add social profiles
        for url in [self.linkedin_url, self.twitter_url, self.facebook_url,
                   self.youtube_url, self.instagram_url]:
            if url and url not in urls:
                urls.append(url)

        # Add alternative domains
        for domain in self.alternative_domains:
            if domain and not any(domain in u for u in urls):
                urls.append(f"https://{domain}")

        return urls


async def geocode_address(address: str, api_key: Optional[str] = None) -> Optional[Tuple[float, float]]:
    """
    Geocode an address to get latitude and longitude.
    Uses Google Geocoding API or similar service.

    Args:
        address: Address string to geocode
        api_key: Optional API key for geocoding service

    Returns:
        Tuple of (latitude, longitude) or None
    """
    if not address:
        return None

    # If no API key provided, skip geocoding
    if not api_key:
        logger.debug("No geocoding API key provided")
        return None

    try:
        # Example using Google Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": api_key
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                if data["status"] == "OK" and data["results"]:
                    location = data["results"][0]["geometry"]["location"]
                    return (location["lat"], location["lng"])

    except Exception as e:
        logger.error(f"Geocoding failed for {address}: {str(e)}")

    return None


async def extract_company_location_data(
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    include_geocoding: bool = False,
    geocoding_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract comprehensive location and website data for a company.

    Args:
        company_name: Company name to search
        company_domain: Company domain to search
        include_geocoding: Whether to geocode addresses without coordinates
        geocoding_api_key: API key for geocoding service

    Returns:
        Dictionary containing:
        - company_info: Basic company information
        - locations: List of all company locations
        - websites: All website and online presence data
        - metadata: Additional metadata
    """
    if not company_name and not company_domain:
        raise ValueError("Either company_name or company_domain must be provided")

    manager = ApolloServiceManager()
    result = {
        "company_info": {},
        "locations": [],
        "websites": {},
        "metadata": {
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "data_source": "apollo.io",
            "geocoding_enabled": include_geocoding
        }
    }

    # Search for the company
    search_result = await manager.search_organizations(
        query=company_name,
        domains=[company_domain] if company_domain else None,
        per_page=5
    )

    if not search_result or not search_result.get("organizations"):
        logger.warning(f"No organization found for {company_name or company_domain}")
        return result

    # Get the best match (usually first result)
    organization = search_result["organizations"][0]

    # Extract basic company info
    result["company_info"] = {
        "name": organization.get("name"),
        "domain": organization.get("primary_domain"),
        "industry": organization.get("industry"),
        "employee_count": organization.get("estimated_num_employees"),
        "revenue": organization.get("annual_revenue"),
        "founded_year": organization.get("founded_year"),
        "description": organization.get("short_description"),
        "apollo_org_id": organization.get("id")
    }

    # Extract primary location
    primary_location = LocationData({
        "street_address": organization.get("street_address"),
        "city": organization.get("city"),
        "state": organization.get("state"),
        "postal_code": organization.get("postal_code"),
        "country": organization.get("country"),
        "country_code": organization.get("country_code"),
        "timezone": organization.get("time_zone"),
        "latitude": organization.get("latitude"),
        "longitude": organization.get("longitude"),
        "location_type": "headquarters",
        "is_primary": True
    })

    # Add geocoding if coordinates are missing
    if include_geocoding and not primary_location.has_coordinates():
        coords = await geocode_address(
            primary_location.get_full_address(),
            geocoding_api_key
        )
        if coords:
            primary_location.latitude, primary_location.longitude = coords
            logger.info(f"Geocoded primary location: {coords}")

    result["locations"].append(primary_location.to_dict())

    # Try to find additional locations through employees in different cities
    if organization.get("primary_domain"):
        # Search for employees to find other office locations
        people_search = await manager.search_people(
            company_domains=[organization["primary_domain"]],
            per_page=100
        )

        if people_search and people_search.get("people"):
            # Extract unique locations from employees
            location_map = {}
            for person in people_search["people"]:
                city = person.get("city")
                state = person.get("state")
                country = person.get("country")

                if city:
                    location_key = f"{city},{state},{country}"
                    if location_key not in location_map:
                        location_map[location_key] = {
                            "city": city,
                            "state": state,
                            "country": country,
                            "employee_count": 0
                        }
                    location_map[location_key]["employee_count"] += 1

            # Add significant locations (with multiple employees)
            for location_key, location_info in location_map.items():
                if location_info["employee_count"] >= 3:  # Threshold for office location
                    # Skip if it's the primary location
                    if (location_info["city"] == primary_location.city and
                        location_info["state"] == primary_location.state):
                        continue

                    additional_location = LocationData({
                        "city": location_info["city"],
                        "state": location_info["state"],
                        "country": location_info["country"],
                        "location_type": "office",
                        "is_primary": False
                    })

                    # Geocode if enabled
                    if include_geocoding:
                        coords = await geocode_address(
                            additional_location.get_full_address(),
                            geocoding_api_key
                        )
                        if coords:
                            additional_location.latitude, additional_location.longitude = coords

                    # Add employee count as metadata
                    location_dict = additional_location.to_dict()
                    location_dict["employee_count"] = location_info["employee_count"]
                    result["locations"].append(location_dict)

    # Extract website and online presence data
    website_data = CompanyWebsiteData({
        "primary_website": organization.get("website_url"),
        "primary_domain": organization.get("primary_domain"),
        "blog_url": organization.get("blog_url"),
        "careers_page": organization.get("careers_page_url"),
        "linkedin_url": organization.get("linkedin_url"),
        "twitter_url": organization.get("twitter_url"),
        "facebook_url": organization.get("facebook_url"),
        "youtube_url": organization.get("youtube_url"),
        "instagram_url": organization.get("instagram_url"),
        "subdomains": organization.get("subdomains", []),
        "alternative_domains": organization.get("alternative_domains", [])
    })

    result["websites"] = website_data.to_dict()

    # Add metadata
    result["metadata"]["total_locations"] = len(result["locations"])
    result["metadata"]["has_multiple_locations"] = len(result["locations"]) > 1
    result["metadata"]["total_websites"] = len(website_data.get_all_urls())

    # Calculate location coverage
    countries = set()
    states = set()
    cities = set()

    for location in result["locations"]:
        if location.get("country"):
            countries.add(location["country"])
        if location.get("state"):
            states.add(location["state"])
        if location.get("city"):
            cities.add(location["city"])

    result["metadata"]["geographic_coverage"] = {
        "countries": list(countries),
        "states": list(states),
        "cities": list(cities),
        "country_count": len(countries),
        "state_count": len(states),
        "city_count": len(cities)
    }

    logger.info(
        f"Extracted location data for {result['company_info']['name']}: "
        f"{len(result['locations'])} locations, {len(result['websites']['all_urls'])} websites"
    )

    return result


async def extract_person_location_data(
    email: Optional[str] = None,
    name: Optional[str] = None,
    include_company_locations: bool = True
) -> Dict[str, Any]:
    """
    Extract location data for a person and optionally their company.

    Args:
        email: Person's email address
        name: Person's name
        include_company_locations: Whether to also extract company locations

    Returns:
        Dictionary containing person and company location data
    """
    if not email and not name:
        raise ValueError("Either email or name must be provided")

    manager = ApolloServiceManager()
    result = {
        "person_info": {},
        "person_location": {},
        "company_locations": [],
        "company_websites": {},
        "metadata": {
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "data_source": "apollo.io"
        }
    }

    # Enrich the person
    person_data = await manager.enrich_person(
        email=email,
        name=name
    )

    if not person_data or not person_data.get("person"):
        logger.warning(f"No person found for {email or name}")
        return result

    person = person_data["person"]
    organization = person_data.get("organization", {})

    # Extract person info
    result["person_info"] = {
        "name": person.get("name"),
        "email": person.get("email"),
        "title": person.get("title"),
        "company": organization.get("name"),
        "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None
    }

    # Extract person's location
    person_location = LocationData({
        "city": person.get("city"),
        "state": person.get("state"),
        "country": person.get("country"),
        "timezone": person.get("time_zone"),
        "location_type": "personal",
        "is_primary": True
    })

    result["person_location"] = person_location.to_dict()

    # Extract company locations if requested
    if include_company_locations and organization.get("primary_domain"):
        company_data = await extract_company_location_data(
            company_name=organization.get("name"),
            company_domain=organization.get("primary_domain")
        )

        result["company_locations"] = company_data.get("locations", [])
        result["company_websites"] = company_data.get("websites", {})

    # Add metadata
    result["metadata"]["person_has_location"] = bool(person_location.city)
    result["metadata"]["company_location_count"] = len(result["company_locations"])

    logger.info(
        f"Extracted location data for {result['person_info']['name']}: "
        f"Person in {person_location.city}, {len(result['company_locations'])} company locations"
    )

    return result


async def batch_extract_locations(
    entities: List[Dict[str, str]],
    entity_type: str = "company",
    include_geocoding: bool = False,
    geocoding_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Batch extract location data for multiple entities.

    Args:
        entities: List of dictionaries with entity identifiers
        entity_type: Type of entity ("company" or "person")
        include_geocoding: Whether to geocode addresses
        geocoding_api_key: API key for geocoding service

    Returns:
        List of extraction results
    """
    results = []

    for entity in entities:
        try:
            if entity_type == "company":
                result = await extract_company_location_data(
                    company_name=entity.get("name"),
                    company_domain=entity.get("domain"),
                    include_geocoding=include_geocoding,
                    geocoding_api_key=geocoding_api_key
                )
            elif entity_type == "person":
                result = await extract_person_location_data(
                    email=entity.get("email"),
                    name=entity.get("name"),
                    include_company_locations=entity.get("include_company", True)
                )
            else:
                raise ValueError(f"Invalid entity type: {entity_type}")

            result["query"] = entity
            results.append(result)

        except Exception as e:
            logger.error(f"Failed to extract location for {entity}: {str(e)}")
            results.append({
                "query": entity,
                "error": str(e),
                "status": "failed"
            })

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    logger.info(f"Batch extraction complete: {len(results)} entities processed")
    return results