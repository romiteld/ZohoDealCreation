#!/usr/bin/env python3
"""
Test script for Apollo.io location and website extraction functionality.

This script tests the new location extraction endpoints and integration
with the main email processing pipeline.
"""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-key-only-for-testing")


async def test_location_extraction():
    """Test the location extraction endpoint"""
    print("\n=== Testing Apollo Location Extraction ===\n")

    # Test cases
    test_cases = [
        {
            "name": "Extract company location by name",
            "endpoint": "/api/apollo/extract/location",
            "payload": {
                "company_name": "Microsoft",
                "extract_type": "company",
                "include_geocoding": False
            }
        },
        {
            "name": "Extract company location by domain",
            "endpoint": "/api/apollo/extract/location",
            "payload": {
                "company_domain": "google.com",
                "extract_type": "company",
                "include_geocoding": False
            }
        },
        {
            "name": "Extract person location with company",
            "endpoint": "/api/apollo/extract/location",
            "payload": {
                "email": "john.doe@example.com",
                "person_name": "John Doe",
                "extract_type": "person"
            }
        }
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in test_cases:
            print(f"Test: {test_case['name']}")
            print("-" * 50)

            try:
                response = await client.post(
                    f"{API_URL}{test_case['endpoint']}",
                    json=test_case['payload'],
                    headers={"X-API-Key": API_KEY}
                )

                if response.status_code == 200:
                    result = response.json()

                    # Display metrics
                    if "metrics" in result:
                        metrics = result["metrics"]
                        print(f"✓ Status: {metrics.get('status', 'unknown')}")

                        if metrics.get("extraction_type") == "company":
                            print(f"  Locations found: {metrics.get('locations_found', 0)}")
                            print(f"  Websites found: {metrics.get('websites_found', 0)}")
                            print(f"  Multiple locations: {metrics.get('has_multiple_locations', False)}")

                            # Show geographic coverage
                            coverage = metrics.get('geographic_coverage', {})
                            if coverage:
                                print(f"  Geographic coverage:")
                                print(f"    Countries: {', '.join(coverage.get('countries', []))}")
                                print(f"    States: {', '.join(coverage.get('states', []))}")
                                print(f"    Cities: {', '.join(coverage.get('cities', []))}")
                        else:
                            print(f"  Person location found: {metrics.get('person_location_found', False)}")
                            print(f"  Company locations: {metrics.get('company_locations_found', 0)}")
                            print(f"  Company websites: {metrics.get('company_websites_found', 0)}")

                    # Display location data
                    if "data" in result:
                        data = result["data"]

                        # Show primary location
                        if "locations" in data and data["locations"]:
                            print("\n  Primary Location:")
                            primary = next((loc for loc in data["locations"] if loc.get("is_primary")), data["locations"][0])
                            print(f"    Address: {primary.get('full_address', 'N/A')}")
                            print(f"    Timezone: {primary.get('timezone', 'N/A')}")

                            # Show additional locations
                            if len(data["locations"]) > 1:
                                print(f"\n  Additional Locations: {len(data['locations']) - 1}")
                                for loc in data["locations"][1:4]:  # Show up to 3 more
                                    print(f"    - {loc.get('city', '')}, {loc.get('state', '')} ({loc.get('location_type', 'Office')})")

                        # Show websites
                        if "websites" in data and data["websites"]:
                            websites = data["websites"]
                            print("\n  Websites:")
                            if websites.get("primary_website"):
                                print(f"    Primary: {websites['primary_website']}")
                            if websites.get("blog_url"):
                                print(f"    Blog: {websites['blog_url']}")
                            if websites.get("careers_page"):
                                print(f"    Careers: {websites['careers_page']}")

                            # Show social profiles
                            social = websites.get("social_profiles", {})
                            if any(social.values()):
                                print("  Social Profiles:")
                                for platform, url in social.items():
                                    if url:
                                        print(f"    {platform.capitalize()}: {url}")

                    print(f"\n✓ Success\n")
                else:
                    print(f"✗ Failed with status {response.status_code}: {response.text}\n")

            except Exception as e:
                print(f"✗ Error: {str(e)}\n")


async def test_batch_location_extraction():
    """Test batch location extraction"""
    print("\n=== Testing Batch Location Extraction ===\n")

    payload = {
        "entities": [
            {"name": "Apple Inc", "domain": "apple.com"},
            {"name": "Amazon", "domain": "amazon.com"},
            {"name": "Netflix", "domain": "netflix.com"}
        ],
        "entity_type": "company",
        "include_geocoding": False
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/apollo/extract/batch-locations",
                json=payload,
                headers={"X-API-Key": API_KEY}
            )

            if response.status_code == 200:
                result = response.json()

                # Display batch metrics
                if "batch_metrics" in result:
                    metrics = result["batch_metrics"]
                    print(f"✓ Batch processing complete")
                    print(f"  Total entities: {metrics.get('total_entities', 0)}")
                    print(f"  Successful: {metrics.get('successful', 0)}")
                    print(f"  Failed: {metrics.get('failed', 0)}")

                # Display results summary
                if "results" in result:
                    print("\nResults Summary:")
                    for entity_result in result["results"]:
                        if "error" not in entity_result:
                            query = entity_result.get("query", {})
                            company_info = entity_result.get("company_info", {})
                            locations = entity_result.get("locations", [])
                            websites = entity_result.get("websites", {})

                            print(f"\n  {company_info.get('name', query.get('name', 'Unknown'))}:")
                            print(f"    Locations: {len(locations)}")
                            if locations:
                                primary = next((loc for loc in locations if loc.get("is_primary")), locations[0])
                                print(f"    HQ: {primary.get('city', 'N/A')}, {primary.get('state', 'N/A')}")

                            if websites:
                                urls = websites.get("all_urls", [])
                                print(f"    Websites: {len(urls)}")
                        else:
                            query = entity_result.get("query", {})
                            print(f"\n  {query.get('name', 'Unknown')}: Failed - {entity_result['error']}")

                print("\n✓ Batch test complete\n")
            else:
                print(f"✗ Failed with status {response.status_code}: {response.text}\n")

        except Exception as e:
            print(f"✗ Error: {str(e)}\n")


async def test_email_processing_with_location():
    """Test email processing with location enrichment"""
    print("\n=== Testing Email Processing with Location Enrichment ===\n")

    # Sample email that should trigger location extraction
    email_payload = {
        "sender_email": "recruiter@techcompany.com",
        "sender_name": "Jane Smith",
        "subject": "Senior Software Engineer Position - San Francisco",
        "body": """
        Hi,

        I'm reaching out from TechCompany regarding an exciting Senior Software Engineer
        position at our San Francisco office.

        We're looking for someone with your background in Python and cloud technologies.
        The role offers competitive compensation and the flexibility to work from any of
        our offices in SF, New York, or Austin.

        Would you be interested in discussing this opportunity?

        Best regards,
        Jane Smith
        Senior Technical Recruiter
        TechCompany Inc.
        """,
        "received_date": "2025-01-16T10:00:00Z"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/intake/email",
                json=email_payload,
                headers={"X-API-Key": API_KEY}
            )

            if response.status_code == 200:
                result = response.json()
                print("✓ Email processed successfully")

                # Check if location data was extracted
                extracted = result.get("extracted", {})
                if extracted:
                    print("\nExtracted Data:")
                    print(f"  Candidate: {extracted.get('candidate_name', 'N/A')}")
                    print(f"  Company: {extracted.get('company_name', 'N/A')}")
                    print(f"  Location: {extracted.get('location', 'N/A')}")
                    print(f"  Website: {extracted.get('company_website', 'N/A')}")

                    # Check notes for location enrichment
                    notes = extracted.get("notes", "")
                    if "Office Locations" in notes or "Location:" in notes:
                        print("\n✓ Location enrichment found in notes")
                    if "Web Presence" in notes or "Blog:" in notes or "Careers:" in notes:
                        print("✓ Website enrichment found in notes")

                print(f"\nDeal ID: {result.get('deal_id', 'N/A')}")
                print(f"Contact ID: {result.get('contact_id', 'N/A')}")
            else:
                print(f"✗ Failed with status {response.status_code}: {response.text}")

        except Exception as e:
            print(f"✗ Error: {str(e)}")


async def main():
    """Run all tests"""
    print("=" * 70)
    print("Apollo.io Location and Website Extraction Test Suite")
    print("=" * 70)

    # Run tests
    await test_location_extraction()
    await test_batch_location_extraction()
    await test_email_processing_with_location()

    print("\n" + "=" * 70)
    print("All tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())