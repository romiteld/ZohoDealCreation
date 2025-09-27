#!/usr/bin/env python3
"""
Adapter for Firecrawl v2 Fire Agent to work with LangGraph Manager
Provides the interface expected by langgraph_manager.py
"""
import os
import json
import logging
from typing import Dict, Optional, Any
from app.firecrawl_v2_fire_agent import FirecrawlV2Enterprise

logger = logging.getLogger(__name__)


class FirecrawlV2Agent:
    """
    Adapter class that wraps FirecrawlV2Enterprise to provide
    the interface expected by LangGraph Manager
    """

    def __init__(self):
        """Initialize Firecrawl v2 Fire Agent adapter"""
        try:
            self.enterprise = FirecrawlV2Enterprise()
            self.initialized = True
            logger.info("✅ Firecrawl v2 Fire Agent initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firecrawl v2: {e}")
            self.enterprise = None
            self.initialized = False

    async def enrich_email_data(
        self,
        email_data: Dict[str, Any],
        extracted_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enrich email data using Firecrawl v2 Enterprise API

        Args:
            email_data: Dictionary with email content
            extracted_data: Previously extracted data with company info

        Returns:
            Dictionary with enriched data
        """
        if not self.initialized:
            logger.warning("⚠️ Firecrawl v2 not initialized, returning empty enrichments")
            return {"enrichments": {}}

        enrichments = {}

        try:
            # Extract company domain from extracted data
            company_domain = None
            if extracted_data:
                if 'company_record' in extracted_data:
                    company_domain = extracted_data['company_record'].get('company_domain')
                elif 'company_website' in extracted_data:
                    company_domain = extracted_data.get('company_website')

            # Enrich company data if domain available
            if company_domain:
                logger.info(f"🚀 Enriching company data for domain: {company_domain}")

                # Clean up domain to full URL if needed
                if not company_domain.startswith('http'):
                    company_url = f"https://{company_domain}"
                else:
                    company_url = company_domain
                logger.info(f"🌐 Using company URL: {company_url}")

                # Extract company data using Firecrawl v2
                # Pass the URL directly so the system can extract the actual company name from content
                logger.info("📞 Calling enterprise.research_company...")
                company_result = self.enterprise.research_company(
                    company_name=company_url,  # Use full URL so system can extract actual company name
                    enable_web_search=True
                )
                logger.info(f"📋 Company research result: {company_result}")

                company_data = company_result.get("data") if company_result and company_result.get("success") else None
                logger.info(f"🏢 Company data extracted: {company_data}")

                if company_data:
                    logger.info(f"✅ Successfully enriched company data from Firecrawl v2")

                    # Map Firecrawl data to expected format
                    enrichments["company"] = {
                        "company_name": company_data.get("company_name"),
                        "description": company_data.get("description"),
                        "phone": company_data.get("contact", {}).get("phone"),
                        "email": company_data.get("contact", {}).get("email"),
                        "address": company_data.get("contact", {}).get("address"),
                        "city": company_data.get("contact", {}).get("city") or company_data.get("city"),
                        "state": company_data.get("contact", {}).get("state") or company_data.get("state"),
                        "linkedin_url": company_data.get("linkedin_url"),
                        "website": company_url,

                        # Executive data
                        "executives": company_data.get("executives", []),
                        "key_executives": [
                            {
                                "name": exec.get("name"),
                                "title": exec.get("title"),
                                "linkedin": exec.get("linkedin_url")
                            }
                            for exec in company_data.get("executives", [])[:5]  # Top 5 executives
                        ],

                        # Additional enrichment fields (can be expanded with more API calls)
                        "employee_count": None,  # Would need additional API call
                        "employee_range": None,
                        "revenue": None,
                        "funding_total": None,
                        "latest_funding_round": None,
                        "valuation": None,
                        "tech_stack": [],
                        "founders": [],
                        "headquarters": company_data.get("contact", {}).get("address"),
                        "industry": None,
                        "products": []
                    }

                    # Extract person/contact data if available
                    sender_name = email_data.get("sender_name", "")
                    company_name = company_data.get("company_name", "")

                    if sender_name and company_name:
                        logger.info(f"🔍 Searching for person profile: {sender_name} at {company_name}")

                        try:
                            person_result = self.enterprise.enrich_executive_data(
                                person_name=sender_name,
                                company_name=company_name
                            )

                            person_data = person_result if person_result else None

                            if person_data:
                                enrichments["contact"] = {
                                    "name": person_data.get("name"),
                                    "title": person_data.get("title"),
                                    "email": person_data.get("email"),
                                    "phone": person_data.get("phone"),
                                    "linkedin_url": person_data.get("linkedin_url"),
                                    "location": person_data.get("location"),
                                    "city": person_data.get("city") or company_data.get("contact", {}).get("city") or company_data.get("city"),
                                    "state": person_data.get("state") or company_data.get("contact", {}).get("state") or company_data.get("state"),
                                    "bio": person_data.get("bio")
                                }
                                logger.info(f"✅ Successfully enriched person data for {sender_name}")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not enrich person data: {e}")

            else:
                logger.warning("⚠️ No company domain found for enrichment")

        except Exception as e:
            logger.error(f"❌ Error during Firecrawl v2 enrichment: {e}")

        return {
            "enrichments": enrichments,
            "source": "firecrawl_v2_fire_agent",
            "success": bool(enrichments)
        }

    def __bool__(self):
        """Return True if service is initialized"""
        return self.initialized