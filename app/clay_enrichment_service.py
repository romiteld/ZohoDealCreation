"""
Clay API Enrichment Service

Provides company and person data enrichment using Clay's Enterprise API.
Integrates with the LangGraph workflow to enhance extracted data.
"""

import os
import requests
import logging
from typing import Dict, Optional, Any
from urllib.parse import urlparse
import time

logger = logging.getLogger(__name__)

class ClayEnrichmentService:
    """Service for enriching data using Clay's Enterprise API"""

    def __init__(self):
        self.api_key = os.getenv("CLAY_API_KEY")
        self.base_url = "https://api.clay.com/v1"  # Placeholder - actual endpoint TBD
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

        if not self.api_key:
            logger.warning("CLAY_API_KEY not found - Clay enrichment will be disabled")

    def is_enabled(self) -> bool:
        """Check if Clay enrichment is enabled"""
        return bool(self.api_key)

    def extract_domain_from_email(self, email: str) -> Optional[str]:
        """Extract domain from email address"""
        try:
            if "@" in email:
                return email.split("@")[1].lower()
        except Exception as e:
            logger.error(f"Error extracting domain from email {email}: {e}")
        return None

    def extract_domain_from_url(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception as e:
            logger.error(f"Error extracting domain from URL {url}: {e}")
        return None

    async def enrich_person_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Enrich person data using email address

        Args:
            email: Person's email address

        Returns:
            Dictionary with enriched person data or None if failed
        """
        if not self.is_enabled():
            return None

        try:
            # Note: This is a placeholder implementation
            # Actual Clay Enterprise API endpoint and format needs to be confirmed
            payload = {
                "email": email,
                "data_sources": ["linkedin", "company_data", "contact_info"]
            }

            response = self.session.post(
                f"{self.base_url}/person/enrich",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return self._normalize_person_data(data)
            else:
                logger.warning(f"Clay person enrichment failed for {email}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error enriching person data for {email}: {e}")
            return None

    async def enrich_company_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Enrich company data using domain

        Args:
            domain: Company domain (e.g., "acme.com")

        Returns:
            Dictionary with enriched company data or None if failed
        """
        if not self.is_enabled():
            return None

        try:
            # Note: This is a placeholder implementation
            # Actual Clay Enterprise API endpoint and format needs to be confirmed
            payload = {
                "domain": domain,
                "data_sources": ["company_info", "industry_data", "size_metrics"]
            }

            response = self.session.post(
                f"{self.base_url}/company/enrich",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return self._normalize_company_data(data)
            else:
                logger.warning(f"Clay company enrichment failed for {domain}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error enriching company data for {domain}: {e}")
            return None

    def _normalize_person_data(self, clay_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Clay person data to our standard format

        Args:
            clay_data: Raw response from Clay API

        Returns:
            Normalized person data
        """
        # Placeholder normalization - actual format depends on Clay API response
        normalized = {
            "clay_enriched": True,
            "first_name": clay_data.get("first_name"),
            "last_name": clay_data.get("last_name"),
            "full_name": clay_data.get("full_name"),
            "title": clay_data.get("title") or clay_data.get("job_title"),
            "company": clay_data.get("company_name"),
            "linkedin_url": clay_data.get("linkedin_url"),
            "location": clay_data.get("location"),
            "industry": clay_data.get("industry"),
            "seniority": clay_data.get("seniority_level"),
            "employment_status": clay_data.get("employment_status"),
            "confidence_score": clay_data.get("confidence", 0.0)
        }

        # Remove None values
        return {k: v for k, v in normalized.items() if v is not None}

    def _normalize_company_data(self, clay_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Clay company data to our standard format

        Args:
            clay_data: Raw response from Clay API

        Returns:
            Normalized company data
        """
        # Placeholder normalization - actual format depends on Clay API response
        normalized = {
            "clay_enriched": True,
            "company_name": clay_data.get("name") or clay_data.get("company_name"),
            "domain": clay_data.get("domain"),
            "website": clay_data.get("website"),
            "industry": clay_data.get("industry"),
            "company_size": clay_data.get("employee_count") or clay_data.get("size"),
            "revenue": clay_data.get("annual_revenue"),
            "location": clay_data.get("location") or clay_data.get("headquarters"),
            "description": clay_data.get("description"),
            "founded_year": clay_data.get("founded"),
            "company_type": clay_data.get("type"),
            "technologies": clay_data.get("technologies", []),
            "confidence_score": clay_data.get("confidence", 0.0)
        }

        # Remove None values
        return {k: v for k, v in normalized.items() if v is not None}

    async def enrich_extracted_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich the extracted data from our LangGraph pipeline

        Args:
            extracted_data: Data from our extraction pipeline

        Returns:
            Enhanced data with Clay enrichments
        """
        if not self.is_enabled():
            logger.info("Clay enrichment disabled - returning original data")
            return extracted_data

        enhanced_data = extracted_data.copy()

        try:
            # Extract contact email for person enrichment
            contact_record = extracted_data.get("contact_record", {})
            contact_email = contact_record.get("email")

            # Extract company domain for company enrichment
            company_record = extracted_data.get("company_record", {})
            company_domain = None

            # Try to get domain from website first
            website = company_record.get("website")
            if website:
                company_domain = self.extract_domain_from_url(website)

            # Fall back to extracting from contact email
            if not company_domain and contact_email:
                company_domain = self.extract_domain_from_email(contact_email)

            # Enrich person data
            if contact_email:
                logger.info(f"Enriching person data for email: {contact_email}")
                person_enrichment = await self.enrich_person_by_email(contact_email)
                if person_enrichment:
                    # Merge enriched data with existing contact record
                    enhanced_contact = contact_record.copy()
                    enhanced_contact.update(person_enrichment)
                    enhanced_data["contact_record"] = enhanced_contact
                    logger.info("Person data enriched successfully")

            # Enrich company data
            if company_domain:
                logger.info(f"Enriching company data for domain: {company_domain}")
                company_enrichment = await self.enrich_company_by_domain(company_domain)
                if company_enrichment:
                    # Merge enriched data with existing company record
                    enhanced_company = company_record.copy()
                    enhanced_company.update(company_enrichment)
                    enhanced_data["company_record"] = enhanced_company
                    logger.info("Company data enriched successfully")

            # Add Clay enrichment metadata
            enhanced_data["clay_enrichment"] = {
                "enabled": True,
                "person_enriched": bool(contact_email and "clay_enriched" in enhanced_data.get("contact_record", {})),
                "company_enriched": bool(company_domain and "clay_enriched" in enhanced_data.get("company_record", {})),
                "enrichment_timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error during Clay enrichment: {e}")
            # Return original data if enrichment fails
            enhanced_data["clay_enrichment"] = {
                "enabled": True,
                "error": str(e),
                "enrichment_timestamp": time.time()
            }

        return enhanced_data

# Singleton instance
clay_service = ClayEnrichmentService()