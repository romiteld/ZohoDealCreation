#!/usr/bin/env python3
"""Test the new Firecrawl v2 FIRE agent implementation"""
import sys
import os
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.firecrawl_v2_fire_agent import FirecrawlV2Enterprise

def test_basic_extraction():
    """Test basic extraction from Microsoft"""
    print("\n" + "="*70)
    print("Testing Firecrawl v2 FIRE Agent - Basic Extraction")
    print("="*70)

    extractor = FirecrawlV2Enterprise()

    # Test with Microsoft
    result = extractor.extract_linkedin_profiles(
        urls=["https://www.microsoft.com"],
        search_for="LinkedIn profiles of executives and leadership team"
    )

    if result.get("success"):
        print("\n✅ Extraction successful!")
        data = result.get("data", {})
        print(f"Company: {data.get('company_name', 'N/A')}")
        print(f"LinkedIn: {data.get('linkedin_url', 'N/A')}")

        executives = data.get('executives', [])
        if executives:
            print(f"\nFound {len(executives)} executives:")
            for exec in executives[:5]:  # Show first 5
                print(f"  • {exec.get('name', 'N/A')} - {exec.get('title', 'N/A')}")
                if exec.get('linkedin_url'):
                    print(f"    LinkedIn: {exec['linkedin_url']}")
        else:
            print("No executives found")
    else:
        print(f"\n❌ Extraction failed: {result.get('error', 'Unknown error')}")

    return result.get("success", False)

def test_company_research():
    """Test company research with web search"""
    print("\n" + "="*70)
    print("Testing Firecrawl v2 FIRE Agent - Company Research")
    print("="*70)

    extractor = FirecrawlV2Enterprise()

    # Test company research
    result = extractor.research_company(
        company_name="Microsoft Corporation",
        enable_web_search=True
    )

    if result.get("success"):
        print("\n✅ Research successful!")
        data = result.get("data", {})

        # Show company info
        for key, value in data.items():
            if value:
                print(f"{key}: {value}")
    else:
        print(f"\n❌ Research failed: {result.get('error', 'Unknown error')}")

    return result.get("success", False)

def test_executive_enrichment():
    """Test executive enrichment"""
    print("\n" + "="*70)
    print("Testing Firecrawl v2 FIRE Agent - Executive Enrichment")
    print("="*70)

    extractor = FirecrawlV2Enterprise()

    # Test with a known executive
    result = extractor.enrich_executive_data(
        person_name="Satya Nadella",
        company_name="Microsoft"
    )

    if result.get("success"):
        print("\n✅ Enrichment successful!")
        data = result.get("data", {})
        print(f"Name: {data.get('name', 'N/A')}")
        print(f"Title: {data.get('title', 'N/A')}")
        print(f"Company: {data.get('company', 'N/A')}")
        print(f"LinkedIn: {data.get('linkedin_url', 'N/A')}")
        print(f"Email: {data.get('email', 'N/A')}")
        print(f"Phone: {data.get('phone', 'N/A')}")
    else:
        print(f"\n❌ Enrichment failed: {result.get('error', 'Unknown error')}")

    return result.get("success", False)

if __name__ == "__main__":
    print("="*70)
    print("FIRECRAWL V2 FIRE AGENT TEST SUITE")
    print("="*70)

    # Run tests
    tests = []

    try:
        tests.append(("Basic Extraction", test_basic_extraction()))
    except Exception as e:
        print(f"Basic extraction error: {e}")
        tests.append(("Basic Extraction", False))

    try:
        tests.append(("Company Research", test_company_research()))
    except Exception as e:
        print(f"Company research error: {e}")
        tests.append(("Company Research", False))

    try:
        tests.append(("Executive Enrichment", test_executive_enrichment()))
    except Exception as e:
        print(f"Executive enrichment error: {e}")
        tests.append(("Executive Enrichment", False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for test_name, passed in tests:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    total_passed = sum(1 for _, p in tests if p)
    print(f"\nTotal: {total_passed}/{len(tests)} tests passed")