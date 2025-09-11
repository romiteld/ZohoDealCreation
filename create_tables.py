#!/usr/bin/env python3
"""
Create all necessary database tables for the TalentWell digest system.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv('.env.local')

from app.integrations import PostgreSQLClient

async def create_tables():
    """Create all database tables."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return False
    
    print(f"📊 Connecting to database...")
    print(f"   Database URL: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")
    
    try:
        # Initialize PostgreSQL client
        postgres_client = PostgreSQLClient(database_url)
        
        # Initialize the connection pool
        await postgres_client.init_pool()
        print("✅ Connected to database")
        
        # Create all tables
        print("🔨 Creating tables...")
        await postgres_client.ensure_tables()
        print("✅ All tables created successfully")
        
        # Verify tables were created
        async with postgres_client.pool.acquire() as conn:
            # Check for main tables
            tables_to_check = [
                'deals',
                'deal_stage_history', 
                'meetings',
                'deal_notes',
                'email_processing_history',
                'batch_processing_status',
                'policy_employers',
                'policy_city_context'
            ]
            
            print("\n📋 Verifying tables:")
            for table in tables_to_check:
                result = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    )
                    """,
                    table
                )
                status = "✅" if result else "❌"
                print(f"   {status} {table}")
        
        # Close the pool
        await postgres_client.close()
        print("\n✅ Database setup complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(create_tables())
    sys.exit(0 if success else 1)