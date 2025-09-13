#!/usr/bin/env python3
"""Test database connection and pgvector extension"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

async def test_connection():
    """Test basic database connection and pgvector extension"""
    database_url = os.getenv("DATABASE_URL")
    print(f"Testing connection to: {database_url}")
    
    try:
        # Test 1: Basic connection
        print("\n1. Testing basic connection...")
        conn = await asyncpg.connect(database_url)
        version = await conn.fetchval("SELECT version()")
        print(f"✓ Connected to PostgreSQL: {version[:50]}...")
        await conn.close()
        
        # Test 2: Create a pool
        print("\n2. Testing connection pool...")
        pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=5,
            command_timeout=60
        )
        print(f"✓ Pool created with {pool.get_size()} connections")
        
        # Test 3: Check for pgvector extension
        print("\n3. Checking pgvector extension...")
        async with pool.acquire() as conn:
            # Check if extension exists
            ext_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
            )
            if ext_exists:
                print("✓ pgvector extension is installed")
            else:
                print("✗ pgvector extension is NOT installed")
                print("  Attempting to create extension...")
                try:
                    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    print("  ✓ pgvector extension created successfully")
                except Exception as e:
                    print(f"  ✗ Failed to create extension: {e}")
        
        # Test 4: Try to register vector type
        print("\n4. Testing pgvector registration...")
        try:
            from pgvector.asyncpg import register_vector
            async with pool.acquire() as conn:
                await register_vector(conn)
                print("✓ pgvector type registered successfully")
        except ImportError:
            print("✗ pgvector Python library not installed")
        except Exception as e:
            print(f"✗ Failed to register vector type: {e}")
            print(f"  Error type: {type(e).__name__}")
        
        # Test 5: Check learning tables
        print("\n5. Checking learning tables...")
        async with pool.acquire() as conn:
            tables = ['ai_corrections', 'learning_patterns', 'extraction_analytics', 'company_templates']
            for table in tables:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                    table
                )
                status = "✓" if exists else "✗"
                print(f"  {status} Table '{table}' {'exists' if exists else 'does not exist'}")
        
        await pool.close()
        print("\n✓ All tests completed")
        
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print(f"  Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())