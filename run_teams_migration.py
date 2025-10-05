#!/usr/bin/env python3
"""
Run database migration for Teams integration tables
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    import psycopg2
    from urllib.parse import urlparse, unquote
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("💡 Install with: pip install psycopg2-binary python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv('.env.local')

def run_migration():
    # Parse database URL
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")

    # Parse the URL
    result = urlparse(db_url)
    password = unquote(result.password) if result.password else None

    # Connect to database
    print(f"🔌 Connecting to database at {result.hostname}...")
    conn = psycopg2.connect(
        database=result.path[1:].split('?')[0],
        user=result.username,
        password=password,
        host=result.hostname,
        port=result.port,
        sslmode='require'
    )

    try:
        with conn.cursor() as cursor:
            # Read migration file
            migration_file = 'migrations/005_teams_integration_tables.sql'
            print(f"📄 Reading migration: {migration_file}")

            with open(migration_file, 'r') as f:
                migration_sql = f.read()

            # Execute migration
            print("⚙️  Running migration...")
            cursor.execute(migration_sql)
            conn.commit()
            print("✅ Migration completed successfully!")

            # Verify tables were created
            cursor.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE tablename LIKE 'teams_%'
                ORDER BY tablename;
            """)

            tables = cursor.fetchall()
            print(f"\n📋 Created {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")

            # Verify views
            cursor.execute("""
                SELECT viewname
                FROM pg_views
                WHERE viewname LIKE 'teams_%'
                ORDER BY viewname;
            """)

            views = cursor.fetchall()
            if views:
                print(f"\n👁️  Created {len(views)} views:")
                for view in views:
                    print(f"  - {view[0]}")

            # Check initial config
            cursor.execute("SELECT * FROM teams_bot_config;")
            configs = cursor.fetchall()
            if configs:
                print(f"\n⚙️  Bot configuration:")
                for config in configs:
                    print(f"  - App ID: {config[1]}")
                    print(f"  - Tenant: {config[3]}")
                    print(f"  - Bot Name: {config[5]}")

        print("\n🎉 Teams integration database setup complete!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)