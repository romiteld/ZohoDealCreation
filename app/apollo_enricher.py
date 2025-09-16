"""
Apollo.io Contact Enrichment Service

This module provides integration with Apollo.io's People Enrichment API
to enrich contact information based on email addresses.
"""

import os
import logging
from typing import Dict, Optional
import httpx

from app.config_manager import get_extraction_config

logger = logging.getLogger(__name__)


async def enrich_contact_with_apollo(email: str) -> Optional[Dict[str, str]]:
    """
    Enrich contact information using Apollo.io's People Enrichment API.

    Args:
        email: The email address to search for contact information

    Returns:
        Dict containing enriched contact data with fields:
        - client_name: Full name of the contact
        - email: Email address
        - phone: Phone number
        - firm_company: Organization name
        - website: Company website
        - job_title: Job title
        - location: City location

        Returns None if enrichment fails or email is not provided.
    """
    if not email:
        logger.debug("No email provided for Apollo enrichment")
        return None

    try:
        # Get Apollo API configuration
        config = get_extraction_config()
        apollo_api_key = config.apollo_api_key

        if not apollo_api_key:
            logger.warning("Apollo API key not configured")
            return None

        # Prepare the API request
        url = "https://api.apollo.io/v1/people/match"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": apollo_api_key
        }

        payload = {
            "email": email
        }

        # Make the API request with 10 second timeout
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Enriching contact via Apollo for email: {email}")
            response = await client.post(url, json=payload, headers=headers)

            # Check response status
            if response.status_code != 200:
                logger.error(f"Apollo API returned status {response.status_code}: {response.text}")
                return None

            # Parse response
            data = response.json()

            # Check if a person was found
            person = data.get("person")
            if not person:
                logger.info(f"No person found in Apollo for email: {email}")
                return None

            # Extract and map the fields
            organization = person.get("organization", {})

            enriched_data = {
                "client_name": person.get("name") or "",
                "email": person.get("email") or email,
                "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
                "firm_company": organization.get("name", ""),
                "website": organization.get("website_url", ""),
                "job_title": person.get("title", ""),
                "location": person.get("city", "")
            }

            # Filter out empty values but keep the structure
            enriched_data = {k: v for k, v in enriched_data.items() if v}

            logger.info(f"Successfully enriched contact for {email}: {list(enriched_data.keys())}")
            return enriched_data

    except httpx.TimeoutException:
        logger.error(f"Apollo API request timed out for email: {email}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Apollo API request error for {email}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during Apollo enrichment for {email}: {str(e)}")
        return None