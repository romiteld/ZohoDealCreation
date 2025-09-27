#!/usr/bin/env python3
"""Test which Apollo endpoints are available with current plan"""

import asyncio
import httpx
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv('.env.local')

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_endpoint(url, payload, description):
    """Test a specific Apollo endpoint"""
    api_key = os.getenv('APOLLO_API_KEY')
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        print(f"\nTesting: {description}")
        print(f"Endpoint: {url}")
        try:
            response = await client.post(url, json=payload, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS - Response keys: {list(data.keys())}")
                return True
            else:
                print(f"❌ FAILED - {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            return False

async def main():
    print("="*60)
    print("Apollo.io API Endpoint Availability Test")
    print("="*60)

    # Test different endpoints
    endpoints = [
        {
            "url": "https://api.apollo.io/v1/people/match",
            "payload": {"email": "test@example.com"},
            "description": "People Match (single email lookup)"
        },
        {
            "url": "https://api.apollo.io/v1/mixed_people/search",
            "payload": {"q_keywords": "test", "page": 1, "per_page": 1},
            "description": "Mixed People Search (advanced search)"
        },
        {
            "url": "https://api.apollo.io/v1/people/search",
            "payload": {"q_keywords": "test", "page": 1, "per_page": 1},
            "description": "People Search (basic search)"
        },
        {
            "url": "https://api.apollo.io/v1/organizations/enrich",
            "payload": {"domain": "example.com"},
            "description": "Organization Enrich (by domain)"
        },
        {
            "url": "https://api.apollo.io/v1/mixed_companies/search",
            "payload": {"q_organization_keyword_tags": "test", "page": 1, "per_page": 1},
            "description": "Mixed Companies Search"
        },
        {
            "url": "https://api.apollo.io/v1/accounts/search",
            "payload": {"q_organization_name": "test", "page": 1, "per_page": 1},
            "description": "Accounts Search"
        },
        {
            "url": "https://api.apollo.io/v1/contacts/search",
            "payload": {"q_keywords": "test", "page": 1, "per_page": 1},
            "description": "Contacts Search"
        }
    ]

    available = []
    unavailable = []

    for endpoint in endpoints:
        success = await test_endpoint(
            endpoint["url"],
            endpoint["payload"],
            endpoint["description"]
        )
        if success:
            available.append(endpoint["description"])
        else:
            unavailable.append(endpoint["description"])

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\n✅ Available Endpoints ({len(available)}):")
    for ep in available:
        print(f"  • {ep}")

    print(f"\n❌ Unavailable Endpoints ({len(unavailable)}):")
    for ep in unavailable:
        print(f"  • {ep}")

if __name__ == "__main__":
    asyncio.run(main())