#!/usr/bin/env python3
"""
Create zoho_sync_metadata table for tracking hourly sync operations with Zoho CRM.
"""
import os
import sys
import psycopg2
from datetime import datetime

# Database connection details
DB_CONFIG = {
    'host': 'well-intake-db-0903.postgres.database.azure.com',
    'user': 'adminuser',
    'password': 'W3llDB2025Pass',
    'database': 'wellintake',
    'sslmode': 'require'
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS zoho_sync_metadata (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,  -- 'deals', 'contacts', 'accounts'
    last_sync_at TIMESTAMPTZ,
    last_successful_sync_at TIMESTAMPTZ,
    next_sync_at TIMESTAMPTZ,
    sync_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'running', 'success', 'failed'
    records_synced INTEGER DEFAULT 0,
    records_created INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    sync_duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sync_type)
);

CREATE INDEX IF NOT EXISTS idx_zoho_sync_metadata_sync_type
ON zoho_sync_metadata(sync_type);

CREATE INDEX IF NOT EXISTS idx_zoho_sync_metadata_last_sync
ON zoho_sync_metadata(last_sync_at DESC);

CREATE INDEX IF NOT EXISTS idx_zoho_sync_metadata_status
ON zoho_sync_metadata(sync_status);

-- Create sync history table for audit trail
CREATE TABLE IF NOT EXISTS zoho_sync_history (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,
    sync_started_at TIMESTAMPTZ NOT NULL,
    sync_completed_at TIMESTAMPTZ,
    sync_status VARCHAR(20) NOT NULL,
    records_synced INTEGER DEFAULT 0,
    records_created INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    sync_duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zoho_sync_history_sync_type
ON zoho_sync_history(sync_type);

CREATE INDEX IF NOT EXISTS idx_zoho_sync_history_started_at
ON zoho_sync_history(sync_started_at DESC);

-- Insert initial sync metadata for deals
INSERT INTO zoho_sync_metadata (sync_type, sync_status, next_sync_at)
VALUES ('deals', 'pending', NOW() + INTERVAL '1 hour')
ON CONFLICT (sync_type) DO NOTHING;
"""

def main():
    print(f"[{datetime.now()}] Creating zoho_sync_metadata tables...")

    conn = None
    try:
        # Connect to database
        print(f"Connecting to database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create tables
        print("Creating zoho_sync_metadata and zoho_sync_history tables...")
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("✅ Tables created successfully")

        # Verify tables
        cursor.execute("""
            SELECT COUNT(*) FROM zoho_sync_metadata;
        """)
        metadata_count = cursor.fetchone()[0]
        print(f"\n✅ Verification: {metadata_count} sync type(s) configured")

        # Display current metadata
        cursor.execute("""
            SELECT sync_type, sync_status, last_successful_sync_at, next_sync_at
            FROM zoho_sync_metadata
            ORDER BY sync_type
        """)
        rows = cursor.fetchall()

        if rows:
            print("\n📋 Current Sync Metadata:")
            print("-" * 100)
            for sync_type, status, last_sync, next_sync in rows:
                print(f"  Type: {sync_type:15} | Status: {status:10} | Last: {last_sync or 'Never':25} | Next: {next_sync}")
            print("-" * 100)

        cursor.close()
        print(f"\n[{datetime.now()}] ✅ zoho_sync_metadata tables creation complete!")
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
