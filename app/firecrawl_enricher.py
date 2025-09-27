"""
Firecrawl v2+ Enrichment Service with FIRE-1 Agent
Uses Firecrawl's advanced Extract API with FIRE-1 agent for comprehensive web scraping
"""

import os
import logging
from typing import Dict, Optional, Any, List
import httpx
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class FirecrawlEnricher:
    """
    Firecrawl v2+ enrichment using Extract API with FIRE-1 agent.
    Capable of extracting comprehensive company and contact information from any website.
    """

    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        self.base_url = "https://api.firecrawl.dev/v2"

    async def extract_company_data(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        email: Optional[str] = None,
        use_fire_agent: bool = True
    ) -> Dict[str, Any]:
        """
        Extract comprehensive company and contact data using Firecrawl v2 Extract API.

        Args:
            domain: Company domain to scrape
            company_name: Company name for search
            email: Email to extract domain from
            use_fire_agent: Whether to use FIRE-1 agent for advanced extraction

        Returns:
            Extracted company and contact information
        """
        if not self.api_key:
            logger.warning("Firecrawl API key not configured")
            return {}

        # Determine the target URL
        target_url = None
        if domain:
            target_url = f"https://{domain}" if not domain.startswith("http") else domain
        elif email and "@" in email:
            email_domain = email.split("@")[1]
            target_url = f"https://{email_domain}"
        elif company_name:
            # Use search to find the company website first
            search_result = await self._search_company_website(company_name)
            if search_result:
                target_url = search_result

        if not target_url:
            logger.warning("No target URL determined for Firecrawl extraction")
            return {}

        try:
            # Define the schema for structured extraction
            schema = {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "industry": {"type": "string"},
                            "website": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"},
                            "address": {"type": "string"},
                            "city": {"type": "string"},
                            "state": {"type": "string"},
                            "zip": {"type": "string"},
                            "country": {"type": "string"},
                            "founded": {"type": "string"},
                            "employee_count": {"type": "string"},
                            "linkedin": {"type": "string"},
                            "twitter": {"type": "string"},
                            "facebook": {"type": "string"},
                            "mission": {"type": "string"},
                            "services": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    },
                    "leadership": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "title": {"type": "string"},
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "linkedin": {"type": "string"},
                                "bio": {"type": "string"}
                            }
                        }
                    },
                    "contacts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "department": {"type": "string"},
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "name": {"type": "string"}
                            }
                        }
                    },
                    "locations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "address": {"type": "string"},
                                "city": {"type": "string"},
                                "state": {"type": "string"},
                                "country": {"type": "string"},
                                "phone": {"type": "string"}
                            }
                        }
                    }
                }
            }

            # Prepare the Extract API request with proper FIRE-1 agent configuration
            extract_payload = {
                "urls": [target_url],
                "prompt": """Extract comprehensive company information including:
                - Company name, description, and industry
                - All contact information (emails, phones, addresses)
                - Leadership team and key personnel with their contact details
                - All office locations
                - Social media profiles
                - Company mission and services
                - Any recruiter or HR contact information
                Navigate to About, Contact, Team, and Leadership pages if available.
                Extract ALL emails and phone numbers found on the website.""",
                "schema": schema
            }

            # Add FIRE-1 agent if requested (correct v2 format)
            if use_fire_agent:
                extract_payload["agent"] = {
                    "model": "FIRE-1"
                }
                logger.info(f"Using FIRE-1 agent for advanced extraction from {target_url}")
            else:
                logger.info(f"Using standard extraction from {target_url}")

            # Make the API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                response = await client.post(
                    f"{self.base_url}/extract",
                    json=extract_payload,
                    headers=headers
                )

                if response.status_code != 200:
                    logger.error(f"Firecrawl Extract API error {response.status_code}: {response.text}")
                    return {}

                result = response.json()
                logger.info(f"Firecrawl API initial response: {result}")

                # v2 Extract API: Initial response returns job ID, need to poll for results
                if result.get("success") and result.get("id"):
                    job_id = result["id"]
                    logger.info(f"Extract job started with ID: {job_id}, polling for completion...")

                    # Poll for job completion
                    final_result = await self._poll_extract_job(job_id)
                    logger.info(f"Extract job completed: {final_result}")

                    # Parse final result
                    if final_result.get("success") and final_result.get("data") and final_result.get("status") == "completed":
                        extracted_data = final_result["data"]
                        logger.info(f"Successfully extracted data from {target_url}: {extracted_data}")
                        return self._normalize_extracted_data(extracted_data)
                    else:
                        logger.warning(f"Extract job failed or incomplete: {final_result}")
                        return {}
                else:
                    logger.error(f"Failed to start extract job. Response: {result}")
                    return {}

        except Exception as e:
            logger.error(f"Firecrawl extraction error: {str(e)}")
            return {}

    async def _search_company_website(self, company_name: str) -> Optional[str]:
        """
        Use Firecrawl search to find company website.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                search_payload = {
                    "query": f"{company_name} official website",
                    "limit": 3
                }

                response = await client.post(
                    f"{self.base_url}/search",
                    json=search_payload,
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        # Return the first result URL
                        return data["data"][0].get("url")

        except Exception as e:
            logger.error(f"Firecrawl search error: {str(e)}")

        return None

    async def _poll_extract_job(self, job_id: str, max_attempts: int = 10) -> Dict:
        """
        Poll for Extract job completion.
        """
        import asyncio

        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            for attempt in range(max_attempts):
                try:
                    response = await client.get(
                        f"{self.base_url}/extract/{job_id}",
                        headers=headers
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "completed":
                            return result
                        elif result.get("status") == "failed":
                            logger.error(f"Extract job failed: {result.get('error')}")
                            return {}

                    # Wait before next poll
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Error polling extract job: {str(e)}")

            logger.warning(f"Extract job {job_id} did not complete in time")
            return {}

    def _normalize_extracted_data(self, data: Dict) -> Dict[str, Any]:
        """
        Normalize extracted data to a consistent format.
        """
        normalized = {
            "company": {},
            "person": {},
            "contacts": [],
            "locations": []
        }

        # Extract company data
        if data.get("company"):
            company = data["company"]
            normalized["company"] = {
                "company_name": company.get("name"),
                "description": company.get("description"),
                "industry": company.get("industry"),
                "website": company.get("website"),
                "email": company.get("email"),
                "phone": company.get("phone"),
                "address": company.get("address"),
                "city": company.get("city"),
                "state": company.get("state"),
                "postal_code": company.get("zip"),
                "country": company.get("country"),
                "founded_year": company.get("founded"),
                "employee_count": company.get("employee_count"),
                "linkedin_url": company.get("linkedin"),
                "twitter_url": company.get("twitter"),
                "facebook_url": company.get("facebook"),
                "company_mission": company.get("mission"),
                "services": company.get("services", [])
            }

        # Extract leadership/person data
        if data.get("leadership") and len(data["leadership"]) > 0:
            # Use first leader as primary contact if no specific person requested
            leader = data["leadership"][0]
            normalized["person"] = {
                "client_name": leader.get("name"),
                "job_title": leader.get("title"),
                "email": leader.get("email"),
                "phone": leader.get("phone"),
                "linkedin_url": leader.get("linkedin"),
                "bio": leader.get("bio")
            }

            # Add all leadership as contacts
            for leader in data.get("leadership", []):
                normalized["contacts"].append({
                    "name": leader.get("name"),
                    "title": leader.get("title"),
                    "email": leader.get("email"),
                    "phone": leader.get("phone"),
                    "department": "Leadership"
                })

        # Extract additional contacts
        for contact in data.get("contacts", []):
            normalized["contacts"].append(contact)

        # Extract locations
        normalized["locations"] = data.get("locations", [])

        # Calculate data completeness
        total_fields = 0
        filled_fields = 0

        for section in ["company", "person"]:
            if normalized.get(section):
                for key, value in normalized[section].items():
                    total_fields += 1
                    if value:
                        filled_fields += 1

        normalized["data_completeness"] = (filled_fields / total_fields * 100) if total_fields > 0 else 0
        normalized["source"] = "firecrawl_v2_extract"
        normalized["extraction_date"] = datetime.utcnow().isoformat()

        return normalized


async def comprehensive_enrichment(
    email: Optional[str] = None,
    name: Optional[str] = None,
    company: Optional[str] = None,
    domain: Optional[str] = None
) -> Dict[str, Any]:
    """
    Comprehensive enrichment using Apollo + Firecrawl v2 with FIRE-1 agent.

    This function orchestrates multiple services:
    1. Apollo for known contacts/companies
    2. Firecrawl Extract with FIRE-1 for web scraping
    3. Intelligent data merging

    Args:
        email: Contact email
        name: Contact name
        company: Company name
        domain: Company domain

    Returns:
        Comprehensive enrichment data from all sources
    """
    from app.apollo_enricher import apollo_deep_enrichment

    # Initialize result
    final_result = {
        "person": None,
        "company": None,
        "contacts": [],
        "locations": [],
        "data_completeness": 0,
        "sources_used": []
    }

    # Step 1: Try Apollo first (it's faster for known contacts)
    logger.info("Starting comprehensive enrichment with Apollo")
    apollo_result = await apollo_deep_enrichment(
        email=email,
        name=name,
        company=company,
        extract_all=True
    )

    if apollo_result and (apollo_result.get("person") or apollo_result.get("company")):
        final_result["person"] = apollo_result.get("person")
        final_result["company"] = apollo_result.get("company")
        final_result["sources_used"].append("apollo")

        # Extract domain from Apollo data if not provided
        if not domain and apollo_result.get("company", {}).get("domain"):
            domain = apollo_result["company"]["domain"]
        elif not domain and apollo_result.get("company", {}).get("website"):
            website = apollo_result["company"]["website"]
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]

    # Step 2: Use Firecrawl v2 Extract with FIRE-1 agent for comprehensive web data
    # This runs even if Apollo found data, to get more comprehensive information
    if domain or company or (email and "@" in email):
        logger.info("Enhancing with Firecrawl v2 Extract using FIRE-1 agent")

        firecrawl_enricher = FirecrawlEnricher()
        firecrawl_result = await firecrawl_enricher.extract_company_data(
            domain=domain,
            company_name=company if not domain else None,
            email=email,
            use_fire_agent=True  # Use FIRE-1 for best results
        )

        if firecrawl_result and firecrawl_result.get("data_completeness", 0) > 0:
            final_result["sources_used"].append("firecrawl_v2_fire1")

            # Merge Firecrawl data, preferring it for fields Apollo doesn't have
            if not final_result["company"]:
                final_result["company"] = firecrawl_result.get("company", {})
            else:
                # Intelligent merge - Firecrawl often has better/fresher data
                for key, value in firecrawl_result.get("company", {}).items():
                    if value and (not final_result["company"].get(key) or
                                  len(str(value)) > len(str(final_result["company"].get(key, "")))):
                        final_result["company"][key] = value

            # Merge person data
            if not final_result["person"]:
                final_result["person"] = firecrawl_result.get("person", {})
            else:
                for key, value in firecrawl_result.get("person", {}).items():
                    if value and not final_result["person"].get(key):
                        final_result["person"][key] = value

            # Add contacts and locations from Firecrawl
            final_result["contacts"].extend(firecrawl_result.get("contacts", []))
            final_result["locations"].extend(firecrawl_result.get("locations", []))

    # Calculate final completeness
    total_fields = 0
    filled_fields = 0

    for section in ["person", "company"]:
        if final_result.get(section):
            for key, value in final_result[section].items():
                total_fields += 1
                if value:
                    filled_fields += 1

    final_result["data_completeness"] = (filled_fields / total_fields * 100) if total_fields > 0 else 0

    logger.info(f"Comprehensive enrichment completed: {final_result['data_completeness']:.1f}% complete using {', '.join(final_result['sources_used'])}")

    return final_result