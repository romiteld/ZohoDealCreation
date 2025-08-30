#!/usr/bin/env python3
"""
Run database migration for GPT-5 context support
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
            # Read migration file (use tables-only version)
            with open('migrations/002_gpt5_tables_only.sql', 'r') as f:
                migration_sql = f.read()
            
            # Execute migration
            print("Running migration...")
            cursor.execute(migration_sql)
            conn.commit()
            print("Migration completed successfully!")
            
            # Verify tables were created
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'email_contexts_400k', 
                    'email_context_chunks',
                    'cost_tracking',
                    'correction_patterns_v2'
                )
                ORDER BY table_name;
            """)
            
            tables = cursor.fetchall()
            print(f"\nCreated {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")
                
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()