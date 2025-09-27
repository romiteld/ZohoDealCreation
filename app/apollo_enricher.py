"""
Apollo.io Comprehensive Contact & Company Enrichment Service

This module maximizes Apollo.io's starter plan capabilities with:
- Unlimited people search
- Unlimited company search
- LinkedIn URL extraction
- Phone number discovery
- Website and location enrichment
"""

import os
import logging
from typing import Dict, Optional, List, Any
import httpx
import json
from datetime import datetime

from app.config_manager import get_extraction_config

logger = logging.getLogger(__name__)


async def enrich_contact_with_apollo(email: str) -> Optional[Dict[str, str]]:
    """
    Enrich contact information using Apollo.io's People Enrichment API.

    Args:
        email: The email address to search for contact information

    Returns:
        Dict containing enriched contact data with fields:
        - client_name: Full name of the contact
        - email: Email address
        - phone: Phone number
        - firm_company: Organization name
        - website: Company website
        - job_title: Job title
        - location: City location

        Returns None if enrichment fails or email is not provided.
    """
    if not email:
        logger.debug("No email provided for Apollo enrichment")
        return None

    try:
        # Get Apollo API configuration
        config = get_extraction_config()
        apollo_api_key = config.apollo_api_key

        if not apollo_api_key:
            logger.warning("Apollo API key not configured")
            return None

        # Prepare the API request
        url = "https://api.apollo.io/v1/people/match"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_api_key
        }

        payload = {
            "email": email
        }

        # Make the API request with 10 second timeout
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Enriching contact via Apollo for email: {email}")
            response = await client.post(url, json=payload, headers=headers)

            # Check response status
            if response.status_code != 200:
                logger.error(f"Apollo API returned status {response.status_code}: {response.text}")
                return None

            # Parse response
            data = response.json()

            # Check if a person was found
            person = data.get("person")
            if not person:
                logger.info(f"No person found in Apollo for email: {email}")
                return None

            # Extract and map the fields
            organization = person.get("organization", {})

            enriched_data = {
                "client_name": person.get("name") or "",
                "email": person.get("email") or email,
                "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
                "firm_company": organization.get("name", ""),
                "website": organization.get("website_url", ""),
                "job_title": person.get("title", ""),
                "location": person.get("city", "")
            }

            # Filter out empty values but keep the structure
            enriched_data = {k: v for k, v in enriched_data.items() if v}

            logger.info(f"Successfully enriched contact for {email}: {list(enriched_data.keys())}")
            return enriched_data

    except httpx.TimeoutException:
        logger.error(f"Apollo API request timed out for email: {email}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Apollo API request error for {email}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during Apollo enrichment for {email}: {str(e)}")
        return None


