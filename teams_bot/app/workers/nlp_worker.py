"""
NLP Query Worker - Service Bus Queue Consumer

Subscribes to teams-nlp-queries queue and processes natural language queries.
Uses ProactiveMessagingService to send results back to Teams users.

Designed for KEDA autoscaling with Azure Container Apps:
- Scale-to-zero when queue is empty
- Scale out (1 replica per 10 messages)
- Faster processing than digest worker (2min lock vs 5min)
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
from azure.identity.aio import DefaultAzureCredential

from app.services.proactive_messaging import create_proactive_messaging_service
from app.models.messages import NLPQueryMessage
from app.api.teams.query_engine import process_natural_language_query
from app.api.teams.adaptive_cards import create_error_card
from well_shared.database.connection import get_connection_manager
from botbuilder.core import CardFactory, MessageFactory
from app.utils.service_bus import normalize_message_body

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False


def handle_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


class NLPWorker:
    """
    Service Bus consumer that processes natural language queries.

    Features:
    - Fast async query processing (2min timeout)
    - Higher concurrency than digest worker
    - Proactive messaging back to Teams users
    - Database tracking for analytics
    - Graceful shutdown on SIGTERM
    """

    def __init__(
        self,
        max_concurrent_messages: int = 10,
        max_wait_time: int = 20
    ):
        """
        Initialize NLP worker.

        Args:
            max_concurrent_messages: Max messages to process concurrently
            max_wait_time: Max seconds to wait for messages before checking shutdown
        """
        self.max_concurrent_messages = max_concurrent_messages
        self.max_wait_time = max_wait_time

        # Service Bus connection - prefer managed identity over connection string
        self.namespace = os.getenv("AZURE_SERVICE_BUS_NAMESPACE")
        self.connection_string = os.getenv(
            "AZURE_SERVICE_BUS_CONNECTION_STRING",
            os.getenv("SERVICE_BUS_CONNECTION_STRING")
        )

        if not self.namespace and not self.connection_string:
            raise ValueError("Either AZURE_SERVICE_BUS_NAMESPACE or SERVICE_BUS_CONNECTION_STRING required")

        self.queue_name = os.getenv("AZURE_SERVICE_BUS_NLP_QUEUE", "teams-nlp-queries")
        self.use_managed_identity = bool(self.namespace)

        self.client: Optional[ServiceBusClient] = None
        self.credential: Optional[DefaultAzureCredential] = None
        self.proactive_messaging = None

        auth_method = "managed identity" if self.use_managed_identity else "connection string"
        logger.info(
            f"NLPWorker initialized: queue={self.queue_name}, "
            f"max_concurrent={max_concurrent_messages}, auth={auth_method}"
        )

    async def initialize(self):
        """Initialize services (database, proactive messaging)."""
        logger.info("Initializing NLPWorker services...")

        # Create Service Bus client with managed identity or connection string
        if self.use_managed_identity:
            self.credential = DefaultAzureCredential()
            self.client = ServiceBusClient(
                fully_qualified_namespace=self.namespace,
                credential=self.credential,
                logging_enable=True
            )
            logger.info(f"✅ Service Bus client initialized with managed identity: {self.namespace}")
        else:
            self.client = ServiceBusClient.from_connection_string(
                self.connection_string,
                logging_enable=True
            )
            logger.info("✅ Service Bus client initialized with connection string")

        # Initialize proactive messaging service
        self.proactive_messaging = await create_proactive_messaging_service()

        logger.info("✅ NLPWorker services initialized")

    async def process_message(self, message, nlp_query: NLPQueryMessage) -> bool:
        """
        Process a single NLP query message.

        Args:
            message: Service Bus message
            nlp_query: Pre-parsed and validated NLP query model

        Returns:
            True if successful, False if failed (triggers dead letter)
        """
        correlation_id = message.correlation_id or "unknown"
        message_id = message.message_id

        logger.info(f"[{correlation_id}] Processing NLP query {message_id}")

        try:

            logger.info(
                f"[{correlation_id}] NLP query: "
                f"query='{nlp_query.query}', "
                f"user={nlp_query.user_email}"
            )

            # Get database connection
            manager = await get_connection_manager()
            async with manager.get_connection() as db:
                # Store query in database
                await db.execute("""
                    INSERT INTO teams_conversations (
                        conversation_id, user_id, user_name, user_email,
                        conversation_type, activity_id, message_text,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
                """,
                    nlp_query.conversation_id,
                    nlp_query.user_email,  # Use email as user_id fallback
                    "Worker User",
                    nlp_query.user_email,
                    "personal",
                    str(nlp_query.message_id),
                    nlp_query.query
                )

                # Process natural language query
                start_time = datetime.now()

                result = await process_natural_language_query(
                    query=nlp_query.query,
                    user_email=nlp_query.user_email,
                    db=db,
                    conversation_context=nlp_query.context or {}
                )

                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # Update conversation with response
                await db.execute("""
                    UPDATE teams_conversations
                    SET bot_response = $1
                    WHERE conversation_id = $2 AND activity_id = $3
                """, "natural_language_query", nlp_query.conversation_id, str(nlp_query.message_id))

                # Send response to Teams user
                if result.get("card"):
                    # Send adaptive card
                    success = await self.proactive_messaging.send_card_to_conversation(
                        conversation_id=nlp_query.conversation_id,
                        service_url=nlp_query.service_url,
                        tenant_id=None,
                        card_json=result["card"]["content"],
                        correlation_id=correlation_id
                    )
                else:
                    # Send text message
                    response_text = result.get("text", "I couldn't process that query.")
                    success = await self.proactive_messaging.send_text_message(
                        conversation_id=nlp_query.conversation_id,
                        service_url=nlp_query.service_url,
                        text=response_text,
                        tenant_id=None,
                        correlation_id=correlation_id
                    )

                if success:
                    logger.info(
                        f"[{correlation_id}] ✅ NLP response delivered to {nlp_query.user_email} "
                        f"({execution_time_ms}ms, confidence={result.get('confidence_score', 0):.2f})"
                    )
                else:
                    logger.error(
                        f"[{correlation_id}] ❌ Failed to deliver NLP response to Teams"
                    )

                return True

        except Exception as e:
            logger.error(
                f"[{correlation_id}] ❌ Error processing NLP query {message_id}: {e}",
                exc_info=True
            )

            # Send error message to user (use pre-parsed nlp_query)
            try:
                error_card = create_error_card(
                    f"Failed to process query: {str(e)}"
                )

                await self.proactive_messaging.send_card_to_conversation(
                    conversation_id=nlp_query.conversation_id,
                    service_url=nlp_query.service_url,
                    tenant_id=None,
                    card_json=error_card["content"],
                    correlation_id=correlation_id
                )
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")

            # Return False to trigger dead letter after retries
            return False

    async def run(self):
        """
        Main worker loop - consume messages from Service Bus queue.

        Runs until shutdown_requested is True (SIGTERM/SIGINT).
        """
        logger.info(f"🚀 Starting NLPWorker on queue: {self.queue_name}")

        async with self.client.get_queue_receiver(
            queue_name=self.queue_name,
            receive_mode=ServiceBusReceiveMode.PEEK_LOCK,
            max_wait_time=self.max_wait_time,
            prefetch_count=0  # Prevent invisible duplicates for long-running tasks
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
        delivery_count = message.delivery_count or 0
        max_delivery_count = 2  # Service Bus queue configuration
        nlp_query = None  # Cache parsed model

        try:
            # Check for poison message before processing (dead-letter on last attempt)
            if delivery_count >= max_delivery_count:
                logger.error(
                    f"⚠️ Message {message.message_id} exceeded max delivery attempts "
                    f"({delivery_count}/{max_delivery_count}). Dead-lettering."
                )
                await receiver.dead_letter_message(
                    message,
                    reason="MaxDeliveryAttemptsExceeded",
                    error_description=f"Message failed after {delivery_count} delivery attempts"
                )
                return

            # Parse and validate message body once (cache for reuse)
            try:
                body_bytes = normalize_message_body(message)
                body = json.loads(body_bytes.decode('utf-8'))
                nlp_query = NLPQueryMessage(**body)  # Cache validated model
            except (json.JSONDecodeError, ValueError, TypeError) as parse_error:
                # Poison message - unparseable or invalid schema
                logger.error(
                    f"⚠️ Message {message.message_id} has invalid format: {parse_error}. Dead-lettering."
                )
                await receiver.dead_letter_message(
                    message,
                    reason="InvalidMessageFormat",
                    error_description=str(parse_error)
                )
                return

            # Process the message (pass cached model to avoid re-parsing)
            success = await self.process_message(message, nlp_query)

            if success:
                # Complete message (remove from queue)
                await receiver.complete_message(message)
                logger.info(f"✅ Message {message.message_id} completed")
            else:
                # Abandon message (will retry based on queue config)
                logger.warning(
                    f"⚠️ Message {message.message_id} abandoned (will retry). "
                    f"Delivery attempt {delivery_count + 1}/{max_delivery_count}"
                )
                await receiver.abandon_message(message)

        except Exception as e:
            logger.error(
                f"Error processing message {message.message_id}: {e}",
                exc_info=True
            )
            try:
                # Check if we should dead-letter due to repeated failures
                # Service Bus auto-dead-letters at maxDeliveryCount, so we explicit dead-letter at count >= 1
                if delivery_count >= max_delivery_count - 1:
                    logger.error(
                        f"⚠️ Message {message.message_id} nearing max retries ({delivery_count}/{max_delivery_count}). Dead-lettering."
                    )
                    await receiver.dead_letter_message(
                        message,
                        reason="ProcessingException",
                        error_description=str(e)
                    )
                else:
                    await receiver.abandon_message(message)
            except Exception as abandon_error:
                logger.error(f"Failed to abandon/dead-letter message: {abandon_error}")

    async def close(self):
        """Clean up resources."""
        logger.info("Closing NLPWorker services...")

        if self.client:
            await self.client.close()

        logger.info("✅ NLPWorker closed")


async def main():
    """
    Main entry point for NLP worker.

    Usage:
        python -m teams_bot.app.workers.nlp_worker

    Environment Variables Required:
        - AZURE_SERVICE_BUS_CONNECTION_STRING
        - AZURE_SERVICE_BUS_NLP_QUEUE (default: teams-nlp-queries)
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
    worker = NLPWorker(
        max_concurrent_messages=int(os.getenv("MAX_CONCURRENT_MESSAGES", "10")),
        max_wait_time=int(os.getenv("MAX_WAIT_TIME", "20"))
    )

    try:
        await worker.initialize()
        await worker.run()
    except Exception as e:
        logger.error(f"Fatal error in NLP worker: {e}", exc_info=True)
    finally:
        await worker.close()

    logger.info("🛑 NLP worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
