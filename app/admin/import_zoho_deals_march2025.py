#!/usr/bin/env python3
"""
Import Zoho deals from CSV export (March 1, 2025+) into deals table.
Uses zoho_user_mapping for owner email resolution.
"""
import os
import sys
import csv
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import List, Dict, Tuple

# Database connection details
DB_CONFIG = {
    'host': 'well-intake-db-0903.postgres.database.azure.com',
    'user': 'adminuser',
    'password': 'W3llDB2025Pass',
    'database': 'wellintake',
    'sslmode': 'require'
}

# CSV file path
CSV_PATH = '/home/romiteld/Development/Desktop_Apps/outlook/Deals_2025_10_07.csv'

# March 1, 2025 cutoff date
CUTOFF_DATE = datetime(2025, 3, 1)

INSERT_SQL = """
INSERT INTO deals (
    id,
    zoho_deal_id,
    deal_name,
    candidate_name,
    company_name,
    stage,
    owner_email,
    created_at,
    modified_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

UPDATE_SQL = """
UPDATE deals SET
    deal_name = %s,
    candidate_name = %s,
    company_name = %s,
    stage = %s,
    owner_email = %s,
    modified_at = %s
WHERE zoho_deal_id = %s
"""

def parse_zoho_datetime(dt_str: str) -> datetime:
    """Parse Zoho datetime format: '2024-07-08 14:56:28' or 'Oct 7, 2025 6:55 PM'"""
    try:
        # Try format: 2024-07-08 14:56:28
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Try format: Oct 7, 2025 6:55 PM
            return datetime.strptime(dt_str, '%b %d, %Y %I:%M %p')
        except ValueError:
            # Try format: Oct 7, 2025
            parts = dt_str.split()
            if len(parts) >= 3:
                return datetime.strptime(' '.join(parts[:3]), '%b %d, %Y')
            raise

def clean_zoho_id(record_id: str) -> str:
    """Remove 'zcrm_' prefix from Zoho Record Id"""
    return record_id.replace('zcrm_', '')

def load_owner_mappings(cursor) -> Dict[str, str]:
    """Load zoho_user_id -> email mappings"""
    cursor.execute("""
        SELECT zoho_user_id, email
        FROM zoho_user_mapping
        WHERE is_active = true
    """)
    return {row[0]: row[1] for row in cursor.fetchall()}

def process_csv(csv_path: str, owner_mappings: Dict[str, str]) -> Tuple[List[tuple], List[Dict]]:
    """
    Process CSV and return (import_rows, skipped_rows).
    Only includes deals from March 1, 2025+.
    """
    import_rows = []
    skipped_rows = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
            try:
                # Parse created date
                created_str = row.get('Created Time', '')
                if not created_str:
                    skipped_rows.append({'row': idx, 'reason': 'Missing Created Time', 'data': row})
                    continue

                created_at = parse_zoho_datetime(created_str)

                # Skip if before March 1, 2025
                if created_at < CUTOFF_DATE:
                    skipped_rows.append({'row': idx, 'reason': 'Before March 1, 2025', 'data': row})
                    continue

                # Clean Zoho Deal ID
                zoho_deal_id = clean_zoho_id(row.get('Record Id', ''))
                if not zoho_deal_id:
                    skipped_rows.append({'row': idx, 'reason': 'Missing Record Id', 'data': row})
                    continue

                # Get owner email (strip zcrm_ prefix)
                owner_zoho_id = clean_zoho_id(row.get('Deal Owner.id', ''))
                owner_email = owner_mappings.get(owner_zoho_id)
                if not owner_email:
                    skipped_rows.append({
                        'row': idx,
                        'reason': f'Unknown owner ID: {owner_zoho_id}',
                        'data': row
                    })
                    continue

                # Build import row
                import_rows.append((
                    zoho_deal_id,
                    row.get('Deal Name', '').strip(),
                    row.get('Contact Name', '').strip(),
                    row.get('Company Name', '').strip(),
                    row.get('Stage', 'Qualification').strip(),
                    owner_email,
                    created_at,
                    datetime.now()  # updated_at
                ))

            except Exception as e:
                skipped_rows.append({'row': idx, 'reason': f'Error: {e}', 'data': row})

    return import_rows, skipped_rows

def main():
    print(f"[{datetime.now()}] Starting Zoho deals import (March 1, 2025+)...")
    print(f"CSV Path: {CSV_PATH}")
    print(f"Cutoff Date: {CUTOFF_DATE.strftime('%Y-%m-%d')}\n")

    conn = None
    try:
        # Connect to database
        print(f"Connecting to database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Load owner mappings
        print("Loading owner mappings from zoho_user_mapping...")
        owner_mappings = load_owner_mappings(cursor)
        print(f"✅ Loaded {len(owner_mappings)} owner mappings\n")

        # Process CSV
        print("Processing CSV file...")
        import_rows, skipped_rows = process_csv(CSV_PATH, owner_mappings)

        print(f"\n📊 Processing Summary:")
        print(f"  Import rows: {len(import_rows)}")
        print(f"  Skipped rows: {len(skipped_rows)}\n")

        # Import deals
        if import_rows:
            print(f"Processing {len(import_rows)} deals...")
            inserted_count = 0
            updated_count = 0

            for row in import_rows:
                zoho_deal_id, deal_name, candidate_name, company_name, stage, owner_email, created_at, modified_at = row

                # Check if deal exists
                cursor.execute("SELECT id FROM deals WHERE zoho_deal_id = %s", (zoho_deal_id,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing deal
                    cursor.execute(UPDATE_SQL, (
                        deal_name, candidate_name, company_name, stage, owner_email, modified_at, zoho_deal_id
                    ))
                    updated_count += 1
                else:
                    # Insert new deal (generate UUID for id)
                    import uuid
                    deal_id = str(uuid.uuid4())
                    cursor.execute(INSERT_SQL, (
                        deal_id, zoho_deal_id, deal_name, candidate_name, company_name,
                        stage, owner_email, created_at, modified_at
                    ))
                    inserted_count += 1

            conn.commit()
            print(f"✅ Inserted: {inserted_count}, Updated: {updated_count}")
        else:
            print("⚠️  No rows to import")

        # Log skipped rows
        if skipped_rows:
            log_filename = f"import_results_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}.log"
            log_path = os.path.join(os.path.dirname(CSV_PATH), log_filename)

            with open(log_path, 'w', encoding='utf-8') as log_file:
                log_file.write(f"Zoho Deals Import - Skipped Rows\n")
                log_file.write(f"Timestamp: {datetime.now()}\n")
                log_file.write(f"Total Skipped: {len(skipped_rows)}\n\n")

                for skip in skipped_rows:
                    log_file.write(f"Row {skip['row']}: {skip['reason']}\n")
                    log_file.write(f"  Data: {skip['data']}\n\n")

            print(f"\n📄 Skipped rows logged to: {log_path}")

        # Verify import
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
        print(f"\n✅ Verification: {total_deals} total deals in database")

        # Show sample
        cursor.execute("""
            SELECT zoho_deal_id, candidate_name, company_name, owner_email, created_at
            FROM deals
            WHERE created_at >= %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (CUTOFF_DATE,))

        rows = cursor.fetchall()
        print(f"\n📋 Sample of Recent Imports:")
        print("-" * 100)
        for zoho_id, candidate, company, owner, created in rows:
            print(f"  {candidate[:25]:25} | {company[:30]:30} | {owner[:30]:30} | {created}")
        print("-" * 100)

        cursor.close()
        print(f"\n[{datetime.now()}] ✅ Import complete!")
        return 0

    except FileNotFoundError:
        print(f"\n❌ CSV file not found: {CSV_PATH}", file=sys.stderr)
        return 1
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