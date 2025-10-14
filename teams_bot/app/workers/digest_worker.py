"""
Digest Worker - Service Bus Queue Consumer

Subscribes to teams-digest-requests queue and processes digest generation requests.
Uses ProactiveMessagingService to send results back to Teams users.

Designed for KEDA autoscaling with Azure Container Apps:
- Scale-to-zero when queue is empty
- Scale out (1 replica per 5 messages)
- Graceful shutdown on termination
"""
import os
import asyncio
import signal
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusReceiveMode

from teams_bot.app.services.proactive_messaging import create_proactive_messaging_service
from teams_bot.app.services.message_bus import MessageBusService
from teams_bot.app.models.messages import DigestRequestMessage
from app.jobs.talentwell_curator import TalentWellCurator
from app.api.teams.adaptive_cards import create_digest_preview_card, create_error_card
from well_shared.database.connection import get_connection_manager

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False


def handle_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


class DigestWorker:
    """
    Service Bus consumer that processes digest generation requests.

    Features:
    - Async message processing with concurrent handlers
    - Automatic retries via Service Bus dead lettering
    - Proactive messaging back to Teams users
    - Database tracking for audit and analytics
    - Graceful shutdown on SIGTERM (for Container Apps)
    """

    def __init__(
        self,
        max_concurrent_messages: int = 5,
        max_wait_time: int = 30
    ):
        """
        Initialize digest worker.

        Args:
            max_concurrent_messages: Max messages to process concurrently
            max_wait_time: Max seconds to wait for messages before checking shutdown
        """
        self.max_concurrent_messages = max_concurrent_messages
        self.max_wait_time = max_wait_time

        # Service Bus connection
        self.connection_string = os.getenv(
            "AZURE_SERVICE_BUS_CONNECTION_STRING",
            os.getenv("SERVICE_BUS_CONNECTION_STRING")
        )
        if not self.connection_string:
            raise ValueError("SERVICE_BUS_CONNECTION_STRING not found")

        self.queue_name = os.getenv("AZURE_SERVICE_BUS_DIGEST_QUEUE", "teams-digest-requests")

        self.client: Optional[ServiceBusClient] = None
        self.proactive_messaging = None
        self.curator = None

        logger.info(
            f"DigestWorker initialized: queue={self.queue_name}, "
            f"max_concurrent={max_concurrent_messages}"
        )

    async def initialize(self):
        """Initialize services (database, proactive messaging, curator)."""
        logger.info("Initializing DigestWorker services...")

        # Create Service Bus client
        self.client = ServiceBusClient.from_connection_string(
            self.connection_string,
            logging_enable=True
        )

        # Initialize proactive messaging service
        self.proactive_messaging = await create_proactive_messaging_service()

        # Initialize curator
        self.curator = TalentWellCurator()
        await self.curator.initialize()

        logger.info("✅ DigestWorker services initialized")

    async def process_message(self, message) -> bool:
        """
        Process a single digest request message.

        Args:
            message: Service Bus message

        Returns:
            True if successful, False if failed (triggers dead letter)
        """
        correlation_id = message.correlation_id or "unknown"
        message_id = message.message_id

        logger.info(f"[{correlation_id}] Processing message {message_id}")

        try:
            # Parse message body
            body = json.loads(str(message))
            digest_request = DigestRequestMessage(**body)

            logger.info(
                f"[{correlation_id}] Digest request: "
                f"audience={digest_request.audience}, "
                f"user={digest_request.user_email}"
            )

            # Get database connection
            manager = await get_connection_manager()
            async with manager.get_connection() as db:
                # Create request record if not exists
                existing = await db.fetchval(
                    "SELECT request_id FROM teams_digest_requests WHERE request_id = $1",
                    str(digest_request.message_id)
                )

                if not existing:
                    await db.execute("""
                        INSERT INTO teams_digest_requests (
                            request_id, user_id, user_email, conversation_id,
                            audience, from_date, to_date, owner, max_candidates,
                            dry_run, status, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, CURRENT_TIMESTAMP)
                    """,
                        str(digest_request.message_id),
                        digest_request.user_email,  # Use email as user_id fallback
                        digest_request.user_email,
                        digest_request.conversation_id,
                        digest_request.audience.value,
                        digest_request.from_date,
                        digest_request.to_date,
                        digest_request.owner,
                        digest_request.max_candidates,
                        False,  # Not dry_run (actual generation)
                        "processing"
                    )

                # Update status to processing
                await db.execute("""
                    UPDATE teams_digest_requests
                    SET status = 'processing', started_at = CURRENT_TIMESTAMP
                    WHERE request_id = $1
                """, str(digest_request.message_id))

                # Generate digest
                start_time = datetime.now()

                result = await self.curator.run_weekly_digest(
                    audience=digest_request.audience.value,
                    from_date=digest_request.from_date.isoformat() if digest_request.from_date else None,
                    to_date=digest_request.to_date.isoformat() if digest_request.to_date else None,
                    owner=digest_request.owner,
                    max_cards=digest_request.max_candidates,
                    dry_run=False,  # Actual generation
                    ignore_cooldown=False
                )

                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # Extract cards metadata
                cards_metadata = [
                    {
                        "deal_id": card.deal_id,
                        "candidate_name": card.candidate_name,
                        "job_title": card.job_title,
                        "company": card.company,
                        "location": card.location,
                        "bullets": [{"text": b.text, "category": b.category} for b in card.bullets],
                        "sentiment_label": card.sentiment_label,
                        "sentiment_score": card.sentiment_score
                    }
                    for card in result.get("cards", [])
                ]

                # Update request with results
                await db.execute("""
                    UPDATE teams_digest_requests
                    SET status = 'completed',
                        cards_generated = $1,
                        total_candidates = $2,
                        cards_metadata = $3,
                        execution_time_ms = $4,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE request_id = $5
                """,
                    len(cards_metadata),
                    len(cards_metadata),
                    json.dumps(cards_metadata),
                    execution_time_ms,
                    str(digest_request.message_id)
                )

                # Create adaptive card
                card = create_digest_preview_card(
                    cards_metadata=cards_metadata,
                    audience=digest_request.audience.value,
                    request_id=str(digest_request.message_id)
                )

                # Send proactive message to Teams user
                success = await self.proactive_messaging.send_card_to_conversation(
                    conversation_id=digest_request.conversation_id,
                    service_url=digest_request.service_url,
                    tenant_id=None,  # Will use default from service
                    card_json=card["content"],
                    correlation_id=correlation_id
                )

                if success:
                    await db.execute("""
                        UPDATE teams_digest_requests
                        SET delivered_at = CURRENT_TIMESTAMP
                        WHERE request_id = $1
                    """, str(digest_request.message_id))

                    logger.info(
                        f"[{correlation_id}] ✅ Digest delivered to {digest_request.user_email} "
                        f"({len(cards_metadata)} cards, {execution_time_ms}ms)"
                    )
                else:
                    logger.error(
                        f"[{correlation_id}] ❌ Failed to deliver digest to Teams"
                    )

                return True

        except Exception as e:
            logger.error(
                f"[{correlation_id}] ❌ Error processing message {message_id}: {e}",
                exc_info=True
            )

            # Update request status
            try:
                manager = await get_connection_manager()
                async with manager.get_connection() as db:
                    await db.execute("""
                        UPDATE teams_digest_requests
                        SET status = 'failed',
                            error_message = $1,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE request_id = $2
                    """, str(e), message_id)

                    # Send error card to user
                    try:
                        body = json.loads(str(message))
                        digest_request = DigestRequestMessage(**body)

                        error_card = create_error_card(
                            f"Failed to generate digest: {str(e)}"
                        )

                        await self.proactive_messaging.send_card_to_conversation(
                            conversation_id=digest_request.conversation_id,
                            service_url=digest_request.service_url,
                            tenant_id=None,
                            card_json=error_card["content"],
                            correlation_id=correlation_id
                        )
                    except Exception as notify_error:
                        logger.error(f"Failed to send error notification: {notify_error}")

            except Exception as db_error:
                logger.error(f"Failed to update database with error: {db_error}")

            # Return False to trigger dead letter after retries
            return False

    async def run(self):
        """
        Main worker loop - consume messages from Service Bus queue.

        Runs until shutdown_requested is True (SIGTERM/SIGINT).
        """
        logger.info(f"🚀 Starting DigestWorker on queue: {self.queue_name}")

        async with self.client.get_queue_receiver(
            queue_name=self.queue_name,
            receive_mode=ServiceBusReceiveMode.PEEK_LOCK,
            max_wait_time=self.max_wait_time
        ) as receiver:

            logger.info("✅ Connected to Service Bus queue, waiting for messages...")

            while not shutdown_requested:
                try:
                    # Receive messages (blocks for max_wait_time seconds)
                    messages = await receiver.receive_messages(
                        max_message_count=self.max_concurrent_messages,
                        max_wait_time=self.max_wait_time
                    )

                    if not messages:
                        logger.debug("No messages received, checking shutdown flag...")
                        continue

                    logger.info(f"📬 Received {len(messages)} messages")

                    # Process messages concurrently
                    tasks = []
                    for message in messages:
                        tasks.append(self._process_and_complete(message, receiver))

                    # Wait for all messages to complete
                    await asyncio.gather(*tasks, return_exceptions=True)

                except Exception as e:
                    if not shutdown_requested:
                        logger.error(f"Error in worker loop: {e}", exc_info=True)
                        await asyncio.sleep(5)  # Back off on error

            logger.info("👋 Shutdown requested, exiting worker loop")

    async def _process_and_complete(self, message, receiver):
        """
        Process a message and complete/abandon it.

        Args:
            message: Service Bus message
            receiver: Service Bus receiver
        """
        try:
            success = await self.process_message(message)

            if success:
                # Complete message (remove from queue)
                await receiver.complete_message(message)
                logger.info(f"✅ Message {message.message_id} completed")
            else:
                # Abandon message (will retry based on queue config)
                await receiver.abandon_message(message)
                logger.warning(f"⚠️ Message {message.message_id} abandoned (will retry)")

        except Exception as e:
            logger.error(f"Error processing message {message.message_id}: {e}", exc_info=True)
            try:
                await receiver.abandon_message(message)
            except Exception as abandon_error:
                logger.error(f"Failed to abandon message: {abandon_error}")

    async def close(self):
        """Clean up resources."""
        logger.info("Closing DigestWorker services...")

        if self.curator:
            await self.curator.close()

        if self.client:
            await self.client.close()

        logger.info("✅ DigestWorker closed")


async def main():
    """
    Main entry point for digest worker.

    Usage:
        python -m teams_bot.app.workers.digest_worker

    Environment Variables Required:
        - AZURE_SERVICE_BUS_CONNECTION_STRING
        - AZURE_SERVICE_BUS_DIGEST_QUEUE (default: teams-digest-requests)
        - TEAMS_BOT_APP_ID
        - TEAMS_BOT_APP_PASSWORD
        - DATABASE_URL
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register shutdown handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Create and initialize worker
    worker = DigestWorker(
        max_concurrent_messages=int(os.getenv("MAX_CONCURRENT_MESSAGES", "5")),
        max_wait_time=int(os.getenv("MAX_WAIT_TIME", "30"))
    )

    try:
        await worker.initialize()
        await worker.run()
    except Exception as e:
        logger.error(f"Fatal error in digest worker: {e}", exc_info=True)
    finally:
        await worker.close()

    logger.info("🛑 Digest worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
