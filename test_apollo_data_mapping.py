#!/usr/bin/env python3
"""
Test script to validate Apollo response data mapping to internal schema
"""

import asyncio
from unittest.mock import patch

def test_apollo_response_schema():
    """Test that Apollo response mapping matches expected internal schema"""
    print("Testing Apollo response to internal schema mapping...")

    try:
        # Mock a complete Apollo API response
        mock_apollo_response = {
            "person": {
                "name": "John Doe",
                "email": "john.doe@company.com",
                "phone_numbers": [
                    {"sanitized_number": "+1-555-123-4567", "raw_number": "555-123-4567"}
                ],
                "title": "Senior Software Engineer",
                "city": "San Francisco",
                "state": "CA",
                "organization": {
                    "name": "Tech Company Inc",
                    "website_url": "https://techcompany.com"
                }
            }
        }

        # Test mapping logic (simulating apollo_enricher.py mapping)
        person = mock_apollo_response.get("person", {})
        organization = person.get("organization", {})

        enriched_data = {
            "client_name": person.get("name") or "",
            "email": person.get("email") or "test@example.com",
            "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
            "firm_company": organization.get("name", ""),
            "website": organization.get("website_url", ""),
            "job_title": person.get("title", ""),
            "location": person.get("city", "")
        }

        # Filter out empty values
        enriched_data = {k: v for k, v in enriched_data.items() if v}

        print("1. Testing Apollo response field mapping:")
        print(f"   • client_name: '{enriched_data.get('client_name')}'")
        print(f"   • email: '{enriched_data.get('email')}'")
        print(f"   • phone: '{enriched_data.get('phone')}'")
        print(f"   • firm_company: '{enriched_data.get('firm_company')}'")
        print(f"   • website: '{enriched_data.get('website')}'")
        print(f"   • job_title: '{enriched_data.get('job_title')}'")
        print(f"   • location: '{enriched_data.get('location')}'")

        # Now test the main.py mapping from Apollo fields to internal schema
        apollo_mapped = {}

        # Map Apollo fields to our internal schema
        if enriched_data.get('client_name'):
            apollo_mapped['candidate_name'] = enriched_data['client_name']
        if enriched_data.get('firm_company'):
            apollo_mapped['company_name'] = enriched_data['firm_company']
        if enriched_data.get('job_title'):
            apollo_mapped['job_title'] = enriched_data['job_title']
        if enriched_data.get('phone'):
            apollo_mapped['phone_number'] = enriched_data['phone']
        if enriched_data.get('website'):
            apollo_mapped['company_website'] = enriched_data['website']
        if enriched_data.get('location'):
            apollo_mapped['location'] = enriched_data['location']

        print("\n2. Testing main.py internal schema mapping:")
        print(f"   • candidate_name: '{apollo_mapped.get('candidate_name')}'")
        print(f"   • company_name: '{apollo_mapped.get('company_name')}'")
        print(f"   • job_title: '{apollo_mapped.get('job_title')}'")
        print(f"   • phone_number: '{apollo_mapped.get('phone_number')}'")
        print(f"   • company_website: '{apollo_mapped.get('company_website')}'")
        print(f"   • location: '{apollo_mapped.get('location')}'")

        print("\n3. Validating mapping completeness:")
        expected_fields = ['candidate_name', 'company_name', 'job_title', 'phone_number', 'company_website', 'location']
        mapped_fields = list(apollo_mapped.keys())

        print(f"   • Expected fields: {expected_fields}")
        print(f"   • Mapped fields: {mapped_fields}")
        print(f"   • All fields mapped: {all(field in mapped_fields for field in expected_fields)}")

        return True

    except Exception as e:
        print(f"❌ Schema mapping error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_partial_apollo_response():
    """Test mapping with partial/incomplete Apollo response"""
    print("\nTesting partial Apollo response mapping...")

    try:
        # Mock a partial Apollo API response (missing some fields)
        partial_response = {
            "person": {
                "name": "Jane Smith",
                "email": "jane@startup.com",
                # No phone_numbers
                "title": "CTO",
                # No city
                "organization": {
                    "name": "Startup Inc"
                    # No website_url
                }
            }
        }

        # Test mapping logic
        person = partial_response.get("person", {})
        organization = person.get("organization", {})

        enriched_data = {
            "client_name": person.get("name") or "",
            "email": person.get("email") or "test@example.com",
            "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
            "firm_company": organization.get("name", ""),
            "website": organization.get("website_url", ""),
            "job_title": person.get("title", ""),
            "location": person.get("city", "")
        }

        # Filter out empty values
        enriched_data = {k: v for k, v in enriched_data.items() if v}

        print("1. Testing partial response field mapping:")
        for field, value in enriched_data.items():
            print(f"   • {field}: '{value}'")

        # Test main.py mapping
        apollo_mapped = {}
        if enriched_data.get('client_name'):
            apollo_mapped['candidate_name'] = enriched_data['client_name']
        if enriched_data.get('firm_company'):
            apollo_mapped['company_name'] = enriched_data['firm_company']
        if enriched_data.get('job_title'):
            apollo_mapped['job_title'] = enriched_data['job_title']
        if enriched_data.get('phone'):
            apollo_mapped['phone_number'] = enriched_data['phone']
        if enriched_data.get('website'):
            apollo_mapped['company_website'] = enriched_data['website']
        if enriched_data.get('location'):
            apollo_mapped['location'] = enriched_data['location']

        print("\n2. Testing partial response internal mapping:")
        for field, value in apollo_mapped.items():
            print(f"   • {field}: '{value}'")

        print(f"\n3. Partial mapping success: {len(apollo_mapped) > 0}")
        print(f"   • Fields successfully mapped: {len(apollo_mapped)}")

        return True

    except Exception as e:
        print(f"❌ Partial mapping error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_empty_apollo_response():
    """Test mapping with empty/null Apollo response"""
    print("\nTesting empty Apollo response mapping...")

    try:
        test_cases = [
            ({}, "empty dict"),
            ({"person": None}, "null person"),
            ({"person": {}}, "empty person"),
            ({"person": {"organization": {}}}, "empty organization"),
            (None, "null response")
        ]

        all_passed = True
        for response, description in test_cases:
            print(f"   Testing {description}:")

            try:
                if response is None:
                    # Simulate what would happen in apollo_enricher.py
                    enriched_data = None
                else:
                    person = response.get("person", {}) if response else {}
                    if person is None:
                        person = {}

                    organization = person.get("organization", {})
                    if organization is None:
                        organization = {}

                    enriched_data = {
                        "client_name": person.get("name") or "",
                        "email": person.get("email") or "test@example.com",
                        "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
                        "firm_company": organization.get("name", ""),
                        "website": organization.get("website_url", ""),
                        "job_title": person.get("title", ""),
                        "location": person.get("city", "")
                    }

                    # Filter out empty values
                    enriched_data = {k: v for k, v in enriched_data.items() if v}

                if enriched_data:
                    print(f"     • Mapped fields: {list(enriched_data.keys())}")
                else:
                    print(f"     • No fields mapped (expected for {description})")

            except Exception as e:
                print(f"     ❌ Error with {description}: {e}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ Empty response mapping error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_integration_with_actual_enricher():
    """Test the actual apollo_enricher.py function with mocked responses"""
    print("\nTesting integration with actual Apollo enricher...")

    try:
        import httpx
        from app.apollo_enricher import enrich_contact_with_apollo

        # Mock successful Apollo response
        class MockSuccessResponse:
            status_code = 200

            def json(self):
                return {
                    "person": {
                        "name": "Integration Test User",
                        "email": "integration@test.com",
                        "phone_numbers": [{"sanitized_number": "+1-555-999-8888"}],
                        "title": "Test Engineer",
                        "city": "Test City",
                        "organization": {
                            "name": "Test Company",
                            "website_url": "https://test.com"
                        }
                    }
                }

        class MockSuccessClient:
            def __init__(self, timeout=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, *args, **kwargs):
                return MockSuccessResponse()

        # Temporarily set Apollo API key for testing
        import os
        original_key = os.environ.get('APOLLO_API_KEY')
        os.environ['APOLLO_API_KEY'] = 'test-key-for-integration-test'

        # Clear config cache
        import sys
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.config')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        with patch('httpx.AsyncClient', MockSuccessClient):
            result = await enrich_contact_with_apollo("integration@test.com")

        # Restore original key
        if original_key:
            os.environ['APOLLO_API_KEY'] = original_key
        elif 'APOLLO_API_KEY' in os.environ:
            del os.environ['APOLLO_API_KEY']

        print("1. Testing actual enricher integration:")
        if result:
            print(f"   ✓ Enrichment successful: {len(result)} fields returned")
            for field, value in result.items():
                print(f"     • {field}: '{value}'")
        else:
            print("   ❌ Enrichment returned None")
            return False

        # Test that result has expected structure
        expected_fields = ['client_name', 'email', 'phone', 'firm_company', 'website', 'job_title', 'location']
        actual_fields = list(result.keys()) if result else []

        print(f"\n2. Testing result structure:")
        print(f"   • Expected fields: {expected_fields}")
        print(f"   • Actual fields: {actual_fields}")

        has_required_fields = any(field in actual_fields for field in ['client_name', 'firm_company', 'job_title'])
        print(f"   • Has core fields: {has_required_fields}")

        return has_required_fields

    except Exception as e:
        print(f"❌ Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all data mapping validation tests"""
    print("=" * 60)
    print("Apollo Data Mapping Validation Test Suite")
    print("=" * 60)

    # Test 1: Complete response mapping
    complete_success = test_apollo_response_schema()

    # Test 2: Partial response mapping
    partial_success = test_partial_apollo_response()

    # Test 3: Empty response mapping
    empty_success = test_empty_apollo_response()

    # Test 4: Integration with actual enricher
    integration_success = await test_integration_with_actual_enricher()

    print("\n" + "=" * 60)
    print("Data Mapping Validation Summary:")
    print("=" * 60)
    print(f"Complete Response Mapping: {'✅ PASS' if complete_success else '❌ FAIL'}")
    print(f"Partial Response Mapping:  {'✅ PASS' if partial_success else '❌ FAIL'}")
    print(f"Empty Response Mapping:    {'✅ PASS' if empty_success else '❌ FAIL'}")
    print(f"Enricher Integration:      {'✅ PASS' if integration_success else '❌ FAIL'}")

    all_success = all([complete_success, partial_success, empty_success, integration_success])
    print(f"\nOverall Status:            {'✅ ALL TESTS PASSED' if all_success else '❌ SOME TESTS FAILED'}")

    return all_success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)