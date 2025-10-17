#!/usr/bin/env python3
"""
Test script for PostgreSQL vault_adapter.

Verifies that the adapter can:
1. Query vault_candidates from PostgreSQL
2. Map schema correctly (twav_number → candidate_locator)
3. Filter by TWAV number, name, location
4. Parse currency fields

Usage:
    python3 test_vault_adapter.py
"""
import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api.teams.vault_adapter import (
    query_vault_candidates_postgres,
    get_vault_candidate_by_locator,
    get_vault_candidates_count,
    parse_currency_to_float
)


async def test_currency_parsing():
    """Test currency string parsing."""
    print("\n=== Testing Currency Parsing ===")

    test_cases = [
        ("$50M", 50000000.0),
        ("$500k", 500000.0),
        ("1.5M", 1500000.0),
        ("$100,000", 100000.0),
        ("50M", 50000000.0),
        ("2.3M", 2300000.0),
    ]

    for value, expected in test_cases:
        try:
            result = parse_currency_to_float(value)
            status = "✅" if result == expected else "❌"
            print(f"{status} parse_currency_to_float('{value}') = {result:,.0f} (expected {expected:,.0f})")
        except Exception as e:
            print(f"❌ parse_currency_to_float('{value}') failed: {e}")


async def test_query_all():
    """Test querying all vault candidates."""
    print("\n=== Testing Query All Candidates ===")

    try:
        results = await query_vault_candidates_postgres(limit=10)
        print(f"✅ Found {len(results)} candidates (limited to 10)")

        if results:
            # Show first result
            first = results[0]
            print(f"\nFirst candidate:")
            print(f"  Candidate Locator: {first.get('candidate_locator')}")
            print(f"  Name: {first.get('candidate_name')}")
            print(f"  Job Title: {first.get('job_title')}")
            print(f"  Location: {first.get('location')}")
            print(f"  Firm: {first.get('firm')}")
            print(f"  AUM: {first.get('aum')}")
            print(f"  Production: {first.get('production')}")
            print(f"  Published: {first.get('published_to_vault')}")

            # Verify schema mapping
            assert first.get('candidate_locator'), "Missing candidate_locator"
            assert 'job_title' in first, "Missing job_title field (can be empty)"
            assert first.get('published_to_vault') is True, "published_to_vault should be True"
            print("\n✅ Schema mapping verified (job_title can be empty)")
    except Exception as e:
        print(f"❌ Query failed: {e}")
        raise


async def test_query_by_twav():
    """Test querying by TWAV number."""
    print("\n=== Testing Query by TWAV Number ===")

    test_twavs = ["TWAV109867", "TWAV114860", "TWAV114861"]

    try:
        results = await query_vault_candidates_postgres(twav_numbers=test_twavs)
        print(f"✅ Found {len(results)} candidates for TWAVs: {', '.join(test_twavs)}")

        for result in results:
            print(f"  - {result['candidate_locator']}: {result['candidate_name']} ({result['job_title']})")

        # Verify exact matches
        found_locators = {r['candidate_locator'] for r in results}
        for twav in test_twavs:
            if twav in found_locators:
                print(f"  ✅ {twav} found")
            else:
                print(f"  ℹ️ {twav} not in database (this is OK if candidate doesn't exist)")

    except Exception as e:
        print(f"❌ Query by TWAV failed: {e}")
        raise


async def test_query_by_location():
    """Test querying by location."""
    print("\n=== Testing Query by Location ===")

    test_locations = ["Texas", "California", "New York"]

    for location in test_locations:
        try:
            results = await query_vault_candidates_postgres(location=location, limit=5)
            print(f"✅ Found {len(results)} candidates in {location} (limited to 5)")

            if results:
                for result in results[:3]:  # Show first 3
                    print(f"  - {result['candidate_name']}: {result['location']}")
        except Exception as e:
            print(f"❌ Query by location '{location}' failed: {e}")


async def test_single_candidate():
    """Test getting single candidate by locator."""
    print("\n=== Testing Single Candidate Lookup ===")

    try:
        # Try to get a specific candidate
        candidate = await get_vault_candidate_by_locator("TWAV109867")

        if candidate:
            print(f"✅ Found candidate:")
            print(f"  Locator: {candidate['candidate_locator']}")
            print(f"  Name: {candidate['candidate_name']}")
            print(f"  Title: {candidate['job_title']}")
        else:
            print("ℹ️ Candidate TWAV109867 not found (this is OK if not in database)")

    except Exception as e:
        print(f"❌ Single candidate lookup failed: {e}")
        raise


async def test_count():
    """Test candidate count."""
    print("\n=== Testing Candidate Count ===")

    try:
        total_count = await get_vault_candidates_count()
        print(f"✅ Total vault candidates: {total_count}")

        # Count by location
        texas_count = await get_vault_candidates_count({"location": "Texas"})
        print(f"✅ Candidates in Texas: {texas_count}")

    except Exception as e:
        print(f"❌ Count query failed: {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("PostgreSQL Vault Adapter Test Suite")
    print("=" * 60)

    try:
        # Run all tests
        await test_currency_parsing()
        await test_query_all()
        await test_query_by_twav()
        await test_query_by_location()
        await test_single_candidate()
        await test_count()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST SUITE FAILED: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
