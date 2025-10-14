#!/usr/bin/env python3
"""
Simple test for role-based access control database lookup.
"""

import asyncio
import sys
from dotenv import load_dotenv

sys.path.insert(0, 'app')
from well_shared.database.connection import get_connection_manager

load_dotenv('.env.local')


async def test_role_lookup():
    """Test role lookup directly."""
    print("🧪 Testing Role Lookup from Database\n")

    test_cases = [
        ("steve@emailthewell.com", "executive"),
        ("brandon@emailthewell.com", "executive"),
        ("daniel.romitelli@emailthewell.com", "executive"),
        ("STEVE@EMAILTHEWELL.COM", "executive"),  # Case insensitive
        ("random.user@emailthewell.com", "recruiter"),  # Default
    ]

    manager = await get_connection_manager()
    async with manager.get_connection() as db:
        for email, expected_role in test_cases:
            result = await db.fetchval(
                "SELECT get_user_role($1)", email
            )
            status = "✅" if result == expected_role else "❌"
            print(f"{status} {email:40s} → {result:10s} (expected: {expected_role})")

    print("\n✅ Role lookup tests completed!")


if __name__ == '__main__':
    asyncio.run(test_role_lookup())
