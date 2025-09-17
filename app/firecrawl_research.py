#!/usr/bin/env python3
"""
Company Research Service using Firecrawl v2 Fire Agent
Provides domain-based company research for the LangGraph workflow
"""
import logging
from typing import Dict, Optional, Any
from .firecrawl_v2_fire_agent import FirecrawlV2Client

logger = logging.getLogger(__name__)

class CompanyResearchService:
    """Service for researching companies using Firecrawl v2 Fire Agent"""

    def __init__(self):
        self.client = FirecrawlV2Client()

    async def research_company(self, email_domain: str, company_guess: Optional[str] = None) -> Dict[str, Any]:
        """
        Research company information from email domain or company name

        Args:
            email_domain: Company email domain (e.g., "mariner.com")
            company_guess: Optional company name guess

        Returns:
            Dict containing company information
        """
        try:
            # First try to extract company name from domain
            company_name = company_guess or self._domain_to_company_name(email_domain)

            logger.info(f"Researching company: {company_name} (domain: {email_domain})")

            # Use Firecrawl v2 to research the company
            urls = [
                f"https://{email_domain}",
                f"https://www.{email_domain}",
                f"https://www.google.com/search?q={company_name} company website contact"
            ]

            # Extract comprehensive company data
            result = self.client.extract(
                urls=urls,
                prompt=f"""Extract comprehensive company information for {company_name}:
                - Company name (official name)
                - Website URL
                - Phone number (main business line)
                - Physical address and locations
                - Company description/industry
                - Key executives and contact information
                - Social media profiles (LinkedIn, etc.)

                Focus on official, verified information from the company website or reliable sources.""",
                enable_web_search=True,
                use_fire_agent=True
            )

            if result.success and result.data:
                # Parse and structure the extracted data
                company_data = self._parse_company_data(result.data, company_name, email_domain)
                company_data['confidence'] = 0.9  # High confidence from Firecrawl research
                logger.info(f"Successfully researched company: {company_name}")
                return company_data
            else:
                logger.warning(f"Firecrawl research failed for {company_name}: {result.data}")
                return self._fallback_company_data(company_name, email_domain)

        except Exception as e:
            logger.error(f"Error researching company {email_domain}: {e}")
            return self._fallback_company_data(company_guess or email_domain, email_domain)

    def _domain_to_company_name(self, domain: str) -> str:
        """Convert email domain to probable company name"""
        # Remove common prefixes/suffixes
        name = domain.replace('www.', '').split('.')[0]

        # Convert to title case and handle common patterns
        if '-' in name:
            name = ' '.join(word.title() for word in name.split('-'))
        elif '_' in name:
            name = ' '.join(word.title() for word in name.split('_'))
        else:
            name = name.title()

        return name

    def _parse_company_data(self, raw_data: Dict, company_name: str, email_domain: str) -> Dict[str, Any]:
        """Parse raw Firecrawl data into structured company information"""

        # Extract key fields from the research data
        company_info = {
            'company_name': company_name,
            'website': f"https://{email_domain}",
            'phone': None,
            'address': None,
            'industry': None,
            'description': None,
            'linkedin': None,
            'executives': [],
            'confidence': 0.9
        }

        # Parse extracted data (structure depends on Firecrawl response format)
        if isinstance(raw_data, dict):
            # Look for common field names
            for key, value in raw_data.items():
                if 'phone' in key.lower() and value:
                    company_info['phone'] = str(value).strip()
                elif 'website' in key.lower() and value:
                    company_info['website'] = str(value).strip()
                elif 'address' in key.lower() and value:
                    company_info['address'] = str(value).strip()
                elif 'industry' in key.lower() and value:
                    company_info['industry'] = str(value).strip()
                elif 'description' in key.lower() and value:
                    company_info['description'] = str(value).strip()
                elif 'linkedin' in key.lower() and value:
                    company_info['linkedin'] = str(value).strip()

        return company_info

    def _fallback_company_data(self, company_name: str, email_domain: str) -> Dict[str, Any]:
        """Provide fallback company data when research fails"""
        return {
            'company_name': company_name,
            'website': f"https://{email_domain}",
            'phone': None,
            'address': None,
            'industry': None,
            'description': f"Company information from {email_domain}",
            'linkedin': None,
            'executives': [],
            'confidence': 0.3  # Low confidence fallback
        }

    async def search_candidate_info(self, candidate_name: str, company_guess: Optional[str] = None) -> Dict[str, Any]:
        """Search for candidate information using Firecrawl"""
        try:
            logger.info(f"Searching for candidate: {candidate_name}")

            # Search for candidate on LinkedIn and company websites
            search_urls = [
                f"https://www.google.com/search?q={candidate_name} LinkedIn profile",
                f"https://www.google.com/search?q={candidate_name} {company_guess or ''} contact"
            ]

            result = self.client.extract(
                urls=search_urls,
                prompt=f"""Find information about {candidate_name}:
                - Current company and job title
                - LinkedIn profile URL
                - Contact information
                - Professional background
                - Company website if available""",
                enable_web_search=True,
                use_fire_agent=True
            )

            if result.success and result.data:
                return self._parse_candidate_data(result.data, candidate_name)
            else:
                return {}

        except Exception as e:
            logger.error(f"Error searching candidate {candidate_name}: {e}")
            return {}

    def _parse_candidate_data(self, raw_data: Dict, candidate_name: str) -> Dict[str, Any]:
        """Parse candidate research data"""
        candidate_info = {
            'name': candidate_name,
            'company': None,
            'title': None,
            'linkedin': None,
            'website': None
        }

        if isinstance(raw_data, dict):
            for key, value in raw_data.items():
                if 'company' in key.lower() and value:
                    candidate_info['company'] = str(value).strip()
                elif 'title' in key.lower() or 'position' in key.lower() and value:
                    candidate_info['title'] = str(value).strip()
                elif 'linkedin' in key.lower() and value:
                    candidate_info['linkedin'] = str(value).strip()
                elif 'website' in key.lower() and value:
                    candidate_info['website'] = str(value).strip()

        return candidate_info