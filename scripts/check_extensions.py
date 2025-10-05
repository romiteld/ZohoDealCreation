#!/usr/bin/env python3
"""
Check available PostgreSQL extensions in Cosmos DB
"""
import os
import psycopg2
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def check_extensions():
    # Parse database URL
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")
    
    # Parse the URL
    result = urlparse(db_url)
    password = unquote(result.password) if result.password else None
    
    # Connect to database
    print(f"Connecting to database...")
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
            # Check installed extensions
            cursor.execute("SELECT extname, extversion FROM pg_extension;")
            extensions = cursor.fetchall()
            print("\nInstalled extensions:")
            for ext in extensions:
                print(f"  - {ext[0]} (version {ext[1]})")
            
            # Check available extensions
            cursor.execute("SELECT name FROM pg_available_extensions WHERE name LIKE '%vector%';")
            vector_exts = cursor.fetchall()
            if vector_exts:
                print("\nAvailable vector extensions:")
                for ext in vector_exts:
                    print(f"  - {ext[0]}")
            else:
                print("\nNo vector extensions available")
                
            # Check existing tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            print(f"\nExisting tables ({len(tables)}):")
            for table in tables[:10]:  # Show first 10
                print(f"  - {table[0]}")
            if len(tables) > 10:
                print(f"  ... and {len(tables)-10} more")
                
    finally:
        conn.close()

if __name__ == "__main__":
    check_extensions()