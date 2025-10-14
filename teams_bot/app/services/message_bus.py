"""
Azure Service Bus messaging service for Teams bot.
Handles publishing messages to queues for async processing with KEDA autoscaling.
"""
import os
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.servicebus.exceptions import ServiceBusError

# Optional: Only needed for queue metrics in API endpoints
try:
    from azure.servicebus.management.aio import ServiceBusAdministrationClient
    ADMIN_CLIENT_AVAILABLE = True
except ImportError:
    ServiceBusAdministrationClient = None
    ADMIN_CLIENT_AVAILABLE = False

from app.models.messages import (
    DigestRequestMessage,
    NLPQueryMessage,
    QueueMetricsResponse,
    DigestAudience
)

logger = logging.getLogger(__name__)


class MessageBusService:
    """Singleton service for Azure Service Bus operations."""

    _instance: Optional['MessageBusService'] = None
    _client: Optional[ServiceBusClient] = None
    _admin_client: Optional[ServiceBusAdministrationClient] = None

    DIGEST_QUEUE = "teams-digest-requests"
    NLP_QUEUE = "teams-nlp-queries"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.connection_string = os.getenv(
            "AZURE_SERVICE_BUS_CONNECTION_STRING",
            os.getenv("SERVICE_BUS_CONNECTION_STRING")
        )

        if not self.connection_string:
            raise ValueError("SERVICE_BUS_CONNECTION_STRING not found in environment")

        self._client = ServiceBusClient.from_connection_string(
            self.connection_string,
            logging_enable=True
        )

        # Only create admin client if available (not needed for workers)
        if ADMIN_CLIENT_AVAILABLE:
            self._admin_client = ServiceBusAdministrationClient.from_connection_string(
                self.connection_string
            )
            logger.info("MessageBusService initialized with admin client")
        else:
            self._admin_client = None
            logger.info("MessageBusService initialized (admin client not available)")

        self._initialized = True

    async def publish_digest_request(
        self,
        conversation_id: str,
        service_url: str,
        audience: str,
        user_email: str,
        **kwargs
    ) -> str:
        """Publish digest generation request to Service Bus queue."""
        try:
            message_obj = DigestRequestMessage(
                conversation_id=conversation_id,
                service_url=service_url,
                audience=DigestAudience(audience),
                user_email=user_email,
                **{k: v for k, v in kwargs.items() if k in DigestRequestMessage.model_fields}
            )

            sb_message = ServiceBusMessage(
                body=message_obj.model_dump_json(),
                content_type="application/json",
                correlation_id=str(message_obj.correlation_id) if message_obj.correlation_id else None,
                message_id=str(message_obj.message_id),
                time_to_live=timedelta(seconds=message_obj.ttl_seconds),
                application_properties={
                    "message_type": "DigestRequestMessage",
                    "audience": audience,
                    "user_email": user_email
                }
            )

            async with self._client.get_queue_sender(self.DIGEST_QUEUE) as sender:
                await sender.send_messages(sb_message)

            logger.info(f"Published digest request: {message_obj.message_id}")
            return str(message_obj.message_id)

        except Exception as e:
            logger.error(f"Failed to publish digest request: {e}")
            raise

    async def get_queue_metrics(self, queue_name: str) -> QueueMetricsResponse:
        """Get metrics for a specific queue."""
        if not self._admin_client:
            raise RuntimeError(
                "Admin client not available. Queue metrics are only supported in API endpoints, "
                "not in worker containers."
            )

        try:
            props = await self._admin_client.get_queue_runtime_properties(queue_name)
            return QueueMetricsResponse(
                queue_name=queue_name,
                active_messages=props.active_message_count,
                dead_letter_messages=props.dead_letter_message_count,
                scheduled_messages=props.scheduled_message_count,
                transfer_messages=props.transfer_message_count,
                total_messages=props.total_message_count,
                size_in_bytes=props.size_in_bytes,
                accessed_at=props.accessed_at_utc,
                updated_at=props.updated_at_utc
            )
        except Exception as e:
            logger.error(f"Failed to get queue metrics: {e}")
            raise

    async def close(self):
        if self._client:
            await self._client.close()
        if self._admin_client:
            await self._admin_client.close()


def get_message_bus() -> MessageBusService:
    return MessageBusService()
