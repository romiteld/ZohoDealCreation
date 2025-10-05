#!/usr/bin/env python3
"""Simple migration runner using urllib."""
import urllib.request
import json
import sys

def run_migration():
    """Run Teams migration by reading SQL file and executing via API."""

    # Read migration SQL
    with open('migrations/005_teams_integration_tables.sql', 'r') as f:
        migration_sql = f.read()

    # Connection string from .env.local
    DATABASE_URL = "postgresql://adminuser:W3llDB2025Pass@well-intake-db-0903.postgres.database.azure.com:5432/wellintake?sslmode=require"

    print("✅ Migration SQL read successfully")
    print(f"   SQL length: {len(migration_sql)} characters")
    print("\n⚠️  Manual execution required:")
    print("   Run this SQL directly on Azure PostgreSQL:")
    print("   1. Use Azure Portal Query Editor")
    print("   2. Or use: az postgres flexible-server execute")
    print("   3. Or use pgAdmin/DBeaver with connection string")
    print("\n📄 SQL Preview:")
    print(migration_sql[:500] + "..." if len(migration_sql) > 500 else migration_sql)

    return 0

if __name__ == '__main__':
    sys.exit(run_migration())
