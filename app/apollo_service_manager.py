"""
Apollo.io Comprehensive Service Manager

This module provides full integration with Apollo.io's API suite,
maximizing the capabilities of the starter plan for comprehensive
client data enrichment and management.
"""

import os
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
import httpx
from enum import Enum

from app.config_manager import get_extraction_config

logger = logging.getLogger(__name__)


class ApolloAPIEndpoints:
    """Apollo.io API endpoint definitions."""
    BASE_URL = "https://api.apollo.io"

    # People APIs
    PEOPLE_SEARCH = "/v1/mixed_people/search"
    PEOPLE_ENRICHMENT = "/v1/people/match"

    # Organization APIs
    ORGANIZATION_SEARCH = "/v1/mixed_companies/search"
    ORGANIZATION_ENRICHMENT = "/v1/organizations/enrich"

    # Contact Management
    CREATE_CONTACT = "/v1/contacts"
    UPDATE_CONTACT = "/v1/contacts/{contact_id}"
    GET_CONTACT = "/v1/contacts/{contact_id}"

    # Sequences
    GET_SEQUENCES = "/v1/emailer_campaigns"
    ADD_TO_SEQUENCE = "/v1/emailer_campaigns/{sequence_id}/add_contact_ids"
    REMOVE_FROM_SEQUENCE = "/v1/emailer_campaigns/{sequence_id}/remove_contact_ids"

    # Lists
    GET_LISTS = "/v1/lists"
    CREATE_LIST = "/v1/lists"
    ADD_TO_LIST = "/v1/lists/{list_id}/add_contact_ids"


class PersonTitle(Enum):
    """Common person titles for filtering."""
    CEO = "ceo"
    CFO = "cfo"
    CTO = "cto"
    VP = "vice_president"
    DIRECTOR = "director"
    MANAGER = "manager"
    RECRUITER = "recruiter"
    HR = "human_resources"


