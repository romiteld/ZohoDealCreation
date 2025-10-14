"""Unit tests for MessageBusService.

Tests cover singleton behavior, message publishing, retry logic,
error handling, and queue metrics retrieval.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from azure.servicebus import ServiceBusMessage
from azure.servicebus.exceptions import (
    MessageSizeExceededError,
    ServiceBusConnectionError,
    ServiceBusError,
    ServiceBusTimeoutError,
)

# Import directly from teams_bot package
import sys
sys.path.insert(0, '/home/romiteld/Development/Desktop_Apps/outlook')

from teams_bot.app.models.messages import (
    DigestAudience,
    DigestRequestMessage,
    MessagePriority,
    NLPQueryMessage,
)
from teams_bot.app.services.message_bus import MessageBusService


class TestMessageBusService:
    """Test suite for MessageBusService."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        # Reset singleton instance before each test
        MessageBusService._instance = None
        MessageBusService._client = None
        MessageBusService._admin_client = None
        MessageBusService._senders = {}
        MessageBusService._initialized = False

        # Set mock connection string
        os.environ["AZURE_SERVICE_BUS_CONNECTION_STRING"] = (
            "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test"
        )

    @pytest.fixture
    def mock_service_bus_client(self):
        """Create mock Service Bus client."""
        with patch("teams_bot.app.services.message_bus.ServiceBusClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.from_connection_string.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_admin_client(self):
        """Create mock Service Bus admin client."""
        with patch("teams_bot.app.services.message_bus.ServiceBusAdministrationClient") as mock_admin:
            mock_instance = MagicMock()
            mock_admin.from_connection_string.return_value = mock_instance
            yield mock_instance

    def test_singleton_pattern(self):
        """Test that MessageBusService follows singleton pattern."""
        service1 = MessageBusService()
        service2 = MessageBusService()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_initialization_without_connection_string(self):
        """Test initialization fails without connection string."""
        del os.environ["AZURE_SERVICE_BUS_CONNECTION_STRING"]

        service = MessageBusService()
        with pytest.raises(ValueError, match="AZURE_SERVICE_BUS_CONNECTION_STRING"):
            await service._ensure_initialized()

    @pytest.mark.asyncio
    async def test_initialization_with_connection_error(self, mock_service_bus_client):
        """Test initialization handles connection errors."""
        mock_service_bus_client.side_effect = Exception("Connection failed")

        service = MessageBusService()
        with pytest.raises(ServiceBusConnectionError, match="Unable to connect"):
            await service._ensure_initialized()

    @pytest.mark.asyncio
    async def test_successful_initialization(self, mock_service_bus_client, mock_admin_client):
        """Test successful service initialization."""
        service = MessageBusService()
        await service._ensure_initialized()

        assert service._initialized is True
        assert service._client is not None
        assert service._admin_client is not None

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_service_bus_client, mock_admin_client):
        """Test async context manager behavior."""
        async with MessageBusService() as service:
            assert service is not None
            assert service._initialized is True

    @pytest.mark.asyncio
    async def test_publish_digest_request(self, mock_service_bus_client, mock_admin_client):
        """Test publishing digest request message."""
        # Setup mock sender
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)
        mock_sender.send_messages = AsyncMock()

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        message_id = await service.publish_digest_request(
            conversation_id="conv_123",
            service_url="https://smba.trafficmanager.net/amer/",
            audience="advisors",
            user_email="test@example.com",
            user_name="Test User",
            tenant_id="tenant_123",
            date_range_days=7,
            include_vault=True,
            include_deals=True,
            include_meetings=True,
            priority=MessagePriority.HIGH,
            ttl_seconds=3600
        )

        assert message_id is not None
        mock_service_bus_client.get_queue_sender.assert_called_with(
            queue_name="teams-digest-requests"
        )
        mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_digest_request_invalid_audience(self, mock_service_bus_client, mock_admin_client):
        """Test publishing digest request with invalid audience."""
        service = MessageBusService()

        with pytest.raises(ValueError, match="Invalid audience"):
            await service.publish_digest_request(
                conversation_id="conv_123",
                service_url="https://test.com",
                audience="invalid_audience",
                user_email="test@example.com"
            )

    @pytest.mark.asyncio
    async def test_publish_nlp_query(self, mock_service_bus_client, mock_admin_client):
        """Test publishing NLP query message."""
        # Setup mock sender
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)
        mock_sender.send_messages = AsyncMock()

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        message_id = await service.publish_nlp_query(
            conversation_id="conv_456",
            service_url="https://smba.trafficmanager.net/amer/",
            query_text="Show me all deals closing this month",
            user_email="test@example.com",
            user_name="Test User",
            context_window={"previous": "context"},
            max_results=10,
            response_format="card"
        )

        assert message_id is not None
        mock_service_bus_client.get_queue_sender.assert_called_with(
            queue_name="teams-nlp-queries"
        )
        mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, mock_service_bus_client, mock_admin_client):
        """Test retry logic on timeout errors."""
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)

        # First call raises timeout, second succeeds
        mock_sender.send_messages = AsyncMock(
            side_effect=[ServiceBusTimeoutError("Timeout"), None]
        )

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
            message_id = await service.publish_digest_request(
                conversation_id="conv_123",
                service_url="https://test.com",
                audience="advisors",
                user_email="test@example.com"
            )

        assert message_id is not None
        assert mock_sender.send_messages.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, mock_service_bus_client, mock_admin_client):
        """Test retry logic on connection errors."""
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)

        # First two calls fail, third succeeds
        mock_sender.send_messages = AsyncMock(
            side_effect=[
                ServiceBusConnectionError("Connection lost"),
                ServiceBusConnectionError("Connection lost"),
                None
            ]
        )

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
            message_id = await service.publish_digest_request(
                conversation_id="conv_123",
                service_url="https://test.com",
                audience="advisors",
                user_email="test@example.com"
            )

        assert message_id is not None
        assert mock_sender.send_messages.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_message_size_exceeded(self, mock_service_bus_client, mock_admin_client):
        """Test that message size errors are not retried."""
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)
        mock_sender.send_messages = AsyncMock(
            side_effect=MessageSizeExceededError("Message too large")
        )

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        with pytest.raises(MessageSizeExceededError):
            await service.publish_digest_request(
                conversation_id="conv_123",
                service_url="https://test.com",
                audience="advisors",
                user_email="test@example.com"
            )

        # Should only try once, no retries
        assert mock_sender.send_messages.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_service_bus_client, mock_admin_client):
        """Test that max retries limit is respected."""
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)
        mock_sender.send_messages = AsyncMock(
            side_effect=ServiceBusTimeoutError("Timeout")
        )

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
            with pytest.raises(ServiceBusError, match="Failed to send message"):
                await service.publish_digest_request(
                    conversation_id="conv_123",
                    service_url="https://test.com",
                    audience="advisors",
                    user_email="test@example.com"
                )

        # Default max_retries is 3, so 4 total attempts
        assert mock_sender.send_messages.call_count == 4

    @pytest.mark.asyncio
    async def test_get_queue_metrics(self, mock_service_bus_client, mock_admin_client):
        """Test retrieving queue metrics."""
        # Mock queue runtime properties
        mock_properties = MagicMock()
        mock_properties.active_message_count = 5
        mock_properties.dead_letter_message_count = 2
        mock_properties.scheduled_message_count = 1
        mock_properties.transfer_dead_letter_message_count = 0
        mock_properties.total_message_count = 8
        mock_properties.size_in_bytes = 1024
        mock_properties.accessed_at = datetime.utcnow()
        mock_properties.updated_at = datetime.utcnow()

        mock_admin_client.get_queue_runtime_properties.return_value = mock_properties

        service = MessageBusService()
        metrics = await service.get_queue_metrics("teams-digest-requests")

        assert metrics["queue_name"] == "teams-digest-requests"
        assert metrics["active_messages"] == 5
        assert metrics["dead_letter_messages"] == 2
        assert metrics["total_messages"] == 8
        assert metrics["size_in_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_get_queue_metrics_error(self, mock_service_bus_client, mock_admin_client):
        """Test handling errors when retrieving queue metrics."""
        mock_admin_client.get_queue_runtime_properties.side_effect = Exception("Queue not found")

        service = MessageBusService()
        with pytest.raises(ServiceBusError, match="Unable to retrieve queue metrics"):
            await service.get_queue_metrics("non-existent-queue")

    @pytest.mark.asyncio
    async def test_health_check(self, mock_service_bus_client, mock_admin_client):
        """Test health check functionality."""
        # Mock queue properties for healthy queues
        mock_properties = MagicMock()
        mock_properties.active_message_count = 5
        mock_properties.dead_letter_message_count = 2
        mock_properties.scheduled_message_count = 0
        mock_properties.transfer_dead_letter_message_count = 0
        mock_properties.total_message_count = 7
        mock_properties.size_in_bytes = 1024
        mock_properties.accessed_at = datetime.utcnow()
        mock_properties.updated_at = datetime.utcnow()

        mock_admin_client.get_queue_runtime_properties.return_value = mock_properties

        service = MessageBusService()
        health = await service.health_check()

        assert health["is_healthy"] is True
        assert health["connection"] == "connected"
        assert "teams-digest-requests" in health["queues"]
        assert "teams-nlp-queries" in health["queues"]
        assert health["queues"]["teams-digest-requests"]["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_queue(self, mock_service_bus_client, mock_admin_client):
        """Test health check with unhealthy queue (too many dead letters)."""
        # Mock queue with too many dead letter messages
        mock_properties = MagicMock()
        mock_properties.active_message_count = 5
        mock_properties.dead_letter_message_count = 15  # Unhealthy threshold
        mock_properties.scheduled_message_count = 0
        mock_properties.transfer_dead_letter_message_count = 0
        mock_properties.total_message_count = 20
        mock_properties.size_in_bytes = 2048
        mock_properties.accessed_at = datetime.utcnow()
        mock_properties.updated_at = datetime.utcnow()

        mock_admin_client.get_queue_runtime_properties.return_value = mock_properties

        service = MessageBusService()
        health = await service.health_check()

        assert health["is_healthy"] is False
        assert health["connection"] == "connected"
        assert health["queues"]["teams-digest-requests"]["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_close_service(self, mock_service_bus_client, mock_admin_client):
        """Test closing the service and cleaning up resources."""
        # Setup mock senders
        mock_sender1 = AsyncMock()
        mock_sender2 = AsyncMock()
        mock_sender1.close = AsyncMock()
        mock_sender2.close = AsyncMock()

        service = MessageBusService()
        await service._ensure_initialized()

        # Add mock senders to cache
        service._senders = {
            "teams-digest-requests": mock_sender1,
            "teams-nlp-queries": mock_sender2
        }

        # Mock client close
        mock_client_close = AsyncMock()
        service._client.close = mock_client_close

        await service.close()

        # Verify all senders were closed
        mock_sender1.close.assert_called_once()
        mock_sender2.close.assert_called_once()

        # Verify client was closed
        mock_client_close.assert_called_once()

        # Verify state was reset
        assert service._senders == {}
        assert service._client is None
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_sender_caching(self, mock_service_bus_client, mock_admin_client):
        """Test that senders are cached and reused."""
        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)
        mock_sender.send_messages = AsyncMock()

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()

        # Send two messages to the same queue
        await service.publish_digest_request(
            conversation_id="conv_1",
            service_url="https://test.com",
            audience="advisors",
            user_email="test1@example.com"
        )

        await service.publish_digest_request(
            conversation_id="conv_2",
            service_url="https://test.com",
            audience="c_suite",
            user_email="test2@example.com"
        )

        # Sender should only be created once
        mock_service_bus_client.get_queue_sender.assert_called_once_with(
            queue_name="teams-digest-requests"
        )

        # But messages should be sent twice
        assert mock_sender.send_messages.call_count == 2

    @pytest.mark.asyncio
    async def test_message_properties_serialization(self, mock_service_bus_client, mock_admin_client):
        """Test that message properties are properly serialized."""
        captured_message = None

        async def capture_message(msg):
            nonlocal captured_message
            captured_message = msg

        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)
        mock_sender.send_messages = AsyncMock(side_effect=capture_message)

        mock_service_bus_client.get_queue_sender.return_value = mock_sender

        service = MessageBusService()
        await service.publish_nlp_query(
            conversation_id="conv_789",
            service_url="https://test.com",
            query_text="Test query",
            user_email="test@example.com",
            max_results=5,
            ttl_seconds=1800
        )

        assert captured_message is not None
        assert captured_message.application_properties["message_type"] == "NLPQueryMessage"
        assert captured_message.application_properties["priority"] == "normal"
        assert captured_message.time_to_live == timedelta(seconds=1800)

        # Verify body can be deserialized
        body = json.loads(captured_message.body)
        assert body["query_text"] == "Test query"
        assert body["max_results"] == 5