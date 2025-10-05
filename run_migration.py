#!/usr/bin/env python3
"""
Direct migration runner for 006_teams_bot_audit_table.sql
Bypasses the API endpoint to apply the migration directly to the database.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment
load_dotenv(".env.local")

async def run_migration():
    """Run the teams bot audit table migration"""

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return False

    print(f"📊 Connecting to database...")

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Read migration file
        migration_path = "migrations/006_teams_bot_audit_table.sql"
        print(f"📄 Reading {migration_path}...")

        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        # Split into statements
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
        print(f"📝 Found {len(statements)} SQL statements")

        # Execute in transaction
        print("🚀 Executing migration...")
        async with conn.transaction():
            for i, statement in enumerate(statements, 1):
                try:
                    await conn.execute(statement)
                    # Show first 60 chars of each statement
                    preview = statement.replace('\n', ' ')[:60]
                    print(f"  ✓ Statement {i}/{len(statements)}: {preview}...")
                except Exception as e:
                    print(f"  ❌ Failed at statement {i}:")
                    print(f"     {statement[:200]}...")
                    print(f"     Error: {e}")
                    raise

        print("✅ Migration completed successfully")

        # Verify table was created
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'teams_bot_audit'
            )
        """)

        if result:
            print("✅ Verified: teams_bot_audit table exists")

            # Check indexes
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'teams_bot_audit'
            """)
            print(f"✅ Created {len(indexes)} indexes:")
            for idx in indexes:
                print(f"   - {idx['indexname']}")

            # Check views
            views = await conn.fetch("""
                SELECT viewname FROM pg_views
                WHERE viewname LIKE 'teams_%'
            """)
            print(f"✅ Created {len(views)} views:")
            for view in views:
                print(f"   - {view['viewname']}")
        else:
            print("⚠️  Warning: teams_bot_audit table not found after migration")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_migration())
    exit(0 if success else 1)