async def apollo_unlimited_people_search(
    email: Optional[str] = None,
    name: Optional[str] = None,
    company_domain: Optional[str] = None,
    job_title: Optional[str] = None,
    location: Optional[str] = None,
    page: int = 1,
    per_page: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Unlimited people search using Apollo.io's comprehensive search API.
    Maximizes data extraction with LinkedIn URLs, phone numbers, and more.

    Args:
        email: Email to search for
        name: Person's name
        company_domain: Company domain
        job_title: Job title to filter by
        location: Location to filter by
        page: Page number for pagination (default: 1)
        per_page: Results per page (default: 10, max: 100)

    Returns:
        Comprehensive person data including LinkedIn, phone, website
    """
    try:
        config = get_extraction_config()
        apollo_api_key = config.apollo_api_key

        if not apollo_api_key:
            logger.warning("Apollo API key not configured")
            return None

        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_api_key
        }

        # Build search payload maximizing filters
        payload = {
            "page": page,
            "per_page": min(per_page, 100)  # Apollo max is 100
        }

        if email:
            payload["q_keywords"] = email
        elif name:
            payload["q_keywords"] = name

        if company_domain:
            payload["organization_domains"] = [company_domain]

        if job_title:
            payload["person_titles"] = [job_title]

        if location:
            payload["person_locations"] = [location]

        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.info(f"Apollo unlimited search for: {email or name}")
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                logger.error(f"Apollo search error {response.status_code}: {response.text}")
                return None

            data = response.json()
            people = data.get("people", [])

            if not people:
                logger.info("No people found in Apollo search")
                return None

            # Get the best match (first result)
            best_match = people[0]
            organization = best_match.get("organization", {})

            # Extract ALL available data
            enriched = {
                # Personal Information
                "client_name": best_match.get("name"),
                "first_name": best_match.get("first_name"),
                "last_name": best_match.get("last_name"),
                "email": best_match.get("email") or email,
                "job_title": best_match.get("title"),
                "headline": best_match.get("headline"),
                "seniority": best_match.get("seniority"),

                # Contact Information
                "phone_numbers": best_match.get("phone_numbers", []),
                "phone": best_match.get("phone_numbers", [{}])[0].get("sanitized_number") if best_match.get("phone_numbers") else None,
                "mobile_phone": next((p.get("sanitized_number") for p in best_match.get("phone_numbers", []) if p.get("type") == "mobile"), None),
                "work_phone": next((p.get("sanitized_number") for p in best_match.get("phone_numbers", []) if p.get("type") == "work"), None),

                # Social Profiles
                "linkedin_url": best_match.get("linkedin_url"),
                "twitter_url": best_match.get("twitter_url"),
                "facebook_url": best_match.get("facebook_url"),
                "github_url": best_match.get("github_url"),

                # Location
                "city": best_match.get("city"),
                "state": best_match.get("state"),
                "country": best_match.get("country"),
                "location": f"{best_match.get('city', '')}, {best_match.get('state', '')}".strip(", "),
                "time_zone": best_match.get("time_zone"),

                # Company Information
                "firm_company": organization.get("name"),
                "company_domain": organization.get("primary_domain"),
                "company_website": organization.get("website_url"),
                "company_linkedin": organization.get("linkedin_url"),
                "company_twitter": organization.get("twitter_url"),
                "company_facebook": organization.get("facebook_url"),
                "company_size": organization.get("estimated_num_employees"),
                "company_industry": organization.get("industry"),
                "company_keywords": organization.get("keywords"),
                "company_location": f"{organization.get('city', '')}, {organization.get('state', '')}".strip(", "),

                # Additional Intelligence
                "technologies": organization.get("technologies", []),
                "company_phone": organization.get("phone"),
                "company_founded_year": organization.get("founded_year"),
                "company_revenue": organization.get("annual_revenue"),
                "company_funding": organization.get("total_funding"),

                # Apollo Metadata
                "apollo_id": best_match.get("id"),
                "organization_id": organization.get("id"),
                "confidence_score": best_match.get("score"),
                "last_updated": best_match.get("updated_at"),

                # Alternative matches (for validation)
                "alternative_matches": [
                    {
                        "name": p.get("name"),
                        "email": p.get("email"),
                        "company": p.get("organization", {}).get("name"),
                        "title": p.get("title"),
                        "linkedin": p.get("linkedin_url")
                    }
                    for p in people[1:4]  # Next 3 matches
                ] if len(people) > 1 else []
            }

            # Clean up None values but keep the structure
            enriched = {k: v for k, v in enriched.items() if v is not None}

            logger.info(f"Apollo unlimited search found: {enriched.get('client_name')} with {len(enriched)} data points")
            return enriched

    except Exception as e:
        logger.error(f"Apollo unlimited search error: {str(e)}")
        return None


async def apollo_unlimited_company_search(
    company_name: Optional[str] = None,
    domain: Optional[str] = None,
    location: Optional[str] = None,
    industry: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Unlimited company search using Apollo.io's organization search API.
    Extracts comprehensive company data including all employees.

    Args:
        company_name: Company name to search
        domain: Company domain
        location: Company location
        industry: Industry filter

    Returns:
        Comprehensive company data with employee information
    """
    try:
        config = get_extraction_config()
        apollo_api_key = config.apollo_api_key

        if not apollo_api_key:
            logger.warning("Apollo API key not configured")
            return None

        url = "https://api.apollo.io/v1/mixed_companies/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_api_key
        }

        payload = {
            "page": 1,
            "per_page": 5
        }

        if company_name:
            payload["q_organization_keyword_tags"] = company_name

        if domain:
            payload["organization_domains"] = [domain]

        if location:
            payload["organization_locations"] = [location]

        if industry:
            payload["organization_industry_tag_ids"] = [industry]

        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.info(f"Apollo company search for: {company_name or domain}")
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                logger.error(f"Apollo company search error {response.status_code}")
                return None

            data = response.json()
            companies = data.get("organizations", [])

            if not companies:
                logger.info("No companies found")
                return None

            company = companies[0]

            # Now search for key employees at this company
            employees_url = "https://api.apollo.io/v1/mixed_people/search"
            employees_payload = {
                "organization_domains": [company.get("primary_domain")],
                "person_titles": ["ceo", "founder", "recruiter", "hr", "talent", "director", "manager", "vp"],
                "page": 1,
                "per_page": 25
            }

            employees_response = await client.post(employees_url, json=employees_payload, headers=headers)
            employees_data = employees_response.json() if employees_response.status_code == 200 else {}
            employees = employees_data.get("people", [])

            enriched = {
                # Company Core Information
                "company_name": company.get("name"),
                "domain": company.get("primary_domain"),
                "website": company.get("website_url"),
                "description": company.get("short_description"),

                # Contact Information
                "phone": company.get("phone"),
                "email_pattern": company.get("email_pattern"),

                # Social Profiles
                "linkedin_url": company.get("linkedin_url"),
                "twitter_url": company.get("twitter_url"),
                "facebook_url": company.get("facebook_url"),
                "youtube_url": company.get("youtube_url"),
                "blog_url": company.get("blog_url"),

                # Location Details
                "street_address": company.get("street_address"),
                "city": company.get("city"),
                "state": company.get("state"),
                "postal_code": company.get("postal_code"),
                "country": company.get("country"),
                "full_address": f"{company.get('street_address', '')}, {company.get('city', '')}, {company.get('state', '')} {company.get('postal_code', '')}".strip(", "),

                # Company Metrics
                "employee_count": company.get("estimated_num_employees"),
                "revenue": company.get("annual_revenue"),
                "revenue_range": company.get("annual_revenue_printed"),
                "funding_total": company.get("total_funding"),
                "funding_stage": company.get("latest_funding_stage"),
                "founded_year": company.get("founded_year"),

                # Industry & Market
                "industry": company.get("industry"),
                "industries": company.get("industries"),
                "keywords": company.get("keywords"),
                "technologies": company.get("technologies", []),
                "naics_codes": company.get("naics_codes"),
                "sic_codes": company.get("sic_codes"),

                # Key Employees
                "key_employees": [
                    {
                        "name": emp.get("name"),
                        "title": emp.get("title"),
                        "email": emp.get("email"),
                        "phone": emp.get("phone_numbers", [{}])[0].get("sanitized_number") if emp.get("phone_numbers") else None,
                        "linkedin": emp.get("linkedin_url"),
                        "seniority": emp.get("seniority")
                    }
                    for emp in employees[:10]  # Top 10 key employees
                ],

                "decision_makers": [
                    {
                        "name": emp.get("name"),
                        "title": emp.get("title"),
                        "email": emp.get("email"),
                        "linkedin": emp.get("linkedin_url")
                    }
                    for emp in employees
                    if any(role in emp.get("title", "").lower() for role in ["ceo", "cto", "cfo", "founder", "president", "vp", "director"])
                ][:5],

                "recruiters": [
                    {
                        "name": emp.get("name"),
                        "title": emp.get("title"),
                        "email": emp.get("email"),
                        "phone": emp.get("phone_numbers", [{}])[0].get("sanitized_number") if emp.get("phone_numbers") else None,
                        "linkedin": emp.get("linkedin_url")
                    }
                    for emp in employees
                    if any(term in emp.get("title", "").lower() for term in ["recruit", "talent", "hr", "human resource", "people"])
                ],

                # Apollo Metadata
                "apollo_org_id": company.get("id"),
                "total_contacts": company.get("num_contacts"),
                "confidence_score": company.get("score")
            }

            enriched = {k: v for k, v in enriched.items() if v}

            logger.info(f"Apollo company search found: {enriched.get('company_name')} with {len(employees)} employees")
            return enriched

    except Exception as e:
        logger.error(f"Apollo company search error: {str(e)}")
        return None


