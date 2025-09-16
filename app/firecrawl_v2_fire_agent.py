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

        self.base_url = "https://api.firecrawl.dev/v2"
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
        """Research company information"""
        urls = [f"https://www.google.com/search?q={company_name} company"]

        result = self.client.extract(
            urls=urls,
            prompt=f"Find information about {company_name} company including website, LinkedIn, and key executives",
            enable_web_search=enable_web_search,
            use_fire_agent=True
        )

        return {
            "success": result.success,
            "data": result.data,
            "error": None if result.success else "Research failed"
        }

    def enrich_executive_data(
        self,
        person_name: str,
        company_name: str
    ) -> Dict:
        """Enrich executive data with LinkedIn and contact info"""
        return self.linkedin_extractor.extract_person_profile(person_name, company_name)


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