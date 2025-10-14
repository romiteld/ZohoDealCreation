#!/usr/bin/env python3
"""
Zoho Sync Scheduler - Hourly background job for syncing deals from Zoho CRM to database.
Runs as a background task, checking zoho_sync_metadata for next_sync_at times.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection details
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'well-intake-db-0903.postgres.database.azure.com'),
    'user': os.getenv('DB_USER', 'adminuser'),
    'password': os.getenv('DB_PASSWORD', 'W3llDB2025Pass'),
    'database': os.getenv('DB_NAME', 'wellintake'),
    'sslmode': 'require'
}

# Zoho OAuth service URL
ZOHO_OAUTH_SERVICE_URL = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth-v2.azurewebsites.net')


class ZohoSyncScheduler:
    """Manages hourly sync operations with Zoho CRM"""

    def __init__(self):
        self.conn = None
        self.sync_interval_hours = 1

    def get_db_connection(self):
        """Get database connection"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def close_db_connection(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()

    async def fetch_zoho_deals(self, modified_since: Optional[datetime] = None) -> List[Dict]:
        """
        Fetch deals from Zoho CRM API.
        Uses the OAuth proxy service for authentication.
        """
        import aiohttp

        try:
            # Build Zoho API request
            base_url = f"{ZOHO_OAUTH_SERVICE_URL}/zoho/v8/Deals"
            params = {
                'fields': 'id,Deal_Name,Contact_Name,Account_Name,Stage,Owner,Created_Time,Modified_Time',
                'per_page': 200
            }

            if modified_since:
                # Only fetch deals modified since last sync
                params['modified_since'] = modified_since.isoformat()

            deals = []
            page = 1

            async with aiohttp.ClientSession() as session:
                while True:
                    params['page'] = page

                    async with session.get(base_url, params=params) as response:
                        if response.status != 200:
                            logger.error(f"Zoho API error: {response.status}")
                            break

                        data = await response.json()

                        if 'data' not in data or not data['data']:
                            break

                        deals.extend(data['data'])

                        # Check if more pages
                        if 'info' in data and data['info'].get('more_records'):
                            page += 1
                        else:
                            break

            logger.info(f"Fetched {len(deals)} deals from Zoho CRM")
            return deals

        except Exception as e:
            logger.error(f"Error fetching Zoho deals: {e}")
            return []

    def get_owner_email_mapping(self) -> Dict[str, str]:
        """Load zoho_user_id -> email mappings"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT zoho_user_id, email
            FROM zoho_user_mapping
            WHERE is_active = true
        """)

        mapping = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()

        return mapping

    async def sync_deals(self) -> Dict[str, int]:
        """
        Sync deals from Zoho CRM to database.
        Returns dict with counts: {created, updated, failed}
        """
        conn = self.get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        stats = {'created': 0, 'updated': 0, 'failed': 0}

        try:
            # Get last successful sync time
            cursor.execute("""
                SELECT last_successful_sync_at
                FROM zoho_sync_metadata
                WHERE sync_type = 'deals'
            """)
            row = cursor.fetchone()
            last_sync = row['last_successful_sync_at'] if row else None

            # Fetch deals from Zoho (only modified since last sync)
            deals = await self.fetch_zoho_deals(modified_since=last_sync)

            if not deals:
                logger.info("No deals to sync")
                return stats

            # Load owner mappings
            owner_mappings = self.get_owner_email_mapping()

            # Process each deal
            for deal in deals:
                try:
                    zoho_deal_id = str(deal.get('id', ''))
                    deal_name = deal.get('Deal_Name', '')
                    candidate_name = deal.get('Contact_Name', {}).get('name', '') if isinstance(deal.get('Contact_Name'), dict) else deal.get('Contact_Name', '')
                    company_name = deal.get('Account_Name', {}).get('name', '') if isinstance(deal.get('Account_Name'), dict) else deal.get('Account_Name', '')
                    stage = deal.get('Stage', 'Qualification')

                    # Get owner email
                    owner_id = str(deal.get('Owner', {}).get('id', '')) if isinstance(deal.get('Owner'), dict) else ''
                    owner_email = owner_mappings.get(owner_id)

                    if not owner_email:
                        logger.warning(f"Unknown owner ID {owner_id} for deal {zoho_deal_id}")
                        stats['failed'] += 1
                        continue

                    # Parse dates
                    created_at = datetime.fromisoformat(deal.get('Created_Time', '').replace('Z', '+00:00'))
                    modified_at = datetime.fromisoformat(deal.get('Modified_Time', '').replace('Z', '+00:00'))

                    # Check if deal exists
                    cursor.execute("SELECT id FROM deals WHERE zoho_deal_id = %s", (zoho_deal_id,))
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing deal
                        cursor.execute("""
                            UPDATE deals SET
                                deal_name = %s,
                                candidate_name = %s,
                                company_name = %s,
                                stage = %s,
                                owner_email = %s,
                                modified_at = %s
                            WHERE zoho_deal_id = %s
                        """, (deal_name, candidate_name, company_name, stage, owner_email, modified_at, zoho_deal_id))
                        stats['updated'] += 1
                    else:
                        # Insert new deal
                        deal_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO deals (
                                id, zoho_deal_id, deal_name, candidate_name, company_name,
                                stage, owner_email, created_at, modified_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (deal_id, zoho_deal_id, deal_name, candidate_name, company_name,
                              stage, owner_email, created_at, modified_at))
                        stats['created'] += 1

                except Exception as e:
                    logger.error(f"Error processing deal {deal.get('id')}: {e}")
                    stats['failed'] += 1
                    continue

            conn.commit()
            cursor.close()

            logger.info(f"Sync complete: {stats['created']} created, {stats['updated']} updated, {stats['failed']} failed")
            return stats

        except Exception as e:
            logger.error(f"Error syncing deals: {e}")
            conn.rollback()
            raise

    async def run_sync(self):
        """Execute a single sync operation"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        sync_started_at = datetime.now()
        sync_status = 'failed'
        error_message = None
        stats = {'created': 0, 'updated': 0, 'failed': 0}

        try:
            # Update metadata: set status to running
            cursor.execute("""
                UPDATE zoho_sync_metadata
                SET sync_status = 'running',
                    last_sync_at = %s,
                    updated_at = %s
                WHERE sync_type = 'deals'
            """, (sync_started_at, sync_started_at))
            conn.commit()

            # Perform sync
            stats = await self.sync_deals()

            # Calculate duration
            sync_completed_at = datetime.now()
            duration_seconds = int((sync_completed_at - sync_started_at).total_seconds())

            # Determine status
            sync_status = 'success' if stats['failed'] == 0 else 'partial_failure'

            # Update metadata: set status to success
            next_sync_at = sync_completed_at + timedelta(hours=self.sync_interval_hours)
            cursor.execute("""
                UPDATE zoho_sync_metadata
                SET sync_status = %s,
                    last_successful_sync_at = %s,
                    next_sync_at = %s,
                    records_synced = %s,
                    records_created = %s,
                    records_updated = %s,
                    records_failed = %s,
                    sync_duration_seconds = %s,
                    error_message = %s,
                    updated_at = %s
                WHERE sync_type = 'deals'
            """, (sync_status, sync_completed_at, next_sync_at,
                  stats['created'] + stats['updated'], stats['created'], stats['updated'], stats['failed'],
                  duration_seconds, error_message, sync_completed_at))

            # Insert sync history
            cursor.execute("""
                INSERT INTO zoho_sync_history (
                    sync_type, sync_started_at, sync_completed_at, sync_status,
                    records_synced, records_created, records_updated, records_failed,
                    sync_duration_seconds, error_message
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ('deals', sync_started_at, sync_completed_at, sync_status,
                  stats['created'] + stats['updated'], stats['created'], stats['updated'], stats['failed'],
                  duration_seconds, error_message))

            conn.commit()
            logger.info(f"✅ Sync complete: {sync_status}")

        except Exception as e:
            error_message = str(e)
            logger.error(f"❌ Sync failed: {error_message}")

            # Update metadata: set status to failed
            cursor.execute("""
                UPDATE zoho_sync_metadata
                SET sync_status = 'failed',
                    error_message = %s,
                    next_sync_at = %s,
                    updated_at = %s
                WHERE sync_type = 'deals'
            """, (error_message, datetime.now() + timedelta(hours=self.sync_interval_hours), datetime.now()))
            conn.commit()

        finally:
            cursor.close()

    async def start_scheduler(self):
        """
        Main scheduler loop - checks every 5 minutes if sync is due.
        """
        logger.info("🚀 Zoho Sync Scheduler started")

        while True:
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Check if sync is due
                cursor.execute("""
                    SELECT sync_type, next_sync_at, sync_status
                    FROM zoho_sync_metadata
                    WHERE sync_type = 'deals'
                      AND next_sync_at <= NOW()
                      AND sync_status != 'running'
                """)

                sync_due = cursor.fetchone()
                cursor.close()

                if sync_due:
                    logger.info(f"⏰ Sync due for {sync_due['sync_type']}")
                    await self.run_sync()
                else:
                    logger.debug("No sync due")

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Wait 5 minutes before next check
            await asyncio.sleep(300)


async def main():
    """Main entry point"""
    scheduler = ZohoSyncScheduler()

    try:
        await scheduler.start_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    finally:
        scheduler.close_db_connection()


if __name__ == "__main__":
    asyncio.run(main())
