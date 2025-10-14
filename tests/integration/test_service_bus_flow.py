"""
Integration tests for Service Bus message flow.
Tests the complete flow from digest request to proactive message delivery.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from azure.servicebus import ServiceBusMessage
from azure.servicebus.exceptions import ServiceBusError, MessageAlreadySettled

from app.service_bus_manager import (
    ServiceBusManager,
    EmailBatchMessage,
    BatchStatus,
    BatchProcessingResult,
    BatchAggregator
)


@pytest.mark.asyncio
class TestServiceBusIntegration:
    """Test Service Bus message flow integration."""

    async def test_digest_request_publish_to_receive_flow(self, service_bus_client):
        """Test complete flow from publish to worker receive."""
        # Arrange
        test_emails = [
            {
                "id": f"email_{i}",
                "subject": f"Test Email {i}",
                "body": f"Body content {i}",
                "from": f"sender{i}@test.com",
                "timestamp": datetime.utcnow().isoformat()
            }
            for i in range(5)
        ]

        # Create mock message for receive
        mock_message = MagicMock()
        batch_msg = EmailBatchMessage(
            batch_id="batch_20250114_120000_5",
            emails=test_emails,
            total_count=5,
            created_at=datetime.utcnow().isoformat(),
            priority=1
        )
        mock_message.__str__ = lambda self: batch_msg.to_json()
        mock_message.message_id = "test-message-id"
        mock_message.delivery_count = 1

        # Configure mock to return message
        service_bus_client._receiver.receive_messages.return_value = [mock_message]

        # Act - Send batch
        batch_id = await service_bus_client.send_batch(test_emails, priority=1)

        # Assert send was called
        assert batch_id.startswith("batch_")
        service_bus_client._sender.send_messages.assert_called_once()

        # Act - Receive batch
        received_batches = await service_bus_client.receive_batch(max_messages=1)

        # Assert
        assert len(received_batches) == 1
        assert received_batches[0].batch_id == batch_msg.batch_id
        assert received_batches[0].total_count == 5
        assert len(received_batches[0].emails) == 5
        service_bus_client._receiver.complete_message.assert_called_once_with(mock_message)

    async def test_dead_letter_queue_handling(self, service_bus_client):
        """Test dead letter queue message handling and retry logic."""
        # Arrange - Create a message that will fail processing
        invalid_message = MagicMock()
        invalid_message.__str__ = lambda self: "invalid json {{"
        invalid_message.message_id = "invalid-msg-id"
        invalid_message.delivery_count = 1

        service_bus_client._receiver.receive_messages.return_value = [invalid_message]

        # Act - Try to receive and process
        received_batches = await service_bus_client.receive_batch()

        # Assert - Message should be sent to dead letter queue
        assert len(received_batches) == 0
        service_bus_client._receiver.dead_letter_message.assert_called_once_with(
            invalid_message,
            reason="InvalidFormat",
            error_description=ANY
        )

    async def test_message_retry_on_failure(self, service_bus_client):
        """Test message retry logic when processing fails."""
        # Arrange
        batch_msg = EmailBatchMessage(
            batch_id="retry_batch_001",
            emails=[{"id": "1", "subject": "Test"}],
            total_count=1,
            created_at=datetime.utcnow().isoformat(),
            retry_count=1,
            max_retries=3
        )

        # Create dead letter message
        dlq_message = MagicMock()
        dlq_message.__str__ = lambda self: batch_msg.to_json()
        dlq_message.dead_letter_reason = "ProcessingError"
        dlq_message.dead_letter_error_description = "Temporary failure"
        dlq_message.delivery_count = 2
        dlq_message.message_id = "dlq-msg-id"

        # Mock dead letter queue receiver
        dlq_receiver = AsyncMock()
        dlq_receiver.receive_messages.return_value = [dlq_message]
        dlq_receiver.complete_message = AsyncMock()
        dlq_receiver.__aenter__ = AsyncMock(return_value=dlq_receiver)
        dlq_receiver.__aexit__ = AsyncMock(return_value=None)

        service_bus_client._client.get_queue_receiver.return_value = dlq_receiver

        # Act
        dead_letters = await service_bus_client.process_dead_letter_queue(max_messages=1)

        # Assert - Message should be retried
        assert len(dead_letters) == 1
        assert dead_letters[0]["action"] == "retried"
        assert dead_letters[0]["batch_id"] == "retry_batch_001"
        service_bus_client._sender.send_messages.assert_called_once()
        dlq_receiver.complete_message.assert_called_once_with(dlq_message)

    async def test_message_expiration_ttl(self, service_bus_client):
        """Test message TTL (Time To Live) expiration."""
        # Arrange
        test_emails = [{"id": "1", "subject": "Expiring message"}]

        # Act
        batch_id = await service_bus_client.send_batch(test_emails, priority=0)

        # Assert - Verify TTL was set
        call_args = service_bus_client._sender.send_messages.call_args
        sent_message = call_args[0][0]

        # The message should have TTL set (24 hours by default)
        assert hasattr(sent_message, 'time_to_live')
        # Note: In real Azure Service Bus, expired messages go to dead letter queue

    async def test_concurrent_message_processing(self, service_bus_client, concurrency_tester):
        """Test concurrent message processing with multiple workers."""
        # Arrange - Create multiple batches
        batches = []
        for i in range(10):
            batch_msg = EmailBatchMessage(
                batch_id=f"concurrent_batch_{i:03d}",
                emails=[{"id": f"{i}-1", "subject": f"Email {i}"}],
                total_count=1,
                created_at=datetime.utcnow().isoformat(),
                priority=i % 3  # Varying priorities
            )
            batches.append(batch_msg)

        # Mock messages for concurrent processing
        mock_messages = []
        for batch in batches:
            msg = MagicMock()
            msg.__str__ = lambda self, b=batch: b.to_json()
            msg.message_id = f"msg-{batch.batch_id}"
            msg.delivery_count = 1
            mock_messages.append(msg)

        # Configure mock to return messages in chunks
        service_bus_client._receiver.receive_messages.side_effect = [
            mock_messages[:3],
            mock_messages[3:6],
            mock_messages[6:9],
            mock_messages[9:]
        ]

        # Act - Process messages concurrently
        async def worker(worker_id):
            """Worker function to process messages."""
            received = await service_bus_client.receive_batch(max_messages=3)
            return worker_id, len(received)

        results, errors = await concurrency_tester.run_concurrent(
            worker,
            0, 1, 2, 3  # 4 workers
        )

        # Assert
        assert len(errors) == 0
        total_processed = sum(count for _, count in results)
        assert total_processed == 10
        # All messages should be completed
        assert service_bus_client._receiver.complete_message.call_count == 10

    async def test_batch_size_limits(self, service_bus_client):
        """Test batch size limits and automatic splitting."""
        # Arrange - Create large batch that exceeds size limit
        large_emails = []
        for i in range(100):
            large_emails.append({
                "id": f"email_{i:03d}",
                "subject": f"Large subject with lots of text {i}" * 10,
                "body": "x" * 5000,  # 5KB per email
                "attachments": ["file1.pdf", "file2.docx"] * 5
            })

        # Mock size check to trigger splitting
        service_bus_client.max_message_size_kb = 100  # Set low limit to trigger split

        # Act
        batch_id = await service_bus_client.send_batch(large_emails, priority=2)

        # Assert - Should have been split into multiple batches
        assert batch_id.startswith("split_")
        # Multiple send calls should have been made
        assert service_bus_client._sender.send_messages.call_count > 1

    async def test_priority_message_ordering(self, service_bus_client):
        """Test that high priority messages are processed first."""
        # Arrange - Create messages with different priorities
        high_priority_batch = EmailBatchMessage(
            batch_id="high_priority_001",
            emails=[{"id": "hp1", "subject": "Urgent"}],
            total_count=1,
            created_at=datetime.utcnow().isoformat(),
            priority=9
        )

        low_priority_batch = EmailBatchMessage(
            batch_id="low_priority_001",
            emails=[{"id": "lp1", "subject": "Regular"}],
            total_count=1,
            created_at=datetime.utcnow().isoformat(),
            priority=1
        )

        # Act - Send both batches
        await service_bus_client.send_batch(high_priority_batch.emails, priority=9)
        await service_bus_client.send_batch(low_priority_batch.emails, priority=1)

        # Assert - High priority message should have priority property set
        calls = service_bus_client._sender.send_messages.call_args_list
        assert len(calls) == 2

        # Check application properties for priority
        high_pri_msg = calls[0][0][0]
        low_pri_msg = calls[1][0][0]

        assert high_pri_msg.application_properties["priority"] == 9
        assert low_pri_msg.application_properties["priority"] == 1


@pytest.mark.asyncio
class TestBatchAggregator:
    """Test intelligent batch aggregation for GPT-5 processing."""

    async def test_optimal_batch_size_calculation(self, service_bus_client):
        """Test that batch aggregator calculates optimal size based on token limits."""
        # Arrange
        aggregator = await service_bus_client.create_batch_aggregator()

        # Assert
        assert aggregator.optimal_batch_size <= 50  # Max emails per batch
        assert aggregator.available_tokens == 390000  # 400K - 10K buffer
        assert aggregator.estimated_tokens == 0
        assert len(aggregator.pending_emails) == 0

    async def test_email_token_estimation(self, service_bus_client):
        """Test token estimation for emails."""
        # Arrange
        aggregator = await service_bus_client.create_batch_aggregator()
        test_email = {
            "subject": "Test Subject " * 10,  # ~40 chars = ~10 tokens
            "body": "x" * 4000,  # 4000 chars = ~1000 tokens
            "attachments": ["file.pdf"] * 10
        }

        # Act
        can_add = aggregator.can_add_email(test_email)
        added = aggregator.add_email(test_email)

        # Assert
        assert can_add is True
        assert added is True
        assert aggregator.estimated_tokens > 1000
        assert len(aggregator.pending_emails) == 1

    async def test_batch_ready_when_full(self, service_bus_client):
        """Test batch readiness detection."""
        # Arrange
        aggregator = await service_bus_client.create_batch_aggregator()
        small_email = {"subject": "Test", "body": "Small content"}

        # Act - Add emails up to optimal size
        for i in range(aggregator.optimal_batch_size):
            aggregator.add_email({**small_email, "id": str(i)})

        # Assert
        assert aggregator.is_ready() is True
        assert len(aggregator.pending_emails) == aggregator.optimal_batch_size

    async def test_batch_flush_sends_to_service_bus(self, service_bus_client):
        """Test flushing batch to Service Bus."""
        # Arrange
        aggregator = await service_bus_client.create_batch_aggregator()
        aggregator.service_bus = service_bus_client

        # Add some emails
        for i in range(5):
            aggregator.add_email({
                "id": str(i),
                "subject": f"Email {i}",
                "body": f"Content {i}"
            })

        # Act
        batch_id = await aggregator.flush(priority=2)

        # Assert
        assert batch_id is not None
        service_bus_client._sender.send_messages.assert_called_once()
        assert len(aggregator.pending_emails) == 0
        assert aggregator.estimated_tokens == 0


@pytest.mark.asyncio
class TestServiceBusErrorHandling:
    """Test Service Bus error handling and resilience."""

    async def test_connection_retry_on_failure(self, service_bus_client):
        """Test connection retry logic on Service Bus errors."""
        # Arrange
        service_bus_client._client = None
        service_bus_client._sender = None
        service_bus_client._receiver = None

        # Mock connection failure then success
        connect_attempts = [ServiceBusError("Connection failed"), None]
        with patch.object(service_bus_client, 'connect', side_effect=connect_attempts):
            # Act & Assert - First attempt should fail
            with pytest.raises(ServiceBusError):
                await service_bus_client.send_batch([{"id": "1"}])

    async def test_message_already_settled_handling(self, service_bus_client):
        """Test handling of already settled messages."""
        # Arrange
        mock_message = MagicMock()
        batch_msg = EmailBatchMessage(
            batch_id="test_batch",
            emails=[{"id": "1"}],
            total_count=1,
            created_at=datetime.utcnow().isoformat()
        )
        mock_message.__str__ = lambda self: batch_msg.to_json()

        service_bus_client._receiver.receive_messages.return_value = [mock_message]
        service_bus_client._receiver.complete_message.side_effect = MessageAlreadySettled()

        # Act
        received = await service_bus_client.receive_batch()

        # Assert - Should handle gracefully and still return the batch
        assert len(received) == 1
        assert received[0].batch_id == "test_batch"

    async def test_queue_status_monitoring(self, service_bus_client):
        """Test queue status and metrics retrieval."""
        # Arrange - Mock peek messages
        peeked = [
            {"batch_id": f"batch_{i}", "email_count": i+1, "priority": i % 3}
            for i in range(5)
        ]
        service_bus_client.peek_messages = AsyncMock(return_value=peeked)

        # Act
        status = await service_bus_client.get_queue_status()

        # Assert
        assert status["queue_name"] == "test-queue"
        assert status["message_count"] == 5
        assert status["total_emails"] == sum(msg["email_count"] for msg in peeked)
        assert status["connected"] is True
        assert "priority_distribution" in status


@pytest.mark.asyncio
class TestDeadLetterQueueRecovery:
    """Test dead letter queue recovery mechanisms."""

    async def test_max_retry_limit_enforcement(self, service_bus_client):
        """Test that messages exceeding max retries are abandoned."""
        # Arrange
        batch_msg = EmailBatchMessage(
            batch_id="max_retry_batch",
            emails=[{"id": "1"}],
            total_count=1,
            created_at=datetime.utcnow().isoformat(),
            retry_count=3,  # Already at max
            max_retries=3
        )

        dlq_message = MagicMock()
        dlq_message.__str__ = lambda self: batch_msg.to_json()
        dlq_message.dead_letter_reason = "MaxRetriesExceeded"
        dlq_message.delivery_count = 4
        dlq_message.message_id = "max-retry-msg"

        dlq_receiver = AsyncMock()
        dlq_receiver.receive_messages.return_value = [dlq_message]
        dlq_receiver.complete_message = AsyncMock()
        dlq_receiver.__aenter__ = AsyncMock(return_value=dlq_receiver)
        dlq_receiver.__aexit__ = AsyncMock(return_value=None)

        service_bus_client._client.get_queue_receiver.return_value = dlq_receiver

        # Act
        dead_letters = await service_bus_client.process_dead_letter_queue()

        # Assert - Should not retry, mark as abandoned
        assert len(dead_letters) == 1
        assert dead_letters[0]["action"] == "abandoned"
        service_bus_client._sender.send_messages.assert_not_called()
        dlq_receiver.complete_message.assert_called_once()

    async def test_corrupt_message_handling_in_dlq(self, service_bus_client):
        """Test handling of corrupt messages in dead letter queue."""
        # Arrange
        corrupt_message = MagicMock()
        corrupt_message.__str__ = lambda self: "not even json"
        corrupt_message.dead_letter_reason = "CorruptMessage"
        corrupt_message.dead_letter_error_description = "Parse error"
        corrupt_message.delivery_count = 1
        corrupt_message.message_id = "corrupt-msg"

        dlq_receiver = AsyncMock()
        dlq_receiver.receive_messages.return_value = [corrupt_message]
        dlq_receiver.complete_message = AsyncMock()
        dlq_receiver.abandon_message = AsyncMock()
        dlq_receiver.__aenter__ = AsyncMock(return_value=dlq_receiver)
        dlq_receiver.__aexit__ = AsyncMock(return_value=None)

        service_bus_client._client.get_queue_receiver.return_value = dlq_receiver

        # Act
        dead_letters = await service_bus_client.process_dead_letter_queue()

        # Assert
        assert len(dead_letters) == 1
        assert dead_letters[0]["action"] == "failed"
        assert "parse_error" in dead_letters[0]
        dlq_receiver.complete_message.assert_called_once()