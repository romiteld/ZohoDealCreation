"""
Apollo.io Enrichment for Free Plan
Uses only endpoints available on the free tier:
- Organization Enrich
- Accounts Search
- Contacts Search
"""

import os
import logging
from typing import Dict, Optional, List, Any
import httpx
import re

from app.config_manager import get_extraction_config

logger = logging.getLogger(__name__)


def extract_domain_from_email(email: str) -> Optional[str]:
    """Extract domain from email address"""
    if not email or '@' not in email:
        return None
    return email.split('@')[1].lower()


async def enrich_organization_by_domain(domain: str) -> Optional[Dict[str, Any]]:
    """
    Enrich organization information using the free Organization Enrich endpoint.

    Args:
        domain: Company domain (e.g., "example.com")

    Returns:
        Organization data including website, industry, employee count, etc.
    """
    try:
        config = get_extraction_config()
        apollo_api_key = config.apollo_api_key

        if not apollo_api_key:
            logger.warning("Apollo API key not configured")
            return None

        url = "https://api.apollo.io/v1/organizations/enrich"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_api_key
        }

        payload = {"domain": domain}

        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Enriching organization for domain: {domain}")
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                logger.error(f"Organization enrich failed {response.status_code}: {response.text}")
                return None

            data = response.json()
            org = data.get("organization")

            if not org:
                logger.info(f"No organization found for domain: {domain}")
                return None

            # Extract comprehensive organization data
            enriched = {
                # Core company info
                "company_name": org.get("name"),
                "domain": org.get("primary_domain") or domain,
                "website": org.get("website_url"),
                "description": org.get("short_description"),

                # Social profiles
                "linkedin_url": org.get("linkedin_url"),
                "twitter_url": org.get("twitter_url"),
                "facebook_url": org.get("facebook_url"),
                "blog_url": org.get("blog_url"),

                # Location
                "street_address": org.get("street_address"),
                "city": org.get("city"),
                "state": org.get("state"),
                "postal_code": org.get("postal_code"),
                "country": org.get("country"),
                "phone": org.get("phone"),

                # Company metrics
                "employee_count": org.get("estimated_num_employees"),
                "revenue": org.get("annual_revenue"),
                "revenue_range": org.get("annual_revenue_printed"),
                "funding_total": org.get("total_funding"),
                "funding_stage": org.get("latest_funding_stage"),
                "founded_year": org.get("founded_year"),

                # Industry
                "industry": org.get("industry"),
                "industries": org.get("industries", []),
                "keywords": org.get("keywords", []),
                "technologies": org.get("technologies", []),

                # Apollo metadata
                "apollo_org_id": org.get("id"),
                "num_contacts": org.get("num_contacts")
            }

            # Clean up None values
            enriched = {k: v for k, v in enriched.items() if v is not None}

            logger.info(f"Organization enrichment successful: {enriched.get('company_name')} with {len(enriched)} data points")
            return enriched

    except Exception as e:
        logger.error(f"Organization enrichment error: {str(e)}")
        return None


