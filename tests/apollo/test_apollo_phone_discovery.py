"""
Test script for Apollo phone number discovery API endpoint

This script tests the comprehensive phone discovery capabilities.
"""

import asyncio
import os
import httpx
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

API_KEY = os.getenv("API_KEY", "dev-key-only-for-testing")
API_URL = os.getenv("API_URL", "http://localhost:8000")


async def test_phone_extraction():
    """Test the phone extraction endpoint with various scenarios"""

    test_cases = [
        {
            "name": "Test with email only",
            "payload": {
                "email": "john.doe@example.com",
                "include_company_phones": True,
                "include_employee_phones": True
            }
        },
        {
            "name": "Test with name and company",
            "payload": {
                "name": "John Doe",
                "company": "Microsoft",
                "include_company_phones": True,
                "include_employee_phones": False
            }
        },
        {
            "name": "Test with real contact (if available)",
            "payload": {
                "email": "daniel.romitelli@emailthewell.com",
                "include_company_phones": True,
                "include_employee_phones": True
            }
        },
        {
            "name": "Test company phone discovery",
            "payload": {
                "company": "salesforce.com",
                "include_company_phones": True,
                "include_employee_phones": True
            }
        }
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test in test_cases:
            print(f"\n{'='*50}")
            print(f"Running: {test['name']}")
            print(f"Payload: {json.dumps(test['payload'], indent=2)}")
            print('='*50)

            try:
                response = await client.post(
                    f"{API_URL}/api/apollo/extract/phones",
                    json=test["payload"],
                    headers={
                        "X-API-Key": API_KEY,
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Success!")
                    print(f"Total phones found: {data.get('total_phones_found', 0)}")
                    print(f"Data completeness: {data.get('data_completeness', 0):.1f}%")

                    if data.get('primary_contact'):
                        print("\n📋 Primary Contact:")
                        contact = data['primary_contact']
                        print(f"  Name: {contact.get('name')}")
                        print(f"  Email: {contact.get('email')}")
                        print(f"  Title: {contact.get('title')}")
                        print(f"  Company: {contact.get('company')}")
                        print(f"  LinkedIn: {contact.get('linkedin')}")

                    if data.get('phone_numbers'):
                        print("\n📱 Phone Numbers:")
                        for phone in data['phone_numbers']:
                            print(f"  • {phone['type']:15} {phone['number']:20} {phone.get('owner', '')}")

                    if data.get('company_info'):
                        print("\n🏢 Company Info:")
                        company = data['company_info']
                        print(f"  Name: {company.get('name')}")
                        print(f"  Website: {company.get('website')}")
                        print(f"  Phone: {company.get('phone')}")
                        print(f"  Industry: {company.get('industry')}")
                        print(f"  Employees: {company.get('employee_count')}")

                    if data.get('metadata'):
                        breakdown = data['metadata'].get('phone_type_breakdown', {})
                        if breakdown:
                            print("\n📊 Phone Type Breakdown:")
                            for phone_type, count in breakdown.items():
                                if count > 0:
                                    print(f"  {phone_type}: {count}")

                else:
                    print(f"❌ Failed with status {response.status_code}")
                    print(f"Error: {response.text}")

            except Exception as e:
                print(f"❌ Exception: {str(e)}")


async def test_contact_enrichment():
    """Test the contact enrichment endpoint"""

    print("\n" + "="*50)
    print("Testing Contact Enrichment Endpoint")
    print("="*50)

    payload = {
        "email": "test@example.com",
        "name": "Test User",
        "company": "Example Corp"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/apollo/enrich/contact",
                params=payload,
                headers={
                    "X-API-Key": API_KEY
                }
            )

            if response.status_code == 200:
                data = response.json()
                print("✅ Enrichment successful!")

                if data.get('person'):
                    print("\n👤 Person Data:")
                    person = data['person']
                    print(f"  Name: {person.get('client_name')}")
                    print(f"  Email: {person.get('email')}")
                    print(f"  Title: {person.get('job_title')}")
                    print(f"  LinkedIn: {person.get('linkedin_url')}")

                if data.get('phone_summary'):
                    summary = data['phone_summary']
                    print(f"\n📱 Phone Summary:")
                    print(f"  Total phones: {summary.get('total_phones', 0)}")
                    if summary.get('primary_phone'):
                        print(f"  Primary: {summary['primary_phone']['number']} ({summary['primary_phone']['type']})")

                if data.get('data_completeness'):
                    print(f"\n📊 Data Completeness: {data['data_completeness']:.1f}%")

            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"Error: {response.text}")

        except Exception as e:
            print(f"❌ Exception: {str(e)}")


async def test_people_search():
    """Test the people search endpoint"""

    print("\n" + "="*50)
    print("Testing People Search Endpoint")
    print("="*50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{API_URL}/api/apollo/search/people",
                params={"query": "CEO Microsoft", "limit": 5},
                headers={
                    "X-API-Key": API_KEY
                }
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data.get('total', 0)} people")

                for person in data.get('people', []):
                    print(f"\n  • {person.get('name')}")
                    print(f"    Title: {person.get('title')}")
                    print(f"    Company: {person.get('company')}")
                    if person.get('phone'):
                        print(f"    Phone: {person.get('phone')}")
                    if person.get('mobile'):
                        print(f"    Mobile: {person.get('mobile')}")
                    if person.get('work_phone'):
                        print(f"    Work: {person.get('work_phone')}")

            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"Error: {response.text}")

        except Exception as e:
            print(f"❌ Exception: {str(e)}")


async def test_company_search():
    """Test the company search endpoint"""

    print("\n" + "="*50)
    print("Testing Company Search Endpoint")
    print("="*50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{API_URL}/api/apollo/search/companies",
                params={"query": "Salesforce", "limit": 3},
                headers={
                    "X-API-Key": API_KEY
                }
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data.get('total', 0)} companies")

                for company in data.get('companies', []):
                    print(f"\n  • {company.get('name')}")
                    print(f"    Domain: {company.get('domain')}")
                    print(f"    Phone: {company.get('phone')}")
                    print(f"    Industry: {company.get('industry')}")
                    print(f"    Employees: {company.get('employee_count')}")
                    print(f"    Location: {company.get('location')}")

            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"Error: {response.text}")

        except Exception as e:
            print(f"❌ Exception: {str(e)}")


async def main():
    """Run all tests"""

    print("\n" + "="*60)
    print("Apollo Phone Discovery API Test Suite")
    print("="*60)
    print(f"API URL: {API_URL}")
    print(f"API Key: {'*' * (len(API_KEY) - 4)}{API_KEY[-4:]}")

    # Check if Apollo API key is configured
    apollo_key = os.getenv("APOLLO_API_KEY")
    if not apollo_key:
        print("\n⚠️  WARNING: APOLLO_API_KEY not configured in .env.local")
        print("   The tests will run but may not return real data.")
        print("   Add your Apollo API key to .env.local to test with real data.")
    else:
        print(f"✅ Apollo API Key configured: {'*' * (len(apollo_key) - 4)}{apollo_key[-4:]}")

    # Run all test suites
    await test_phone_extraction()
    await test_contact_enrichment()
    await test_people_search()
    await test_company_search()

    print("\n" + "="*60)
    print("Test suite completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())