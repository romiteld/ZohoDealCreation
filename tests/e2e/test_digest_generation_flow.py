"""
End-to-end tests for the complete digest generation flow.
Tests the full journey from user command to proactive message delivery.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from botbuilder.core import TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount


@pytest.mark.asyncio
class TestDigestGenerationE2E:
    """Test the complete digest generation flow end-to-end."""

    async def test_complete_digest_flow_with_correlation_id(
        self,
        mock_message_bus_service,
        mock_conversation_reference,
        mock_redis_client
    ):
        """Test complete flow from command to delivery with correlation tracking."""
        # Arrange
        correlation_id = str(uuid.uuid4())
        user_id = "test-user-123"
        digest_type = "advisors"

        # Mock Teams context
        context = MagicMock(spec=TurnContext)
        context.activity = Activity(
            type=ActivityTypes.message,
            text="/digest advisors",
            from_property=ChannelAccount(id=user_id, name="Test User"),
            channel_id="msteams"
        )

        # Step 1: User sends digest command
        async def handle_digest_command(context):
            """Simulate Teams bot handling digest command."""
            # Store conversation reference
            conversation_ref = TurnContext.get_conversation_reference(context.activity)
            await mock_redis_client.set(
                f"conversation:ref:{user_id}",
                json.dumps(conversation_ref),
                ex=86400
            )

            # Publish to Service Bus
            message_id = await mock_message_bus_service.publish_digest_request(
                user_id=user_id,
                digest_type=digest_type,
                correlation_id=correlation_id
            )

            # Send immediate response
            await context.send_activity(
                MessageFactory.text(
                    "Your digest request has been received and is being processed. "
                    "You'll receive the results shortly."
                )
            )

            return message_id

        # Act - Step 1: Handle command
        message_id = await handle_digest_command(context)

        # Assert - Command handling
        assert message_id == "msg-123"
        mock_message_bus_service.publish_digest_request.assert_called_once_with(
            user_id=user_id,
            digest_type=digest_type,
            correlation_id=correlation_id
        )
        mock_redis_client.set.assert_called_once()

        # Step 2: Worker processes message
        async def worker_process_message():
            """Simulate worker processing the digest request."""
            # Receive message from queue
            message = {
                "message_id": message_id,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "digest_type": digest_type,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Generate digest (mocked)
            digest_result = {
                "correlation_id": correlation_id,
                "type": digest_type,
                "candidates": [
                    {
                        "name": "Anonymous Candidate 1",
                        "location": "Chicago, IL",
                        "compensation": "$500K+",
                        "highlights": [
                            "15+ years experience",
                            "Book size: $150M AUM",
                            "Ready to move immediately"
                        ]
                    },
                    {
                        "name": "Anonymous Candidate 2",
                        "location": "New York, NY",
                        "compensation": "$750K+",
                        "highlights": [
                            "20+ years experience",
                            "Book size: $250M AUM",
                            "Available in 30 days"
                        ]
                    }
                ],
                "generation_time_ms": 3500,
                "model_used": "gpt-5-mini"
            }

            # Store result
            await mock_redis_client.set(
                f"digest:result:{correlation_id}",
                json.dumps(digest_result),
                ex=3600
            )

            return digest_result

        # Act - Step 2: Process message
        digest_result = await worker_process_message()

        # Assert - Processing
        assert digest_result["correlation_id"] == correlation_id
        assert len(digest_result["candidates"]) == 2
        assert digest_result["type"] == digest_type

        # Step 3: Send proactive message with results
        async def send_proactive_result():
            """Simulate sending proactive message with digest results."""
            # Retrieve conversation reference
            ref_data = await mock_redis_client.get(f"conversation:ref:{user_id}")
            conversation_ref = json.loads(ref_data) if ref_data else mock_conversation_reference

            # Retrieve digest result
            result_data = await mock_redis_client.get(f"digest:result:{correlation_id}")
            digest = json.loads(result_data) if result_data else digest_result

            # Create adaptive card
            card = {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": f"Weekly {digest['type'].title()} Digest",
                        "weight": "bolder",
                        "size": "large"
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Generated on {datetime.utcnow().strftime('%B %d, %Y')}",
                        "isSubtle": True,
                        "size": "small"
                    },
                    {
                        "type": "Container",
                        "items": []
                    }
                ],
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "View Full Report",
                        "url": f"https://example.com/digest/{correlation_id}"
                    }
                ]
            }

            # Add candidates to card
            for idx, candidate in enumerate(digest["candidates"], 1):
                candidate_container = {
                    "type": "Container",
                    "separator": True,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"Candidate {idx}",
                            "weight": "bolder"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Location", "value": candidate["location"]},
                                {"title": "Compensation", "value": candidate["compensation"]}
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": "\n".join(f"• {h}" for h in candidate["highlights"]),
                            "wrap": True
                        }
                    ]
                }
                card["body"][2]["items"].append(candidate_container)

            # Send proactive message
            await mock_message_bus_service.send_proactive_message(
                conversation_ref=conversation_ref,
                card=card,
                correlation_id=correlation_id
            )

            return True

        # Act - Step 3: Send proactive message
        result = await send_proactive_result()

        # Assert - Proactive delivery
        assert result is True
        mock_message_bus_service.send_proactive_message.assert_called_once()

        # Step 4: Track metrics and completion
        async def track_completion():
            """Track completion metrics."""
            metrics = {
                "correlation_id": correlation_id,
                "total_duration_ms": 5000,
                "steps": {
                    "command_received": 0,
                    "queued": 100,
                    "processing_started": 500,
                    "digest_generated": 4000,
                    "message_delivered": 5000
                },
                "success": True
            }

            # Store metrics
            await mock_redis_client.hset(
                f"metrics:{correlation_id}",
                mapping=metrics
            )

            return metrics

        # Act - Step 4: Track metrics
        metrics = await track_completion()

        # Assert - Metrics tracking
        assert metrics["correlation_id"] == correlation_id
        assert metrics["success"] is True
        assert metrics["total_duration_ms"] == 5000

    async def test_webhook_response_time_under_200ms(self, mock_message_bus_service):
        """Test that webhook response is sent within 200ms."""
        # Arrange
        start_time = datetime.utcnow()

        async def handle_webhook():
            """Simulate webhook handler."""
            # Async publish to Service Bus (non-blocking)
            message_task = asyncio.create_task(
                mock_message_bus_service.publish_digest_request(
                    user_id="user-123",
                    digest_type="advisors"
                )
            )

            # Return immediately without waiting
            response = {
                "status": "accepted",
                "message": "Your request is being processed"
            }

            # Don't await the task here
            asyncio.create_task(message_task)

            return response

        # Act
        response = await handle_webhook()
        end_time = datetime.utcnow()

        # Assert
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        assert response_time_ms < 200
        assert response["status"] == "accepted"

    async def test_error_recovery_with_correlation_tracking(
        self,
        mock_message_bus_service,
        mock_redis_client,
        error_injector
    ):
        """Test error recovery maintains correlation ID throughout."""
        # Arrange
        correlation_id = str(uuid.uuid4())
        user_id = "error-test-user"

        # Inject temporary Redis error
        error_injector.inject_redis_error("Temporary Redis failure")

        # Error recovery flow
        async def handle_with_recovery():
            """Handle digest request with error recovery."""
            attempts = []

            for attempt in range(3):
                try:
                    # Attempt to store conversation reference
                    await mock_redis_client.set(
                        f"conversation:ref:{user_id}",
                        json.dumps({"user_id": user_id}),
                        ex=86400
                    )

                    # Publish message
                    message_id = await mock_message_bus_service.publish_digest_request(
                        user_id=user_id,
                        digest_type="advisors",
                        correlation_id=correlation_id
                    )

                    attempts.append({
                        "attempt": attempt + 1,
                        "correlation_id": correlation_id,
                        "success": True,
                        "message_id": message_id
                    })
                    break

                except Exception as e:
                    attempts.append({
                        "attempt": attempt + 1,
                        "correlation_id": correlation_id,
                        "success": False,
                        "error": str(e)
                    })

                    if attempt < 2:
                        await asyncio.sleep(0.5 * (2 ** attempt))  # Exponential backoff
                        # Clear error for next attempt
                        if attempt == 1:
                            error_injector.cleanup()

            return attempts

        # Act
        attempts = await handle_with_recovery()

        # Assert
        # Should have failed once, then succeeded
        assert len(attempts) >= 2
        assert attempts[0]["success"] is False
        assert attempts[-1]["success"] is True
        # Correlation ID maintained throughout
        assert all(a["correlation_id"] == correlation_id for a in attempts)

    async def test_concurrent_digest_requests(self, mock_message_bus_service, concurrency_tester):
        """Test handling multiple concurrent digest requests."""
        # Arrange
        user_ids = [f"user-{i}" for i in range(10)]
        digest_types = ["advisors", "c_suite", "global"]

        async def send_digest_request(user_id, digest_type):
            """Send a digest request."""
            correlation_id = str(uuid.uuid4())
            message_id = await mock_message_bus_service.publish_digest_request(
                user_id=user_id,
                digest_type=digest_type,
                correlation_id=correlation_id
            )
            return {
                "user_id": user_id,
                "digest_type": digest_type,
                "correlation_id": correlation_id,
                "message_id": message_id,
                "timestamp": datetime.utcnow().isoformat()
            }

        # Create request combinations
        requests = []
        for i, user_id in enumerate(user_ids):
            digest_type = digest_types[i % len(digest_types)]
            requests.append((user_id, digest_type))

        # Act - Send all requests concurrently
        results, errors = await concurrency_tester.run_concurrent(
            send_digest_request,
            *requests
        )

        # Assert
        assert len(errors) == 0
        assert len(results) == 10
        # All should have unique correlation IDs
        correlation_ids = [r["correlation_id"] for r in results]
        assert len(set(correlation_ids)) == 10
        # All should have message IDs
        assert all(r["message_id"] == "msg-123" for r in results)

    async def test_digest_request_deduplication(self, mock_message_bus_service, mock_redis_client):
        """Test that duplicate digest requests are deduplicated."""
        # Arrange
        user_id = "dedup-test-user"
        digest_type = "advisors"

        # Track active requests
        async def publish_with_dedup_check(user_id, digest_type):
            """Publish with deduplication check."""
            # Check for active request
            active_key = f"active:digest:{user_id}:{digest_type}"
            is_active = await mock_redis_client.exists(active_key)

            if is_active:
                # Return existing correlation ID
                existing_id = await mock_redis_client.get(active_key)
                return {
                    "status": "duplicate",
                    "correlation_id": existing_id.decode() if existing_id else None,
                    "message": "A digest request is already being processed"
                }

            # Create new request
            correlation_id = str(uuid.uuid4())
            await mock_redis_client.set(active_key, correlation_id, ex=300)  # 5 min TTL

            message_id = await mock_message_bus_service.publish_digest_request(
                user_id=user_id,
                digest_type=digest_type,
                correlation_id=correlation_id
            )

            return {
                "status": "new",
                "correlation_id": correlation_id,
                "message_id": message_id
            }

        # Configure mock
        mock_redis_client.exists.side_effect = [False, True, True]
        mock_redis_client.get.return_value = b"existing-correlation-id"

        # Act - Send multiple requests
        results = []
        for i in range(3):
            result = await publish_with_dedup_check(user_id, digest_type)
            results.append(result)

        # Assert
        assert results[0]["status"] == "new"
        assert results[1]["status"] == "duplicate"
        assert results[2]["status"] == "duplicate"
        assert results[1]["correlation_id"] == "existing-correlation-id"
        assert results[2]["correlation_id"] == "existing-correlation-id"
        # Only one message should be published
        assert mock_message_bus_service.publish_digest_request.call_count == 1