class ApolloServiceManager:
    """
    Comprehensive Apollo.io API service manager.
    Maximizes starter plan capabilities for client data enrichment.
    """

    def __init__(self):
        """Initialize Apollo service manager with API configuration."""
        config = get_extraction_config()
        self.api_key = config.apollo_api_key
        self.base_url = ApolloAPIEndpoints.BASE_URL
        self.timeout = 15.0  # Increased timeout for complex searches

        if not self.api_key:
            logger.warning("Apollo API key not configured - service will be limited")

    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for Apollo API requests."""
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Make an async request to Apollo API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            payload: Request body for POST/PUT requests
            params: Query parameters for GET requests

        Returns:
            Response data or None if request fails
        """
        if not self.api_key:
            logger.error("Apollo API key not configured")
            return None

        url = f"{self.base_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    response = await client.get(
                        url, headers=self._get_headers(), params=params
                    )
                elif method == "POST":
                    response = await client.post(
                        url, headers=self._get_headers(), json=payload
                    )
                elif method == "PUT":
                    response = await client.put(
                        url, headers=self._get_headers(), json=payload
                    )
                elif method == "DELETE":
                    response = await client.delete(
                        url, headers=self._get_headers()
                    )
                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return None

                if response.status_code != 200:
                    logger.error(
                        f"Apollo API error {response.status_code}: {response.text}"
                    )
                    return None

                return response.json()

        except httpx.TimeoutException:
            logger.error(f"Apollo API timeout for {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Apollo API request error: {str(e)}")
            return None

    # ==================== PEOPLE SEARCH ====================

    async def search_people(
        self,
        query: Optional[str] = None,
        titles: Optional[List[str]] = None,
        company_domains: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        revenue_range: Optional[Dict[str, int]] = None,
        employee_range: Optional[Dict[str, int]] = None,
        technologies: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 25
    ) -> Optional[Dict]:
        """
        Search for people using Apollo's advanced filters.
        Maximizes starter plan search capabilities.

        Args:
            query: Text search query
            titles: List of job titles to filter by
            company_domains: List of company domains
            locations: List of locations (cities, states, countries)
            industries: List of industries
            revenue_range: Dict with min/max revenue in millions
            employee_range: Dict with min/max employee count
            technologies: List of technologies used by companies
            page: Page number for pagination
            per_page: Results per page (max 100)

        Returns:
            Search results with people data or None
        """
        payload = {
            "page": page,
            "per_page": min(per_page, 100)  # API limit
        }

        if query:
            payload["q_keywords"] = query

        if titles:
            payload["person_titles"] = titles

        if company_domains:
            payload["organization_domains"] = company_domains

        if locations:
            payload["person_locations"] = locations

        if industries:
            payload["organization_industry_tag_ids"] = industries

        if revenue_range:
            if "min" in revenue_range:
                payload["organization_annual_revenue_min"] = revenue_range["min"]
            if "max" in revenue_range:
                payload["organization_annual_revenue_max"] = revenue_range["max"]

        if employee_range:
            if "min" in employee_range:
                payload["organization_num_employees_min"] = employee_range["min"]
            if "max" in employee_range:
                payload["organization_num_employees_max"] = employee_range["max"]

        if technologies:
            payload["technologies"] = technologies

        logger.info(f"Searching Apollo for people with filters: {list(payload.keys())}")
        result = await self._make_request("POST", ApolloAPIEndpoints.PEOPLE_SEARCH, payload)

        if result:
            people_count = len(result.get("people", []))
            logger.info(f"Found {people_count} people in Apollo search")

        return result

    # ==================== PEOPLE ENRICHMENT ====================

    async def enrich_person(
        self,
        email: Optional[str] = None,
        name: Optional[str] = None,
        company: Optional[str] = None,
        linkedin_url: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Enrich a person's data using multiple identifiers.
        Enhanced version of the existing enrichment.

        Args:
            email: Email address
            name: Full name
            company: Company name or domain
            linkedin_url: LinkedIn profile URL

        Returns:
            Enriched person data or None
        """
        if not any([email, name, linkedin_url]):
            logger.warning("No identifier provided for enrichment")
            return None

        payload = {}

        if email:
            payload["email"] = email
        if name:
            payload["name"] = name
        if company:
            payload["organization_name"] = company
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        logger.info(f"Enriching person with: {list(payload.keys())}")
        result = await self._make_request("POST", ApolloAPIEndpoints.PEOPLE_ENRICHMENT, payload)

        if result and result.get("person"):
            logger.info(f"Successfully enriched person: {result['person'].get('name', 'Unknown')}")

        return result

    # ==================== ORGANIZATION SEARCH ====================

    async def search_organizations(
        self,
        query: Optional[str] = None,
        domains: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        revenue_range: Optional[Dict[str, int]] = None,
        employee_range: Optional[Dict[str, int]] = None,
        technologies: Optional[List[str]] = None,
        funding_stage: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 25
    ) -> Optional[Dict]:
        """
        Search for organizations using advanced filters.

        Args:
            query: Text search query
            domains: List of company domains
            industries: List of industries
            locations: List of locations
            revenue_range: Dict with min/max revenue
            employee_range: Dict with min/max employees
            technologies: Technologies used
            funding_stage: Funding stages (seed, series_a, etc.)
            page: Page number
            per_page: Results per page

        Returns:
            Organization search results or None
        """
        payload = {
            "page": page,
            "per_page": min(per_page, 100)
        }

        if query:
            payload["q_organization_keyword_tags"] = query

        if domains:
            payload["organization_domains"] = domains

        if industries:
            payload["organization_industry_tag_ids"] = industries

        if locations:
            payload["organization_locations"] = locations

        if revenue_range:
            if "min" in revenue_range:
                payload["organization_annual_revenue_min"] = revenue_range["min"]
            if "max" in revenue_range:
                payload["organization_annual_revenue_max"] = revenue_range["max"]

        if employee_range:
            if "min" in employee_range:
                payload["organization_num_employees_min"] = employee_range["min"]
            if "max" in employee_range:
                payload["organization_num_employees_max"] = employee_range["max"]

        if technologies:
            payload["technologies"] = technologies

        if funding_stage:
            payload["organization_funding_stage"] = funding_stage

        logger.info(f"Searching organizations with filters: {list(payload.keys())}")
        result = await self._make_request("POST", ApolloAPIEndpoints.ORGANIZATION_SEARCH, payload)

        if result:
            org_count = len(result.get("organizations", []))
            logger.info(f"Found {org_count} organizations")

        return result

    # ==================== ORGANIZATION ENRICHMENT ====================

    async def enrich_organization(
        self,
        domain: Optional[str] = None,
        name: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Enrich organization data.

        Args:
            domain: Company domain
            name: Company name

        Returns:
            Enriched organization data or None
        """
        if not (domain or name):
            logger.warning("No organization identifier provided")
            return None

        payload = {}
        if domain:
            payload["domain"] = domain
        if name:
            payload["name"] = name

        logger.info(f"Enriching organization: {domain or name}")
        result = await self._make_request("POST", ApolloAPIEndpoints.ORGANIZATION_ENRICHMENT, payload)

        if result and result.get("organization"):
            org_name = result["organization"].get("name", "Unknown")
            logger.info(f"Successfully enriched organization: {org_name}")

        return result

    # ==================== INTELLIGENT SEARCH ====================

    async def find_decision_makers(
        self,
        company_domain: str,
        titles: Optional[List[str]] = None
    ) -> Optional[List[Dict]]:
        """
        Find key decision makers at a company.

        Args:
            company_domain: Company domain
            titles: Specific titles to search for

        Returns:
            List of decision makers or None
        """
        if not titles:
            titles = [
                PersonTitle.CEO.value,
                PersonTitle.CFO.value,
                PersonTitle.CTO.value,
                PersonTitle.VP.value,
                PersonTitle.DIRECTOR.value,
                PersonTitle.RECRUITER.value,
                PersonTitle.HR.value
            ]

        result = await self.search_people(
            company_domains=[company_domain],
            titles=titles,
            per_page=50
        )

        if result and result.get("people"):
            decision_makers = result["people"]
            logger.info(f"Found {len(decision_makers)} decision makers at {company_domain}")
            return decision_makers

        return None

    async def find_similar_companies(
        self,
        reference_domain: str,
        limit: int = 10
    ) -> Optional[List[Dict]]:
        """
        Find companies similar to a reference company.

        Args:
            reference_domain: Domain of reference company
            limit: Number of similar companies to find

        Returns:
            List of similar companies or None
        """
        # First, enrich the reference company to get its attributes
        ref_company = await self.enrich_organization(domain=reference_domain)

        if not ref_company or not ref_company.get("organization"):
            logger.warning(f"Could not enrich reference company: {reference_domain}")
            return None

        org = ref_company["organization"]

        # Extract company attributes
        industries = org.get("industry_tag_ids", [])
        employee_count = org.get("estimated_num_employees", 0)

        # Search for similar companies
        employee_range = {
            "min": int(employee_count * 0.5) if employee_count else None,
            "max": int(employee_count * 2) if employee_count else None
        }

        result = await self.search_organizations(
            industries=industries[:3] if industries else None,  # Use top 3 industries
            employee_range=employee_range if employee_count else None,
            per_page=limit + 1  # +1 to account for the reference company
        )

        if result and result.get("organizations"):
            # Filter out the reference company
            similar = [
                org for org in result["organizations"]
                if org.get("primary_domain") != reference_domain
            ][:limit]

            logger.info(f"Found {len(similar)} similar companies to {reference_domain}")
            return similar

        return None

    # ==================== RECRUITER INTELLIGENCE ====================

    async def analyze_recruitment_landscape(
        self,
        job_title: str,
        location: Optional[str] = None,
        industries: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze the recruitment landscape for a specific role.
        Perfect for understanding candidate pools and competition.

        Args:
            job_title: Target job title
            location: Geographic location
            industries: Target industries

        Returns:
            Analysis results with candidate pool data
        """
        analysis = {
            "job_title": job_title,
            "location": location,
            "timestamp": datetime.utcnow().isoformat(),
            "total_candidates": 0,
            "top_companies": [],
            "average_tenure": None,
            "common_skills": [],
            "salary_range": None
        }

        # Search for people with this title
        people_result = await self.search_people(
            titles=[job_title],
            locations=[location] if location else None,
            industries=industries,
            per_page=100  # Max for analysis
        )

        if people_result and people_result.get("people"):
            people = people_result["people"]
            analysis["total_candidates"] = len(people)

            # Analyze companies
            company_counts = {}
            for person in people:
                if person.get("organization", {}).get("name"):
                    company = person["organization"]["name"]
                    company_counts[company] = company_counts.get(company, 0) + 1

            # Get top companies
            analysis["top_companies"] = sorted(
                [{"name": k, "count": v} for k, v in company_counts.items()],
                key=lambda x: x["count"],
                reverse=True
            )[:10]

            # Extract common skills/keywords from headlines
            skills = {}
            for person in people:
                headline = person.get("headline", "")
                for word in headline.lower().split():
                    if len(word) > 4:  # Filter short words
                        skills[word] = skills.get(word, 0) + 1

            analysis["common_skills"] = sorted(
                [{"skill": k, "frequency": v} for k, v in skills.items()],
                key=lambda x: x["frequency"],
                reverse=True
            )[:20]

        logger.info(
            f"Recruitment landscape analysis for {job_title}: "
            f"{analysis['total_candidates']} candidates found"
        )

        return analysis

    # ==================== BATCH ENRICHMENT ====================

    async def batch_enrich_contacts(
        self,
        contacts: List[Dict[str, str]]
    ) -> List[Dict]:
        """
        Enrich multiple contacts in batch.
        Optimized for processing email lists.

        Args:
            contacts: List of dicts with email/name/company

        Returns:
            List of enriched contacts
        """
        enriched = []

        for contact in contacts:
            result = await self.enrich_person(
                email=contact.get("email"),
                name=contact.get("name"),
                company=contact.get("company")
            )

            if result and result.get("person"):
                enriched.append({
                    "original": contact,
                    "enriched": result["person"],
                    "organization": result.get("organization"),
                    "success": True
                })
            else:
                enriched.append({
                    "original": contact,
                    "enriched": None,
                    "organization": None,
                    "success": False
                })

        success_count = sum(1 for e in enriched if e["success"])
        logger.info(
            f"Batch enrichment complete: {success_count}/{len(contacts)} successful"
        )

        return enriched

    # ==================== COMPETITOR ANALYSIS ====================

    async def analyze_competitors(
        self,
        company_domain: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze competitors and their recruitment teams.

        Args:
            company_domain: Your company domain
            limit: Number of competitors to analyze

        Returns:
            Competitor analysis with recruitment insights
        """
        analysis = {
            "company": company_domain,
            "competitors": [],
            "total_recruiters": 0,
            "average_company_size": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Find similar companies
        similar_companies = await self.find_similar_companies(
            company_domain, limit
        )

        if not similar_companies:
            logger.warning("No competitors found")
            return analysis

        total_employees = 0

        for company in similar_companies:
            competitor_data = {
                "name": company.get("name"),
                "domain": company.get("primary_domain"),
                "employees": company.get("estimated_num_employees", 0),
                "industry": company.get("industry", ""),
                "recruiters": []
            }

            # Find recruiters at this company
            if competitor_data["domain"]:
                recruiters = await self.search_people(
                    company_domains=[competitor_data["domain"]],
                    titles=[PersonTitle.RECRUITER.value, PersonTitle.HR.value],
                    per_page=10
                )

                if recruiters and recruiters.get("people"):
                    competitor_data["recruiters"] = [
                        {
                            "name": r.get("name"),
                            "title": r.get("title"),
                            "email": r.get("email")
                        }
                        for r in recruiters["people"]
                    ]
                    analysis["total_recruiters"] += len(recruiters["people"])

            analysis["competitors"].append(competitor_data)
            total_employees += competitor_data["employees"]

        if analysis["competitors"]:
            analysis["average_company_size"] = total_employees // len(analysis["competitors"])

        logger.info(
            f"Competitor analysis complete: {len(analysis['competitors'])} competitors, "
            f"{analysis['total_recruiters']} total recruiters found"
        )

        return analysis


# ==================== MAIN INTEGRATION FUNCTION ====================

async def apollo_full_enrichment(
    email: Optional[str] = None,
    name: Optional[str] = None,
    company: Optional[str] = None,
    deep_search: bool = False
) -> Dict[str, Any]:
    """
    Comprehensive enrichment using all Apollo capabilities.
    This is the main function to call for maximum data extraction.

    Args:
        email: Email address
        name: Person's name
        company: Company name or domain
        deep_search: Enable deep search for related data

    Returns:
        Comprehensive enrichment results
    """
    manager = ApolloServiceManager()
    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "person": None,
        "organization": None,
        "decision_makers": [],
        "similar_people": [],
        "recruitment_landscape": None
    }

    # Primary enrichment
    if email or name:
        person_data = await manager.enrich_person(email, name, company)
        if person_data:
            result["person"] = person_data.get("person")
            result["organization"] = person_data.get("organization")

    # Deep search if enabled
    if deep_search and result["organization"]:
        org_domain = result["organization"].get("primary_domain")

        if org_domain:
            # Find decision makers
            decision_makers = await manager.find_decision_makers(org_domain)
            if decision_makers:
                result["decision_makers"] = decision_makers[:5]  # Top 5

            # Find similar people in the industry
            if result["person"] and result["person"].get("title"):
                similar = await manager.search_people(
                    titles=[result["person"]["title"]],
                    industries=result["organization"].get("industry_tag_ids", [])[:2],
                    per_page=10
                )
                if similar and similar.get("people"):
                    result["similar_people"] = similar["people"][:5]

            # Analyze recruitment landscape if it's a recruiter
            if result["person"] and "recruit" in result["person"].get("title", "").lower():
                landscape = await manager.analyze_recruitment_landscape(
                    job_title=result["person"]["title"],
                    location=result["person"].get("city")
                )
                result["recruitment_landscape"] = landscape

    logger.info(
        f"Full Apollo enrichment complete: "
        f"Person: {bool(result['person'])}, "
        f"Org: {bool(result['organization'])}, "
        f"Decision Makers: {len(result['decision_makers'])}, "
        f"Similar: {len(result['similar_people'])}"
    )

    return result