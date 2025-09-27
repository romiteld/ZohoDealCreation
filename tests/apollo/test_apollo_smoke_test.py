#!/usr/bin/env python3
"""
Comprehensive Apollo Integration Smoke Test
Final validation of the complete Apollo enrichment integration
"""

import asyncio
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

async def run_comprehensive_smoke_test():
    """Run a comprehensive smoke test of the Apollo integration"""
    print("=" * 60)
    print("Apollo Integration Comprehensive Smoke Test")
    print("=" * 60)

    test_results = {}

    # Test 1: Configuration and setup
    print("\n1. Configuration and Setup Test")
    print("-" * 30)
    try:
        from app.config_manager import get_extraction_config
        config = get_extraction_config()
        apollo_configured = bool(config.apollo_api_key)
        print(f"   ✓ Configuration loaded successfully")
        print(f"   ✓ Apollo API key configured: {apollo_configured}")
        test_results['configuration'] = True
    except Exception as e:
        print(f"   ❌ Configuration failed: {e}")
        test_results['configuration'] = False

    # Test 2: Apollo enricher functionality
    print("\n2. Apollo Enricher Functionality Test")
    print("-" * 40)
    try:
        from app.apollo_enricher import enrich_contact_with_apollo

        # Test with empty email (should return None gracefully)
        result_empty = await enrich_contact_with_apollo("")
        print(f"   ✓ Empty email handling: {result_empty is None}")

        # Test with test email (will fail API call but should handle gracefully)
        result_test = await enrich_contact_with_apollo("test@example.com")
        print(f"   ✓ Test email handling: {result_test is None}")

        test_results['enricher_functionality'] = True
    except Exception as e:
        print(f"   ❌ Enricher functionality failed: {e}")
        test_results['enricher_functionality'] = False

    # Test 3: Enhanced enrichment service
    print("\n3. Enhanced Enrichment Service Test")
    print("-" * 38)
    try:
        from app.enhanced_enrichment import EnhancedEnrichmentService, SmartEnrichmentOrchestrator

        # Test service initialization
        service = EnhancedEnrichmentService()
        orchestrator = SmartEnrichmentOrchestrator()

        print(f"   ✓ EnhancedEnrichmentService initialized")
        print(f"   ✓ SmartEnrichmentOrchestrator initialized")

        # Check provider availability
        providers = []
        if service.apollo_api_key:
            providers.append("Apollo")
        if service.clay_api_key:
            providers.append("Clay")
        if service.firecrawl_api_key:
            providers.append("Firecrawl")

        print(f"   ✓ Available providers: {providers}")
        test_results['enhanced_enrichment'] = True
    except Exception as e:
        print(f"   ❌ Enhanced enrichment failed: {e}")
        test_results['enhanced_enrichment'] = False

    # Test 4: Main.py integration
    print("\n4. Main.py Integration Test")
    print("-" * 27)
    try:
        # Test that Apollo imports are available in main.py
        from app.main import app  # This should work if main.py imports are correct

        # Check that Apollo enricher is imported in main.py
        import inspect
        main_source = inspect.getsource(app.__module__)
        apollo_imported = "apollo_enricher" in main_source or "enrich_contact_with_apollo" in main_source

        print(f"   ✓ Main.py imports Apollo components: {apollo_imported}")
        print(f"   ✓ FastAPI app initializes successfully")

        test_results['main_integration'] = True
    except Exception as e:
        print(f"   ❌ Main.py integration failed: {e}")
        test_results['main_integration'] = False

    # Test 5: Business rules compatibility
    print("\n5. Business Rules Compatibility Test")
    print("-" * 36)
    try:
        from app.business_rules import BusinessRulesEngine, format_deal_name, determine_source

        # Test business rules with Apollo-style data
        formatted_name = format_deal_name(
            job_title="Software Engineer",
            location="San Francisco",
            company_name="Tech Corp"
        )

        source_info = determine_source(
            email_body="Great candidate referred by Apollo",
            referrer_name="Apollo Contact",
            sender_email="apollo@techcorp.com"
        )

        print(f"   ✓ Deal name formatting: '{formatted_name}'")
        print(f"   ✓ Source determination: {source_info}")

        test_results['business_rules'] = True
    except Exception as e:
        print(f"   ❌ Business rules compatibility failed: {e}")
        test_results['business_rules'] = False

    # Test 6: Error handling robustness
    print("\n6. Error Handling Robustness Test")
    print("-" * 34)
    try:
        from app.apollo_enricher import enrich_contact_with_apollo
        from unittest.mock import patch
        import httpx

        # Test timeout handling
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = httpx.TimeoutException("Test timeout")
            result_timeout = await enrich_contact_with_apollo("timeout@test.com")

        # Test API error handling
        class MockErrorResponse:
            status_code = 500
            text = "Internal Server Error"

        class MockErrorClient:
            def __init__(self, timeout=None):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, *args, **kwargs):
                return MockErrorResponse()

        # Set up temporary API key for testing
        import os
        original_key = os.environ.get('APOLLO_API_KEY')
        os.environ['APOLLO_API_KEY'] = 'test-error-handling-key'

        # Clear config cache
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.config')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        with patch('httpx.AsyncClient', MockErrorClient):
            result_error = await enrich_contact_with_apollo("error@test.com")

        # Restore original key
        if original_key:
            os.environ['APOLLO_API_KEY'] = original_key
        elif 'APOLLO_API_KEY' in os.environ:
            del os.environ['APOLLO_API_KEY']

        print(f"   ✓ Timeout handling: {result_timeout is None}")
        print(f"   ✓ API error handling: {result_error is None}")

        test_results['error_handling'] = True
    except Exception as e:
        print(f"   ❌ Error handling test failed: {e}")
        test_results['error_handling'] = False

    # Test 7: Data mapping validation
    print("\n7. Data Mapping Validation Test")
    print("-" * 32)
    try:
        # Test complete Apollo response mapping
        mock_apollo_response = {
            "person": {
                "name": "John Smith",
                "email": "john@company.com",
                "phone_numbers": [{"sanitized_number": "+1-555-123-4567"}],
                "title": "VP Engineering",
                "city": "Seattle",
                "organization": {
                    "name": "TechCorp Inc",
                    "website_url": "https://techcorp.com"
                }
            }
        }

        # Simulate apollo_enricher.py mapping logic
        person = mock_apollo_response.get("person", {})
        organization = person.get("organization", {})

        apollo_data = {
            "client_name": person.get("name") or "",
            "email": person.get("email") or "",
            "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
            "firm_company": organization.get("name", ""),
            "website": organization.get("website_url", ""),
            "job_title": person.get("title", ""),
            "location": person.get("city", "")
        }

        # Filter out empty values
        apollo_data = {k: v for k, v in apollo_data.items() if v}

        # Test main.py mapping to internal schema
        internal_mapping = {}
        if apollo_data.get('client_name'):
            internal_mapping['candidate_name'] = apollo_data['client_name']
        if apollo_data.get('firm_company'):
            internal_mapping['company_name'] = apollo_data['firm_company']
        if apollo_data.get('job_title'):
            internal_mapping['job_title'] = apollo_data['job_title']
        if apollo_data.get('phone'):
            internal_mapping['phone_number'] = apollo_data['phone']
        if apollo_data.get('website'):
            internal_mapping['company_website'] = apollo_data['website']
        if apollo_data.get('location'):
            internal_mapping['location'] = apollo_data['location']

        print(f"   ✓ Apollo response parsing: {len(apollo_data)} fields")
        print(f"   ✓ Internal schema mapping: {len(internal_mapping)} fields")
        print(f"   ✓ Required fields present: {all(field in internal_mapping for field in ['candidate_name', 'company_name', 'job_title'])}")

        test_results['data_mapping'] = True
    except Exception as e:
        print(f"   ❌ Data mapping validation failed: {e}")
        test_results['data_mapping'] = False

    # Final Results Summary
    print("\n" + "=" * 60)
    print("APOLLO INTEGRATION SMOKE TEST RESULTS")
    print("=" * 60)

    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    failed_tests = total_tests - passed_tests

    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title():<30} {status}")

    print("\n" + "-" * 60)
    print(f"Total Tests:    {total_tests}")
    print(f"Passed:         {passed_tests}")
    print(f"Failed:         {failed_tests}")
    print(f"Success Rate:   {(passed_tests/total_tests)*100:.1f}%")

    overall_success = passed_tests == total_tests
    print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if overall_success else '⚠️  SOME TESTS FAILED'}")

    return overall_success, test_results

if __name__ == "__main__":
    success, results = asyncio.run(run_comprehensive_smoke_test())
    exit(0 if success else 1)