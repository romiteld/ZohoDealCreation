"""
Zoho Sync Worker - Service Bus Queue Processor

Processes webhook events from Azure Service Bus queue:
1. Fetches full payload from zoho_webhook_log
2. Normalizes data types (phone, picklist, owner lookups)
3. Performs UPSERT with conflict detection
4. Updates webhook log status
5. Deletes Redis dedupe key on success

Handles at-least-once delivery semantics from Service Bus.
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import asyncpg

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.zoho_sync_models import (
    ZohoSyncMessage,
    ZohoModule,
    WebhookEventType,
    ProcessingStatus,
    ZohoSyncConflict,
    ConflictType,
    ResolutionStrategy
)
from well_shared.cache.redis_manager import RedisCacheManager
from teams_bot.app.utils.service_bus import normalize_message_body

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING") or os.getenv(
    "AZURE_SERVICE_BUS_CONNECTION_STRING"
)
SERVICE_BUS_QUEUE_NAME = os.getenv("SERVICE_BUS_ZOHO_SYNC_QUEUE", "zoho-sync-events")
REDIS_DEDUPE_TTL_SECONDS = int(os.getenv("REDIS_DEDUPE_TTL_SECONDS", "600"))


class ZohoSyncWorker:
    """Service Bus worker for processing Zoho webhook events"""

    def __init__(self):
        """Initialize worker with Service Bus and database connections"""
        if not SERVICE_BUS_CONNECTION_STRING:
            raise ValueError("SERVICE_BUS_CONNECTION_STRING required")

        if not DATABASE_URL:
            raise ValueError("DATABASE_URL required")

        self.connection_string = SERVICE_BUS_CONNECTION_STRING
        self.queue_name = SERVICE_BUS_QUEUE_NAME
        self.database_url = DATABASE_URL

        self._client: Optional[ServiceBusClient] = None
        self._receiver = None
        self._db_pool: Optional[asyncpg.Pool] = None
        self._redis_manager: Optional[RedisCacheManager] = None

        # Load field mapper on startup (lazy import to avoid circular dependency)
        self._field_mapper = None

    async def _get_field_mapper(self):
        """Lazy load field mapper"""
        if self._field_mapper is None:
            from app.services.zoho_field_mapper import ZohoFieldMapper
            self._field_mapper = ZohoFieldMapper()
        return self._field_mapper

    async def start(self):
        """Start processing messages from Service Bus queue"""
        logger.info(f"🚀 Starting Zoho Sync Worker on queue: {self.queue_name}")

        try:
            # Initialize connections
            self._client = ServiceBusClient.from_connection_string(
                self.connection_string,
                logging_enable=True
            )
            self._receiver = self._client.get_queue_receiver(
                queue_name=self.queue_name,
                max_wait_time=30
            )

            # Create database connection pool
            self._db_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )

            # Initialize Redis manager
            self._redis_manager = RedisCacheManager()

            logger.info("✓ Worker initialized successfully")

            # Main processing loop
            async with self._receiver:
                while True:
                    messages = await self._receiver.receive_messages(
                        max_message_count=10,
                        max_wait_time=5
                    )

                    for msg in messages:
                        try:
                            await self._process_message(msg)
                            await self._receiver.complete_message(msg)
                            logger.info(f"✓ Message completed: {msg.message_id}")

                        except Exception as e:
                            logger.error(f"❌ Error processing message: {e}", exc_info=True)
                            # Abandon message (Service Bus will retry)
                            await self._receiver.abandon_message(msg)
                            logger.warning(f"⚠️  Message abandoned for retry: {msg.message_id}")

                    # Brief pause to prevent tight loop
                    await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            raise
        finally:
            await self.close()

    async def _process_message(self, message):
        """
        Process a single Service Bus message.

        Args:
            message: ServiceBusReceivedMessage
        """
        # Normalize message body (handle different SDK versions)
        body_bytes = normalize_message_body(message)
        body_json = body_bytes.decode("utf-8")
        message_data = json.loads(body_json)

        # Parse into Pydantic model for validation
        try:
            sync_message = ZohoSyncMessage(**message_data)
        except Exception as e:
            logger.error(f"Invalid message schema: {e}, body: {message_data}")
            raise  # Will send to DLQ

        logger.info(
            f"Processing: {sync_message.module.value}:{sync_message.zoho_id} "
            f"(log_id: {sync_message.log_id}, retry: {sync_message.retry_count})"
        )

        # Fetch full payload from webhook log
        webhook_log = await self._fetch_webhook_log(sync_message.log_id)

        if not webhook_log:
            logger.error(f"Webhook log not found: {sync_message.log_id}")
            raise ValueError(f"Missing webhook log: {sync_message.log_id}")

        # Update status to 'processing'
        await self._update_webhook_log_status(
            sync_message.log_id,
            ProcessingStatus.PROCESSING
        )

        # Normalize payload using field mapper
        field_mapper = await self._get_field_mapper()
        normalized_data = await field_mapper.coerce_payload(
            sync_message.module.value,
            webhook_log["payload_raw"]
        )

        # Perform UPSERT with conflict detection
        try:
            await self._upsert_record(
                module=sync_message.module.value,
                zoho_id=sync_message.zoho_id,
                modified_time=sync_message.modified_time,
                payload=normalized_data,
                log_id=sync_message.log_id
            )

            # Mark as success
            await self._update_webhook_log_status(
                sync_message.log_id,
                ProcessingStatus.SUCCESS,
                processed_at=datetime.utcnow()
            )

            # Delete Redis dedupe key
            await self._delete_dedupe_key(
                sync_message.module.value,
                sync_message.event_type.value,
                sync_message.zoho_id,
                sync_message.payload_sha
            )

            logger.info(f"✅ Successfully processed {sync_message.module.value}:{sync_message.zoho_id}")

        except ConflictDetectedError as e:
            # Conflict detected - logged to zoho_sync_conflicts
            await self._update_webhook_log_status(
                sync_message.log_id,
                ProcessingStatus.CONFLICT,
                error_message=str(e)
            )
            logger.warning(f"⚠️  Conflict detected: {e}")

        except Exception as e:
            # Processing failed - mark as failed
            await self._update_webhook_log_status(
                sync_message.log_id,
                ProcessingStatus.FAILED,
                error_message=str(e)
            )
            logger.error(f"❌ Processing failed: {e}", exc_info=True)
            raise  # Will retry via Service Bus

    async def _fetch_webhook_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Fetch webhook log entry by ID"""
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, module, event_type, zoho_id, payload_raw, payload_sha256,
                       received_at, processing_status, retry_count
                FROM zoho_webhook_log
                WHERE id = $1
            """, log_id)

            if row:
                return dict(row)
            return None

    async def _update_webhook_log_status(
        self,
        log_id: str,
        status: ProcessingStatus,
        error_message: Optional[str] = None,
        processed_at: Optional[datetime] = None
    ):
        """Update webhook log processing status"""
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE zoho_webhook_log
                SET processing_status = $1,
                    error_message = $2,
                    processed_at = $3
                WHERE id = $4
            """, status.value, error_message, processed_at, log_id)

    async def _upsert_record(
        self,
        module: str,
        zoho_id: str,
        modified_time: datetime,
        payload: Dict[str, Any],
        log_id: str
    ):
        """
        Perform UPSERT with conflict detection.

        Raises:
            ConflictDetectedError: If incoming Modified_Time < stored Modified_Time
        """
        table_name = f"zoho_{module.lower()}"

        async with self._db_pool.acquire() as conn:
            # Start transaction
            async with conn.transaction():
                # Lock row for update (prevents race conditions)
                existing = await conn.fetchrow(f"""
                    SELECT zoho_id, modified_time, data_payload, sync_version
                    FROM {table_name}
                    WHERE zoho_id = $1
                    FOR UPDATE
                """, zoho_id)

                # Conflict detection: incoming older than stored
                if existing and existing["modified_time"] > modified_time:
                    logger.warning(
                        f"Stale update detected: incoming {modified_time} < "
                        f"stored {existing['modified_time']} for {module}:{zoho_id}"
                    )

                    # Log conflict to zoho_sync_conflicts table
                    await self._log_conflict(
                        conn=conn,
                        module=module,
                        zoho_id=zoho_id,
                        conflict_type=ConflictType.STALE_UPDATE,
                        incoming_modified_time=modified_time,
                        existing_modified_time=existing["modified_time"],
                        previous_snapshot=existing["data_payload"],
                        incoming_payload=payload
                    )

                    raise ConflictDetectedError(
                        f"Stale update for {module}:{zoho_id}: "
                        f"incoming {modified_time} < stored {existing['modified_time']}"
                    )

                # Extract owner information from payload
                owner_email, owner_name = await self._extract_owner_info(payload)

                # Extract timestamps
                created_time = self._parse_datetime(payload.get("Created_Time"))
                if not created_time:
                    created_time = modified_time  # Fallback

                # Perform UPSERT (last-write-wins based on Modified_Time)
                await conn.execute(f"""
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
                    modified_time, json.dumps(payload)
                )

                logger.debug(f"✓ UPSERT complete for {module}:{zoho_id}")

    async def _log_conflict(
        self,
        conn: asyncpg.Connection,
        module: str,
        zoho_id: str,
        conflict_type: ConflictType,
        incoming_modified_time: datetime,
        existing_modified_time: Optional[datetime],
        previous_snapshot: Optional[Dict[str, Any]],
        incoming_payload: Dict[str, Any]
    ):
        """Log sync conflict to zoho_sync_conflicts table"""
        import uuid

        conflict_id = str(uuid.uuid4())

        await conn.execute("""
            INSERT INTO zoho_sync_conflicts
                (id, module, zoho_id, conflict_type, incoming_modified_time,
                 existing_modified_time, previous_snapshot, incoming_payload,
                 resolution_strategy, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        """,
            conflict_id, module, zoho_id, conflict_type.value,
            incoming_modified_time, existing_modified_time,
            json.dumps(previous_snapshot) if previous_snapshot else None,
            json.dumps(incoming_payload),
            ResolutionStrategy.LAST_WRITE_WINS.value
        )

        logger.info(f"✓ Conflict logged: {conflict_id} ({conflict_type.value})")

    async def _extract_owner_info(self, payload: Dict[str, Any]) -> tuple[str, Optional[str]]:
        """
        Extract owner email and name from payload.

        Owner field in Zoho: {"id": "...", "name": "Steve Perry", "email": "steve@..."}
        """
        owner = payload.get("Owner", {})

        if isinstance(owner, dict):
            owner_email = owner.get("email") or owner.get("Email")
            owner_name = owner.get("name") or owner.get("Name")

            # Fallback to default owner if not provided
            if not owner_email:
                owner_email = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL", "steve.perry@emailthewell.com")
                logger.warning(f"No owner email in payload, using default: {owner_email}")

            return owner_email, owner_name

        # Fallback
        default_owner = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL", "steve.perry@emailthewell.com")
        return default_owner, None

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse Zoho datetime string to datetime object"""
        if not dt_str:
            return None

        try:
            # Zoho format: 2025-10-17T14:30:00+00:00 or 2025-10-17T14:30:00Z
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse datetime: {dt_str}, error: {e}")
            return None

    async def _delete_dedupe_key(self, module: str, event_type: str, zoho_id: str, payload_sha: str):
        """Delete Redis dedupe key after successful processing"""
        dedupe_key = f"dedupe:{module}:{event_type}:{zoho_id}:{payload_sha}"

        try:
            await self._redis_manager.client.delete(dedupe_key)
            logger.debug(f"✓ Deleted dedupe key: {dedupe_key}")
        except Exception as e:
            logger.warning(f"Failed to delete dedupe key: {e}")

    async def close(self):
        """Close all connections"""
        try:
            if self._receiver:
                await self._receiver.close()
            if self._client:
                await self._client.close()
            if self._db_pool:
                await self._db_pool.close()
            logger.info("Worker connections closed")
        except Exception as e:
            logger.error(f"Error closing worker: {e}")


class ConflictDetectedError(Exception):
    """Raised when a sync conflict is detected"""
    pass


async def main():
    """Main entry point for running worker"""
    worker = ZohoSyncWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
