#!/usr/bin/env python3
"""
Firecrawl v2 Enterprise Integration with FIRE-1 Agent
Complete implementation using Extract API with advanced agent capabilities
"""
import os
import json
import logging
import requests
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass, field
from datetime import datetime
import time
from dotenv import load_dotenv

load_dotenv('.env.local')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    """Result from Firecrawl extraction"""
    success: bool
    data: Dict
    status: str
    job_id: Optional[str] = None
    expires_at: Optional[str] = None
    tokens_used: Optional[int] = None

class FirecrawlV2Client:
    """
    Firecrawl v2 Client with FIRE-1 Agent Support
    Implements Extract endpoint with advanced capabilities
    """

    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment")

        self.base_url = "https://api.firecrawl.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def extract(
        self,
        urls: List[str],
        prompt: Optional[str] = None,
        schema: Optional[Dict] = None,
        enable_web_search: bool = False,
        use_fire_agent: bool = False,
        wait_for_completion: bool = True,
        timeout: int = 60
    ) -> ExtractionResult:
        """
        Extract structured data from URLs using Firecrawl v2

        Args:
            urls: List of URLs to extract from (supports wildcards like example.com/*)
            prompt: Natural language description of data to extract
            schema: JSON schema for structured extraction
            enable_web_search: Allow following links outside specified domains
            use_fire_agent: Enable FIRE-1 agent for complex navigation
            wait_for_completion: Wait for extraction to complete
            timeout: Maximum time to wait for completion

        Returns:
            ExtractionResult with extracted data
        """
        if not urls:
            raise ValueError("At least one URL is required")

        if not prompt and not schema:
            raise ValueError("Either prompt or schema is required")

        logger.info(f"🔥 Extracting from {len(urls)} URL(s) with {'FIRE-1 agent' if use_fire_agent else 'standard extraction'}")

        # Build request payload
        payload = {
            "urls": urls
        }

        if prompt:
            payload["prompt"] = prompt

        if schema:
            payload["schema"] = schema

        if enable_web_search:
            payload["enableWebSearch"] = True

        if use_fire_agent:
            payload["agent"] = {
                "model": "FIRE-1"
            }

        # Start extraction job
        try:
            response = requests.post(
                f"{self.base_url}/extract",
                json=payload,
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"❌ Extract failed: {response.status_code} - {response.text}")
                return ExtractionResult(
                    success=False,
                    data={},
                    status="failed"
                )

            result = response.json()

            # If job is async, we get a job ID
            if result.get("status") == "processing":
                job_id = result.get("id")
                logger.info(f"📋 Extraction job started: {job_id}")

                if wait_for_completion:
                    return self._wait_for_extraction(job_id, timeout)
                else:
                    return ExtractionResult(
                        success=True,
                        data={},
                        status="processing",
                        job_id=job_id,
                        expires_at=result.get("expiresAt")
                    )

            # Direct result (for simple extractions)
            return ExtractionResult(
                success=result.get("success", False),
                data=result.get("data", {}),
                status=result.get("status", "completed"),
                expires_at=result.get("expiresAt"),
                tokens_used=result.get("tokensUsed")
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error: {e}")
            return ExtractionResult(
                success=False,
                data={},
                status="failed"
            )

    def _wait_for_extraction(self, job_id: str, timeout: int) -> ExtractionResult:
        """
        Wait for extraction job to complete

        Args:
            job_id: The extraction job ID
            timeout: Maximum time to wait

        Returns:
            ExtractionResult with final data
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.base_url}/extract/{job_id}",
                    headers=self.headers,
                    timeout=10
                )

                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status")

                    if status == "completed":
                        logger.info("✅ Extraction completed successfully")
                        return ExtractionResult(
                            success=True,
                            data=result.get("data", {}),
                            status="completed",
                            job_id=job_id,
                            expires_at=result.get("expiresAt"),
                            tokens_used=result.get("tokensUsed")
                        )

                    elif status == "failed":
                        logger.error("❌ Extraction failed")
                        return ExtractionResult(
                            success=False,
                            data={},
                            status="failed",
                            job_id=job_id
                        )

                    elif status == "cancelled":
                        logger.warning("⚠️ Extraction cancelled")
                        return ExtractionResult(
                            success=False,
                            data={},
                            status="cancelled",
                            job_id=job_id
                        )

                    # Still processing
                    logger.debug(f"⏳ Still processing... ({int(time.time() - start_time)}s)")

            except Exception as e:
                logger.error(f"Error checking status: {e}")

            time.sleep(2)  # Poll every 2 seconds

        logger.warning(f"⏱️ Extraction timed out after {timeout} seconds")
        return ExtractionResult(
            success=False,
            data={},
            status="timeout",
            job_id=job_id
        )

    def extract_with_fire_agent(
        self,
        urls: List[str],
        extraction_goal: str,
        schema: Optional[Dict] = None
    ) -> ExtractionResult:
        """
        Use FIRE-1 agent for complex extractions requiring navigation

        Args:
            urls: Starting URLs for extraction
            extraction_goal: Description of what to extract
            schema: Optional schema for structured output

        Returns:
            ExtractionResult with extracted data
        """
        logger.info(f"🚀 Using FIRE-1 agent for complex extraction")

        # FIRE-1 is particularly good at:
        # - Navigating through multiple pages
        # - Handling dynamic content
        # - Extracting from complex structures like forums
        # - Following pagination

        return self.extract(
            urls=urls,
            prompt=extraction_goal,
            schema=schema,
            enable_web_search=True,  # Often needed for complex tasks
            use_fire_agent=True,
            wait_for_completion=True
        )

class LinkedInExtractor:
    """
    Specialized extractor for LinkedIn and company data
    Uses FIRE-1 agent for complex profile extraction
    """

    def __init__(self):
        self.client = FirecrawlV2Client()

    def extract_company_linkedin_data(self, company_url: str) -> Dict:
        """
        Extract company data including LinkedIn profiles of executives

        Args:
            company_url: Company website URL

        Returns:
            Dictionary with company data and LinkedIn profiles
        """
        schema = {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "company_description": {"type": "string"},
                "linkedin_company_url": {"type": "string"},
                "executives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "title": {"type": "string"},
                            "linkedin_url": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"}
                        },
                        "required": ["name", "title"]
                    }
                },
                "contact_info": {
                    "type": "object",
                    "properties": {
                        "main_phone": {"type": "string"},
                        "main_email": {"type": "string"},
                        "address": {"type": "string"}
                    }
                }
            },
            "required": ["company_name"]
        }

        prompt = """
        Extract comprehensive company information including:
        1. Company name and description
        2. LinkedIn company page URL
        3. All executive team members with their names, titles, and LinkedIn profiles
        4. Contact information (phone, email, address)

        Search the About, Team, Leadership, and Contact pages for this information.
        """

        # Use wildcard to crawl entire site
        urls = [f"{company_url}/*"] if not company_url.endswith("/*") else [company_url]

        result = self.client.extract_with_fire_agent(
            urls=urls,
            extraction_goal=prompt,
            schema=schema
        )

        return result.data if result.success else {}

    def extract_person_profile(self, person_name: str, company_name: str) -> Dict:
        """
        Extract person profile data from LinkedIn and web sources

        Args:
            person_name: Name of the person to search for
            company_name: Company they work at

        Returns:
            Dictionary with person profile data
        """
        logger.info(f"🔍 Searching for {person_name} at {company_name}")

        # Build search query
        search_query = f"{person_name} {company_name} LinkedIn"

        # Define schema for person data extraction
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "title": {"type": "string"},
                "company": {"type": "string"},
                "linkedin_url": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "location": {"type": "string"},
                "bio": {"type": "string"},
                "experience": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "company": {"type": "string"},
                            "duration": {"type": "string"}
                        }
                    }
                },
                "education": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "degree": {"type": "string"},
                            "school": {"type": "string"},
                            "year": {"type": "string"}
                        }
                    }
                }
            }
        }

        prompt = f"""
        Find and extract professional profile information for {person_name} who works at {company_name}.
        Look for:
        1. LinkedIn profile URL
        2. Current job title and company
        3. Contact information (email, phone if available)
        4. Location
        5. Professional biography or summary
        6. Work experience history
        7. Education background

        Focus on finding the most accurate and up-to-date information.
        """

        try:
            # Use FIRE-1 agent for comprehensive search
            result = self.client.extract_with_fire_agent(
                urls=[f"https://www.google.com/search?q={search_query}"],
                extraction_goal=prompt,
                schema=schema
            )

            if result.success:
                data = result.data
                return {
                    "success": True,
                    "data": {
                        "name": data.get("name", person_name),
                        "title": data.get("title", ""),
                        "company": data.get("company", company_name),
                        "linkedin_url": data.get("linkedin_url", ""),
                        "email": data.get("email", ""),
                        "phone": data.get("phone", ""),
                        "location": data.get("location", ""),
                        "bio": data.get("bio", ""),
                        "experience": data.get("experience", []),
                        "education": data.get("education", [])
                    },
                    "confidence": 0.9 if data.get("linkedin_url") else 0.7,
                    "extraction_method": "FIRE-1 Agent Person Search"
                }
            else:
                # Fallback to basic search
                logger.warning("FIRE-1 extraction failed, using fallback")
                return {
                    "success": False,
                    "data": {
                        "name": person_name,
                        "company": company_name
                    },
                    "error": "Could not find detailed profile information"
                }

        except Exception as e:
            logger.error(f"❌ Person profile extraction failed: {e}")
            return {
                "success": False,
                "data": {
                    "name": person_name,
                    "company": company_name
                },
                "error": str(e)
            }

    def extract_linkedin_from_email(self, email_data: Dict) -> Dict:
        """
        Extract LinkedIn profiles from email content

        Args:
            email_data: Email data with sender info and body

        Returns:
            Enhanced data with LinkedIn profiles
        """
        # Extract domain from email
        email = email_data.get("sender_email", "")
        if "@" not in email:
            return {"error": "No valid email found"}

        domain = email.split("@")[1]
        company_url = f"https://{domain}"

        # Extract company data
        company_data = self.extract_company_linkedin_data(company_url)

        # Try to match sender with executives
        sender_name = email_data.get("sender_name", "").lower()
        sender_linkedin = None

        for exec in company_data.get("executives", []):
            if exec.get("name", "").lower() in sender_name or sender_name in exec.get("name", "").lower():
                sender_linkedin = exec.get("linkedin_url")
                break

        return {
            "sender": {
                "name": email_data.get("sender_name"),
                "email": email,
                "linkedin_url": sender_linkedin
            },
            "company": company_data,
            "extraction_method": "FIRE-1 Agent",
            "confidence": 0.9 if sender_linkedin else 0.7
        }

def integrate_with_langgraph(extraction_result: Dict) -> Dict:
    """
    Integrate Firecrawl extraction with LangGraph workflow

    Args:
        extraction_result: Initial extraction from LangGraph

    Returns:
        Enhanced extraction with Firecrawl data
    """
    try:
        extractor = LinkedInExtractor()

        # Prepare email data
        email_data = {
            "sender_name": f"{extraction_result.get('first_name', '')} {extraction_result.get('last_name', '')}".strip(),
            "sender_email": extraction_result.get("email", ""),
            "body": extraction_result.get("original_body", "")
        }

        # Extract LinkedIn data
        enhanced = extractor.extract_linkedin_from_email(email_data)

        # Merge results
        if enhanced.get("company"):
            extraction_result["company_linkedin"] = enhanced["company"].get("linkedin_company_url")
            extraction_result["company_executives"] = enhanced["company"].get("executives", [])

            # Update company info if we found better data
            if enhanced["company"].get("company_name"):
                extraction_result["company_name"] = enhanced["company"]["company_name"]

        if enhanced.get("sender", {}).get("linkedin_url"):
            extraction_result["linkedin_url"] = enhanced["sender"]["linkedin_url"]

        extraction_result["firecrawl_confidence"] = enhanced.get("confidence", 0.0)
        extraction_result["extraction_method"] = enhanced.get("extraction_method", "standard")

    except Exception as e:
        logger.error(f"Firecrawl enhancement failed: {e}")
        # Return original if enhancement fails

    return extraction_result

class FirecrawlV2Enterprise:
    """Main Firecrawl v2 Enterprise API with FIRE agent support"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API key from environment or parameter"""
        self.client = FirecrawlV2Client()
        self.linkedin_extractor = LinkedInExtractor()
        self.logger = logging.getLogger(__name__)

    def extract_linkedin_profiles(
        self,
        urls: List[str],
        search_for: str = "LinkedIn profiles of executives and leadership team"
    ) -> Dict:
        """Extract LinkedIn profiles from company websites"""
        schema = {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "linkedin_url": {"type": "string"},
                "executives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "title": {"type": "string"},
                            "linkedin_url": {"type": "string"}
                        }
                    }
                }
            }
        }

        result = self.client.extract(
            urls=urls,
            prompt=search_for,
            schema=schema,
            enable_web_search=True,
            use_fire_agent=True
        )

        return {
            "success": result.success,
            "data": result.data,
            "error": None if result.success else "Extraction failed"
        }

    def research_company(
        self,
        company_name: str,
        enable_web_search: bool = True
    ) -> Dict:
        """Research company information using Scrape API"""
        logger.info(f"🔍 Starting company research for: {company_name}")

        # Use the company domain directly for better results
        company_url = f"https://{company_name}" if not company_name.startswith('http') else company_name
        logger.info(f"🌐 Constructed URL: {company_url}")

        try:
            # Use basic scrape API which works with our token limits
            payload = {
                "url": company_url,
                "formats": ["markdown"],
                "onlyMainContent": True
            }
            logger.info(f"📡 Sending Firecrawl request with payload: {payload}")

            response = requests.post(
                f"{self.client.base_url}/scrape",
                json=payload,
                headers=self.client.headers,
                timeout=30
            )

            logger.info(f"📋 Firecrawl response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Firecrawl response success: {result.get('success')}")

                if result.get("success"):
                    markdown_content = result.get("data", {}).get("markdown", "")
                    logger.info(f"📄 Markdown content length: {len(markdown_content)}")
                    logger.debug(f"📄 Markdown preview: {markdown_content[:200]}...")

                    # Extract basic company info from markdown
                    company_data = self._parse_company_data(markdown_content, company_name)
                    logger.info(f"🏢 Parsed company data: {company_data}")

                    return {
                        "success": True,
                        "data": company_data,
                        "error": None
                    }
                else:
                    logger.error(f"❌ Firecrawl returned success=False: {result}")

            logger.warning(f"Company research failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Company research error: {e}")

        return {
            "success": False,
            "data": {},
            "error": "Research failed - could not scrape company website"
        }

    def enrich_executive_data(
        self,
        person_name: str,
        company_name: str
    ) -> Dict:
        """Enrich executive data with basic profile info"""
        # Simplified approach - return basic structure
        return {
            "name": person_name,
            "title": "",
            "company": company_name,
            "linkedin_url": "",
            "email": "",
            "phone": "",
            "location": "",
            "bio": ""
        }

    def _parse_company_data(self, markdown_content: str, company_name: str) -> Dict:
        """Parse company data from scraped markdown content"""
        import re

        # Extract basic company information from markdown
        # Extract actual company name from content instead of using URL
        extracted_company_name = self._extract_company_name_from_content(markdown_content, company_name)

        company_data = {
            "company_name": extracted_company_name,
            "description": "",
            "phone": "",
            "email": "",
            "address": "",
            "linkedin_url": "",
            "website": f"https://{company_name}" if not company_name.startswith('http') else company_name,
            "executives": [],
            "contact": {}
        }

        if not markdown_content:
            return company_data

        # Look for phone numbers with context prioritization
        phone_pattern = r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'

        # Find all phone numbers with surrounding context for better selection
        company_phone = self._extract_company_phone(markdown_content, phone_pattern)
        if company_phone:
            company_data["phone"] = company_phone
            company_data["contact"]["phone"] = company_phone

        # Look for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, markdown_content)
        if emails:
            # Filter out common generic emails and prefer contact/info emails
            filtered_emails = [e for e in emails if any(keyword in e.lower() for keyword in ['contact', 'info', 'hello', 'support'])]
            company_data["email"] = filtered_emails[0] if filtered_emails else emails[0]
            company_data["contact"]["email"] = company_data["email"]

        # Look for LinkedIn URL
        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/company/[^\\s)"]+'
        linkedin_matches = re.findall(linkedin_pattern, markdown_content)
        if linkedin_matches:
            company_data["linkedin_url"] = linkedin_matches[0]

        # Extract first paragraph as description (simple heuristic)
        lines = markdown_content.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 50 and not line.startswith('#') and not line.startswith('*'):
                company_data["description"] = line[:200] + "..." if len(line) > 200 else line
                break

        # Look for address patterns and extract city/state
        address_pattern = r'\d+[^,\n]*(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)[^,\n]*(?:,\s*[^,\n]+)*(?:,\s*[A-Z]{2})?(?:\s+\d{5})?'
        addresses = re.findall(address_pattern, markdown_content, re.IGNORECASE)
        if addresses:
            company_data["address"] = addresses[0]
            company_data["contact"]["address"] = company_data["address"]
            # Store for city/state extraction
            self._last_extracted_address = company_data["address"]

        # Extract city and state from content (including the address we just found)
        city_state_data = self._extract_city_state_from_content(markdown_content)
        if city_state_data:
            company_data["contact"].update(city_state_data)
            # Also add city/state at the top level for LangGraph research node
            company_data.update(city_state_data)

        return company_data

    def _extract_company_name_from_content(self, markdown_content: str, fallback_url: str) -> str:
        """Extract actual company name from website content"""
        import re

        # Try different patterns to find company name
        patterns = [
            # Look for title tags or h1 headers
            r'(?i)(?:^|\n)#{1,2}\s*([^#\n]+?)(?:\s*-\s*(?:Home|Welcome|About))?(?:\n|$)',
            # Look for "About [Company]" or "Welcome to [Company]"
            r'(?i)(?:About|Welcome to)\s+([A-Z][^,.\n]*?(?:\s+)?(?:Inc|LLC|Corp|Company|Group|Holdings|Solutions|Technologies|Services|Advisors|Financial))',
            # Look for company name in context - preserve spaces before LLC/Inc
            r'(?i)([A-Z][^,.\n]*?(?:\s+)?(?:Inc|LLC|Corp|Company|Group|Holdings|Solutions|Technologies|Services|Advisors|Financial))',
            # Look for copyright notices
            r'(?i)©.*?(\d{4}).*?([A-Z][^,.\n]*?(?:\s+)?(?:Inc|LLC|Corp|Company|Group|Holdings|Solutions|Technologies|Services|Advisors|Financial))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, markdown_content)
            if matches:
                # Take the first match and clean it up
                if isinstance(matches[0], tuple):
                    company_name = matches[0][-1].strip()  # Take last group from tuple
                else:
                    company_name = matches[0].strip()

                # Clean up the name while preserving proper spacing
                company_name = re.sub(r'\s+', ' ', company_name)  # Normalize whitespace
                company_name = company_name.strip('.,!?')  # Remove trailing punctuation

                # Fix common formatting issues while preserving spaces before LLC/Inc
                company_name = re.sub(r'(\w)(LLC|Inc|Corp)', r'\1 \2', company_name)  # Add space if missing
                company_name = re.sub(r'Financial([a-z])', r'Financial \1', company_name)  # Fix "FinancialLLC" -> "Financial LLC"

                if len(company_name) > 3 and len(company_name) < 100:  # Reasonable length
                    return company_name

        # Fallback: try to extract from URL and format properly
        if fallback_url.startswith('http'):
            from urllib.parse import urlparse
            domain = urlparse(fallback_url).netloc
            domain = domain.replace('www.', '').replace('.com', '').replace('.net', '').replace('.org', '')
            # Convert domain to proper case and add spaces before capitals
            formatted_name = ''
            for i, char in enumerate(domain):
                if i > 0 and char.isupper() and domain[i-1].islower():
                    formatted_name += ' '
                formatted_name += char
            # Check if it looks like it should have LLC/Inc
            if any(suffix in domain.lower() for suffix in ['llc', 'inc', 'corp']):
                formatted_name = re.sub(r'(\w)(llc|inc|corp)$', r'\1 \2', formatted_name, flags=re.IGNORECASE)
                formatted_name = formatted_name.replace('llc', 'LLC').replace('inc', 'Inc').replace('corp', 'Corp')
            return formatted_name.title()

        return fallback_url

    def _extract_company_phone(self, markdown_content: str, phone_pattern: str) -> str:
        """Extract company phone number with context prioritization"""
        import re

        # Split content into lines for context analysis
        lines = markdown_content.split('\n')
        phone_candidates = []

        for i, line in enumerate(lines):
            phones = re.findall(phone_pattern, line)
            if phones:
                # Get surrounding context (2 lines before and after)
                context_start = max(0, i-2)
                context_end = min(len(lines), i+3)
                context = ' '.join(lines[context_start:context_end]).lower()

                for phone_tuple in phones:
                    # Validate phone number parts are reasonable
                    area_code = phone_tuple[0]
                    prefix = phone_tuple[1]
                    suffix = phone_tuple[2]

                    # Skip if area code starts with 0 or 1 (invalid US area codes)
                    if area_code[0] in ['0', '1']:
                        continue

                    # Skip if any part is all zeros
                    if area_code == '000' or prefix == '000' or suffix == '0000':
                        continue

                    formatted_phone = f"({area_code}) {prefix}-{suffix}"

                    # Score based on context keywords
                    score = 0

                    # Prioritize main company contact info
                    if any(keyword in context for keyword in ['contact', 'office', 'main', 'headquarters', 'corporate']):
                        score += 10
                    if any(keyword in context for keyword in ['phone', 'call', 'tel']):
                        score += 5
                    if any(keyword in context for keyword in ['sales', 'support', 'customer']):
                        score += 3

                    # Deprioritize personal/individual contacts
                    if any(keyword in context for keyword in ['mobile', 'cell', 'personal', 'direct']):
                        score -= 5
                    if any(keyword in context for keyword in ['fax', 'toll-free', '800-', '888-', '877-']):
                        score -= 2

                    phone_candidates.append((formatted_phone, score, i))

        # Return highest scoring phone number
        if phone_candidates:
            phone_candidates.sort(key=lambda x: (-x[1], x[2]))  # Sort by score desc, then line number asc
            return phone_candidates[0][0]

        return ""

    def _extract_city_state_from_content(self, markdown_content: str) -> dict:
        """Extract city and state from content using multiple patterns"""
        import re

        # Common US state abbreviations for validation
        us_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        }

        # First try to extract from the address we found
        if hasattr(self, '_last_extracted_address'):
            # Look for patterns like "801 N Brand Blvd Suite 1400, Glendale, CA 91203"
            address_city_state = re.search(r',\s*([^,]+),\s*([A-Z]{2})\s*\d{5}', self._last_extracted_address)
            if address_city_state:
                city = address_city_state.group(1).strip()
                state = address_city_state.group(2).strip()
                if state in us_states:
                    logger.info(f"✅ Extracted city/state from address: {city}, {state}")
                    return {"city": city, "state": state}

            # If we have a partial address, look for city/state near it in the content
            if self._last_extracted_address and len(self._last_extracted_address) > 10:
                # Search for the address in content and look for city/state nearby
                address_escaped = re.escape(self._last_extracted_address)
                # Look for city/state within 100 characters after the address
                nearby_pattern = f'{address_escaped}[^\\n]{{0,100}}([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*),\\s*([A-Z]{{2}})\\s*\\d{{5}}'
                nearby_match = re.search(nearby_pattern, markdown_content)
                if nearby_match:
                    city = nearby_match.group(1).strip()
                    state = nearby_match.group(2).strip()
                    if state in us_states:
                        logger.info(f"✅ Found city/state near address: {city}, {state}")
                        return {"city": city, "state": state}

        patterns = [
            # Pattern 1: Complete address with city, state: "Suite 1400 Glendale, CA 91203"
            r'(?:Suite|Ste|Floor|Fl)?\s*\d+\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s*\d{5}',
            # Pattern 2: City, State ZIP format (most reliable)
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s*\d{5}',
            # Pattern 3: Look for "Glendale, CA" or "Los Angeles, California" near common location keywords
            r'(?i)(?:office|location|address|headquarters?|branch|facility)[\s:]*(?:is)?[\s\w]*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})',
            # Pattern 4: City, State format with proper capitalization
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b',
            # Pattern 5: Located in City, State
            r'(?i)(?:located|based|headquartered)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b',
            # Pattern 6: Address continuation pattern "Blvd Glendale, CA"
            r'(?:Blvd|Boulevard|Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Way|Place|Plaza|Court|Ct)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b',
            # Pattern 7: Contact information section with city/state
            r'(?i)(?:contact|visit|find us|location)[\s\S]{0,50}([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s*\d{5}',
            # Pattern 8: Footer or copyright with location
            r'(?i)(?:©|\(c\)|copyright)[\s\S]{0,50}([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b',
        ]

        candidates = []

        for pattern in patterns:
            matches = re.findall(pattern, markdown_content)
            for match in matches:
                city, state = match[0].strip(), match[1].strip().upper()

                # Validate state abbreviation
                if state in us_states and len(city) > 2 and len(city) < 50:
                    # Skip if city looks like a street type
                    if city.lower() not in ['street', 'avenue', 'road', 'boulevard', 'drive', 'lane', 'suite', 'floor']:
                        # Score based on context and pattern reliability
                        score = 1
                        if 'headquarter' in markdown_content.lower() or 'located' in markdown_content.lower():
                            score += 2
                        # Boost score for complete address patterns
                        if 'Pattern 1' in str(pattern) or 'Pattern 2' in str(pattern):
                            score += 3
                        candidates.append((city, state, score))

        # Return highest scoring candidate
        if candidates:
            candidates.sort(key=lambda x: -x[2])  # Sort by score descending
            city, state, _ = candidates[0]
            return {"city": city, "state": state}

        return {}


