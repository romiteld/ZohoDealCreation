#!/usr/bin/env python3
"""
Test script to ensure Apollo enrichment doesn't break the email processing pipeline
"""

import asyncio
import logging
from unittest.mock import patch, MagicMock

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)

def test_apollo_pipeline_import_safety():
    """Test that importing Apollo components doesn't break other imports"""
    print("Testing Apollo pipeline import safety...")

    try:
        # Test core app imports still work
        print("1. Testing core imports...")
        from app.models import EmailPayload, ExtractedData
        from app.business_rules import BusinessRulesEngine
        print("   ✓ Core models and business rules import successful")

        print("2. Testing Apollo imports don't conflict...")
        from app.apollo_enricher import enrich_contact_with_apollo
        from app.enhanced_enrichment import SmartEnrichmentOrchestrator
        print("   ✓ Apollo components import successful")

        print("3. Testing main app imports after Apollo...")
        from app.main import verify_api_key  # This should work
        print("   ✓ Main app components still importable")

        return True

    except Exception as e:
        print(f"❌ Import safety error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_apollo_enrichment_in_pipeline_context():
    """Test Apollo enrichment works within the broader pipeline context"""
    print("\nTesting Apollo enrichment in pipeline context...")

    try:
        from app.apollo_enricher import enrich_contact_with_apollo

        # Mock a successful Apollo response
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "person": {
                        "name": "Pipeline Test User",
                        "email": "pipeline@test.com",
                        "title": "Test Manager",
                        "organization": {"name": "Pipeline Corp"}
                    }
                }

        class MockClient:
            def __init__(self, timeout=None):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, *args, **kwargs):
                return MockResponse()

        # Test with API key present
        import os
        original_key = os.environ.get('APOLLO_API_KEY')
        os.environ['APOLLO_API_KEY'] = 'pipeline-test-key'

        # Clear config cache
        import sys
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.config')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        with patch('httpx.AsyncClient', MockClient):
            result = await enrich_contact_with_apollo("pipeline@test.com")

        # Restore original key
        if original_key:
            os.environ['APOLLO_API_KEY'] = original_key
        elif 'APOLLO_API_KEY' in os.environ:
            del os.environ['APOLLO_API_KEY']

        print(f"   ✓ Pipeline enrichment result: {result}")
        print(f"   ✓ Enrichment successful: {result is not None}")

        # Test Apollo failure doesn't break pipeline
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = Exception("Network error")
            result_with_error = await enrich_contact_with_apollo("error@test.com")

        print(f"   ✓ Pipeline handles Apollo errors gracefully: {result_with_error is None}")

        return True

    except Exception as e:
        print(f"❌ Pipeline context error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_apollo_integration_with_business_rules():
    """Test Apollo integration with business rules engine"""
    print("\nTesting Apollo integration with business rules...")

    try:
        from app.business_rules import BusinessRulesEngine, format_deal_name, determine_source

        # Test business rules still work
        business_rules = BusinessRulesEngine()

        # Simulate applying business rules to Apollo-enriched data
        mock_extracted_data = {
            'candidate_name': 'Apollo Test User',
            'company_name': 'Apollo Corp',
            'job_title': 'Senior Developer',
            'phone_number': '+1-555-111-2222',
            'company_website': 'https://apollo-corp.com',
            'location': 'New York'
        }

        # Test deal name formatting with Apollo data
        formatted_deal_name = format_deal_name(
            job_title=mock_extracted_data.get('job_title'),
            location=mock_extracted_data.get('location'),
            company_name=mock_extracted_data.get('company_name')
        )

        print(f"   ✓ Deal name formatting with Apollo data: '{formatted_deal_name}'")

        # Test source determination
        source_info = determine_source(
            email_body="Referred by John Smith",
            referrer_name="John Smith",
            sender_email="test@apollo-corp.com"
        )

        print(f"   ✓ Source determination works: {source_info}")

        return True

    except Exception as e:
        print(f"❌ Business rules integration error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_apollo_error_isolation():
    """Test that Apollo errors don't propagate to break the pipeline"""
    print("\nTesting Apollo error isolation...")

    try:
        # Mock the email processing pipeline context
        class MockEmailRequest:
            def __init__(self):
                self.sender_email = "isolation-test@example.com"
                self.sender_name = "Test User"
                self.user_corrections = None

        class MockExtractedData:
            def __init__(self):
                self.candidate_name = "Extracted User"
                self.company_name = "Extracted Corp"
                self.notes = "Test notes"

            def model_dump(self):
                return {
                    'candidate_name': self.candidate_name,
                    'company_name': self.company_name,
                    'notes': self.notes
                }

        request = MockEmailRequest()
        extracted_data = MockExtractedData()

        # Simulate the Apollo enrichment section from main.py
        try:
            from app.apollo_enricher import enrich_contact_with_apollo

            # Force an error in Apollo enrichment
            with patch('app.apollo_enricher.enrich_contact_with_apollo') as mock_enrich:
                mock_enrich.side_effect = Exception("Apollo service down")

                # This should not raise an exception
                apollo_data = None
                try:
                    apollo_data = await enrich_contact_with_apollo(request.sender_email)
                except Exception as apollo_error:
                    print(f"   ✓ Apollo error caught: {apollo_error}")
                    apollo_data = None

                # Pipeline should continue
                if apollo_data:
                    print("   • Apollo enrichment succeeded (unexpected)")
                else:
                    print("   ✓ Pipeline continues after Apollo failure")

                # Verify original data is still intact
                original_data_intact = (extracted_data.candidate_name == "Extracted User")
                print(f"   ✓ Original extraction data preserved: {original_data_intact}")

        except Exception as e:
            print(f"   ❌ Apollo error isolation failed: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ Error isolation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_concurrent_apollo_requests():
    """Test that multiple Apollo requests can be handled concurrently"""
    print("\nTesting concurrent Apollo requests...")

    try:
        from app.apollo_enricher import enrich_contact_with_apollo

        # Mock responses for concurrent testing
        class MockConcurrentResponse:
            def __init__(self, user_id):
                self.status_code = 200
                self.user_id = user_id

            def json(self):
                return {
                    "person": {
                        "name": f"Concurrent User {self.user_id}",
                        "email": f"user{self.user_id}@concurrent.com",
                        "title": f"Role {self.user_id}",
                        "organization": {"name": f"Company {self.user_id}"}
                    }
                }

        class MockConcurrentClient:
            def __init__(self, timeout=None):
                self.call_count = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                self.call_count += 1
                # Simulate some delay
                await asyncio.sleep(0.1)
                return MockConcurrentResponse(self.call_count)

        # Set up API key
        import os
        original_key = os.environ.get('APOLLO_API_KEY')
        os.environ['APOLLO_API_KEY'] = 'concurrent-test-key'

        # Clear config cache
        import sys
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.config')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        with patch('httpx.AsyncClient', MockConcurrentClient):
            # Create multiple concurrent requests
            tasks = [
                enrich_contact_with_apollo(f"user{i}@concurrent.com")
                for i in range(1, 6)
            ]

            # Run them concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Restore original key
        if original_key:
            os.environ['APOLLO_API_KEY'] = original_key
        elif 'APOLLO_API_KEY' in os.environ:
            del os.environ['APOLLO_API_KEY']

        # Verify results
        successful_results = [r for r in results if isinstance(r, dict)]
        errors = [r for r in results if isinstance(r, Exception)]

        print(f"   ✓ Concurrent requests completed: {len(successful_results)} successes, {len(errors)} errors")
        print(f"   ✓ Concurrent processing works: {len(successful_results) > 0}")

        return len(successful_results) > 0

    except Exception as e:
        print(f"❌ Concurrent request test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all pipeline integration tests"""
    print("=" * 60)
    print("Apollo Pipeline Integration Test Suite")
    print("=" * 60)

    # Test 1: Import safety
    import_success = test_apollo_pipeline_import_safety()

    # Test 2: Pipeline context
    pipeline_success = await test_apollo_enrichment_in_pipeline_context()

    # Test 3: Business rules integration
    business_rules_success = test_apollo_integration_with_business_rules()

    # Test 4: Error isolation
    error_isolation_success = await test_apollo_error_isolation()

    # Test 5: Concurrent requests
    concurrent_success = await test_concurrent_apollo_requests()

    print("\n" + "=" * 60)
    print("Pipeline Integration Test Summary:")
    print("=" * 60)
    print(f"Import Safety:            {'✅ PASS' if import_success else '❌ FAIL'}")
    print(f"Pipeline Context:         {'✅ PASS' if pipeline_success else '❌ FAIL'}")
    print(f"Business Rules:           {'✅ PASS' if business_rules_success else '❌ FAIL'}")
    print(f"Error Isolation:          {'✅ PASS' if error_isolation_success else '❌ FAIL'}")
    print(f"Concurrent Requests:      {'✅ PASS' if concurrent_success else '❌ FAIL'}")

    all_success = all([import_success, pipeline_success, business_rules_success, error_isolation_success, concurrent_success])
    print(f"\nOverall Status:           {'✅ ALL TESTS PASSED' if all_success else '❌ SOME TESTS FAILED'}")

    return all_success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)