async def apollo_deep_enrichment(
    email: Optional[str] = None,
    name: Optional[str] = None,
    company: Optional[str] = None,
    extract_all: bool = True
) -> Dict[str, Any]:
    """
    Comprehensive enrichment using all Apollo.io capabilities.
    Automatically falls back to free plan endpoints if paid endpoints fail.

    Args:
        email: Email address
        name: Person's name
        company: Company name or domain
        extract_all: Extract all available data including employees

    Returns:
        Complete enrichment with person, company, and network data
    """
    result = {
        "person": None,
        "company": None,
        "network": [],
        "data_completeness": 0
    }

    # Try paid endpoints first
    paid_api_failed = False

    # Step 1: Search for the person (paid endpoint)
    if email or name:
        person_data = await apollo_unlimited_people_search(
            email=email,
            name=name,
            company_domain=company
        )
        if person_data:
            result["person"] = person_data

            # Extract company domain for further enrichment
            if not company and person_data.get("company_domain"):
                company = person_data.get("company_domain")
        else:
            # Check if it's an API access error
            paid_api_failed = True

    # Step 2: Search for the company (paid endpoint)
    if not paid_api_failed and (company or (result["person"] and result["person"].get("firm_company"))):
        company_search_term = company or result["person"].get("firm_company")
        company_data = await apollo_unlimited_company_search(
            company_name=company_search_term if not company_search_term.endswith(".com") else None,
            domain=company_search_term if company_search_term.endswith(".com") else None
        )
        if company_data:
            result["company"] = company_data
        else:
            paid_api_failed = True

    # Fallback to free plan enrichment if paid endpoints fail
    if paid_api_failed or (not result["person"] and not result["company"]):
        logger.info("Falling back to Apollo free plan enrichment")
        try:
            from app.apollo_free_plan_enricher import apollo_free_enrichment

            free_result = await apollo_free_enrichment(
                email=email,
                name=name,
                company=company
            )

            # Merge free plan results
            if free_result:
                if not result["person"] and free_result.get("person"):
                    result["person"] = free_result["person"]

                if not result["company"] and free_result.get("company"):
                    result["company"] = free_result["company"]

                # Add contacts as network if available
                if free_result.get("contacts") and extract_all:
                    result["network"] = [
                        {
                            "name": c.get("name"),
                            "title": c.get("title"),
                            "email": c.get("email"),
                            "phone": c.get("phone"),
                            "linkedin": c.get("linkedin_url")
                        }
                        for c in free_result["contacts"][:5]
                    ]

                # Use free plan completeness if no paid data
                if not result["person"] and not result["company"]:
                    result["data_completeness"] = free_result.get("data_completeness", 0)
        except Exception as e:
            logger.error(f"Free plan enrichment fallback error: {str(e)}")

    # Fallback to Firecrawl if Apollo has no data
    if not result["person"] and not result["company"] and (email or company):
        logger.info("Apollo returned no data, trying Firecrawl web research")
        try:
            from app.firecrawl_research import CompanyResearchService

            research_service = CompanyResearchService()

            # Extract domain from email if available
            research_domain = None
            if email and '@' in email:
                email_domain = email.split('@')[1]
                # Skip generic email domains
                generic_domains = [
                    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                    'aol.com', 'icloud.com', 'me.com', 'mac.com', 'msn.com',
                    'live.com', 'protonmail.com', 'ymail.com'
                ]
                if email_domain not in generic_domains:
                    research_domain = email_domain
                    logger.info(f"Using email domain for Firecrawl research: {research_domain}")

            # Research the company/domain
            if research_domain or company:
                firecrawl_result = await research_service.research_company(
                    email_domain=research_domain,
                    company_guess=company
                )

                if firecrawl_result:
                    logger.info(f"Firecrawl found data: {firecrawl_result}")

                    # Map Firecrawl data to Apollo format
                    if firecrawl_result.get('company_name') or firecrawl_result.get('website'):
                        result["company"] = {
                            "name": firecrawl_result.get('company_name', company),
                            "website": firecrawl_result.get('website', ''),
                            "phone": firecrawl_result.get('phone', ''),
                            "industry": firecrawl_result.get('industry', ''),
                            "description": firecrawl_result.get('description', ''),
                            "linkedin_url": firecrawl_result.get('linkedin_url', ''),
                            "address": firecrawl_result.get('address', ''),
                            "city": firecrawl_result.get('city', ''),
                            "state": firecrawl_result.get('state', ''),
                            "source": "firecrawl"
                        }

                    # Try to find person info if we have a name
                    if name and not result["person"]:
                        candidate_info = await research_service.search_candidate_info(name, company)
                        if candidate_info:
                            result["person"] = {
                                "name": name,
                                "email": email,
                                "phone": candidate_info.get('phone', ''),
                                "linkedin_url": candidate_info.get('linkedin', ''),
                                "title": candidate_info.get('title', ''),
                                "company": company or firecrawl_result.get('company_name', ''),
                                "city": candidate_info.get('location', ''),
                                "source": "firecrawl"
                            }

                    # Update completeness score
                    if result["company"] or result["person"]:
                        result["data_completeness"] = 60  # Firecrawl data is less complete than Apollo

        except Exception as e:
            logger.error(f"Firecrawl enrichment error: {str(e)}")

    # Step 3: Calculate data completeness (if we have paid data)
    if result["person"] or result["company"]:
        total_fields = 0
        filled_fields = 0

        if result["person"]:
            important_fields = ["email", "phone", "linkedin_url", "firm_company", "job_title", "location"]
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

        if total_fields > 0:
            result["data_completeness"] = (filled_fields / total_fields * 100)

    # Step 4: Build network connections if requested (for paid data)
    if extract_all and result["company"] and result["company"].get("key_employees"):
        result["network"] = result["company"]["key_employees"][:5]

    logger.info(
        f"Apollo deep enrichment complete: "
        f"Person: {bool(result['person'])}, "
        f"Company: {bool(result['company'])}, "
        f"Completeness: {result['data_completeness']:.0f}%"
    )

    return result


