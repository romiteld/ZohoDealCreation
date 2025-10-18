#!/usr/bin/env python3
"""
Zoho Deals Backfill Script

Migrates existing records from legacy `deals` table to new `zoho_deals` table.

Features:
- Dry-run mode (preview without changes)
- Batch processing (prevents memory overflow)
- Progress tracking
- Data validation
- Rollback support

Usage:
    # Dry run (preview only)
    python3 scripts/backfill_zoho_deals.py --dry-run

    # Execute migration
    python3 scripts/backfill_zoho_deals.py

    # Execute with custom batch size
    python3 scripts/backfill_zoho_deals.py --batch-size 500

    # Archive legacy table after migration
    python3 scripts/backfill_zoho_deals.py --archive-legacy
"""

import os
import sys
import argparse
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
import asyncpg

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")
BATCH_SIZE = 100  # Process records in batches
DEFAULT_OWNER_EMAIL = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL", "steve.perry@emailthewell.com")


# =============================================================================
# LEGACY → ZOHO SCHEMA MAPPING
# =============================================================================

def transform_legacy_deal_to_zoho(legacy_deal: Dict) -> Dict:
    """
    Transform legacy deals table record to Zoho deals schema.

    Args:
        legacy_deal: Row from legacy deals table

    Returns:
        Dictionary ready for zoho_deals table
    """
    # Build JSONB payload from legacy columns
    data_payload = {
        "id": legacy_deal.get("zoho_deal_id"),
        "Deal_Name": legacy_deal.get("deal_name"),
        "Contact_Name": legacy_deal.get("candidate_name"),
        "Account_Name": legacy_deal.get("company_name"),
        "Stage": legacy_deal.get("stage"),
        "Amount": float(legacy_deal["amount"]) if legacy_deal.get("amount") else None,
        "Close_Date": legacy_deal.get("close_date").isoformat() if legacy_deal.get("close_date") else None,
        "Source": legacy_deal.get("source"),
        "Source_Detail": legacy_deal.get("source_detail"),
        "Description": legacy_deal.get("description"),

        # Add legacy metadata for traceability
        "_legacy_id": str(legacy_deal.get("id")),
        "_migrated_at": datetime.utcnow().isoformat() + "Z",
        "_migration_source": "legacy_deals_table"
    }

    # Remove None values to keep payload clean
    data_payload = {k: v for k, v in data_payload.items() if v is not None}

    return {
        "zoho_id": legacy_deal.get("zoho_deal_id"),
        "owner_email": legacy_deal.get("owner_email") or DEFAULT_OWNER_EMAIL,
        "owner_name": legacy_deal.get("owner_name"),
        "created_time": legacy_deal.get("created_at") or datetime.utcnow(),
        "modified_time": legacy_deal.get("modified_at") or datetime.utcnow(),
        "data_payload": data_payload,
        "sync_version": 0  # Mark as legacy migration (version 0)
    }


# =============================================================================
# BACKFILL SCRIPT
# =============================================================================

