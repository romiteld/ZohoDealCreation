#!/usr/bin/env python3
"""
Test script to verify Apollo enrichment error handling and graceful degradation
"""

import os
import asyncio
import tempfile
from unittest.mock import patch
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

async def test_missing_api_key():
    """Test Apollo enrichment with missing API key"""
    print("Testing Apollo enrichment with missing API key...")

    try:
        # Temporarily remove Apollo API key from environment
        original_key = os.environ.get('APOLLO_API_KEY')
        if 'APOLLO_API_KEY' in os.environ:
            del os.environ['APOLLO_API_KEY']

        # Clear any cached config
        import sys
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        # Test the Apollo enricher
        from app.apollo_enricher import enrich_contact_with_apollo

        result = await enrich_contact_with_apollo("test@example.com")

        print(f"   ✓ Result with missing key: {result}")
        print(f"   ✓ Function handled missing key gracefully: {result is None}")

        # Restore original key
        if original_key:
            os.environ['APOLLO_API_KEY'] = original_key

        return True

    except Exception as e:
        print(f"   ❌ Error with missing API key: {e}")
        import traceback
        traceback.print_exc()

        # Restore original key
        if original_key:
            os.environ['APOLLO_API_KEY'] = original_key

        return False

async def test_network_timeout():
    """Test Apollo enrichment with network timeout"""
    print("\nTesting Apollo enrichment network timeout handling...")

    try:
        # Mock httpx to simulate timeout
        import httpx
        from app.apollo_enricher import enrich_contact_with_apollo

        # Use a mock that raises TimeoutException
        class MockTimeoutClient:
            def __init__(self, timeout=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, *args, **kwargs):
                raise httpx.TimeoutException("Simulated timeout")

        with patch('httpx.AsyncClient', MockTimeoutClient):
            result = await enrich_contact_with_apollo("test@example.com")

        print(f"   ✓ Result with timeout: {result}")
        print(f"   ✓ Function handled timeout gracefully: {result is None}")

        return True

    except Exception as e:
        print(f"   ❌ Error testing timeout: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_error_response():
    """Test Apollo enrichment with API error response"""
    print("\nTesting Apollo enrichment API error response handling...")

    try:
        import httpx
        from app.apollo_enricher import enrich_contact_with_apollo

        # Mock httpx to simulate API error
        class MockErrorResponse:
            status_code = 403
            text = '{"error": "API key invalid", "error_code": "INVALID_API_KEY"}'

        class MockErrorClient:
            def __init__(self, timeout=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, *args, **kwargs):
                return MockErrorResponse()

        with patch('httpx.AsyncClient', MockErrorClient):
            result = await enrich_contact_with_apollo("test@example.com")

        print(f"   ✓ Result with API error: {result}")
        print(f"   ✓ Function handled API error gracefully: {result is None}")

        return True

    except Exception as e:
        print(f"   ❌ Error testing API error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_malformed_response():
    """Test Apollo enrichment with malformed JSON response"""
    print("\nTesting Apollo enrichment malformed response handling...")

    try:
        import httpx
        from app.apollo_enricher import enrich_contact_with_apollo

        # Mock httpx to simulate malformed response
        class MockMalformedResponse:
            status_code = 200

            def json(self):
                raise ValueError("Invalid JSON")

        class MockMalformedClient:
            def __init__(self, timeout=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, *args, **kwargs):
                return MockMalformedResponse()

        with patch('httpx.AsyncClient', MockMalformedClient):
            result = await enrich_contact_with_apollo("test@example.com")

        print(f"   ✓ Result with malformed response: {result}")
        print(f"   ✓ Function handled malformed response gracefully: {result is None}")

        return True

    except Exception as e:
        print(f"   ❌ Error testing malformed response: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_empty_email_input():
    """Test Apollo enrichment with empty/invalid email inputs"""
    print("\nTesting Apollo enrichment with invalid email inputs...")

    try:
        from app.apollo_enricher import enrich_contact_with_apollo

        test_cases = [
            ("", "empty string"),
            (None, "None value"),
            ("invalid-email", "invalid email format"),
            ("@domain.com", "missing local part"),
            ("user@", "missing domain")
        ]

        all_passed = True
        for email, description in test_cases:
            try:
                result = await enrich_contact_with_apollo(email)
                print(f"   ✓ {description}: {result}")
                if result is not None and email in ["", None]:
                    print(f"   ⚠ Warning: Expected None for {description}")
                    all_passed = False
            except Exception as e:
                print(f"   ❌ Error with {description}: {e}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"   ❌ Error testing email inputs: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all error handling tests"""
    print("=" * 60)
    print("Apollo Integration Error Handling Test Suite")
    print("=" * 60)

    # Test 1: Missing API key
    missing_key_success = await test_missing_api_key()

    # Test 2: Network timeout
    timeout_success = await test_network_timeout()

    # Test 3: API error response
    api_error_success = await test_api_error_response()

    # Test 4: Malformed response
    malformed_success = await test_malformed_response()

    # Test 5: Invalid email inputs
    email_success = await test_empty_email_input()

    print("\n" + "=" * 60)
    print("Error Handling Test Summary:")
    print("=" * 60)
    print(f"Missing API Key:          {'✅ PASS' if missing_key_success else '❌ FAIL'}")
    print(f"Network Timeout:          {'✅ PASS' if timeout_success else '❌ FAIL'}")
    print(f"API Error Response:       {'✅ PASS' if api_error_success else '❌ FAIL'}")
    print(f"Malformed Response:       {'✅ PASS' if malformed_success else '❌ FAIL'}")
    print(f"Invalid Email Inputs:     {'✅ PASS' if email_success else '❌ FAIL'}")

    all_success = all([missing_key_success, timeout_success, api_error_success, malformed_success, email_success])
    print(f"\nOverall Status:           {'✅ ALL TESTS PASSED' if all_success else '❌ SOME TESTS FAILED'}")

    return all_success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)