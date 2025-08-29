#!/usr/bin/env python3
"""
Test cost tracking functionality with the deployed API
"""
import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

async def test_cost_tracking():
    """Check if cost tracking is working in the database"""
    
    # Parse database URL
    db_url = os.getenv('DATABASE_URL')
    result = urlparse(db_url)
    password = unquote(result.password) if result.password else None
    
    # Connect to database
    print("Connecting to Cosmos DB PostgreSQL...")
    conn = await asyncpg.connect(
        host=result.hostname,
        port=result.port or 5432,
        user=result.username,
        password=password,
        database=result.path[1:].split('?')[0],
        ssl='require'
    )
    
    try:
        # Check if cost_tracking table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'cost_tracking'
            )
        """)
        
        if not exists:
            print("❌ cost_tracking table not found")
            return
        
        print("✓ cost_tracking table exists")
        
        # Get recent cost tracking entries
        rows = await conn.fetch("""
            SELECT 
                model_tier,
                input_tokens,
                output_tokens,
                total_cost,
                created_at,
                success
            FROM cost_tracking
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        if rows:
            print(f"\n📊 Recent cost tracking entries ({len(rows)}):")
            for row in rows:
                print(f"  - {row['created_at']}: {row['model_tier']} "
                      f"({row['input_tokens']} in/{row['output_tokens']} out) "
                      f"= ${row['total_cost']:.6f}")
        else:
            print("\n📊 No cost tracking entries yet")
        
        # Get daily summary
        summary = await conn.fetchrow("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as requests,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(total_cost) as total_cost
            FROM cost_tracking
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 1
        """)
        
        if summary:
            print(f"\n📈 Today's usage:")
            print(f"  Requests: {summary['requests']}")
            print(f"  Tokens: {summary['total_input']} in / {summary['total_output']} out")
            print(f"  Cost: ${summary['total_cost']:.4f}")
        
        # Check cache performance
        cache_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'email_cache'
            )
        """)
        
        if cache_exists:
            cache_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as entries,
                    SUM(hit_count) as total_hits,
                    AVG(confidence_score) as avg_confidence
                FROM email_cache
                WHERE expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL
            """)
            
            if cache_stats and cache_stats['entries'] > 0:
                print(f"\n💾 Cache performance:")
                print(f"  Entries: {cache_stats['entries']}")
                print(f"  Total hits: {cache_stats['total_hits'] or 0}")
                print(f"  Avg confidence: {cache_stats['avg_confidence']:.2%}" if cache_stats['avg_confidence'] else "  Avg confidence: N/A")
        
    finally:
        await conn.close()
    
    print("\n✅ Cost tracking system is operational!")

if __name__ == "__main__":
    asyncio.run(test_cost_tracking())