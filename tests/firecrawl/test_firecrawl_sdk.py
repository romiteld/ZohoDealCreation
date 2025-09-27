#!/usr/bin/env python3
"""
Test Firecrawl SDK with proper extract format based on documentation
"""
import os
import json
import logging
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field

# Load environment
load_dotenv('.env.local')
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Define Pydantic model for company data (based on documentation)
class CompanyInfo(BaseModel):
    company_name: str = Field(description="Official legal company name")
    industry: str = Field(description="Industry or business sector", default="")
    employees: str = Field(description="Number of employees or employee range", default="")
    location: str = Field(description="Headquarters location (city, state/country)", default="")
    website: str = Field(description="Company website URL", default="")
    description: str = Field(description="Brief company description", default="")


def test_firecrawl_extract(domain: str = "microsoft.com"):
    """Test Firecrawl extraction using SDK with scrape_url and extract format"""

    # Initialize Firecrawl app
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        logger.error("FIRECRAWL_API_KEY not found in environment")
        return

    app = FirecrawlApp(api_key=api_key)
    url = f"https://{domain}"

    logger.info(f"Testing Firecrawl SDK extraction for: {url}")

    try:
        # Method 1: Using scrape_url with extract format (as per documentation)
        logger.info("Method 1: Using scrape_url with extract format and Pydantic schema")

        result = app.scrape_url(
            url,
            params={
                'formats': ['extract'],
                'extract': {
                    'schema': CompanyInfo.model_json_schema(),
                    'prompt': f"Extract company information from {domain} including name, industry, employee count, headquarters location, website, and description",
                    'systemPrompt': "You are a helpful assistant that extracts company information from websites"
                }
            }
        )

        # Check the result
        if result and 'extract' in result:
            extracted_data = result['extract']
            logger.info("✅ Extraction successful!")
            logger.info(f"Company Name: {extracted_data.get('company_name', 'Not found')}")
            logger.info(f"Industry: {extracted_data.get('industry', 'Not found')}")
            logger.info(f"Employees: {extracted_data.get('employees', 'Not found')}")
            logger.info(f"Location: {extracted_data.get('location', 'Not found')}")
            logger.info(f"Description: {extracted_data.get('description', 'Not found')[:100]}...")

            print("\nFull extracted data:")
            print(json.dumps(extracted_data, indent=2))
        else:
            logger.warning("No extract field in result")
            print("\nFull result:")
            print(json.dumps(result, indent=2))

    except Exception as e:
        logger.error(f"Error with scrape_url method: {e}")

    print("\n" + "="*70 + "\n")

    try:
        # Method 2: Try using extract method directly if available
        logger.info("Method 2: Testing direct extract method (if available)")

        # Check if extract method exists
        if hasattr(app, 'extract'):
            extract_result = app.extract(
                urls=[url],
                schema=CompanyInfo.model_json_schema(),
                prompt="Extract the company information"
            )

            if extract_result and 'data' in extract_result:
                logger.info("✅ Extract method worked!")
                print(json.dumps(extract_result['data'], indent=2))
        else:
            logger.info("Extract method not available in SDK, using scrape_url is correct")

    except AttributeError:
        logger.info("Extract method not available in SDK - scrape_url with extract format is the right approach")
    except Exception as e:
        logger.error(f"Error with extract method: {e}")

    print("\n" + "="*70 + "\n")

    # Method 3: Simple extraction without Pydantic model
    try:
        logger.info("Method 3: Simple extraction without Pydantic model")

        simple_result = app.scrape_url(
            url,
            params={
                'formats': ['extract', 'markdown'],
                'extract': {
                    'prompt': f"""Extract from {domain}:
                    - Company name
                    - Industry
                    - Number of employees
                    - Headquarters location
                    - Brief description
                    Return as JSON with these fields."""
                }
            }
        )

        if simple_result:
            if 'extract' in simple_result:
                logger.info("✅ Simple extraction successful!")
                print("\nExtracted data:")
                print(json.dumps(simple_result['extract'], indent=2))

            # Also show if we got markdown
            if 'markdown' in simple_result:
                logger.info("Also received markdown content (first 500 chars):")
                print(simple_result['markdown'][:500])

    except Exception as e:
        logger.error(f"Error with simple extraction: {e}")


if __name__ == "__main__":
    # Test with different domains
    test_domains = ["microsoft.com", "google.com", "apple.com"]

    for domain in test_domains:
        print(f"\n{'#'*70}")
        print(f"# Testing: {domain}")
        print(f"{'#'*70}\n")
        test_firecrawl_extract(domain)
        print("\n")