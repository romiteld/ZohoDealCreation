#!/usr/bin/env python3
"""
Detect duplicate deals using fuzzy matching (90%+ similarity).
Generates CSV report and flags duplicates in database.
"""
import os
import sys
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from fuzzywuzzy import fuzz
from typing import List, Dict, Tuple

# Database connection details
DB_CONFIG = {
    'host': 'well-intake-db-0903.postgres.database.azure.com',
    'user': 'adminuser',
    'password': 'W3llDB2025Pass',
    'database': 'wellintake',
    'sslmode': 'require'
}

SIMILARITY_THRESHOLD = 90  # 90% fuzzy match threshold


def get_all_deals(cursor) -> List[Dict]:
    """Fetch all deals from database"""
    cursor.execute("""
        SELECT
            id,
            zoho_deal_id,
            deal_name,
            candidate_name,
            company_name,
            stage,
            owner_email,
            created_at
        FROM deals
        ORDER BY created_at
    """)

    return [dict(row) for row in cursor.fetchall()]


def calculate_similarity(deal1: Dict, deal2: Dict) -> int:
    """
    Calculate fuzzy similarity between two deals.
    Uses candidate_name and company_name for matching.
    """
    # Normalize strings
    candidate1 = (deal1.get('candidate_name') or '').lower().strip()
    candidate2 = (deal2.get('candidate_name') or '').lower().strip()
    company1 = (deal1.get('company_name') or '').lower().strip()
    company2 = (deal2.get('company_name') or '').lower().strip()

    # Calculate fuzzy match scores
    candidate_score = fuzz.ratio(candidate1, candidate2)
    company_score = fuzz.ratio(company1, company2)

    # Weighted average (candidate name is more important)
    overall_score = int((candidate_score * 0.7) + (company_score * 0.3))

    return overall_score


def find_duplicates(deals: List[Dict]) -> List[Tuple[Dict, Dict, int]]:
    """
    Find duplicate deals using fuzzy matching.
    Returns list of (deal1, deal2, similarity_score) tuples.
    """
    duplicates = []

    for i in range(len(deals)):
        for j in range(i + 1, len(deals)):
            deal1 = deals[i]
            deal2 = deals[j]

            similarity = calculate_similarity(deal1, deal2)

            if similarity >= SIMILARITY_THRESHOLD:
                duplicates.append((deal1, deal2, similarity))

    return duplicates


def main():
    print(f"[{datetime.now()}] Starting duplicate detection...")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD}%\n")

    conn = None
    try:
        # Connect to database
        print(f"Connecting to database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch all deals
        print("Fetching all deals from database...")
        deals = get_all_deals(cursor)
        print(f"✅ Loaded {len(deals)} deals\n")

        # Find duplicates
        print("Running fuzzy duplicate detection...")
        duplicates = find_duplicates(deals)
        print(f"✅ Found {len(duplicates)} potential duplicate pairs\n")

        if not duplicates:
            print("No duplicates found!")
            cursor.close()
            return 0

        # Generate CSV report
        report_filename = f"duplicates_report_{datetime.now().strftime('%Y_%m_%d')}.csv"
        report_path = os.path.join('/home/romiteld/Development/Desktop_Apps/outlook', report_filename)

        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Deal1_ID', 'Deal1_ZohoID', 'Deal1_Candidate', 'Deal1_Company', 'Deal1_Owner', 'Deal1_Created',
                'Deal2_ID', 'Deal2_ZohoID', 'Deal2_Candidate', 'Deal2_Company', 'Deal2_Owner', 'Deal2_Created',
                'Similarity_%', 'Recommended_Action'
            ])

            # Write duplicates
            for deal1, deal2, similarity in duplicates:
                # Older deal should be kept
                older_deal = deal1 if deal1['created_at'] < deal2['created_at'] else deal2
                newer_deal = deal2 if deal1['created_at'] < deal2['created_at'] else deal1

                action = f"Keep {older_deal['zoho_deal_id']}, review {newer_deal['zoho_deal_id']}"

                writer.writerow([
                    deal1['id'], deal1['zoho_deal_id'], deal1['candidate_name'], deal1['company_name'],
                    deal1['owner_email'], deal1['created_at'],
                    deal2['id'], deal2['zoho_deal_id'], deal2['candidate_name'], deal2['company_name'],
                    deal2['owner_email'], deal2['created_at'],
                    similarity, action
                ])

        print(f"✅ Report generated: {report_path}")

        # Display top 5 duplicates
        print(f"\n📋 Top 5 Duplicate Pairs:")
        print("-" * 120)

        sorted_dupes = sorted(duplicates, key=lambda x: x[2], reverse=True)[:5]

        for deal1, deal2, similarity in sorted_dupes:
            print(f"  {similarity}% match:")
            print(f"    Deal 1: {deal1['candidate_name']:30} @ {deal1['company_name']:30} (Zoho: {deal1['zoho_deal_id']})")
            print(f"    Deal 2: {deal2['candidate_name']:30} @ {deal2['company_name']:30} (Zoho: {deal2['zoho_deal_id']})")
            print()

        print("-" * 120)

        # Ask about Rob Beck specifically
        rob_beck_dupes = [
            (d1, d2, sim) for d1, d2, sim in duplicates
            if 'rob' in (d1.get('candidate_name') or '').lower() and 'beck' in (d1.get('candidate_name') or '').lower()
            or 'rob' in (d2.get('candidate_name') or '').lower() and 'beck' in (d2.get('candidate_name') or '').lower()
        ]

        if rob_beck_dupes:
            print(f"\n⚠️  Found {len(rob_beck_dupes)} Rob Beck duplicate(s)")
            for d1, d2, sim in rob_beck_dupes:
                print(f"  {sim}% match: {d1['zoho_deal_id']} vs {d2['zoho_deal_id']}")

        cursor.close()
        print(f"\n[{datetime.now()}] ✅ Duplicate detection complete!")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            conn.close()
            print("Database connection closed")


if __name__ == "__main__":
    sys.exit(main())
