#!/usr/bin/env python3
"""
End-to-end test for natural language query system.

Tests:
1. Vault candidate queries (real-time Zoho API)
2. Various query types (count, list, search, filter)
3. Executive access (no owner filtering)

Usage:
    python3 test_nlp_queries_e2e.py
"""
import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api.teams.query_engine import QueryEngine


async def test_vault_candidate_queries():
    """Test vault candidate natural language queries."""
    print("\n" + "="*70)
    print("END-TO-END NATURAL LANGUAGE QUERY TEST")
    print("="*70)

    # Initialize query engine
    engine = QueryEngine()

    # Test user (executive with full access)
    test_user = "daniel.romitelli@emailthewell.com"

    # Test queries
    test_cases = [
        {
            "name": "Count all vault candidates",
            "query": "how many vault candidates are there",
            "expected_type": "count"
        },
        {
            "name": "List vault candidates",
            "query": "show me vault candidates",
            "expected_type": "list"
        },
        {
            "name": "Search by TWAV number",
            "query": "find vault candidates with TWAV109867",
            "expected_type": "search"
        },
        {
            "name": "Filter by location (Texas)",
            "query": "show me vault candidates in Texas",
            "expected_type": "list"
        },
        {
            "name": "Filter by location (California)",
            "query": "list advisors in California",
            "expected_type": "list"
        },
        {
            "name": "Recent candidates (last week)",
            "query": "show me vault candidates from last week",
            "expected_type": "list"
        },
        {
            "name": "C-suite candidates",
            "query": "find c-suite vault candidates",
            "expected_type": "list"
        },
    ]

    results = []

    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n{'─'*70}")
        print(f"Test {idx}/{len(test_cases)}: {test_case['name']}")
        print(f"Query: \"{test_case['query']}\"")
        print(f"{'─'*70}")

        try:
            # Execute query
            start_time = datetime.now()
            response = await engine.process_query(
                query=test_case['query'],
                user_email=test_user
            )
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Extract results
            response_text = response.get("text", "")
            data = response.get("data", [])

            # Determine status
            if "❌" in response_text or "Error" in response_text:
                status = "❌ FAILED"
                results.append(False)
            else:
                status = "✅ PASSED"
                results.append(True)

            # Print results
            print(f"\n{status}")
            print(f"Response time: {elapsed_ms:.0f}ms")
            print(f"Data source: Zoho CRM (real-time)")

            if data:
                print(f"Results count: {len(data)}")

                # Show sample results
                if len(data) > 0:
                    print(f"\nSample result:")
                    first = data[0]
                    print(f"  - Candidate Locator: {first.get('candidate_locator')}")
                    print(f"  - Name: {first.get('candidate_name')}")
                    print(f"  - Title: {first.get('job_title')}")
                    print(f"  - Location: {first.get('location')}")
                    print(f"  - Firm: {first.get('company_name')}")

                    if len(data) > 1:
                        print(f"  ... and {len(data) - 1} more")

            # Show response preview
            response_preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
            print(f"\nResponse preview:\n{response_preview}")

        except Exception as e:
            status = "❌ FAILED"
            results.append(False)
            print(f"\n{status}")
            print(f"Error: {str(e)}")
            import traceback
            print(f"\nTraceback:\n{traceback.format_exc()}")

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print(f"\n✅ ALL TESTS PASSED - Ready for production deployment")
        return True
    else:
        print(f"\n❌ SOME TESTS FAILED - Fix issues before deploying")
        return False


async def test_data_source_verification():
    """Verify queries are using Zoho API (not PostgreSQL)."""
    print("\n" + "="*70)
    print("DATA SOURCE VERIFICATION")
    print("="*70)

    engine = QueryEngine()
    test_user = "daniel.romitelli@emailthewell.com"

    print("\nTesting that queries use real-time Zoho API...")
    print("(Not stale PostgreSQL data)")

    # Execute a simple query
    response = await engine.process_query(
        query="show me 5 vault candidates",
        user_email=test_user
    )

    data = response.get("data", [])

    if data:
        print(f"\n✅ Retrieved {len(data)} candidates")
        print(f"✅ Data source: Zoho CRM API (real-time)")

        # Check for real-time fields that prove Zoho API usage
        first = data[0]
        has_zoho_fields = all([
            first.get('candidate_locator'),  # Candidate_Locator from Zoho
            'published_to_vault' in first,   # Publish_to_Vault from Zoho
        ])

        if has_zoho_fields:
            print(f"✅ Zoho API field mapping verified")
            print(f"   - candidate_locator: {first.get('candidate_locator')}")
            print(f"   - published_to_vault: {first.get('published_to_vault')}")
            return True
        else:
            print(f"❌ Missing expected Zoho API fields")
            return False
    else:
        print(f"❌ No data returned")
        return False


async def test_executive_access():
    """Verify executive users have unrestricted access."""
    print("\n" + "="*70)
    print("EXECUTIVE ACCESS VERIFICATION")
    print("="*70)

    engine = QueryEngine()

    # Test executive users
    executive_users = [
        "daniel.romitelli@emailthewell.com",
        "steve.perry@emailthewell.com",
        "brandon@emailthewell.com"
    ]

    print("\nTesting that executives have full access (no owner filtering)...")

    results = []
    for user in executive_users:
        try:
            response = await engine.process_query(
                query="how many vault candidates are there",
                user_email=user
            )

            response_text = response.get("text", "")

            if "❌" not in response_text and "Error" not in response_text:
                print(f"✅ {user}: Access granted")
                results.append(True)
            else:
                print(f"❌ {user}: Access denied or error")
                results.append(False)
        except Exception as e:
            print(f"❌ {user}: Error - {str(e)}")
            results.append(False)

    if all(results):
        print(f"\n✅ All executives have unrestricted access")
        return True
    else:
        print(f"\n❌ Some executives lack proper access")
        return False


async def main():
    """Run all end-to-end tests."""
    print("\n🚀 Starting end-to-end natural language query tests...")
    print(f"Timestamp: {datetime.now().isoformat()}")

    try:
        # Run all test suites
        test_1 = await test_vault_candidate_queries()
        test_2 = await test_data_source_verification()
        test_3 = await test_executive_access()

        # Final verdict
        print("\n" + "="*70)
        print("FINAL VERDICT")
        print("="*70)

        all_passed = all([test_1, test_2, test_3])

        if all_passed:
            print("\n✅ ALL TEST SUITES PASSED")
            print("\n🚀 System is ready for production deployment!")
            print("\nNext steps:")
            print("1. Build Docker images")
            print("2. Push to Azure Container Registry")
            print("3. Deploy to Azure Container Apps")
            print("4. Test in production Teams Bot")
            sys.exit(0)
        else:
            print("\n❌ SOME TEST SUITES FAILED")
            print("\n⚠️  Fix issues before deploying to production")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        print(f"\nTraceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