def test_fire_agent():
    """Test the FIRE-1 agent implementation"""
    print("\n" + "="*70)
    print("TESTING FIRECRAWL V2 WITH FIRE-1 AGENT")
    print("="*70)

    client = FirecrawlV2Client()

    # Test 1: Simple extraction
    print("\n1. Testing simple extraction without FIRE agent:")
    result = client.extract(
        urls=["https://www.firecrawl.dev"],
        prompt="Extract the company mission",
        use_fire_agent=False
    )
    print(f"   Success: {result.success}")
    print(f"   Status: {result.status}")
    if result.data:
        print(f"   Data: {json.dumps(result.data, indent=2)[:200]}...")

    # Test 2: Complex extraction with FIRE-1
    print("\n2. Testing FIRE-1 agent for complex extraction:")
    result = client.extract_with_fire_agent(
        urls=["https://www.microsoft.com/*"],
        extraction_goal="Find all executive team members with their LinkedIn profiles",
        schema={
            "type": "object",
            "properties": {
                "executives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "title": {"type": "string"},
                            "linkedin_url": {"type": "string"}
                        }
                    }
                }
            }
        }
    )
    print(f"   Success: {result.success}")
    print(f"   Status: {result.status}")
    if result.tokens_used:
        print(f"   Tokens used: {result.tokens_used}")

    # Test 3: LinkedIn extraction
    print("\n3. Testing LinkedIn extraction from email:")
    extractor = LinkedInExtractor()
    email_data = {
        "sender_name": "John Doe",
        "sender_email": "john@microsoft.com",
        "body": "Looking forward to connecting on LinkedIn"
    }
    enhanced = extractor.extract_linkedin_from_email(email_data)
    print(f"   Extraction method: {enhanced.get('extraction_method')}")
    print(f"   Confidence: {enhanced.get('confidence')}")

    print("\n" + "="*70)
    print("FIRE-1 AGENT TEST COMPLETE")
    print("="*70)

if __name__ == "__main__":
    test_fire_agent()