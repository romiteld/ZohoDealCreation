#!/usr/bin/env python3
"""
Load vault candidates from CSV into PostgreSQL database.
Creates a temporary table for vault candidate generation.

This allows:
1. Single CSV parse (not on every generation)
2. Redis caching of GPT-5 bullet responses
3. Database queries for candidate filtering
4. Production-ready data flow pattern

Usage:
    python3 load_vault_candidates_to_db.py --csv Candidates_2025_10_09.csv
"""

import asyncio
import asyncpg
import csv
import json
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment
load_dotenv('.env.local')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_vault_candidates_table(pool):
    """Create vault_candidates table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vault_candidates (
                twav_number VARCHAR(50) PRIMARY KEY,
                candidate_name TEXT,
                title TEXT,
                city TEXT,
                state TEXT,
                current_location TEXT,
                location_detail TEXT,
                firm TEXT,
                years_experience TEXT,
                aum TEXT,
                production TEXT,
                book_size_clients TEXT,
                transferable_book TEXT,
                licenses TEXT,
                professional_designations TEXT,
                headline TEXT,
                interviewer_notes TEXT,
                top_performance TEXT,
                candidate_experience TEXT,
                background_notes TEXT,
                other_screening_notes TEXT,
                availability TEXT,
                compensation TEXT,
                linkedin_profile TEXT,
                zoom_meeting_id TEXT,
                zoom_meeting_url TEXT,
                raw_data JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_vault_candidates_twav ON vault_candidates(twav_number);
            CREATE INDEX IF NOT EXISTS idx_vault_candidates_title ON vault_candidates(title);
            CREATE INDEX IF NOT EXISTS idx_vault_candidates_location ON vault_candidates(current_location);
        """)
        logger.info("✅ vault_candidates table created/verified")

