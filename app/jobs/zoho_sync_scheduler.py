#!/usr/bin/env python3
"""
Zoho Multi-Module Sync Scheduler (V2)

Supports continuous sync for multiple Zoho modules with:
- Environment-driven configuration
- Token bucket rate limiting (100 calls/min)
- Exponential backoff for 429 throttling
- Sequential polling by priority
- Integration with webhook-based continuous sync infrastructure

Modules: Leads, Deals, Contacts, Accounts
Runs as background task, checking zoho_sync_metadata for next_sync_at times.
"""

import os
import sys
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from collections import deque
import asyncpg
import httpx
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.zoho_field_mapper import ZohoFieldMapper
from app.models.zoho_sync_models import ZohoModule

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")
ZOHO_OAUTH_SERVICE_URL = os.getenv(
    "ZOHO_OAUTH_SERVICE_URL",
    "https://well-zoho-oauth-v2.azurewebsites.net"
)

# Modules to sync (comma-separated, e.g., "Leads,Deals,Contacts,Accounts")
ZOHO_MODULES_TO_SYNC = os.getenv("ZOHO_MODULES_TO_SYNC", "Leads,Deals,Contacts,Accounts")
SYNC_INTERVAL_MINUTES = int(os.getenv("ZOHO_SYNC_INTERVAL_MINUTES", "15"))

# Hard cutoff date - ONLY sync data from March 1, 2025 onwards
DATA_CUTOFF_DATE = datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

# Rate limiting (Zoho: 100 API calls per minute)
RATE_LIMIT_CALLS_PER_MINUTE = int(os.getenv("ZOHO_RATE_LIMIT", "100"))
RATE_LIMIT_WINDOW_SECONDS = 60

# Module priority (highest to lowest)
MODULE_PRIORITY = {
    "Leads": 1,
    "Deals": 2,
    "Contacts": 3,
    "Accounts": 4
}


# =============================================================================
# TOKEN BUCKET RATE LIMITER
# =============================================================================

class TokenBucket:
    """
    Token bucket algorithm for rate limiting Zoho API calls.

    Allows bursts up to bucket capacity while maintaining average rate.
    """

    def __init__(self, rate: int, capacity: int):
        """
        Initialize token bucket.

        Args:
            rate: Tokens added per second (e.g., 100/60 = 1.67 calls/sec)
            capacity: Maximum burst capacity
        """
        self.rate = rate / RATE_LIMIT_WINDOW_SECONDS  # Calls per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from bucket (wait if not available).

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True when tokens acquired
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Wait until enough tokens available
            while self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)

                # Refill after waiting
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

            # Consume tokens
            self.tokens -= tokens
            return True


# =============================================================================
# ZOHO MULTI-MODULE SYNC SCHEDULER
# =============================================================================