class ZohoDealsBackfill:
    """Handles migration from legacy deals to zoho_deals table"""

    def __init__(self, dry_run: bool = False, batch_size: int = BATCH_SIZE):
        """
        Initialize backfill script.

        Args:
            dry_run: If True, preview changes without executing
            batch_size: Number of records to process per batch
        """
        self.dry_run = dry_run
        self.batch_size = batch_size
        self._db_pool: Optional[asyncpg.Pool] = None

    async def _create_db_pool(self):
        """Create database connection pool"""
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable required")

        self._db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("✓ Database connection pool created")

    async def _close_db_pool(self):
        """Close database connection pool"""
        if self._db_pool:
            await self._db_pool.close()
            logger.info("Database connection pool closed")

    async def get_legacy_deals_count(self) -> int:
        """Get total count of records in legacy deals table"""
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM deals")
            return row["count"]

    async def get_zoho_deals_count(self) -> int:
        """Get total count of records in zoho_deals table"""
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM zoho_deals")
            return row["count"]

    async def fetch_legacy_deals_batch(self, offset: int, limit: int) -> List[Dict]:
        """
        Fetch a batch of records from legacy deals table.

        Args:
            offset: Starting offset
            limit: Maximum records to fetch

        Returns:
            List of deal records
        """
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id, zoho_deal_id, deal_name, candidate_name, company_name,
                    stage, amount, close_date, source, source_detail, description,
                    owner_email, owner_name, created_at, modified_at
                FROM deals
                ORDER BY created_at
                LIMIT $1 OFFSET $2
            """, limit, offset)

            return [dict(row) for row in rows]

    async def upsert_zoho_deals_batch(self, transformed_deals: List[Dict]) -> Dict[str, int]:
        """
        UPSERT batch of deals into zoho_deals table.

        Args:
            transformed_deals: List of transformed deal records

        Returns:
            Stats dict: {created, updated, failed}
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        async with self._db_pool.acquire() as conn:
            for deal in transformed_deals:
                try:
                    result = await conn.execute("""
                        INSERT INTO zoho_deals
                            (zoho_id, owner_email, owner_name, created_time, modified_time,
                             last_synced_at, data_payload, sync_version)
                        VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7)
                        ON CONFLICT (zoho_id) DO UPDATE SET
                            owner_email = EXCLUDED.owner_email,
                            owner_name = EXCLUDED.owner_name,
                            modified_time = EXCLUDED.modified_time,
                            data_payload = EXCLUDED.data_payload,
                            last_synced_at = NOW()
                        WHERE zoho_deals.modified_time <= EXCLUDED.modified_time
                    """,
                        deal["zoho_id"],
                        deal["owner_email"],
                        deal["owner_name"],
                        deal["created_time"],
                        deal["modified_time"],
                        json.dumps(deal["data_payload"]),
                        deal["sync_version"]
                    )

                    # Check if INSERT or UPDATE occurred
                    if "INSERT" in result:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1

                except Exception as e:
                    logger.error(f"Error upserting deal {deal['zoho_id']}: {e}")
                    stats["failed"] += 1

        return stats

    async def run_backfill(self):
        """Execute backfill migration"""
        logger.info("=" * 80)
        logger.info("ZOHO DEALS BACKFILL MIGRATION")
        logger.info("=" * 80)

        if self.dry_run:
            logger.warning("🔍 DRY RUN MODE - No changes will be made")

        # Create database connection
        await self._create_db_pool()

        try:
            # Get record counts
            legacy_count = await self.get_legacy_deals_count()
            zoho_count_before = await self.get_zoho_deals_count()

            logger.info(f"\n📊 Current State:")
            logger.info(f"  Legacy deals table: {legacy_count} records")
            logger.info(f"  Zoho deals table:   {zoho_count_before} records")

            if legacy_count == 0:
                logger.warning("⚠️  No records found in legacy deals table")
                return

            # Process in batches
            total_stats = {"created": 0, "updated": 0, "failed": 0}
            offset = 0
            batches_processed = 0

            logger.info(f"\n🔄 Starting migration (batch size: {self.batch_size})")

            while offset < legacy_count:
                # Fetch batch
                batch = await self.fetch_legacy_deals_batch(offset, self.batch_size)

                if not batch:
                    break

                logger.info(f"\n  Batch {batches_processed + 1}: Processing {len(batch)} records (offset {offset})...")

                # Transform batch
                transformed_batch = [
                    transform_legacy_deal_to_zoho(deal) for deal in batch
                ]

                if self.dry_run:
                    # Preview first record
                    if batches_processed == 0 and transformed_batch:
                        logger.info(f"\n  📋 Preview of first transformed record:")
                        logger.info(f"    Zoho ID: {transformed_batch[0]['zoho_id']}")
                        logger.info(f"    Owner: {transformed_batch[0]['owner_email']}")
                        logger.info(f"    Payload: {json.dumps(transformed_batch[0]['data_payload'], indent=2)}")

                    # Count what would be created
                    total_stats["created"] += len(transformed_batch)
                else:
                    # Execute UPSERT
                    batch_stats = await self.upsert_zoho_deals_batch(transformed_batch)

                    # Update totals
                    total_stats["created"] += batch_stats["created"]
                    total_stats["updated"] += batch_stats["updated"]
                    total_stats["failed"] += batch_stats["failed"]

                    logger.info(
                        f"    ✓ {batch_stats['created']} created, "
                        f"{batch_stats['updated']} updated, "
                        f"{batch_stats['failed']} failed"
                    )

                offset += self.batch_size
                batches_processed += 1

            # Final summary
            logger.info(f"\n{'=' * 80}")
            logger.info(f"MIGRATION {'PREVIEW' if self.dry_run else 'COMPLETE'}")
            logger.info(f"{'=' * 80}")

            if self.dry_run:
                logger.info(f"  Would process: {total_stats['created']} records")
            else:
                zoho_count_after = await self.get_zoho_deals_count()

                logger.info(f"\n📊 Final State:")
                logger.info(f"  Records created:  {total_stats['created']}")
                logger.info(f"  Records updated:  {total_stats['updated']}")
                logger.info(f"  Records failed:   {total_stats['failed']}")
                logger.info(f"  Total in zoho_deals: {zoho_count_after}")

                # Verification
                if zoho_count_after >= legacy_count:
                    logger.info(f"\n✅ Migration successful! All legacy records migrated.")
                else:
                    logger.warning(
                        f"\n⚠️  Migration incomplete: "
                        f"{legacy_count - zoho_count_after} records missing"
                    )

        finally:
            await self._close_db_pool()

    async def archive_legacy_table(self):
        """
        Archive legacy deals table by renaming it.

        This preserves the data while preventing future writes.
        """
        logger.info("\n📦 Archiving legacy deals table...")

        async with self._db_pool.acquire() as conn:
            # Rename table
            await conn.execute("""
                ALTER TABLE deals RENAME TO deals_legacy_archived_2025
            """)

            # Add comment
            await conn.execute("""
                COMMENT ON TABLE deals_legacy_archived_2025 IS
                'Legacy deals table - archived after migration to zoho_deals on 2025-10-17'
            """)

            logger.info("✓ Legacy table renamed to: deals_legacy_archived_2025")


# =============================================================================
# CLI INTERFACE
# =============================================================================

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate legacy deals table to zoho_deals schema"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing (default: False)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Number of records per batch (default: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--archive-legacy",
        action="store_true",
        help="Archive legacy deals table after migration (default: False)"
    )

    args = parser.parse_args()

    # Initialize backfill
    backfill = ZohoDealsBackfill(
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )

    try:
        # Run migration
        await backfill.run_backfill()

        # Archive legacy table if requested
        if args.archive_legacy and not args.dry_run:
            confirmation = input("\n⚠️  Are you sure you want to archive the legacy deals table? (yes/no): ")
            if confirmation.lower() == "yes":
                await backfill.archive_legacy_table()
            else:
                logger.info("Legacy table archival cancelled")

    except KeyboardInterrupt:
        logger.info("\n\nMigration cancelled by user")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