async def load_csv_to_database(csv_path: str, pool):
    """Load CSV data into vault_candidates table."""

    csv.field_size_limit(1000000)

    candidates_loaded = 0

    async with pool.acquire() as conn:
        # Clear existing data
        await conn.execute("TRUNCATE TABLE vault_candidates")
        logger.info("Cleared existing vault_candidates data")

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                twav = row.get('Candidate Locator', '').strip()
                if not twav:
                    continue

                # Extract Zoom meeting ID from URL (Cover Letter Recording URL has the actual Zoom links)
                zoom_url = row.get('Cover Letter  Recording URL', '').strip()  # Note: double space in column name
                zoom_meeting_id = ''
                if zoom_url and 'share/' in zoom_url:
                    # Extract meeting ID from URL like: /rec/share/MEETING_ID.HASH?startTime=...
                    parts = zoom_url.split('share/')[-1].split('?')[0]
                    # The full string including hash is the meeting ID
                    zoom_meeting_id = parts

                # Parse city/state from Current Location
                city = row.get('City', '').strip()
                state = row.get('State', '').strip()
                current_location = row.get('Current Location', '').strip()

                if (not city or not state) and current_location:
                    if ',' in current_location:
                        parts = current_location.split(',')
                        if len(parts) == 2:
                            city = parts[0].strip()
                            state = parts[1].strip()
                    elif 'Greater' not in current_location and not city:
                        city = current_location

                # Insert into database
                await conn.execute("""
                    INSERT INTO vault_candidates (
                        twav_number,
                        candidate_name,
                        title,
                        city,
                        state,
                        current_location,
                        location_detail,
                        firm,
                        years_experience,
                        aum,
                        production,
                        book_size_clients,
                        transferable_book,
                        licenses,
                        professional_designations,
                        headline,
                        interviewer_notes,
                        top_performance,
                        candidate_experience,
                        background_notes,
                        other_screening_notes,
                        availability,
                        compensation,
                        linkedin_profile,
                        zoom_meeting_id,
                        zoom_meeting_url,
                        raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27)
                    ON CONFLICT (twav_number) DO UPDATE SET
                        candidate_name = EXCLUDED.candidate_name,
                        title = EXCLUDED.title,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        current_location = EXCLUDED.current_location,
                        location_detail = EXCLUDED.location_detail,
                        firm = EXCLUDED.firm,
                        years_experience = EXCLUDED.years_experience,
                        aum = EXCLUDED.aum,
                        production = EXCLUDED.production,
                        book_size_clients = EXCLUDED.book_size_clients,
                        transferable_book = EXCLUDED.transferable_book,
                        licenses = EXCLUDED.licenses,
                        professional_designations = EXCLUDED.professional_designations,
                        headline = EXCLUDED.headline,
                        interviewer_notes = EXCLUDED.interviewer_notes,
                        top_performance = EXCLUDED.top_performance,
                        candidate_experience = EXCLUDED.candidate_experience,
                        background_notes = EXCLUDED.background_notes,
                        other_screening_notes = EXCLUDED.other_screening_notes,
                        availability = EXCLUDED.availability,
                        compensation = EXCLUDED.compensation,
                        linkedin_profile = EXCLUDED.linkedin_profile,
                        zoom_meeting_id = EXCLUDED.zoom_meeting_id,
                        zoom_meeting_url = EXCLUDED.zoom_meeting_url,
                        raw_data = EXCLUDED.raw_data,
                        updated_at = NOW()
                """,
                    twav,
                    row.get('Candidate Name', '').strip(),
                    row.get('Title', '').strip(),
                    city,
                    state,
                    current_location,
                    row.get('Location Detail', '').strip(),  # Location Detail
                    row.get('Employer', '').strip(),  # Firm
                    row.get('Years of Experience', '').strip(),
                    row.get('Book Size (AUM)', '').strip(),  # AUM
                    row.get('Production L12Mo', '').strip(),  # Production
                    row.get('Book Size (Clients)', '').strip(),  # Book Size (Clients)
                    row.get('Transferable Book of Business', '').strip(),  # Transferable Book
                    row.get('Licenses Exams - Confirmation Notes', '').strip() or row.get('Licenses and Exams', '').strip(),  # Licenses
                    row.get('Professional Designations', '').strip(),  # Professional Designations
                    row.get('Headline', '').strip(),
                    row.get('Interviewer Notes', '').strip(),
                    row.get('Top Performance Result', '').strip(),  # Top Performance
                    row.get('Candidate Experience', '').strip(),
                    row.get('Background Notes', '').strip(),  # Background Notes
                    row.get('Other Screening Notes', '').strip(),  # Other Screening Notes
                    row.get('When Available?', '').strip(),  # Availability
                    row.get('Desired Comp', '').strip(),  # Compensation
                    row.get('LinkedIn Profile', '').strip(),  # LinkedIn Profile
                    zoom_meeting_id,
                    zoom_url,
                    json.dumps(dict(row))  # Store full row as JSONB
                )

                candidates_loaded += 1

                if candidates_loaded % 10 == 0:
                    logger.info(f"Loaded {candidates_loaded} candidates...")

    logger.info(f"✅ Loaded {candidates_loaded} vault candidates into database")
    return candidates_loaded

async def main():
    parser = argparse.ArgumentParser(description='Load vault candidates CSV into PostgreSQL')
    parser.add_argument('--csv', default='Candidates_2025_10_09.csv', help='Path to CSV file')
    args = parser.parse_args()

    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not found in environment")
        return

    logger.info(f"Connecting to PostgreSQL...")
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)

    try:
        # Create table
        await create_vault_candidates_table(pool)

        # Load CSV data
        count = await load_csv_to_database(args.csv, pool)

        # Verify data
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM vault_candidates")
            logger.info(f"\n✅ Database now contains {total} vault candidates")

            # Sample data
            sample = await conn.fetchrow("""
                SELECT twav_number, candidate_name, title, current_location
                FROM vault_candidates
                LIMIT 1
            """)
            if sample:
                logger.info(f"\nSample record:")
                logger.info(f"  TWAV: {sample['twav_number']}")
                logger.info(f"  Name: {sample['candidate_name']}")
                logger.info(f"  Title: {sample['title']}")
                logger.info(f"  Location: {sample['current_location']}")

    finally:
        await pool.close()

if __name__ == '__main__':
    asyncio.run(main())
