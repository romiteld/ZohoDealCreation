#!/usr/bin/env python3
"""
Run database migration for Teams Bot Audit Table
"""
import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def run_migration():
    # Parse database URL
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")

    # Parse the URL
    result = urlparse(db_url)

    # Decode password (it contains URL-encoded characters)
    from urllib.parse import unquote
    password = unquote(result.password) if result.password else None

    # Connect to database
    print(f"Connecting to database at {result.hostname}...")
    conn = psycopg2.connect(
        database=result.path[1:].split('?')[0],  # Remove query params
        user=result.username,
        password=password,
        host=result.hostname,
        port=result.port,
        sslmode='require'
    )

    try:
        with conn.cursor() as cursor:
            # Read migration file
            with open('migrations/006_teams_bot_audit_table.sql', 'r') as f:
                migration_sql = f.read()

            # Execute migration
            print("Running migration...")
            cursor.execute(migration_sql)
            conn.commit()
            print("✅ Migration completed successfully!")

            # Verify table was created
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'teams_bot_audit'
                )
            """)
            table_exists = cursor.fetchone()[0]

            if table_exists:
                print("✅ teams_bot_audit table created")

                # Check indexes
                cursor.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'teams_bot_audit'
                    ORDER BY indexname
                """)
                indexes = cursor.fetchall()
                print(f"✅ Created {len(indexes)} indexes:")
                for idx in indexes:
                    print(f"  - {idx[0]}")

                # Check views
                cursor.execute("""
                    SELECT viewname
                    FROM pg_views
                    WHERE viewname LIKE 'teams_%audit%' OR viewname LIKE 'teams_activity_%'
                    ORDER BY viewname
                """)
                views = cursor.fetchall()
                print(f"✅ Created {len(views)} views:")
                for view in views:
                    print(f"  - {view[0]}")
            else:
                print("❌ Table creation failed")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        print("🔌 Database connection closed")

if __name__ == "__main__":
    run_migration()
