#!/usr/bin/env python3
"""
Simple migration runner for Teams integration tables.
Uses psycopg2 to avoid async requirements.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

def run_migration():
    """Run the Teams integration migration."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed")
        print("Trying alternative connection method...")
        try:
            # Try using asyncpg with asyncio
            import asyncio
            import asyncpg

            async def run_async():
                database_url = os.getenv('DATABASE_URL')
                if not database_url:
                    print('ERROR: DATABASE_URL not found')
                    return False

                print('Connecting to database...')
                conn = await asyncpg.connect(database_url)

                print('Reading migration file...')
                with open('migrations/005_teams_integration_tables.sql', 'r') as f:
                    migration_sql = f.read()

                print('Executing migration...')
                await conn.execute(migration_sql)
                print('✅ Migration executed successfully')

                # Verify tables
                tables = await conn.fetch("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public' AND tablename LIKE 'teams_%'
                    ORDER BY tablename
                """)

                print(f'\n✅ Created {len(tables)} Teams tables:')
                for table in tables:
                    print(f'   - {table["tablename"]}')

                await conn.close()
                return True

            success = asyncio.run(run_async())
            return 0 if success else 1

        except ImportError:
            print("ERROR: Neither psycopg2 nor asyncpg available")
            return 1

    # Use psycopg2
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('ERROR: DATABASE_URL not found')
        return 1

    print('Connecting to database...')
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    print('Reading migration file...')
    with open('migrations/005_teams_integration_tables.sql', 'r') as f:
        migration_sql = f.read()

    print('Executing migration...')
    cursor.execute(migration_sql)
    conn.commit()
    print('✅ Migration executed successfully')

    # Verify tables
    cursor.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tablename LIKE 'teams_%'
        ORDER BY tablename
    """)

    tables = cursor.fetchall()
    print(f'\n✅ Created {len(tables)} Teams tables:')
    for table in tables:
        print(f'   - {table[0]}')

    cursor.close()
    conn.close()
    return 0

if __name__ == '__main__':
    sys.exit(run_migration())