async def search_contacts(
    organization_name: Optional[str] = None,
    domain: Optional[str] = None,
    q_keywords: Optional[str] = None,
    limit: int = 10
) -> Optional[List[Dict[str, Any]]]:
    """
    Search for contacts using the free Contacts Search endpoint.

    Args:
        organization_name: Company name to search within
        domain: Company domain to search within
        q_keywords: Keywords to search (name, email, title, etc.)
        limit: Maximum number of results

    Returns:
        List of contact information
    """
    try:
        config = get_extraction_config()
        apollo_api_key = config.apollo_api_key

        if not apollo_api_key:
            logger.warning("Apollo API key not configured")
            return None

        url = "https://api.apollo.io/v1/contacts/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_api_key
        }

        payload = {
            "page": 1,
            "per_page": min(limit, 25)  # Max 25 per page on free tier
        }

        if q_keywords:
            payload["q_keywords"] = q_keywords

        if organization_name:
            payload["q_organization_name"] = organization_name

        if domain:
            payload["q_organization_domains"] = domain

        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Searching contacts: keywords={q_keywords}, org={organization_name}, domain={domain}")
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                logger.error(f"Contacts search failed {response.status_code}: {response.text}")
                return None

            data = response.json()
            contacts = data.get("contacts", [])

            if not contacts:
                logger.info("No contacts found")
                return None

            # Extract contact information
            enriched_contacts = []
            for contact in contacts:
                org = contact.get("organization", {})
                enriched = {
                    # Personal info
                    "name": contact.get("name"),
                    "first_name": contact.get("first_name"),
                    "last_name": contact.get("last_name"),
                    "email": contact.get("email"),
                    "title": contact.get("title"),
                    "seniority": contact.get("seniority"),

                    # Contact details
                    "phone_numbers": contact.get("phone_numbers", []),
                    "phone": contact.get("sanitized_phone"),

                    # Social profiles
                    "linkedin_url": contact.get("linkedin_url"),
                    "twitter_url": contact.get("twitter_url"),
                    "facebook_url": contact.get("facebook_url"),

                    # Location
                    "city": contact.get("city"),
                    "state": contact.get("state"),
                    "country": contact.get("country"),

                    # Company info
                    "company_name": org.get("name"),
                    "company_domain": org.get("primary_domain"),
                    "company_industry": org.get("industry"),

                    # Apollo metadata
                    "apollo_id": contact.get("id"),
                    "contact_stage": contact.get("contact_stage"),
                    "last_activity": contact.get("last_activity_date")
                }

                # Clean up None values
                enriched = {k: v for k, v in enriched.items() if v is not None}
                enriched_contacts.append(enriched)

            logger.info(f"Found {len(enriched_contacts)} contacts")
            return enriched_contacts

    except Exception as e:
        logger.error(f"Contacts search error: {str(e)}")
        return None


async def apollo_free_enrichment(
    email: Optional[str] = None,
    name: Optional[str] = None,
    company: Optional[str] = None
) -> Dict[str, Any]:
    """
    Comprehensive enrichment using only free Apollo.io endpoints.

    Args:
        email: Email address
        name: Person's name
        company: Company name or domain

    Returns:
        Enrichment data from available free endpoints
    """
    result = {
        "person": None,
        "company": None,
        "contacts": [],
        "data_completeness": 0
    }

    # Extract domain from email if available
    domain = None
    if email:
        domain = extract_domain_from_email(email)
    elif company and '.' in company:
        domain = company

    # Step 1: Enrich organization if we have a domain
    if domain:
        org_data = await enrich_organization_by_domain(domain)
        if org_data:
            result["company"] = org_data

            # Update company name if we found it
            if not company and org_data.get("company_name"):
                company = org_data["company_name"]

    # Step 2: Search for contacts
    if email or name or company or domain:
        contacts = await search_contacts(
            organization_name=company,
            domain=domain,
            q_keywords=email or name,
            limit=10
        )

        if contacts:
            # Try to find the specific person if we have identifying info
            if email or name:
                # Look for exact match first
                for contact in contacts:
                    if email and contact.get("email") == email:
                        result["person"] = contact
                        break
                    elif name and contact.get("name") == name:
                        result["person"] = contact
                        break

                # If no exact match, take the first result as best guess
                if not result["person"] and contacts:
                    result["person"] = contacts[0]

            # Store all contacts for reference
            result["contacts"] = contacts

    # Step 3: Calculate data completeness
    total_fields = 0
    filled_fields = 0

    if result["person"]:
        important_fields = ["email", "phone", "linkedin_url", "company_name", "title"]
        for field in important_fields:
            total_fields += 1
            if result["person"].get(field):
                filled_fields += 1

    if result["company"]:
        important_fields = ["website", "phone", "linkedin_url", "employee_count", "industry"]
        for field in important_fields:
            total_fields += 1
            if result["company"].get(field):
                filled_fields += 1

    result["data_completeness"] = (filled_fields / total_fields * 100) if total_fields > 0 else 0

    logger.info(
        f"Apollo free enrichment complete: "
        f"Person: {bool(result['person'])}, "
        f"Company: {bool(result['company'])}, "
        f"Contacts: {len(result['contacts'])}, "
        f"Completeness: {result['data_completeness']:.0f}%"
    )

    return result