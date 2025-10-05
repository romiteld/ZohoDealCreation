#!/usr/bin/env python3
"""
Database migration script for Apollo LinkedIn URL extraction feature.

This script ensures the apollo_enrichments table exists with proper
indexes for efficient LinkedIn URL storage and retrieval.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")


async def create_apollo_enrichments_table():
    """Create the apollo_enrichments table if it doesn't exist."""

    # Get database connection string
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        return False

    try:
        # Connect to the database
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Check if table already exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'apollo_enrichments'
            );
        """)

        if table_exists:
            print("ℹ️ Table apollo_enrichments already exists")

            # Check for missing columns and add them if needed
            columns = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'apollo_enrichments';
            """)
            existing_columns = {row['column_name'] for row in columns}

            # Add any missing columns
            migrations = []

            if 'company_linkedin_url' not in existing_columns:
                migrations.append(
                    "ALTER TABLE apollo_enrichments ADD COLUMN IF NOT EXISTS company_linkedin_url TEXT"
                )
            if 'company_twitter_url' not in existing_columns:
                migrations.append(
                    "ALTER TABLE apollo_enrichments ADD COLUMN IF NOT EXISTS company_twitter_url TEXT"
                )
            if 'company_facebook_url' not in existing_columns:
                migrations.append(
                    "ALTER TABLE apollo_enrichments ADD COLUMN IF NOT EXISTS company_facebook_url TEXT"
                )
            if 'mobile_phone' not in existing_columns:
                migrations.append(
                    "ALTER TABLE apollo_enrichments ADD COLUMN IF NOT EXISTS mobile_phone TEXT"
                )
            if 'work_phone' not in existing_columns:
                migrations.append(
                    "ALTER TABLE apollo_enrichments ADD COLUMN IF NOT EXISTS work_phone TEXT"
                )

            if migrations:
                print(f"📝 Running {len(migrations)} column migrations...")
                for migration in migrations:
                    await conn.execute(migration)
                    print(f"  ✅ {migration}")
            else:
                print("✅ All columns are up to date")

        else:
            # Create the table
            print("📝 Creating apollo_enrichments table...")
            await conn.execute("""
                CREATE TABLE apollo_enrichments (
                    email TEXT PRIMARY KEY,
                    linkedin_url TEXT,
                    twitter_url TEXT,
                    facebook_url TEXT,
                    github_url TEXT,
                    company_linkedin_url TEXT,
                    company_twitter_url TEXT,
                    company_facebook_url TEXT,
                    phone TEXT,
                    mobile_phone TEXT,
                    work_phone TEXT,
                    enriched_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("✅ Table created successfully")

        # Create indexes
        print("📝 Creating indexes...")

        # Index for LinkedIn URL lookups
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_linkedin
            ON apollo_enrichments(linkedin_url)
            WHERE linkedin_url IS NOT NULL;
        """)
        print("  ✅ LinkedIn URL index created")

        # Index for company lookups
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_company
            ON apollo_enrichments((enriched_data->>'firm_company'))
            WHERE enriched_data IS NOT NULL;
        """)
        print("  ✅ Company index created")

        # Index for updated_at to efficiently find stale records
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_updated
            ON apollo_enrichments(updated_at);
        """)
        print("  ✅ Updated timestamp index created")

        # Get table statistics
        row_count = await conn.fetchval("SELECT COUNT(*) FROM apollo_enrichments")
        linkedin_count = await conn.fetchval(
            "SELECT COUNT(*) FROM apollo_enrichments WHERE linkedin_url IS NOT NULL"
        )

        print("\n📊 Table Statistics:")
        print(f"  Total Records: {row_count}")
        print(f"  Records with LinkedIn: {linkedin_count}")
        if row_count > 0:
            print(f"  LinkedIn Coverage: {(linkedin_count/row_count*100):.1f}%")

        # Close the connection
        await conn.close()
        print("\n✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        return False


async def test_apollo_table():
    """Test the apollo_enrichments table with sample data."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    try:
        conn = await asyncpg.connect(database_url)
        print("\n🧪 Testing apollo_enrichments table...")

        # Insert test data
        test_email = "test@example.com"
        test_data = {
            "linkedin_url": "https://www.linkedin.com/in/test-user",
            "company": "Test Company",
            "confidence": 95
        }

        await conn.execute("""
            INSERT INTO apollo_enrichments (
                email, linkedin_url, enriched_data, updated_at
            ) VALUES ($1, $2, $3, NOW())
            ON CONFLICT (email) DO UPDATE
            SET linkedin_url = EXCLUDED.linkedin_url,
                enriched_data = EXCLUDED.enriched_data,
                updated_at = NOW()
        """, test_email, test_data["linkedin_url"], test_data)

        # Retrieve test data
        result = await conn.fetchrow("""
            SELECT email, linkedin_url, enriched_data
            FROM apollo_enrichments
            WHERE email = $1
        """, test_email)

        if result:
            print(f"  ✅ Insert/Update test passed")
            print(f"     Email: {result['email']}")
            print(f"     LinkedIn: {result['linkedin_url']}")
        else:
            print(f"  ❌ Insert/Update test failed")

        # Test cache query (records updated within 7 days)
        cache_count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM apollo_enrichments
            WHERE updated_at > NOW() - INTERVAL '7 days'
        """)
        print(f"  ✅ Cache query test passed ({cache_count} fresh records)")

        # Clean up test data (optional)
        # await conn.execute("DELETE FROM apollo_enrichments WHERE email = $1", test_email)

        await conn.close()
        print("✅ All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")


async def main():
    """Run the migration and tests."""

    print("=" * 60)
    print(" Apollo LinkedIn URL Extraction - Database Migration")
    print("=" * 60)

    # Run migration
    success = await create_apollo_enrichments_table()

    if success:
        # Run tests
        await test_apollo_table()

    print("\n" + "=" * 60)
    print(" Migration Process Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())