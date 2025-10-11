#!/usr/bin/env python3
"""
Fetch missing Title and Desired Compensation from Zoho CRM.
Updates vault_candidates table with data from Zoho.

Required fields:
- Title (job title categorization)
- Desired Comp (compensation expectations)

Usage:
    python3 fetch_missing_zoho_data.py
"""

import asyncio
import asyncpg
import httpx
import logging
from dotenv import load_dotenv
import os
import time

load_dotenv('.env.local')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ZOHO_OAUTH_SERVICE_URL = os.getenv('ZOHO_OAUTH_SERVICE_URL')
ZOHO_API_BASE = 'https://www.zohoapis.com/crm/v8'

async def fetch_candidate_from_zoho(candidate_locator: str) -> dict:
    """Fetch candidate details from Zoho by Candidate Locator."""

    url = f"{ZOHO_API_BASE}/Candidates/search"
    params = {
        'criteria': f"(Candidate_Locator:equals:{candidate_locator})"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get OAuth token through proxy
        token_response = await client.get(f"{ZOHO_OAUTH_SERVICE_URL}/oauth/token")
        if token_response.status_code != 200:
            logger.error(f"Failed to get OAuth token: {token_response.text}")
            return {}

        access_token = token_response.json().get('access_token')

        # Search for candidate
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logger.warning(f"Failed to fetch {candidate_locator}: {response.status_code}")
            return {}

        data = response.json()
        candidates = data.get('data', [])

        if not candidates:
            logger.warning(f"No Zoho record found for {candidate_locator}")
            return {}

        candidate = candidates[0]

        return {
            'title': candidate.get('Title', ''),
            'desired_comp': candidate.get('Desired_Comp', ''),
            'candidate_experience': candidate.get('Candidate_Experience', ''),
            'zoho_id': candidate.get('id', '')
        }

async def update_missing_fields():
    """Fetch missing Title and Desired Comp from Zoho and update database."""

    database_url = os.getenv('DATABASE_URL')
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)

    try:
        async with pool.acquire() as conn:
            # Get candidates missing Title or Compensation
            missing = await conn.fetch("""
                SELECT twav_number, candidate_name, title, compensation
                FROM vault_candidates
                WHERE (title IS NULL OR title = '')
                   OR (compensation IS NULL OR compensation = '')
                ORDER BY twav_number
            """)

            logger.info(f"Found {len(missing)} candidates with missing Title or Compensation")

            if not missing:
                logger.info("✅ All candidates have Title and Compensation")
                return

            # Fetch from Zoho and update
            updated_count = 0
            failed_count = 0

            for i, record in enumerate(missing, 1):
                twav = record['twav_number']
                logger.info(f"Processing {i}/{len(missing)}: {twav} - {record['candidate_name']}")

                try:
                    zoho_data = await fetch_candidate_from_zoho(twav)

                    if zoho_data:
                        # Update database
                        updates = []
                        params = [twav]
                        param_num = 2

                        if zoho_data.get('title') and (not record['title'] or record['title'] == ''):
                            updates.append(f"title = ${param_num}")
                            params.append(zoho_data['title'])
                            param_num += 1

                        if zoho_data.get('desired_comp') and (not record['compensation'] or record['compensation'] == ''):
                            updates.append(f"compensation = ${param_num}")
                            params.append(zoho_data['desired_comp'])
                            param_num += 1

                        if zoho_data.get('candidate_experience'):
                            updates.append(f"candidate_experience = ${param_num}")
                            params.append(zoho_data['candidate_experience'])
                            param_num += 1

                        if updates:
                            query = f"""
                                UPDATE vault_candidates
                                SET {', '.join(updates)}, updated_at = NOW()
                                WHERE twav_number = $1
                            """
                            await conn.execute(query, *params)
                            updated_count += 1
                            logger.info(f"  ✓ Updated {twav}")
                        else:
                            logger.warning(f"  ⚠️  No data to update for {twav}")
                    else:
                        failed_count += 1
                        logger.warning(f"  ❌ Failed to fetch Zoho data for {twav}")

                    # Rate limiting
                    if i % 10 == 0:
                        await asyncio.sleep(1)
                    else:
                        await asyncio.sleep(0.1)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ❌ Error processing {twav}: {e}")

            logger.info(f"\n✅ Updated {updated_count} candidates")
            logger.info(f"❌ Failed to update {failed_count} candidates")

            # Verify completeness
            async with pool.acquire() as conn:
                total = await conn.fetchval('SELECT COUNT(*) FROM vault_candidates')

                title_complete = await conn.fetchval(
                    "SELECT COUNT(*) FROM vault_candidates WHERE title IS NOT NULL AND title != ''"
                )
                comp_complete = await conn.fetchval(
                    "SELECT COUNT(*) FROM vault_candidates WHERE compensation IS NOT NULL AND compensation != ''"
                )

                logger.info(f"\n=== Final Verification ===")
                logger.info(f"Title: {title_complete}/{total} ({title_complete/total*100:.1f}%)")
                logger.info(f"Compensation: {comp_complete}/{total} ({comp_complete/total*100:.1f}%)")

    finally:
        await pool.close()

async def main():
    logger.info("Fetching missing Title and Desired Compensation from Zoho CRM...")
    await update_missing_fields()

if __name__ == '__main__':
    asyncio.run(main())
