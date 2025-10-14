#!/usr/bin/env python3
"""
Clear all cached vault alert bullets from Redis.
Must be run before generating NEW anonymized bullets.
"""
import asyncio
import sys
from dotenv import load_dotenv
import os

load_dotenv('.env.local')

sys.path.insert(0, '/home/romiteld/Development/Desktop_Apps/outlook/well_shared')
from well_shared.cache.redis_manager import RedisCacheManager

async def clear_bullet_cache():
    """Delete all bullet cache keys from Redis."""
    print("🔄 Connecting to Redis...")
    cache_mgr = RedisCacheManager(
        connection_string=os.getenv('AZURE_REDIS_CONNECTION_STRING')
    )
    await cache_mgr.connect()
    print("✅ Connected to Redis")
    print()

    # Delete all keys matching the bullet cache pattern
    pattern = "bullets_boss_format:*"
    print(f"🗑️  Deleting all keys matching pattern: {pattern}")

    try:
        # Get Redis client
        redis_client = cache_mgr.client

        if not redis_client:
            print("❌ Redis client not available")
            return

        # Scan for keys
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)

            if keys:
                # Delete keys in batch
                await redis_client.delete(*keys)
                deleted_count += len(keys)
                print(f"   Deleted {len(keys)} keys... (Total: {deleted_count})")

            if cursor == 0:
                break

        print()
        print(f"✅ Cache cleared successfully!")
        print(f"   Total keys deleted: {deleted_count}")

    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
        raise
    finally:
        try:
            await cache_mgr.disconnect()
        except:
            pass

if __name__ == '__main__':
    asyncio.run(clear_bullet_cache())