class ZohoMultiModuleSyncScheduler:
    """
    Manages polling-based sync for multiple Zoho modules.

    Complements webhook-based real-time sync by:
    - Reconciling missed webhooks
    - Backfilling gaps during downtime
    - Periodic health checks
    """

    def __init__(self):
        """Initialize scheduler with rate limiter and field mapper"""
        self._db_pool: Optional[asyncpg.Pool] = None
        self._field_mapper: Optional[ZohoFieldMapper] = None
        self._rate_limiter = TokenBucket(
            rate=RATE_LIMIT_CALLS_PER_MINUTE,
            capacity=RATE_LIMIT_CALLS_PER_MINUTE
        )

        # Parse modules from environment
        self.modules_to_sync = [
            m.strip() for m in ZOHO_MODULES_TO_SYNC.split(",") if m.strip()
        ]
        self.sync_interval_minutes = SYNC_INTERVAL_MINUTES

        # Load field mappings
        self._module_fields_cache: Dict[str, str] = {}  # Cache comma-separated field lists

        logger.info(
            f"Scheduler initialized: {self.modules_to_sync} modules, "
            f"{self.sync_interval_minutes}-minute interval, "
            f"{RATE_LIMIT_CALLS_PER_MINUTE} calls/min rate limit"
        )

    async def _get_field_mapper(self) -> ZohoFieldMapper:
        """Lazy load field mapper"""
        if self._field_mapper is None:
            self._field_mapper = ZohoFieldMapper()
        return self._field_mapper

    def _get_module_fields(self, module: str) -> str:
        """
        Get comma-separated field list for a Zoho module.

        Returns curated essential fields (max 50 due to Zoho API limit).
        Cached after first use for performance.

        NOTE: Zoho API has a 50-field limit per request. We select the most
        important fields for vault sync and store full raw payload for flexibility.

        Args:
            module: Module name (Leads, Deals, Contacts, Accounts)

        Returns:
            Comma-separated string of essential field API names
        """
        if module in self._module_fields_cache:
            return self._module_fields_cache[module]

        # Essential fields for Leads (45 fields - under 50 limit)
        # Prioritizes vault-related fields, professional info, and metadata
        if module == "Leads":
            essential_fields = [
                # Core identification
                'id', 'Full_Name', 'First_Name', 'Last_Name', 'Email', 'Phone', 'Mobile',
                # VAULT CRITICAL
                'Publish_to_Vault',
                # Professional
                'Designation', 'Employer', 'LinkedIn_Profile',
                # Location
                'Current_Location', 'City', 'State', 'Zip_Code', 'Is_Mobile', 'Remote',
                'In_Office', 'Open_to_Hybrid', 'Mobility_Details', 'Location_Detail',
                # Financial
                'Book_Size_AUM', 'Book_Size_Clients', 'Production_L12Mo', 'Desired_Comp',
                'Transferrable_Book_of_Business',
                # Availability
                'When_Available',
                # Credentials
                'Licenses_and_Exams', 'Professional_Designations', 'Years_of_Experience',
                'Bachelor_s_Degree', 'Specialty_Area_Expertise',
                # Metadata
                'Owner', 'Created_Time', 'Modified_Time', 'Created_By', 'Modified_By',
                'Last_Activity_Time', 'Date_Published_to_Vault',
                # Status
                'Lead_Status', 'Lead_Source', 'Candidate_Stage', 'Candidate_Type',
                # Notes
                'Candidate_Experience', 'Candidate_Locator'
            ]
        else:
            # For other modules, load top 50 from mappings
            mappings_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'zoho_field_mappings.json'
            )
            with open(mappings_path, 'r') as f:
                mappings = json.load(f)

            if module not in mappings['modules']:
                raise ValueError(f"Module {module} not found in field mappings")

            # Get first 50 fields
            module_data = mappings['modules'][module]
            essential_fields = list(module_data['fields'].keys())[:50]

        fields_str = ",".join(essential_fields)
        self._module_fields_cache[module] = fields_str

        logger.info(f"Using {len(essential_fields)} essential fields for {module}")

        return fields_str

    async def _create_db_pool(self):
        """Create PostgreSQL connection pool"""
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
        """Close PostgreSQL connection pool"""
        if self._db_pool:
            await self._db_pool.close()
            logger.info("Database connection pool closed")

    async def _get_oauth_token(self) -> str:
        """Get OAuth access token from proxy service"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ZOHO_OAUTH_SERVICE_URL}/oauth/token")
            response.raise_for_status()
            data = response.json()
            return data["access_token"]

    async def _fetch_zoho_module_records(
        self,
        module: str,
        modified_since: Optional[datetime] = None,
        max_retries: int = 3
    ) -> List[Dict]:
        """
        Fetch records from Zoho CRM API with rate limiting and retry logic.

        Args:
            module: Zoho module name (Leads, Deals, Contacts, Accounts)
            modified_since: Only fetch records modified after this timestamp
            max_retries: Maximum retry attempts for 429 throttling

        Returns:
            List of records from Zoho
        """
        # Get OAuth token
        access_token = await self._get_oauth_token()

        records = []
        page = 1
        base_wait = 1  # Initial wait time for exponential backoff

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                # Acquire rate limit token
                await self._rate_limiter.acquire()

                # Build request - call Zoho API directly
                url = f"https://www.zohoapis.com/crm/v8/{module}"

                # Get comma-separated field list for this module
                # NOTE: "fields" param is REQUIRED by Zoho API
                # Using "fields=All" returns minimal data (only id)
                # Must provide explicit comma-separated field names from mappings
                fields_list = self._get_module_fields(module)

                params = {
                    "per_page": 200,
                    "page": page,
                    "fields": fields_list
                }
                headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

                if modified_since:
                    params["modified_since"] = modified_since.isoformat()

                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = await client.get(url, params=params, headers=headers)

                        # Handle 429 throttling with exponential backoff
                        if response.status_code == 429:
                            wait_time = base_wait * (2 ** retry_count)
                            logger.warning(
                                f"Rate limited (429) for {module}, "
                                f"retrying in {wait_time}s (attempt {retry_count + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue

                        response.raise_for_status()
                        data = response.json()

                        if "data" not in data or not data["data"]:
                            # No more records
                            return records

                        records.extend(data["data"])
                        logger.debug(f"Fetched page {page} for {module}: {len(data['data'])} records")

                        # Check for more pages
                        if data.get("info", {}).get("more_records"):
                            page += 1
                            break  # Exit retry loop, continue to next page
                        else:
                            # No more pages
                            return records

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            # Already handled above
                            continue
                        elif e.response.status_code == 400:
                            # Check if it's pagination limit (2000 records max with page param)
                            try:
                                error_data = response.json()
                                if error_data.get("code") == "DISCRETE_PAGINATION_LIMIT_EXCEEDED":
                                    logger.warning(
                                        f"Reached Zoho pagination limit (2000 records) for {module}. "
                                        "Fetched maximum available records."
                                    )
                                    return records
                            except:
                                pass
                            logger.error(f"HTTP error fetching {module}: {e}")
                            raise
                        else:
                            logger.error(f"HTTP error fetching {module}: {e}")
                            raise
                    except Exception as e:
                        logger.error(f"Error fetching {module}: {e}")
                        raise

                # If we exhausted retries on 429
                if retry_count >= max_retries:
                    logger.error(f"Exceeded max retries for {module} due to rate limiting")
                    return records

        return records

    async def _upsert_module_records(
        self,
        module: str,
        records: List[Dict]
    ) -> Dict[str, int]:
        """
        UPSERT records into zoho_{module} table with field normalization.

        Args:
            module: Zoho module name
            records: List of Zoho records

        Returns:
            Stats dict: {created, updated, failed}
        """
        table_name = f"zoho_{module.lower()}"
        stats = {"created": 0, "updated": 0, "failed": 0}

        field_mapper = await self._get_field_mapper()

        async with self._db_pool.acquire() as conn:
            for record in records:
                try:
                    # Extract core fields
                    zoho_id = str(record.get("id", ""))
                    if not zoho_id:
                        logger.warning(f"Skipping record without ID: {record}")
                        stats["failed"] += 1
                        continue

                    # Store raw payload (field mapper coerce is too aggressive, strips all fields)
                    # TODO: Fix field mapper to preserve all fields
                    normalized_payload = record

                    # Extract owner
                    owner = record.get("Owner", {})
                    if isinstance(owner, dict):
                        owner_email = owner.get("email") or owner.get("Email")
                        owner_name = owner.get("name") or owner.get("Name")
                    else:
                        owner_email = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL", "steve.perry@emailthewell.com")
                        owner_name = None

                    # Parse timestamps
                    created_time_str = record.get("Created_Time")
                    modified_time_str = record.get("Modified_Time")

                    created_time = datetime.fromisoformat(
                        created_time_str.replace("Z", "+00:00")
                    ) if created_time_str else datetime.utcnow()

                    modified_time = datetime.fromisoformat(
                        modified_time_str.replace("Z", "+00:00")
                    ) if modified_time_str else datetime.utcnow()

                    # Check if this is a vault candidate (Leads only)
                    is_vault = False
                    if module == "Leads":
                        publish_to_vault = record.get("Publish_to_Vault")
                        is_vault = publish_to_vault is True or str(publish_to_vault).lower() == "true"

                    # UPSERT record (with vault candidate flag for Leads)
                    if module == "Leads":
                        result = await conn.execute(f"""
                            INSERT INTO {table_name}
                                (zoho_id, owner_email, owner_name, created_time, modified_time,
                                 last_synced_at, data_payload, sync_version, is_vault_candidate)
                            VALUES ($1, $2, $3, $4, $5, NOW(), $6, 1, $7)
                            ON CONFLICT (zoho_id) DO UPDATE SET
                                owner_email = EXCLUDED.owner_email,
                                owner_name = EXCLUDED.owner_name,
                                modified_time = EXCLUDED.modified_time,
                                data_payload = EXCLUDED.data_payload,
                                last_synced_at = NOW(),
                                sync_version = {table_name}.sync_version + 1,
                                is_vault_candidate = EXCLUDED.is_vault_candidate
                            WHERE {table_name}.modified_time <= EXCLUDED.modified_time
                        """,
                            zoho_id, owner_email, owner_name, created_time,
                            modified_time, json.dumps(normalized_payload), is_vault
                        )
                    else:
                        result = await conn.execute(f"""
                            INSERT INTO {table_name}
                                (zoho_id, owner_email, owner_name, created_time, modified_time,
                                 last_synced_at, data_payload, sync_version)
                            VALUES ($1, $2, $3, $4, $5, NOW(), $6, 1)
                            ON CONFLICT (zoho_id) DO UPDATE SET
                                owner_email = EXCLUDED.owner_email,
                                owner_name = EXCLUDED.owner_name,
                                modified_time = EXCLUDED.modified_time,
                                data_payload = EXCLUDED.data_payload,
                                last_synced_at = NOW(),
                                sync_version = {table_name}.sync_version + 1
                            WHERE {table_name}.modified_time <= EXCLUDED.modified_time
                        """,
                            zoho_id, owner_email, owner_name, created_time,
                            modified_time, json.dumps(normalized_payload)
                        )

                    # Check if INSERT or UPDATE occurred
                    if "INSERT" in result:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1

                except Exception as e:
                    logger.error(f"Error upserting {module} record {record.get('id')}: {e}")
                    stats["failed"] += 1

        return stats

    async def _sync_module(self, module: str) -> Dict[str, int]:
        """
        Sync a single module from Zoho to database.

        Args:
            module: Zoho module name

        Returns:
            Stats dict: {created, updated, failed}
        """
        logger.info(f"🔄 Starting sync for {module}")

        # Get last sync time from metadata
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT last_successful_sync_at
                FROM zoho_sync_metadata
                WHERE sync_type = $1
            """, module)

            last_sync = row["last_successful_sync_at"] if row else None

        # Enforce hard cutoff date (March 1, 2025) - never fetch data before this
        if last_sync is None or last_sync < DATA_CUTOFF_DATE:
            modified_since = DATA_CUTOFF_DATE
            logger.info(f"Applying data cutoff: only syncing records from {DATA_CUTOFF_DATE.date()} onwards")
        else:
            modified_since = last_sync
            logger.info(f"Incremental sync from {modified_since.isoformat()}")

        # Fetch records from Zoho
        records = await self._fetch_zoho_module_records(module, modified_since=modified_since)

        if not records:
            logger.info(f"No new records for {module}")
            return {"created": 0, "updated": 0, "failed": 0}

        logger.info(f"Fetched {len(records)} records for {module}")

        # UPSERT records
        stats = await self._upsert_module_records(module, records)

        logger.info(
            f"✅ {module} sync complete: "
            f"{stats['created']} created, {stats['updated']} updated, {stats['failed']} failed"
        )

        return stats

    async def _update_sync_metadata(
        self,
        module: str,
        status: str,
        stats: Dict[str, int],
        duration_seconds: int,
        error_message: Optional[str] = None
    ):
        """Update zoho_sync_metadata after sync"""
        async with self._db_pool.acquire() as conn:
            next_sync_at = datetime.utcnow() + timedelta(minutes=self.sync_interval_minutes)

            await conn.execute("""
                INSERT INTO zoho_sync_metadata
                    (sync_type, sync_status, last_successful_sync_at, next_sync_at,
                     records_synced, records_created, records_updated, records_failed,
                     sync_duration_seconds, error_message, updated_at)
                VALUES ($1, $2, NOW(), $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (sync_type) DO UPDATE SET
                    sync_status = EXCLUDED.sync_status,
                    last_successful_sync_at = EXCLUDED.last_successful_sync_at,
                    next_sync_at = EXCLUDED.next_sync_at,
                    records_synced = EXCLUDED.records_synced,
                    records_created = EXCLUDED.records_created,
                    records_updated = EXCLUDED.records_updated,
                    records_failed = EXCLUDED.records_failed,
                    sync_duration_seconds = EXCLUDED.sync_duration_seconds,
                    error_message = EXCLUDED.error_message,
                    updated_at = NOW()
            """,
                module, status, next_sync_at,
                stats["created"] + stats["updated"], stats["created"],
                stats["updated"], stats["failed"],
                duration_seconds, error_message
            )

    async def _run_module_sync(self, module: str):
        """Execute sync for a single module with error handling"""
        sync_started_at = datetime.utcnow()
        stats = {"created": 0, "updated": 0, "failed": 0}
        status = "failed"
        error_message = None

        try:
            # Update status to running
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoho_sync_metadata
                    SET sync_status = 'running',
                        last_sync_at = $1,
                        updated_at = $1
                    WHERE sync_type = $2
                """, sync_started_at, module)

            # Perform sync
            stats = await self._sync_module(module)

            # Determine final status
            status = "success" if stats["failed"] == 0 else "partial_failure"

        except Exception as e:
            error_message = str(e)
            logger.error(f"❌ {module} sync failed: {error_message}")
            status = "failed"

        finally:
            # Update metadata
            duration_seconds = int((datetime.utcnow() - sync_started_at).total_seconds())
            await self._update_sync_metadata(
                module, status, stats, duration_seconds, error_message
            )

    async def _get_modules_due_for_sync(self) -> List[str]:
        """
        Get modules that are due for sync, ordered by priority.

        Returns:
            List of module names in priority order
        """
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sync_type
                FROM zoho_sync_metadata
                WHERE next_sync_at <= NOW()
                  AND sync_status != 'running'
                  AND sync_type = ANY($1::text[])
            """, self.modules_to_sync)

            modules_due = [row["sync_type"] for row in rows]

        # Sort by priority
        modules_due.sort(key=lambda m: MODULE_PRIORITY.get(m, 999))

        return modules_due

    async def start_scheduler(self):
        """
        Main scheduler loop.

        Checks every 5 minutes for modules due for sync.
        Processes modules sequentially by priority.
        """
        logger.info("🚀 Zoho Multi-Module Sync Scheduler started")
        logger.info(f"Modules: {', '.join(self.modules_to_sync)}")
        logger.info(f"Sync interval: {self.sync_interval_minutes} minutes")

        # Create database pool
        await self._create_db_pool()

        try:
            while True:
                try:
                    # Get modules due for sync
                    modules_due = await self._get_modules_due_for_sync()

                    if modules_due:
                        logger.info(f"⏰ {len(modules_due)} module(s) due for sync: {', '.join(modules_due)}")

                        # Sync modules sequentially (respects rate limits)
                        for module in modules_due:
                            await self._run_module_sync(module)

                    else:
                        logger.debug("No modules due for sync")

                except Exception as e:
                    logger.error(f"Scheduler loop error: {e}", exc_info=True)

                # Wait 5 minutes before next check
                await asyncio.sleep(300)

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            await self._close_db_pool()


async def main():
    """Main entry point"""
    scheduler = ZohoMultiModuleSyncScheduler()
    await scheduler.start_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