async def extract_linkedin_urls(
    email: Optional[str] = None,
    name: Optional[str] = None,
    company: Optional[str] = None,
    job_title: Optional[str] = None,
    location: Optional[str] = None,
    save_to_db: bool = True
) -> Dict[str, Any]:
    """
    Specialized function to extract LinkedIn URLs and all social media profiles
    using Apollo.io's search capabilities.

    This function maximizes LinkedIn discovery by:
    1. Searching for people by email, name, or company
    2. Extracting all available social media URLs
    3. Finding company social profiles
    4. Storing results in database for quick retrieval

    Args:
        email: Email address to search
        name: Person's full name
        company: Company name or domain
        job_title: Job title for better matching
        location: Location for filtering
        save_to_db: Whether to save results to database

    Returns:
        Dict containing:
        - linkedin_url: Person's LinkedIn profile URL
        - twitter_url: Person's Twitter profile URL
        - facebook_url: Person's Facebook profile URL
        - github_url: Person's GitHub profile URL
        - company_linkedin_url: Company LinkedIn page
        - company_twitter_url: Company Twitter page
        - company_facebook_url: Company Facebook page
        - phone_numbers: List of all phone numbers found
        - alternative_profiles: Other potential matches
        - confidence_score: Confidence in the match (0-100)
    """
    logger.info(f"Extracting LinkedIn URLs for: email={email}, name={name}, company={company}")

    result = {
        "linkedin_url": None,
        "twitter_url": None,
        "facebook_url": None,
        "github_url": None,
        "company_linkedin_url": None,
        "company_twitter_url": None,
        "company_facebook_url": None,
        "phone_numbers": [],
        "alternative_profiles": [],
        "confidence_score": 0,
        "source": "apollo",
        "extracted_at": datetime.utcnow().isoformat()
    }

    try:
        # First, check if we already have this data in the database
        if email and save_to_db:
            try:
                from app.integrations import get_postgres_client
                postgres_client = await get_postgres_client()

                if postgres_client and postgres_client.pool:
                    async with postgres_client.pool.acquire() as conn:
                        cached_data = await conn.fetchrow(
                            """
                            SELECT
                                linkedin_url, twitter_url, facebook_url, github_url,
                                company_linkedin_url, company_twitter_url, company_facebook_url,
                                phone, mobile_phone, work_phone, enriched_data
                            FROM apollo_enrichments
                            WHERE email = $1
                                AND updated_at > NOW() - INTERVAL '7 days'
                            """,
                            email
                        )

                        if cached_data:
                            logger.info(f"Found cached LinkedIn data for {email}")
                            result.update({
                                "linkedin_url": cached_data["linkedin_url"],
                                "twitter_url": cached_data["twitter_url"],
                                "facebook_url": cached_data["facebook_url"],
                                "github_url": cached_data["github_url"],
                                "company_linkedin_url": cached_data["company_linkedin_url"],
                                "company_twitter_url": cached_data["company_twitter_url"],
                                "company_facebook_url": cached_data["company_facebook_url"],
                                "phone_numbers": [
                                    p for p in [
                                        cached_data["phone"],
                                        cached_data["mobile_phone"],
                                        cached_data["work_phone"]
                                    ] if p
                                ],
                                "confidence_score": 100,
                                "source": "cache"
                            })
                            return result
            except Exception as db_error:
                logger.warning(f"Database cache check failed: {db_error}")

        # Use Apollo's unlimited people search for maximum data extraction
        person_data = await apollo_unlimited_people_search(
            email=email,
            name=name,
            company_domain=company if company and "." in company else None,
            job_title=job_title,
            location=location
        )

        if person_data:
            # Extract personal social profiles
            result["linkedin_url"] = person_data.get("linkedin_url")
            result["twitter_url"] = person_data.get("twitter_url")
            result["facebook_url"] = person_data.get("facebook_url")
            result["github_url"] = person_data.get("github_url")

            # Extract company social profiles
            result["company_linkedin_url"] = person_data.get("company_linkedin")
            result["company_twitter_url"] = person_data.get("company_twitter")
            result["company_facebook_url"] = person_data.get("company_facebook")

            # Extract all phone numbers
            phone_numbers = []
            if person_data.get("phone"):
                phone_numbers.append({"type": "primary", "number": person_data["phone"]})
            if person_data.get("mobile_phone"):
                phone_numbers.append({"type": "mobile", "number": person_data["mobile_phone"]})
            if person_data.get("work_phone"):
                phone_numbers.append({"type": "work", "number": person_data["work_phone"]})
            if person_data.get("phone_numbers"):
                for phone_obj in person_data["phone_numbers"]:
                    if phone_obj.get("sanitized_number"):
                        phone_numbers.append({
                            "type": phone_obj.get("type", "other"),
                            "number": phone_obj["sanitized_number"]
                        })
            result["phone_numbers"] = phone_numbers

            # Include alternative matches for validation
            result["alternative_profiles"] = person_data.get("alternative_matches", [])

            # Calculate confidence score based on data completeness
            confidence_factors = [
                result["linkedin_url"] is not None,  # +20 points
                email and person_data.get("email") == email,  # +20 points
                name and person_data.get("client_name"),  # +15 points
                company and person_data.get("firm_company"),  # +15 points
                len(phone_numbers) > 0,  # +10 points
                result["company_linkedin_url"] is not None,  # +10 points
                person_data.get("apollo_id") is not None  # +10 points
            ]
            weights = [20, 20, 15, 15, 10, 10, 10]
            result["confidence_score"] = sum(w for f, w in zip(confidence_factors, weights) if f)

            # Add additional metadata
            result["person_name"] = person_data.get("client_name")
            result["person_email"] = person_data.get("email", email)
            result["person_title"] = person_data.get("job_title")
            result["company_name"] = person_data.get("firm_company")
            result["company_domain"] = person_data.get("company_domain")
            result["location"] = person_data.get("location")

        # If we didn't find the person but have a company, search for the company
        elif company and not person_data:
            company_data = await apollo_unlimited_company_search(
                company_name=company if not company.endswith(".com") else None,
                domain=company if company.endswith(".com") else None
            )

            if company_data:
                result["company_linkedin_url"] = company_data.get("linkedin_url")
                result["company_twitter_url"] = company_data.get("twitter_url")
                result["company_facebook_url"] = company_data.get("facebook_url")
                result["company_name"] = company_data.get("company_name")
                result["company_domain"] = company_data.get("domain")

                # Extract recruiters and decision makers as alternatives
                alternatives = []
                for recruiter in company_data.get("recruiters", [])[:3]:
                    if recruiter.get("linkedin"):
                        alternatives.append({
                            "name": recruiter.get("name"),
                            "title": recruiter.get("title"),
                            "linkedin": recruiter.get("linkedin"),
                            "email": recruiter.get("email"),
                            "role": "recruiter"
                        })
                for decision_maker in company_data.get("decision_makers", [])[:2]:
                    if decision_maker.get("linkedin"):
                        alternatives.append({
                            "name": decision_maker.get("name"),
                            "title": decision_maker.get("title"),
                            "linkedin": decision_maker.get("linkedin"),
                            "email": decision_maker.get("email"),
                            "role": "decision_maker"
                        })
                result["alternative_profiles"] = alternatives
                result["confidence_score"] = 50  # Medium confidence for company-only match

        # Save to database for future use
        if save_to_db and email and (result["linkedin_url"] or result["company_linkedin_url"]):
            try:
                from app.integrations import get_postgres_client
                postgres_client = await get_postgres_client()

                if postgres_client and postgres_client.pool:
                    async with postgres_client.pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO apollo_enrichments (
                                email, linkedin_url, twitter_url, facebook_url, github_url,
                                company_linkedin_url, company_twitter_url, company_facebook_url,
                                phone, mobile_phone, work_phone, enriched_data, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                            ON CONFLICT (email) DO UPDATE SET
                                linkedin_url = EXCLUDED.linkedin_url,
                                twitter_url = EXCLUDED.twitter_url,
                                facebook_url = EXCLUDED.facebook_url,
                                github_url = EXCLUDED.github_url,
                                company_linkedin_url = EXCLUDED.company_linkedin_url,
                                company_twitter_url = EXCLUDED.company_twitter_url,
                                company_facebook_url = EXCLUDED.company_facebook_url,
                                phone = EXCLUDED.phone,
                                mobile_phone = EXCLUDED.mobile_phone,
                                work_phone = EXCLUDED.work_phone,
                                enriched_data = EXCLUDED.enriched_data,
                                updated_at = NOW()
                            """,
                            email,
                            result["linkedin_url"],
                            result["twitter_url"],
                            result["facebook_url"],
                            result["github_url"],
                            result["company_linkedin_url"],
                            result["company_twitter_url"],
                            result["company_facebook_url"],
                            phone_numbers[0]["number"] if len(phone_numbers) > 0 else None,
                            next((p["number"] for p in phone_numbers if p["type"] == "mobile"), None),
                            next((p["number"] for p in phone_numbers if p["type"] == "work"), None),
                            json.dumps(result)
                        )
                        logger.info(f"Saved LinkedIn URLs to database for {email}")
            except Exception as db_error:
                logger.error(f"Failed to save LinkedIn URLs to database: {db_error}")

        logger.info(
            f"LinkedIn extraction complete: "
            f"LinkedIn={'Yes' if result['linkedin_url'] else 'No'}, "
            f"Company LinkedIn={'Yes' if result['company_linkedin_url'] else 'No'}, "
            f"Confidence={result['confidence_score']}%"
        )

    except Exception as e:
        logger.error(f"LinkedIn URL extraction failed: {str(e)}")
        result["error"] = str(e)

    return result