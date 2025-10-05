#!/usr/bin/env python3
"""
Test script for Apollo.io unlimited people search production endpoint
"""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

API_KEY = os.getenv('API_KEY')
BASE_URL = "http://localhost:8000"  # Change to production URL when deployed

async def test_people_search():
    """Test the Apollo people search endpoint with various parameters"""

    # Test cases
    test_cases = [
        {
            "name": "Search by email",
            "params": {
                "email": "john.smith@example.com"
            }
        },
        {
            "name": "Search by name and company",
            "params": {
                "name": "John Smith",
                "company_domain": "example.com"
            }
        },
        {
            "name": "Search by job title and location",
            "params": {
                "job_title": "Software Engineer",
                "location": "San Francisco",
                "per_page": 10
            }
        },
        {
            "name": "Search with all filters",
            "params": {
                "name": "Jane Doe",
                "company_domain": "techcompany.com",
                "job_title": "Product Manager",
                "location": "New York",
                "page": 1,
                "per_page": 5
            }
        }
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in test_cases:
            print(f"\n{'='*60}")
            print(f"Test: {test_case['name']}")
            print(f"Parameters: {json.dumps(test_case['params'], indent=2)}")
            print(f"{'='*60}")

            try:
                response = await client.post(
                    f"{BASE_URL}/api/apollo/search/people",
                    headers={
                        "X-API-Key": API_KEY,
                        "Content-Type": "application/json"
                    },
                    json=test_case['params']
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Success!")
                    print(f"Status: {result.get('status')}")

                    # Check data quality
                    if 'data_quality' in result:
                        quality = result['data_quality']
                        print(f"\nData Quality:")
                        print(f"  - Completeness: {quality.get('completeness_score')}%")
                        print(f"  - Critical Fields: {quality.get('critical_completeness')}%")
                        print(f"  - Has LinkedIn: {quality.get('has_linkedin')}")
                        print(f"  - Has Phone: {quality.get('has_phone')}")
                        print(f"  - Has Email: {quality.get('has_email')}")
                        print(f"  - Has Company Website: {quality.get('has_company_website')}")

                    # Show person data if found
                    if 'data' in result and result['data'].get('person'):
                        person = result['data']['person']
                        print(f"\nPerson Found:")
                        print(f"  - Name: {person.get('full_name')}")
                        print(f"  - Email: {person.get('email')}")
                        print(f"  - Title: {person.get('job_title')}")
                        print(f"  - LinkedIn: {person.get('linkedin_url')}")
                        print(f"  - Phone: {person.get('primary_phone')}")

                        if person.get('company'):
                            company = person['company']
                            print(f"\nCompany:")
                            print(f"  - Name: {company.get('name')}")
                            print(f"  - Website: {company.get('website')}")
                            print(f"  - Industry: {company.get('industry')}")

                    # Check cache status
                    print(f"\nCache Hit: {result.get('cache_hit', False)}")

                else:
                    print(f"❌ Error: Status code {response.status_code}")
                    print(f"Response: {response.text}")

            except Exception as e:
                print(f"❌ Exception: {str(e)}")

async def test_cache_behavior():
    """Test that caching works properly by making the same request twice"""

    print("\n" + "="*60)
    print("Testing Cache Behavior")
    print("="*60)

    test_params = {
        "name": "Test User",
        "company_domain": "example.com"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # First request (should miss cache)
        print("\n1st Request (should miss cache)...")
        response1 = await client.post(
            f"{BASE_URL}/api/apollo/search/people",
            headers={"X-API-Key": API_KEY},
            json=test_params
        )

        if response1.status_code == 200:
            result1 = response1.json()
            print(f"Cache Hit: {result1.get('cache_hit', False)}")

        # Second request (should hit cache)
        print("\n2nd Request (should hit cache)...")
        response2 = await client.post(
            f"{BASE_URL}/api/apollo/search/people",
            headers={"X-API-Key": API_KEY},
            json=test_params
        )

        if response2.status_code == 200:
            result2 = response2.json()
            print(f"Cache Hit: {result2.get('cache_hit', False)}")

            if result2.get('cache_hit'):
                print("✅ Cache is working properly!")
            else:
                print("⚠️ Cache might not be configured")

async def test_pagination():
    """Test pagination functionality"""

    print("\n" + "="*60)
    print("Testing Pagination")
    print("="*60)

    test_params = {
        "job_title": "Software Engineer",
        "location": "San Francisco"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test different pages
        for page in [1, 2]:
            print(f"\nPage {page}:")
            params = {**test_params, "page": page, "per_page": 5}

            response = await client.post(
                f"{BASE_URL}/api/apollo/search/people",
                headers={"X-API-Key": API_KEY},
                json=params
            )

            if response.status_code == 200:
                result = response.json()
                data = result.get('data', {})
                print(f"  - Total Results: {data.get('total_results', 0)}")
                print(f"  - Current Page: {data.get('page')}")
                print(f"  - Per Page: {data.get('per_page')}")

async def main():
    """Run all tests"""

    print("\n" + "="*60)
    print("Apollo.io People Search Production Endpoint Tests")
    print("="*60)

    # Check API key
    if not API_KEY:
        print("❌ Error: API_KEY not found in .env.local")
        return

    print(f"✅ API Key configured")
    print(f"📍 Testing against: {BASE_URL}")

    # Run tests
    await test_people_search()
    await test_cache_behavior()
    await test_pagination()

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())