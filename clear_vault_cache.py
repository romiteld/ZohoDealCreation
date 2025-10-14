#!/usr/bin/env python3
"""
Clear contaminated Redis cache before deploying anonymization.

This script removes all cached vault alert bullets from Redis.
The cache was populated before anonymization was implemented,
so it contains non-anonymized data with 24-hour TTL.

Run this BEFORE deploying anonymization fixes to ensure all
new alerts are generated with proper confidentiality controls.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
import redis.asyncio as redis

# Load environment
load_dotenv('.env.local')


async def clear_vault_cache():
    """Clear all vault alert bullets from Redis cache."""
    conn_string = os.getenv('AZURE_REDIS_CONNECTION_STRING')

    if not conn_string:
        print("❌ ERROR: AZURE_REDIS_CONNECTION_STRING not found in environment")
        print("   Make sure .env.local is configured with Redis connection string")
        sys.exit(1)

    print("=" * 80)
    print("VAULT CACHE CLEARING SCRIPT")
    print("=" * 80)
    print()
    print("🔄 Connecting to Azure Redis...")

    try:
        client = redis.from_url(conn_string, decode_responses=True)
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)

    try:
        # Find all cached bullets
        print("🔍 Searching for cached bullet entries...")
        keys = await client.keys('bullets_boss_format:*')

        if not keys:
            print("✅ No cached bullets found - cache is already clear")
            print()
            print("=" * 80)
            print("RESULT: Cache is clean, ready for anonymized generation")
            print("=" * 80)
            return

        print(f"📊 Found {len(keys)} cached bullet entries:")
        print(f"   Pattern: bullets_boss_format:TWAV*")
        print(f"   Count: {len(keys)} entries")
        print(f"   TTL: 24 hours (contaminated with non-anonymized data)")
        print()

        # Confirmation prompt
        print("⚠️  WARNING: These cached entries contain NON-ANONYMIZED data")
        print("   - Firm names (Merrill Lynch, Cresset, etc.)")
        print("   - Exact AUM figures ($1.68B, $300M, etc.)")
        print("   - Specific locations with ZIP codes")
        print("   - University names")
        print()

        response = input("Proceed with cache clearing? (yes/no): ").strip().lower()

        if response != 'yes':
            print("❌ Cache clearing cancelled by user")
            return

        # Delete all cached entries
        print()
        print("🗑️  Deleting cached entries...")
        await client.delete(*keys)

        # Verify deletion
        remaining = await client.keys('bullets_boss_format:*')

        if remaining:
            print(f"⚠️  Warning: {len(remaining)} entries still remain")
        else:
            print("✅ All cached entries successfully deleted")

        print()
        print("=" * 80)
        print("CACHE CLEARING COMPLETE")
        print("=" * 80)
        print()
        print("✅ Redis cache cleared successfully")
        print(f"   Deleted: {len(keys)} entries")
        print(f"   Remaining: {len(remaining)} entries")
        print()
        print("📌 NEXT STEPS:")
        print("   1. Deploy anonymization fixes to production")
        print("   2. Generate new alerts (will use PRIVACY_MODE=true)")
        print("   3. Run verify_anonymization.py to confirm zero violations")
        print("   4. Send test email to executives for approval")
        print()

    except Exception as e:
        print(f"❌ Error during cache clearing: {e}")
        sys.exit(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(clear_vault_cache())
