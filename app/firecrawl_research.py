"""
Firecrawl integration for company research
Provides web scraping and research capabilities for the LangGraph workflow
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Any
import aiohttp
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class FirecrawlResearcher:
    """Web research using Firecrawl API for company validation"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.base_url = "https://api.firecrawl.dev/v1"
        
        if not self.api_key:
            logger.warning("Firecrawl API key not configured")
        else:
            logger.info("Firecrawl researcher initialized")
    
    async def research_company_domain(self, domain: str) -> Dict[str, Any]:
        """Research a company based on its email domain"""
        
        if not self.api_key:
            logger.warning("Firecrawl API key not available")
            return {"company_name": None, "confidence": 0}
        
        try:
            # First, try to scrape the main website
            website_url = f"https://{domain}"
            logger.info(f"Researching company website: {website_url}")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Scrape the website to get company information
            async with aiohttp.ClientSession() as session:
                scrape_data = {
                    "url": website_url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "maxAge": 172800000  # Cache for 2 days
                }
                
                async with session.post(
                    f"{self.base_url}/scrape",
                    headers=headers,
                    json=scrape_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        company_info = self._extract_company_from_content(
                            result.get("markdown", ""),
                            domain
                        )
                        return company_info
                    else:
                        logger.warning(f"Firecrawl scrape failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Firecrawl research error: {e}")
        
        # Fallback: Try to search for the domain
        return await self.search_company(domain)
    
    async def search_company(self, query: str) -> Dict[str, Any]:
        """Search for company information using Firecrawl search"""
        
        if not self.api_key:
            return {"company_name": None, "confidence": 0}
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            search_data = {
                "query": f"{query} company official name headquarters",
                "limit": 3,
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json=search_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return self._extract_company_from_search(result, query)
                    else:
                        logger.warning(f"Firecrawl search failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Firecrawl search error: {e}")
        
        return {"company_name": None, "confidence": 0}
    
    def _extract_company_from_content(self, content: str, domain: str) -> Dict[str, Any]:
        """Extract company name from scraped content"""
        
        # Look for common patterns in website content
        patterns = [
            "Welcome to ",
            "About ",
            "© ",
            "Copyright ",
            domain.split('.')[0].title()
        ]
        
        company_name = None
        confidence = 0.0
        
        # Try to find company name in content
        content_lower = content.lower()
        
        # Look for the domain name in various forms
        domain_base = domain.split('.')[0]
        
        if domain_base in content_lower:
            # Found domain reference, look for proper name nearby
            lines = content.split('\n')
            for line in lines[:10]:  # Check first 10 lines
                if domain_base.lower() in line.lower():
                    # Clean and extract potential company name
                    clean_line = line.strip()
                    if clean_line and len(clean_line) < 100:
                        company_name = clean_line.split('|')[0].strip()
                        company_name = company_name.split('-')[0].strip()
                        confidence = 0.8
                        break
        
        if not company_name:
            # Fallback to domain-based inference
            company_name = domain_base.replace('-', ' ').replace('_', ' ').title()
            confidence = 0.6
        
        return {
            "company_name": company_name,
            "confidence": confidence,
            "source": "website_scrape"
        }
    
    def _extract_company_from_search(self, search_results: Dict, query: str) -> Dict[str, Any]:
        """Extract company information from search results"""
        
        if not search_results.get("web"):
            return {"company_name": None, "confidence": 0}
        
        # Analyze search results
        for result in search_results["web"][:3]:
            title = result.get("title", "")
            description = result.get("description", "")
            markdown = result.get("markdown", "")
            
            # Look for company indicators
            if "company" in title.lower() or "inc" in title.lower() or "llc" in title.lower():
                # Extract company name from title
                company_name = title.split('-')[0].strip()
                company_name = company_name.split('|')[0].strip()
                
                return {
                    "company_name": company_name,
                    "confidence": 0.7,
                    "source": "web_search"
                }
        
        # Fallback
        query_base = query.split('.')[0] if '.' in query else query
        return {
            "company_name": query_base.replace('-', ' ').title(),
            "confidence": 0.5,
            "source": "inference"
        }


class CompanyResearchService:
    """Service layer for company research combining multiple sources"""
    
    def __init__(self):
        self.firecrawl = FirecrawlResearcher()
        logger.info("Company research service initialized")
    
    async def search_candidate_info(self, candidate_name: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for candidate's LinkedIn, company website, and contact information
        
        Returns:
            Dict with linkedin_url, website, email, phone, company_name
        """
        
        if not self.firecrawl.api_key:
            logger.warning("Firecrawl API key not available for candidate search")
            return {}
        
        try:
            # Build search query
            search_query = candidate_name
            if company_name:
                search_query = f"{candidate_name} {company_name}"
            
            logger.info(f"Searching for candidate info: {search_query}")
            
            headers = {
                "Authorization": f"Bearer {self.firecrawl.api_key}",
                "Content-Type": "application/json"
            }
            
            # Search for candidate information
            search_data = {
                "query": f"{search_query} LinkedIn OR contact OR email",
                "limit": 5,
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.firecrawl.base_url}/search",
                    headers=headers,
                    json=search_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return self._extract_candidate_info(result, candidate_name)
                    else:
                        logger.warning(f"Firecrawl candidate search failed: {response.status}")
        
        except asyncio.TimeoutError:
            logger.warning("Firecrawl candidate search timed out")
        except Exception as e:
            logger.error(f"Firecrawl candidate search error: {e}")
        
        return {}
    
    def _extract_candidate_info(self, search_results: Dict, candidate_name: str) -> Dict[str, Any]:
        """Extract candidate information from search results"""
        
        extracted_info = {}
        
        if not search_results.get("data"):
            return extracted_info
        
        # Process search results
        for result in search_results["data"][:5]:
            url = result.get("url", "")
            content = result.get("markdown", "")
            
            # Check for LinkedIn URL
            if "linkedin.com/in/" in url and "linkedin_url" not in extracted_info:
                extracted_info["linkedin_url"] = url
                logger.info(f"Found LinkedIn: {url}")
            
            # Extract email from content
            if "email" not in extracted_info:
                import re
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                emails = re.findall(email_pattern, content)
                for email in emails:
                    # Skip generic emails
                    if not any(x in email.lower() for x in ['noreply', 'support', 'info', 'admin']):
                        extracted_info["email"] = email
                        logger.info(f"Found email: {email}")
                        break
            
            # Extract phone from content
            if "phone" not in extracted_info:
                import re
                phone_patterns = [
                    r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US phone
                    r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',  # US phone with parens
                    r'\b\d{3}\.\d{3}\.\d{4}\b'  # US phone with dots
                ]
                for pattern in phone_patterns:
                    phones = re.findall(pattern, content)
                    if phones:
                        extracted_info["phone"] = phones[0]
                        logger.info(f"Found phone: {phones[0]}")
                        break
            
            # Extract company website
            if "website" not in extracted_info and candidate_name.lower() in content.lower():
                # Look for company website mentions
                url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
                urls = re.findall(url_pattern, content)
                for found_url in urls:
                    if not any(x in found_url for x in ['linkedin.com', 'facebook.com', 'twitter.com']):
                        extracted_info["website"] = f"https://{found_url}"
                        logger.info(f"Found website: {extracted_info['website']}")
                        break
        
        return extracted_info
    
    async def research_company(self, 
                              email_domain: str,
                              company_guess: Optional[str] = None) -> Dict[str, Any]:
        """
        Research company using multiple strategies
        
        Returns:
            Dict with company_name, confidence, and source
        """
        
        best_result = {
            "company_name": None,
            "confidence": 0.0,
            "source": "unknown"
        }
        
        # Strategy 1: Use explicit company name if provided with high confidence
        if company_guess:
            best_result = {
                "company_name": company_guess,
                "confidence": 0.85,
                "source": "email_content"
            }
        
        # Strategy 2: Research the domain if confidence is not high enough
        if best_result["confidence"] < 0.85 and email_domain:
            try:
                research_result = await self.firecrawl.research_company_domain(email_domain)
                
                if research_result["confidence"] > best_result["confidence"]:
                    best_result = research_result
                    
            except Exception as e:
                logger.warning(f"Domain research failed: {e}")
        
        # Strategy 3: Fallback to domain inference if needed
        if best_result["confidence"] < 0.5 and email_domain:
            domain_parts = email_domain.split('.')
            if domain_parts:
                company_name = domain_parts[0].replace('-', ' ').replace('_', ' ').title()
                best_result = {
                    "company_name": company_name,
                    "confidence": 0.4,
                    "source": "domain_inference"
                }
        
        logger.info(f"Company research result: {best_result}")
        return best_result