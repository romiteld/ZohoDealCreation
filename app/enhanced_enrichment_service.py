"""
Enhanced Enrichment Service

Combines Firecrawl, Serper, and data validation to provide rich company and person data.
Integrates seamlessly with our existing LangGraph workflow.
"""

import os
import re
import requests
import logging
from typing import Dict, Optional, Any, List
from urllib.parse import urlparse, urljoin
import asyncio
import time

logger = logging.getLogger(__name__)

class EnhancedEnrichmentService:
    """Enhanced data enrichment using multiple sources"""

    def __init__(self):
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.session = requests.Session()

    def is_enabled(self) -> bool:
        """Check if enrichment services are available"""
        return bool(self.firecrawl_api_key and self.serper_api_key)

    def extract_domain_from_email(self, email: str) -> Optional[str]:
        """Extract domain from email address"""
        try:
            if "@" in email:
                return email.split("@")[1].lower()
        except Exception as e:
            logger.error(f"Error extracting domain from email {email}: {e}")
        return None

    def normalize_domain(self, domain_input: str) -> Optional[str]:
        """Normalize domain from various inputs (URL, domain, email)"""
        try:
            domain = domain_input.lower().strip()

            # If it looks like an email, extract domain
            if "@" in domain:
                domain = domain.split("@")[1]

            # If it doesn't start with http, add it
            if not domain.startswith(("http://", "https://")):
                domain = f"https://{domain}"

            # Parse and clean
            parsed = urlparse(domain)
            clean_domain = parsed.netloc.lower()

            # Remove www. prefix
            if clean_domain.startswith("www."):
                clean_domain = clean_domain[4:]

            return clean_domain
        except Exception as e:
            logger.error(f"Error normalizing domain {domain_input}: {e}")
        return None

    async def search_company_info(self, company_name: str, domain: str = None) -> Dict[str, Any]:
        """Search for company information using Serper API"""
        if not self.serper_api_key:
            return {}

        try:
            # Build search query
            query_parts = [company_name]
            if domain:
                query_parts.append(f"site:{domain}")

            search_query = " ".join(query_parts)

            headers = {
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "q": search_query,
                "num": 5,
                "type": "search"
            }

            response = requests.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_search_results(data, company_name)

        except Exception as e:
            logger.error(f"Error searching company info for {company_name}: {e}")

        return {}

    def _parse_search_results(self, search_data: Dict, company_name: str) -> Dict[str, Any]:
        """Parse search results to extract company information"""
        enriched_data = {
            "search_enriched": True,
            "search_source": "serper_google"
        }

        # Extract from organic results
        organic = search_data.get("organic", [])
        for result in organic[:3]:  # Check first 3 results
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            link = result.get("link", "")

            # Look for LinkedIn company page
            if "linkedin.com/company" in link:
                enriched_data["linkedin_company_url"] = link

            # Look for company size indicators
            size_patterns = [
                r'(\d+)-(\d+)\s+employees',
                r'(\d+)\+?\s+employees',
                r'team of (\d+)',
                r'staff of (\d+)'
            ]

            for pattern in size_patterns:
                match = re.search(pattern, snippet)
                if match:
                    enriched_data["estimated_size"] = match.group(0)
                    break

            # Look for industry indicators
            industry_keywords = [
                "financial services", "consulting", "technology", "healthcare",
                "manufacturing", "retail", "education", "real estate",
                "marketing", "legal", "insurance", "banking"
            ]

            for keyword in industry_keywords:
                if keyword in snippet or keyword in title:
                    enriched_data["industry_hint"] = keyword.title()
                    break

        # Extract from knowledge graph if available
        knowledge_graph = search_data.get("knowledgeGraph", {})
        if knowledge_graph:
            enriched_data["knowledge_graph"] = {
                "type": knowledge_graph.get("type"),
                "description": knowledge_graph.get("description"),
                "website": knowledge_graph.get("website")
            }

        return enriched_data

    async def scrape_company_website(self, domain: str) -> Dict[str, Any]:
        """Scrape company website for additional information"""
        if not self.firecrawl_api_key:
            return {}

        try:
            headers = {
                "Authorization": f"Bearer {self.firecrawl_api_key}",
                "Content-Type": "application/json"
            }

            # Try to scrape the main page and about page
            urls_to_try = [
                f"https://{domain}",
                f"https://{domain}/about",
                f"https://{domain}/about-us",
                f"https://{domain}/company"
            ]

            for url in urls_to_try:
                try:
                    payload = {
                        "url": url,
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                        "timeout": 8000
                    }

                    response = requests.post(
                        "https://api.firecrawl.dev/v1/scrape",
                        headers=headers,
                        json=payload,
                        timeout=15
                    )

                    if response.status_code == 200:
                        data = response.json()
                        markdown_content = data.get("data", {}).get("markdown", "")

                        if markdown_content and len(markdown_content) > 100:
                            return self._extract_company_details(markdown_content, url)

                    # Rate limiting
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping company website {domain}: {e}")

        return {}

    def _extract_company_details(self, content: str, source_url: str) -> Dict[str, Any]:
        """Extract company details from scraped content"""
        details = {
            "website_scraped": True,
            "source_url": source_url
        }

        content_lower = content.lower()

        # Extract company description (first paragraph with substantial content)
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if len(para) > 100 and not para.startswith('#'):
                details["company_description"] = para[:500] + "..." if len(para) > 500 else para
                break

        # Look for contact information
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        if emails:
            # Filter out common non-business emails
            business_emails = [e for e in emails if not any(x in e.lower() for x in ['noreply', 'no-reply', 'example.com'])]
            if business_emails:
                details["contact_email"] = business_emails[0]

        # Look for phone numbers
        phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'
        phones = re.findall(phone_pattern, content)
        if phones:
            details["contact_phone"] = f"({phones[0][0]}) {phones[0][1]}-{phones[0][2]}"

        # Look for location information
        location_patterns = [
            r'headquartered in ([^,\n]+)',
            r'based in ([^,\n]+)',
            r'located in ([^,\n]+)',
            r'office[s]? in ([^,\n]+)'
        ]

        for pattern in location_patterns:
            match = re.search(pattern, content_lower)
            if match:
                details["headquarters"] = match.group(1).title()
                break

        # Look for employee count
        employee_patterns = [
            r'(\d+)\+?\s+employees',
            r'team of (\d+)',
            r'staff of (\d+)',
            r'(\d+)-(\d+)\s+people'
        ]

        for pattern in employee_patterns:
            match = re.search(pattern, content_lower)
            if match:
                details["team_size"] = match.group(0)
                break

        return details

    def validate_and_enhance_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance contact information"""
        enhanced_contact = contact_data.copy()

        # Validate email format
        email = enhanced_contact.get("email")
        if email:
            email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
            if re.match(email_pattern, email):
                enhanced_contact["email_valid"] = True
                # Extract domain for company matching
                enhanced_contact["email_domain"] = self.extract_domain_from_email(email)
            else:
                enhanced_contact["email_valid"] = False

        # Standardize phone format
        phone = enhanced_contact.get("phone")
        if phone:
            # Remove all non-digits
            digits = re.sub(r'\D', '', phone)
            if len(digits) == 10:
                enhanced_contact["phone_formatted"] = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            elif len(digits) == 11 and digits[0] == '1':
                enhanced_contact["phone_formatted"] = f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

        # Enhance name formatting
        first_name = enhanced_contact.get("first_name", "").strip()
        last_name = enhanced_contact.get("last_name", "").strip()
        if first_name:
            enhanced_contact["first_name"] = first_name.title()
        if last_name:
            enhanced_contact["last_name"] = last_name.title()

        if first_name and last_name:
            enhanced_contact["full_name"] = f"{first_name} {last_name}".title()

        return enhanced_contact

    async def enrich_extracted_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich extracted data with additional information"""
        if not self.is_enabled():
            logger.info("Enhanced enrichment disabled - returning original data")
            return extracted_data

        enhanced_data = extracted_data.copy()

        try:
            # Get basic data
            contact_record = extracted_data.get("contact_record", {})
            company_record = extracted_data.get("company_record", {})

            # Enhance contact data
            if contact_record:
                enhanced_contact = self.validate_and_enhance_contact(contact_record)
                enhanced_data["contact_record"] = enhanced_contact

            # Get company domain for enrichment
            company_domain = None
            company_name = company_record.get("company_name", "")

            # Try to get domain from website
            website = company_record.get("website")
            if website:
                company_domain = self.normalize_domain(website)

            # Fall back to email domain
            if not company_domain:
                contact_email = contact_record.get("email")
                if contact_email:
                    company_domain = self.extract_domain_from_email(contact_email)

            # Enrich company data if we have a domain or name
            if company_domain or company_name:
                logger.info(f"Enriching company: {company_name} ({company_domain})")

                # Run searches in parallel
                search_task = self.search_company_info(company_name, company_domain)
                scrape_task = None

                if company_domain:
                    scrape_task = self.scrape_company_website(company_domain)

                # Wait for results
                search_results = await search_task
                scrape_results = await scrape_task if scrape_task else {}

                # Merge enriched data
                enhanced_company = company_record.copy()
                enhanced_company.update(search_results)
                enhanced_company.update(scrape_results)

                # Add normalized domain
                if company_domain:
                    enhanced_company["normalized_domain"] = company_domain

                enhanced_data["company_record"] = enhanced_company

                logger.info("Company data enriched successfully")

            # Add enrichment metadata
            enhanced_data["enrichment_metadata"] = {
                "enhanced": True,
                "services_used": [],
                "timestamp": time.time()
            }

            if self.firecrawl_api_key:
                enhanced_data["enrichment_metadata"]["services_used"].append("firecrawl")
            if self.serper_api_key:
                enhanced_data["enrichment_metadata"]["services_used"].append("serper")

        except Exception as e:
            logger.error(f"Error during enhanced enrichment: {e}")
            # Return original data if enrichment fails
            enhanced_data["enrichment_metadata"] = {
                "enhanced": False,
                "error": str(e),
                "timestamp": time.time()
            }

        return enhanced_data

# Singleton instance
enhanced_enrichment_service = EnhancedEnrichmentService()