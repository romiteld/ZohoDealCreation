#!/usr/bin/env python3
"""
Test script for Firecrawl v2 extract endpoint implementation
Tests the enhanced company extraction with structured data
"""

import asyncio
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.firecrawl_enhanced import FirecrawlExtractor
from app.firecrawl_research import FirecrawlResearcher, CompanyResearchService

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_extract_endpoint():
    """Test the new Firecrawl v2 extract endpoint with various domains"""

    extractor = FirecrawlExtractor()

    # Test domains with expected results
    test_cases = [
        {
            "domain": "microsoft.com",
            "expected_name_contains": "Microsoft",
            "expected_fields": ["company_name", "industry", "headquarters"]
        },
        {
            "domain": "stripe.com",
            "expected_name_contains": "Stripe",
            "expected_fields": ["company_name", "industry", "description"]
        },
        {
            "domain": "openai.com",
            "expected_name_contains": "OpenAI",
            "expected_fields": ["company_name", "description"]
        },
        {
            "domain": "example-nonexistent-domain-12345.com",  # Test fallback
            "expected_name_contains": None,
            "expected_fields": []
        }
    ]

    print("\n" + "="*80)
    print("TESTING FIRECRAWL V2 EXTRACT ENDPOINT")
    print("="*80)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Domain: {test_case['domain']}")
        print("-" * 40)

        try:
            # Test the extract endpoint
            result = await extractor.extract_company_structured(test_case['domain'])

            # Print results
            if result.get("company_name"):
                print(f"✅ Company Name: {result.get('company_name')}")
                print(f"   Confidence: {result.get('confidence', 0):.2f}")
                print(f"   Method: {result.get('extraction_method', 'unknown')}")

                # Check for expected fields
                for field in ["website", "industry", "description", "headquarters"]:
                    if field in result:
                        value = result[field]
                        if isinstance(value, dict):
                            # Handle nested headquarters object
                            non_null = {k: v for k, v in value.items() if v}
                            if non_null:
                                print(f"   {field.title()}: {non_null}")
                        elif value:
                            print(f"   {field.title()}: {value[:100]}..." if len(str(value)) > 100 else f"   {field.title()}: {value}")

                # Validate expected name
                if test_case["expected_name_contains"]:
                    if test_case["expected_name_contains"].lower() in result.get("company_name", "").lower():
                        print(f"   ✅ Name validation passed")
                    else:
                        print(f"   ⚠️ Expected name to contain '{test_case['expected_name_contains']}'")
            else:
                print(f"❌ No company name extracted")
                if test_case["expected_name_contains"] is None:
                    print(f"   ✅ Expected failure (test domain)")

        except Exception as e:
            print(f"❌ Error: {e}")
            logger.error(f"Test failed for {test_case['domain']}: {e}", exc_info=True)


async def test_research_service_integration():
    """Test the CompanyResearchService with the new enhanced extraction"""

    service = CompanyResearchService()

    print("\n" + "="*80)
    print("TESTING COMPANY RESEARCH SERVICE INTEGRATION")
    print("="*80)

    # Test company research with various email domains
    test_emails = [
        ("john@stripe.com", "Stripe"),
        ("sarah@microsoft.com", "Microsoft"),
        ("alex@smallstartup123.com", None),  # Unknown company
    ]

    for email, expected_company in test_emails:
        domain = email.split('@')[1]
        print(f"\n[Email Domain: {domain}]")
        print("-" * 40)

        try:
            result = await service.research_company(
                email_domain=domain,
                company_guess=None  # Test pure extraction
            )

            print(f"Company: {result.get('company_name', 'Unknown')}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            print(f"Source: {result.get('source', 'unknown')}")

            if expected_company:
                if expected_company.lower() in (result.get('company_name', '') or '').lower():
                    print(f"✅ Correct company identified")
                else:
                    print(f"⚠️ Expected '{expected_company}'")

        except Exception as e:
            print(f"❌ Error: {e}")
            logger.error(f"Research failed for {domain}: {e}", exc_info=True)


async def test_fallback_mechanism():
    """Test the fallback from extract to scrape"""

    print("\n" + "="*80)
    print("TESTING FALLBACK MECHANISM")
    print("="*80)

    researcher = FirecrawlResearcher()

    # Test with a domain that might trigger fallback
    test_domain = "github.com"

    print(f"\n[Testing fallback with: {test_domain}]")
    print("-" * 40)

    try:
        result = await researcher.research_company_domain(test_domain)

        print(f"Company: {result.get('company_name', 'Unknown')}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"Source: {result.get('source', 'unknown')}")

        # Check if we used extraction or fallback
        if 'extraction_method' in result:
            print(f"Method used: {result['extraction_method']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Fallback test failed: {e}", exc_info=True)


async def test_candidate_search():
    """Test candidate information search with personal websites"""

    print("\n" + "="*80)
    print("TESTING CANDIDATE SEARCH")
    print("="*80)

    service = CompanyResearchService()

    # Test candidate search
    test_candidates = [
        ("Jerry Fetta", "Wealth DynamX"),  # Real person with likely personal site
        ("John Smith", "ABC Company"),     # Generic name
    ]

    for candidate_name, company in test_candidates:
        print(f"\n[Candidate: {candidate_name} at {company}]")
        print("-" * 40)

        try:
            result = await service.search_candidate_info(
                candidate_name=candidate_name,
                company_name=company
            )

            if result:
                for key, value in result.items():
                    if value:
                        print(f"   {key}: {value}")
            else:
                print("   No information found")

        except Exception as e:
            print(f"❌ Error: {e}")
            logger.error(f"Candidate search failed: {e}", exc_info=True)


async def main():
    """Run all tests"""

    print(f"\n🚀 Firecrawl V2 Extract Test Suite")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key: {'✅ Configured' if os.getenv('FIRECRAWL_API_KEY') else '❌ Missing'}")

    try:
        # Run tests in sequence to avoid rate limiting
        await test_extract_endpoint()
        await asyncio.sleep(1)  # Brief pause between test suites

        await test_research_service_integration()
        await asyncio.sleep(1)

        await test_fallback_mechanism()
        await asyncio.sleep(1)

        await test_candidate_search()

        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        logger.error(f"Test suite error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)