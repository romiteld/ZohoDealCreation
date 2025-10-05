#!/usr/bin/env python3
"""
Test script for LinkedIn URL extraction endpoint.

This script tests the new /api/apollo/extract/linkedin endpoint
to verify LinkedIn and social media URL extraction capabilities.
"""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "your-api-key-here")


async def test_linkedin_extraction():
    """Test LinkedIn URL extraction with various scenarios."""

    # Test cases with different input combinations
    test_cases = [
        {
            "name": "Test with email only",
            "params": {
                "email": "john.doe@example.com"
            }
        },
        {
            "name": "Test with name and company",
            "params": {
                "name": "John Doe",
                "company": "Example Company"
            }
        },
        {
            "name": "Test with all parameters",
            "params": {
                "email": "jane.smith@techcorp.com",
                "name": "Jane Smith",
                "company": "TechCorp",
                "job_title": "Software Engineer",
                "location": "San Francisco"
            }
        },
        {
            "name": "Test with company domain",
            "params": {
                "company": "microsoft.com"
            }
        }
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in test_cases:
            print(f"\n{'='*60}")
            print(f"Running: {test_case['name']}")
            print(f"Parameters: {test_case['params']}")
            print(f"{'='*60}")

            try:
                # Make the API request
                response = await client.post(
                    f"{API_URL}/api/apollo/extract/linkedin",
                    json=test_case["params"],
                    headers={
                        "X-API-Key": API_KEY,
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    result = response.json()

                    print("\n✅ SUCCESS - LinkedIn extraction completed")
                    print(f"\nResults:")
                    print(f"  LinkedIn URL: {result.get('linkedin_url', 'Not found')}")
                    print(f"  Company LinkedIn: {result.get('company_linkedin_url', 'Not found')}")
                    print(f"  Twitter URL: {result.get('twitter_url', 'Not found')}")
                    print(f"  Facebook URL: {result.get('facebook_url', 'Not found')}")
                    print(f"  GitHub URL: {result.get('github_url', 'Not found')}")

                    if result.get('phone_numbers'):
                        print(f"\n  Phone Numbers:")
                        for phone in result['phone_numbers']:
                            print(f"    - {phone.get('type', 'Unknown')}: {phone.get('number')}")

                    print(f"\n  Confidence Score: {result.get('confidence_score', 0)}%")
                    print(f"  Source: {result.get('source', 'Unknown')}")

                    if result.get('alternative_profiles'):
                        print(f"\n  Alternative Profiles Found: {len(result['alternative_profiles'])}")
                        for i, alt in enumerate(result['alternative_profiles'][:3], 1):
                            print(f"    {i}. {alt.get('name')} - {alt.get('title')} at {alt.get('company')}")
                            if alt.get('linkedin'):
                                print(f"       LinkedIn: {alt['linkedin']}")

                    # Additional metadata
                    if result.get('person_name'):
                        print(f"\n  Person Name: {result['person_name']}")
                    if result.get('person_title'):
                        print(f"  Job Title: {result['person_title']}")
                    if result.get('company_name'):
                        print(f"  Company: {result['company_name']}")
                    if result.get('location'):
                        print(f"  Location: {result['location']}")

                else:
                    print(f"\n❌ ERROR - Status Code: {response.status_code}")
                    print(f"Response: {response.text}")

            except httpx.TimeoutException:
                print(f"\n⏱️ TIMEOUT - Request took too long")
            except Exception as e:
                print(f"\n❌ ERROR: {str(e)}")

            # Small delay between tests
            await asyncio.sleep(1)


async def test_batch_extraction():
    """Test batch LinkedIn extraction for multiple contacts."""

    contacts = [
        {"email": "contact1@example.com", "name": "Contact One"},
        {"email": "contact2@example.com", "name": "Contact Two"},
        {"email": "contact3@example.com", "name": "Contact Three"}
    ]

    print(f"\n{'='*60}")
    print("Testing Batch LinkedIn Extraction")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []

        for contact in contacts:
            task = client.post(
                f"{API_URL}/api/apollo/extract/linkedin",
                json=contact,
                headers={
                    "X-API-Key": API_KEY,
                    "Content-Type": "application/json"
                }
            )
            tasks.append(task)

        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, (contact, response) in enumerate(zip(contacts, responses), 1):
            print(f"\nContact {i}: {contact['name']} ({contact['email']})")

            if isinstance(response, Exception):
                print(f"  ❌ Error: {str(response)}")
            elif response.status_code == 200:
                result = response.json()
                if result.get('linkedin_url'):
                    print(f"  ✅ LinkedIn: {result['linkedin_url']}")
                else:
                    print(f"  ⚠️ No LinkedIn URL found")
                print(f"  Confidence: {result.get('confidence_score', 0)}%")
            else:
                print(f"  ❌ Status: {response.status_code}")


async def test_cache_performance():
    """Test cache performance by making repeated requests."""

    print(f"\n{'='*60}")
    print("Testing Cache Performance")
    print(f"{'='*60}")

    test_email = "cache.test@example.com"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # First request (should hit Apollo API)
        print("\n1st Request (Cold Cache):")
        start_time = asyncio.get_event_loop().time()

        response1 = await client.post(
            f"{API_URL}/api/apollo/extract/linkedin",
            json={"email": test_email},
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            }
        )

        time1 = asyncio.get_event_loop().time() - start_time

        if response1.status_code == 200:
            result1 = response1.json()
            print(f"  Source: {result1.get('source')}")
            print(f"  Time: {time1:.2f} seconds")
            print(f"  LinkedIn: {result1.get('linkedin_url', 'Not found')}")

        # Second request (should hit cache)
        print("\n2nd Request (Warm Cache):")
        start_time = asyncio.get_event_loop().time()

        response2 = await client.post(
            f"{API_URL}/api/apollo/extract/linkedin",
            json={"email": test_email},
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            }
        )

        time2 = asyncio.get_event_loop().time() - start_time

        if response2.status_code == 200:
            result2 = response2.json()
            print(f"  Source: {result2.get('source')}")
            print(f"  Time: {time2:.2f} seconds")
            print(f"  LinkedIn: {result2.get('linkedin_url', 'Not found')}")

        if time1 > 0 and time2 > 0:
            speedup = time1 / time2
            print(f"\n  🚀 Cache Speedup: {speedup:.1f}x faster")


async def main():
    """Run all test scenarios."""

    print("\n" + "="*60)
    print(" LinkedIn URL Extraction Test Suite")
    print("="*60)
    print(f"\nAPI URL: {API_URL}")
    print(f"API Key: {'*' * (len(API_KEY) - 4) + API_KEY[-4:] if len(API_KEY) > 4 else '****'}")

    # Run individual tests
    await test_linkedin_extraction()

    # Run batch test
    await test_batch_extraction()

    # Run cache performance test
    await test_cache_performance()

    print("\n" + "="*60)
    print(" Test Suite Completed")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())