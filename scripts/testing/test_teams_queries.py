#!/usr/bin/env python3
"""
Test Teams bot natural language queries with role-based access control.
Tests the query engine directly without needing Teams authentication.

Usage:
    python3 test_teams_queries.py
"""

import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, 'app')
from api.teams.query_engine import process_natural_language_query
from well_shared.database.connection import get_connection_manager

load_dotenv('.env.local')


async def test_query(user_email: str, query: str, expected_role: str):
    """Test a single query and print results."""
    print(f"\n{'='*80}")
    print(f"👤 User: {user_email}")
    print(f"🔑 Expected Role: {expected_role}")
    print(f"💬 Query: {query}")
    print(f"{'='*80}")

    try:
        manager = await get_connection_manager()
        async with manager.get_connection() as db:
            result = await process_natural_language_query(query, user_email, db)

            print(f"\n✅ Query successful!")
            print(f"\nIntent: {result.get('intent', 'Unknown')}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            print(f"Table: {result.get('table', 'Unknown')}")
            print(f"Owner Filter: {result.get('owner_filter', 'None (unscoped)')}")

            # Show query results (handle both list and dict responses)
            data = result.get('data')
            if data:
                # Handle count/aggregate responses (dict with single value)
                if isinstance(data, dict):
                    print(f"\n📊 Result: {data}")
                # Handle list responses (records)
                elif isinstance(data, list):
                    print(f"\n📊 Results: {len(data)} records")
                    for i, record in enumerate(data[:3], 1):  # Show first 3
                        print(f"\n  {i}. {record}")
                    if len(data) > 3:
                        print(f"  ... and {len(data) - 3} more")
                else:
                    print(f"\n📊 Result: {data}")
            else:
                print(f"\n📭 No records found")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run test scenarios."""

    print("🧪 Testing Teams Bot Natural Language Queries")
    print("=" * 80)

    # Test 1: Executive user (unscoped access)
    await test_query(
        user_email="steve@emailthewell.com",
        query="show all deals from last 7 days",
        expected_role="executive"
    )

    # Test 2: Executive user with vault candidates
    await test_query(
        user_email="brandon@emailthewell.com",
        query="list vault candidates",
        expected_role="executive"
    )

    # Test 3: Regular recruiter (owner-filtered)
    await test_query(
        user_email="test.recruiter@emailthewell.com",
        query="show my deals",
        expected_role="recruiter"
    )

    # Test 4: Regular recruiter with vault (should work - shared resource)
    await test_query(
        user_email="test.recruiter@emailthewell.com",
        query="show vault candidates available now",
        expected_role="recruiter"
    )

    # Test 5: Executive with conversational query
    await test_query(
        user_email="daniel.romitelli@emailthewell.com",
        query="can you please show me all the recent meetings",
        expected_role="executive"
    )

    # Test 6: Case insensitive executive lookup
    await test_query(
        user_email="STEVE@EMAILTHEWELL.COM",
        query="count all deals",
        expected_role="executive"
    )

    print(f"\n{'='*80}")
    print("✅ All tests completed!")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(main())
