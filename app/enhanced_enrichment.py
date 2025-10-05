"""
Enhanced Data Enrichment Service
Integrates multiple data providers for comprehensive company and contact enrichment
"""

import os
import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv('.env.local')
logger = logging.getLogger(__name__)


class EnhancedEnrichmentService:
    """Multi-provider data enrichment with fallback strategies"""

    def __init__(self):
        # API Keys (add these to .env.local)
        self.clay_api_key = os.getenv("CLAY_API_KEY")
        self.apollo_api_key = os.getenv("APOLLO_API_KEY")
        self.clearbit_api_key = os.getenv("CLEARBIT_API_KEY")
        self.pdl_api_key = os.getenv("PDL_API_KEY")  # People Data Labs

        # Existing Firecrawl for web scraping
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")

    async def enrich_company(self, domain: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrich company with multiple data sources
        Returns comprehensive company profile
        """

        enriched_data = {
            "company_name": company_name,
            "domain": domain,
            "revenue": None,
            "employee_count": None,
            "industry": None,
            "founded_year": None,
            "funding_total": None,
            "tech_stack": [],
            "company_type": None,
            "headquarters": None,
            "description": None,
            "linkedin_url": None,
            "confidence_score": 0
        }

        # Try Clay first (most comprehensive)
        if self.clay_api_key:
            clay_data = await self._enrich_with_clay(domain)
            if clay_data:
                enriched_data.update(clay_data)
                enriched_data["confidence_score"] = 0.95
                return enriched_data

        # Fallback to Clearbit
        if self.clearbit_api_key:
            clearbit_data = await self._enrich_with_clearbit(domain)
            if clearbit_data:
                enriched_data.update(clearbit_data)
                enriched_data["confidence_score"] = 0.90
                return enriched_data

        # Fallback to Apollo
        if self.apollo_api_key:
            apollo_data = await self._enrich_with_apollo(domain)
            if apollo_data:
                enriched_data.update(apollo_data)
                enriched_data["confidence_score"] = 0.85
                return enriched_data

        # Last resort: Firecrawl web scraping
        if self.firecrawl_api_key:
            firecrawl_data = await self._enrich_with_firecrawl(domain)
            if firecrawl_data:
                enriched_data.update(firecrawl_data)
                enriched_data["confidence_score"] = 0.70

        return enriched_data

    async def enrich_contact(self, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrich contact with multiple data sources
        Returns comprehensive contact profile
        """

        enriched_contact = {
            "email": email,
            "full_name": name,
            "first_name": None,
            "last_name": None,
            "phone": None,
            "mobile_phone": None,
            "job_title": None,
            "seniority": None,
            "department": None,
            "linkedin_url": None,
            "twitter_url": None,
            "location": None,
            "company_name": None,
            "company_domain": None,
            "confidence_score": 0
        }

        # Extract domain from email
        domain = email.split('@')[1] if '@' in email else None

        # Try People Data Labs first (best for people data)
        if self.pdl_api_key:
            pdl_data = await self._enrich_with_pdl(email)
            if pdl_data:
                enriched_contact.update(pdl_data)
                enriched_contact["confidence_score"] = 0.95
                return enriched_contact

        # Fallback to Apollo
        if self.apollo_api_key:
            apollo_data = await self._enrich_contact_apollo(email)
            if apollo_data:
                enriched_contact.update(apollo_data)
                enriched_contact["confidence_score"] = 0.90
                return enriched_contact

        # Fallback to Clearbit
        if self.clearbit_api_key:
            clearbit_data = await self._enrich_contact_clearbit(email)
            if clearbit_data:
                enriched_contact.update(clearbit_data)
                enriched_contact["confidence_score"] = 0.85

        return enriched_contact

    async def _enrich_with_clay(self, domain: str) -> Optional[Dict[str, Any]]:
        """Clay.com enrichment - most comprehensive"""
        try:
            headers = {
                "Authorization": f"Bearer {self.clay_api_key}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                # Clay's company enrichment endpoint
                payload = {
                    "domain": domain,
                    "providers": ["clearbit", "pdl", "apollo", "zoominfo"],
                    "fields": ["revenue", "employee_count", "industry", "tech_stack", "funding"]
                }

                async with session.post(
                    "https://api.clay.com/v1/companies/enrich",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "company_name": data.get("name"),
                            "revenue": data.get("revenue"),
                            "employee_count": data.get("employee_count"),
                            "industry": data.get("industry"),
                            "tech_stack": data.get("technologies", []),
                            "funding_total": data.get("funding_total"),
                            "headquarters": data.get("location"),
                            "description": data.get("description"),
                            "linkedin_url": data.get("linkedin_url")
                        }
        except Exception as e:
            logger.error(f"Clay enrichment error: {e}")
        return None

    async def _enrich_with_clearbit(self, domain: str) -> Optional[Dict[str, Any]]:
        """Clearbit enrichment - good for company data"""
        try:
            headers = {
                "Authorization": f"Bearer {self.clearbit_api_key}"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://company.clearbit.com/v2/companies/find?domain={domain}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "company_name": data.get("name"),
                            "revenue": data.get("metrics", {}).get("annualRevenue"),
                            "employee_count": data.get("metrics", {}).get("employees"),
                            "industry": data.get("category", {}).get("industry"),
                            "tech_stack": data.get("tech", []),
                            "founded_year": data.get("foundedYear"),
                            "company_type": data.get("type"),
                            "headquarters": data.get("location"),
                            "description": data.get("description"),
                            "linkedin_url": data.get("linkedin", {}).get("handle")
                        }
        except Exception as e:
            logger.error(f"Clearbit enrichment error: {e}")
        return None

    async def _enrich_with_apollo(self, domain: str) -> Optional[Dict[str, Any]]:
        """Apollo.io enrichment - good balance of data and cost"""
        try:
            headers = {
                "X-Api-Key": self.apollo_api_key,
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                payload = {
                    "domain": domain
                }

                async with session.post(
                    "https://api.apollo.io/v1/organizations/enrich",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        org = data.get("organization", {})
                        return {
                            "company_name": org.get("name"),
                            "revenue": org.get("estimated_annual_revenue"),
                            "employee_count": org.get("number_of_employees"),
                            "industry": org.get("industry"),
                            "tech_stack": org.get("technologies", []),
                            "founded_year": org.get("founded_year"),
                            "headquarters": org.get("headquarters_location"),
                            "description": org.get("short_description"),
                            "linkedin_url": org.get("linkedin_url")
                        }
        except Exception as e:
            logger.error(f"Apollo enrichment error: {e}")
        return None

    async def _enrich_with_pdl(self, email: str) -> Optional[Dict[str, Any]]:
        """People Data Labs enrichment - best for contact data"""
        try:
            headers = {
                "X-Api-Key": self.pdl_api_key
            }

            async with aiohttp.ClientSession() as session:
                params = {
                    "email": email,
                    "pretty": True
                }

                async with session.get(
                    "https://api.peopledatalabs.com/v5/person/enrich",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == 200:
                            person = data.get("data", {})
                            return {
                                "full_name": person.get("full_name"),
                                "first_name": person.get("first_name"),
                                "last_name": person.get("last_name"),
                                "phone": person.get("phone_numbers", [{}])[0].get("number"),
                                "mobile_phone": person.get("mobile_phone"),
                                "job_title": person.get("job_title"),
                                "seniority": person.get("job_title_levels", [None])[0],
                                "linkedin_url": person.get("linkedin_url"),
                                "twitter_url": person.get("twitter_url"),
                                "location": person.get("location_name"),
                                "company_name": person.get("job_company_name"),
                                "company_domain": person.get("job_company_website")
                            }
        except Exception as e:
            logger.error(f"PDL enrichment error: {e}")
        return None

    async def _enrich_contact_apollo(self, email: str) -> Optional[Dict[str, Any]]:
        """Apollo contact enrichment"""
        try:
            headers = {
                "X-Api-Key": self.apollo_api_key,
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                payload = {
                    "email": email
                }

                async with session.post(
                    "https://api.apollo.io/v1/people/enrich",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        person = data.get("person", {})
                        return {
                            "full_name": person.get("name"),
                            "first_name": person.get("first_name"),
                            "last_name": person.get("last_name"),
                            "phone": person.get("phone_numbers", [{}])[0].get("raw_number"),
                            "job_title": person.get("title"),
                            "seniority": person.get("seniority"),
                            "department": person.get("departments", [None])[0],
                            "linkedin_url": person.get("linkedin_url"),
                            "location": f"{person.get('city')}, {person.get('state')}",
                            "company_name": person.get("organization", {}).get("name")
                        }
        except Exception as e:
            logger.error(f"Apollo contact enrichment error: {e}")
        return None

    async def _enrich_contact_clearbit(self, email: str) -> Optional[Dict[str, Any]]:
        """Clearbit contact enrichment"""
        try:
            headers = {
                "Authorization": f"Bearer {self.clearbit_api_key}"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://person.clearbit.com/v2/people/find?email={email}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "full_name": data.get("name", {}).get("fullName"),
                            "first_name": data.get("name", {}).get("givenName"),
                            "last_name": data.get("name", {}).get("familyName"),
                            "job_title": data.get("employment", {}).get("title"),
                            "seniority": data.get("employment", {}).get("seniority"),
                            "linkedin_url": data.get("linkedin", {}).get("handle"),
                            "twitter_url": data.get("twitter", {}).get("handle"),
                            "location": data.get("location"),
                            "company_name": data.get("employment", {}).get("name"),
                            "company_domain": data.get("employment", {}).get("domain")
                        }
        except Exception as e:
            logger.error(f"Clearbit contact enrichment error: {e}")
        return None

    async def _enrich_with_firecrawl(self, domain: str) -> Optional[Dict[str, Any]]:
        """Fallback to existing Firecrawl for basic web scraping"""
        # Use existing Firecrawl implementation
        from app.firecrawl_research import FirecrawlResearcher
        researcher = FirecrawlResearcher(self.firecrawl_api_key)
        result = await researcher.research_company_domain(domain)

        if result.get("company_name"):
            return {
                "company_name": result.get("company_name"),
                "confidence_score": result.get("confidence", 0.5)
            }
        return None


class SmartEnrichmentOrchestrator:
    """
    Orchestrates enrichment across multiple providers
    Implements waterfall strategy and caching
    """

    def __init__(self):
        self.enricher = EnhancedEnrichmentService()
        logger.info("Smart Enrichment Orchestrator initialized")

    async def enrich_email_data(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriches email extraction with comprehensive data
        Adds revenue, employee count, tech stack, phone numbers, etc.
        """

        enriched = email_data.copy()

        # Extract key identifiers
        candidate_email = email_data.get("contact_record", {}).get("email")
        company_name = email_data.get("company_record", {}).get("company_name")
        domain = None

        if candidate_email and '@' in candidate_email:
            domain = candidate_email.split('@')[1]

        # Enrich company data
        if domain or company_name:
            logger.info(f"Enriching company: {company_name or domain}")
            company_data = await self.enricher.enrich_company(
                domain=domain,
                company_name=company_name
            )

            # Add enriched fields to company record
            if enriched.get("company_record"):
                enriched["company_record"].update({
                    "revenue": company_data.get("revenue"),
                    "employee_count": company_data.get("employee_count"),
                    "industry": company_data.get("industry"),
                    "tech_stack": company_data.get("tech_stack"),
                    "funding_total": company_data.get("funding_total"),
                    "headquarters": company_data.get("headquarters"),
                    "company_linkedin": company_data.get("linkedin_url"),
                    "enrichment_confidence": company_data.get("confidence_score")
                })

        # Enrich contact data
        if candidate_email:
            logger.info(f"Enriching contact: {candidate_email}")
            contact_data = await self.enricher.enrich_contact(
                email=candidate_email,
                name=f"{email_data.get('contact_record', {}).get('first_name')} {email_data.get('contact_record', {}).get('last_name')}"
            )

            # Add enriched fields to contact record
            if enriched.get("contact_record"):
                # Only update if we got better data
                if contact_data.get("phone") and not enriched["contact_record"].get("phone"):
                    enriched["contact_record"]["phone"] = contact_data.get("phone")

                if contact_data.get("mobile_phone"):
                    enriched["contact_record"]["mobile_phone"] = contact_data.get("mobile_phone")

                if contact_data.get("linkedin_url"):
                    enriched["contact_record"]["linkedin_url"] = contact_data.get("linkedin_url")

                if contact_data.get("job_title") and not enriched.get("deal_record", {}).get("job_title"):
                    enriched["deal_record"]["job_title"] = contact_data.get("job_title")

                enriched["contact_record"]["enrichment_confidence"] = contact_data.get("confidence_score")

        # Add enrichment metadata
        enriched["enrichment_metadata"] = {
            "enriched_at": datetime.utcnow().isoformat(),
            "providers_used": self._get_active_providers(),
            "company_confidence": company_data.get("confidence_score", 0) if 'company_data' in locals() else 0,
            "contact_confidence": contact_data.get("confidence_score", 0) if 'contact_data' in locals() else 0
        }

        logger.info(f"Enrichment complete with confidence: Company={enriched['enrichment_metadata']['company_confidence']}, Contact={enriched['enrichment_metadata']['contact_confidence']}")

        return enriched

    def _get_active_providers(self) -> List[str]:
        """Returns list of configured data providers"""
        providers = []
        if self.enricher.clay_api_key:
            providers.append("Clay")
        if self.enricher.apollo_api_key:
            providers.append("Apollo")
        if self.enricher.clearbit_api_key:
            providers.append("Clearbit")
        if self.enricher.pdl_api_key:
            providers.append("PeopleDataLabs")
        if self.enricher.firecrawl_api_key:
            providers.append("Firecrawl")
        return providers


# Integration with existing LangGraph workflow
async def enhance_langgraph_with_enrichment(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Drop-in replacement for research_company node in LangGraph
    Uses enhanced enrichment instead of just Firecrawl
    """

    orchestrator = SmartEnrichmentOrchestrator()

    # Get extraction result from state
    extraction_result = state.get('extraction_result', {})

    # Run comprehensive enrichment
    enriched_data = await orchestrator.enrich_email_data(extraction_result)

    # Update state with enriched data
    state['company_research'] = enriched_data.get('enrichment_metadata', {})
    state['extraction_result'] = enriched_data

    return state