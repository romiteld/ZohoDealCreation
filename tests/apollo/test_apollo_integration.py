#!/usr/bin/env python3
"""
Test Apollo enrichment integration in the main API endpoint
"""

import asyncio
import os
from unittest.mock import AsyncMock, patch
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

async def test_apollo_integration():
    """Test that Apollo enrichment is properly integrated"""

    # Mock Apollo response
    mock_apollo_data = {
        "client_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-123-4567",
        "firm_company": "Example Corp",
        "website": "https://example.com",
        "job_title": "Senior Developer",
        "location": "San Francisco"
    }

    # Test the enrich_contact_with_apollo function directly
    try:
        from app.apollo_enricher import enrich_contact_with_apollo

        with patch('app.apollo_enricher.httpx.AsyncClient') as mock_client_class:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "person": {
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "phone_numbers": [{"sanitized_number": "+1-555-123-4567"}],
                    "title": "Senior Developer",
                    "city": "San Francisco",
                    "organization": {
                        "name": "Example Corp",
                        "website_url": "https://example.com"
                    }
                }
            }

            # Setup proper async context manager mocking
            mock_client = AsyncMock()
            mock_client.post.return_value.__aenter__.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Test enrichment
            result = await enrich_contact_with_apollo("john.doe@example.com")

            print("✅ Apollo enrichment function test:")
            print(f"   Result: {result}")

            # Verify mapping
            expected_mapping = {
                'candidate_name': 'John Doe',
                'company_name': 'Example Corp',
                'job_title': 'Senior Developer',
                'phone_number': '+1-555-123-4567',
                'company_website': 'https://example.com',
                'location': 'San Francisco'
            }

            if result:
                print("✅ Apollo returned data successfully")

                # Test field mapping logic
                apollo_mapped = {}
                if result.get('client_name'):
                    apollo_mapped['candidate_name'] = result['client_name']
                if result.get('firm_company'):
                    apollo_mapped['company_name'] = result['firm_company']
                if result.get('job_title'):
                    apollo_mapped['job_title'] = result['job_title']
                if result.get('phone'):
                    apollo_mapped['phone_number'] = result['phone']
                if result.get('website'):
                    apollo_mapped['company_website'] = result['website']
                if result.get('location'):
                    apollo_mapped['location'] = result['location']

                print("✅ Field mapping test:")
                print(f"   Mapped fields: {list(apollo_mapped.keys())}")
                print(f"   Mapped data: {apollo_mapped}")

                # Verify all expected fields are mapped
                for field in expected_mapping.keys():
                    if field in apollo_mapped:
                        print(f"   ✅ {field}: {apollo_mapped[field]}")
                    else:
                        print(f"   ❌ Missing: {field}")
            else:
                print("❌ Apollo returned no data")

    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

def test_import_integration():
    """Test that the main.py import is working"""
    try:
        from app.main import enrich_contact_with_apollo
        print("✅ Apollo enrichment import successful in main.py")
        return True
    except ImportError as e:
        print(f"❌ Apollo enrichment import failed in main.py: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Apollo enrichment integration...\n")

    # Test import
    import_success = test_import_integration()

    if import_success:
        # Test functionality
        asyncio.run(test_apollo_integration())

    print("\n✅ Apollo integration test completed!")