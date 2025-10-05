#!/usr/bin/env python3
"""
Clay API Discovery and Testing Script

Safely tests Clay API endpoints to understand:
1. Actual endpoint URLs
2. Request/response formats
3. Available data fields
4. Rate limits and authentication

IMPORTANT: Uses minimal requests to avoid overloading Clay's service
"""

import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def test_clay_api():
    """Test Clay API with various potential endpoints and methods"""

    api_key = os.getenv("CLAY_API_KEY")
    if not api_key:
        print("❌ CLAY_API_KEY not found in environment")
        return

    print("🧪 Clay API Discovery Test")
    print("=" * 50)
    print(f"API Key: {api_key[:8]}...")
    print()

    # Potential base URLs based on research
    potential_base_urls = [
        "https://api.clay.com",
        "https://api.clay.com/v1",
        "https://api.clay.com/v2",
        "https://clay.com/api",
        "https://clay.com/api/v1",
        "https://enterprise.clay.com/api",
        "https://enterprise-api.clay.com"
    ]

    # Test authentication methods
    auth_methods = [
        {"Authorization": f"Bearer {api_key}"},
        {"Authorization": f"Token {api_key}"},
        {"X-API-Key": api_key},
        {"Clay-API-Key": api_key},
        {"api_key": api_key}
    ]

    # Potential endpoints based on documentation research
    test_endpoints = [
        "/health",
        "/status",
        "/person/enrich",
        "/company/enrich",
        "/enrich/person",
        "/enrich/company",
        "/lookup/person",
        "/lookup/company",
        "/people",
        "/companies"
    ]

    successful_requests = []

    # Test 1: Check if any base URL is accessible
    print("🔍 Testing Base URLs...")
    for base_url in potential_base_urls[:3]:  # Limit to first 3 to avoid overloading
        try:
            response = requests.get(
                base_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            print(f"   {base_url}: {response.status_code}")
            if response.status_code != 404:
                print(f"      Response: {response.text[:100]}...")
                successful_requests.append({
                    "url": base_url,
                    "status": response.status_code,
                    "response": response.text[:200]
                })
        except Exception as e:
            print(f"   {base_url}: ERROR - {e}")

        time.sleep(1)  # Rate limiting

    print()

    # Test 2: Try common API patterns with successful base URL
    if successful_requests:
        base_url = successful_requests[0]["url"]
        print(f"🔍 Testing Endpoints on {base_url}...")

        for endpoint in test_endpoints[:4]:  # Limit to avoid overloading
            for auth_method in auth_methods[:2]:  # Test first 2 auth methods
                try:
                    full_url = f"{base_url}{endpoint}"
                    response = requests.get(
                        full_url,
                        headers=auth_method,
                        timeout=5
                    )

                    print(f"   GET {endpoint} (auth: {list(auth_method.keys())[0]}): {response.status_code}")

                    if response.status_code < 500:  # Any non-server error
                        print(f"      Response: {response.text[:100]}...")

                        if response.status_code == 200:
                            try:
                                json_data = response.json()
                                print(f"      JSON Keys: {list(json_data.keys())}")
                            except:
                                pass

                    if response.status_code == 200:
                        successful_requests.append({
                            "url": full_url,
                            "method": "GET",
                            "auth": auth_method,
                            "status": response.status_code,
                            "response": response.text[:500]
                        })
                        break  # Found working auth, no need to test others

                except Exception as e:
                    print(f"   GET {endpoint}: ERROR - {e}")

                time.sleep(0.5)  # Rate limiting between requests

            time.sleep(1)  # Rate limiting between endpoints

    print()

    # Test 3: Try POST requests for enrichment (with safe test data)
    if any(req["status"] == 200 for req in successful_requests):
        print("🔍 Testing POST Enrichment Endpoints...")

        # Safe test data
        test_person_data = {
            "email": "test@example.com"  # Safe test email
        }

        test_company_data = {
            "domain": "example.com"  # Safe test domain
        }

        for base_url in [req["url"].split("/v")[0] if "/v" in req["url"] else req["url"] for req in successful_requests if req["status"] == 200][:1]:

            # Test person enrichment
            for person_endpoint in ["/person/enrich", "/enrich/person", "/people"]:
                try:
                    response = requests.post(
                        f"{base_url}{person_endpoint}",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=test_person_data,
                        timeout=10
                    )

                    print(f"   POST {person_endpoint}: {response.status_code}")
                    if response.status_code < 500:
                        print(f"      Response: {response.text[:150]}...")

                    if response.status_code == 200:
                        successful_requests.append({
                            "url": f"{base_url}{person_endpoint}",
                            "method": "POST",
                            "data": test_person_data,
                            "status": response.status_code,
                            "response": response.text[:500]
                        })

                except Exception as e:
                    print(f"   POST {person_endpoint}: ERROR - {e}")

                time.sleep(2)  # Longer delay for POST requests

            # Test company enrichment
            for company_endpoint in ["/company/enrich", "/enrich/company", "/companies"]:
                try:
                    response = requests.post(
                        f"{base_url}{company_endpoint}",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=test_company_data,
                        timeout=10
                    )

                    print(f"   POST {company_endpoint}: {response.status_code}")
                    if response.status_code < 500:
                        print(f"      Response: {response.text[:150]}...")

                    if response.status_code == 200:
                        successful_requests.append({
                            "url": f"{base_url}{company_endpoint}",
                            "method": "POST",
                            "data": test_company_data,
                            "status": response.status_code,
                            "response": response.text[:500]
                        })

                except Exception as e:
                    print(f"   POST {company_endpoint}: ERROR - {e}")

                time.sleep(2)  # Longer delay for POST requests

    print()
    print("📋 DISCOVERY RESULTS")
    print("=" * 50)

    if successful_requests:
        print("✅ Successful API Calls Found:")
        for i, req in enumerate(successful_requests, 1):
            print(f"\n{i}. {req['method']} {req['url']}")
            print(f"   Status: {req['status']}")
            if 'auth' in req:
                print(f"   Auth: {list(req['auth'].keys())[0]}")
            if 'data' in req:
                print(f"   Data: {req['data']}")
            print(f"   Response: {req['response'][:200]}...")
    else:
        print("❌ No successful API calls found")
        print("\nPossible reasons:")
        print("• API key may not be valid")
        print("• Endpoints may be different than expected")
        print("• Enterprise API access may not be activated")
        print("• Need to contact Clay for Enterprise API documentation")

    print("\n💡 Next Steps:")
    if successful_requests:
        print("• Use successful endpoints in production code")
        print("• Map response fields to our data structure")
        print("• Implement proper error handling")
        print("• Add rate limiting based on Clay's limits")
    else:
        print("• Contact Clay support for Enterprise API access")
        print("• Verify API key is correct and activated")
        print("• Check Clay documentation for actual endpoints")

    print("\n⚠️  Rate Limiting Applied:")
    print("• 1-2 second delays between requests")
    print("• Limited to essential endpoint testing")
    print("• Used safe test data (example.com)")

if __name__ == "__main__":
    test_clay_api()