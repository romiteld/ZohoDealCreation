#!/usr/bin/env python3
"""
Clear all vault candidate bullet cache after anonymization improvements.

After fixing:
1. AUM formatting (range → rounded with +)
2. Job title extraction in headers
3. University name removal patterns

All cached bullets need to be regenerated.
"""
import asyncio
import os
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv('.env.local')

async def clear_all_vault_cache():
    """Clear all cached bullets for vault candidates."""
    redis_url = os.getenv('AZURE_REDIS_CONNECTION_STRING')
    redis_client = redis.from_url(redis_url, decode_responses=True)

    print("\n" + "="*70)
    print("🧹 CLEARING ALL VAULT CANDIDATE CACHE")
    print("="*70)
    print("\nReason: Major anonymization improvements")
    print("  1. AUM format: range → rounded with +")
    print("  2. Headers: generic → actual job titles")
    print("  3. Universities: enhanced removal patterns")
    print("\n" + "="*70 + "\n")

    # Pattern matches: bullets_boss_format:TWAV*
    pattern = "bullets_boss_format:*"

    print(f"🔍 Scanning for keys matching: {pattern}")

    # Use SCAN to find all matching keys (safer than KEYS)
    deleted_count = 0
    cursor = 0

    while True:
        cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)

        if keys:
            # Delete in batch
            deleted = await redis_client.delete(*keys)
            deleted_count += deleted
            print(f"   ✅ Deleted {deleted} cache entries (Total: {deleted_count})")

        if cursor == 0:
            break

    await redis_client.close()

    print(f"\n{'='*70}")
    print(f"✅ CACHE CLEARED")
    print(f"{'='*70}")
    print(f"   Total entries deleted: {deleted_count}")
    print(f"\n📋 NEXT STEPS:")
    print(f"   1. Run: python3 send_boss_approval_realtime.py")
    print(f"   2. First candidate will take ~15-20 seconds (GPT-5 generation)")
    print(f"   3. All 146 candidates: ~40-60 minutes total")
    print(f"   4. Results will show:")
    print(f"      - AUM values like '$500M+' (not '$400M-$500M')")
    print(f"      - Headers like 'Senior Advisor Candidate Alert'")
    print(f"      - No university names in output")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    asyncio.run(clear_all_vault_cache())
