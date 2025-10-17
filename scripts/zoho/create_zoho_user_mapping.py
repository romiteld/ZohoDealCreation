#!/usr/bin/env python3
"""
Create zoho_user_mapping table and populate with owner email mappings.
Excludes Jay Robinson per user request.
"""
import os
import sys
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Database connection details
DB_CONFIG = {
    'host': 'well-intake-db-0903.postgres.database.azure.com',
    'user': 'adminuser',
    'password': 'W3llDB2025Pass',
    'database': 'wellintake',
    'sslmode': 'require'
}

# Owner mappings (EXCLUDING Jay Robinson)
OWNER_MAPPINGS = [
    ('6221978000000914023', 'Steve Perry', 'steve@emailthewell.com'),
    ('6221978000000460001', 'Brandon Murphy', 'brandon@emailthewell.com'),
    ('6221978000093425402', 'Daniel Romitelli', 'daniel.romitelli@emailthewell.com'),
    ('6221978000044268128', 'Queency Carinosa', 'queency@emailthewell.com'),
    ('6221978000083759001', 'Wesley Pennock', 'wesley@emailthewell.com')
]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS zoho_user_mapping (
    zoho_user_id TEXT PRIMARY KEY,
    zoho_display_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zoho_user_mapping_email
ON zoho_user_mapping(email);

CREATE INDEX IF NOT EXISTS idx_zoho_user_mapping_active
ON zoho_user_mapping(is_active) WHERE is_active = true;
"""

INSERT_SQL = """
INSERT INTO zoho_user_mapping (zoho_user_id, zoho_display_name, email)
VALUES %s
ON CONFLICT (zoho_user_id) DO UPDATE SET
    zoho_display_name = EXCLUDED.zoho_display_name,
    email = EXCLUDED.email;
"""

def main():
    print(f"[{datetime.now()}] Starting zoho_user_mapping table creation...")

    conn = None
    try:
        # Connect to database
        print(f"Connecting to database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create table
        print("Creating zoho_user_mapping table...")
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("✅ Table created successfully")

        # Insert owner mappings
        print(f"Inserting {len(OWNER_MAPPINGS)} owner mappings...")
        execute_values(cursor, INSERT_SQL, OWNER_MAPPINGS)
        conn.commit()
        print(f"✅ Inserted {len(OWNER_MAPPINGS)} owner mappings")

        # Verify results
        cursor.execute("SELECT COUNT(*) FROM zoho_user_mapping WHERE is_active = true")
        count = cursor.fetchone()[0]
        print(f"\n✅ Verification: {count} active user mappings in table")

        # Display mappings
        cursor.execute("""
            SELECT zoho_user_id, zoho_display_name, email
            FROM zoho_user_mapping
            ORDER BY zoho_display_name
        """)
        rows = cursor.fetchall()

        print("\n📋 Current Mappings:")
        print("-" * 80)
        for zoho_id, name, email in rows:
            print(f"  {name:20} | {email:35} | {zoho_id}")
        print("-" * 80)

        cursor.close()
        print(f"\n[{datetime.now()}] ✅ zoho_user_mapping table creation complete!")
        return 0

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    sys.exit(main())
