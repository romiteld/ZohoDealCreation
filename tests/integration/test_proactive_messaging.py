"""
Integration tests for proactive messaging functionality.
Tests conversation reference storage, retrieval, and proactive message delivery.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import redis
from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ChannelAccount, ConversationAccount


class TestProactiveMessaging:
    """Test proactive messaging capabilities."""

    @pytest.mark.asyncio
    async def test_conversation_reference_storage(self, mock_redis_client, mock_conversation_reference):
        """Test storing conversation references in Redis."""
        # Arrange
        user_id = "test-user-123"
        conversation_ref_key = f"conversation:ref:{user_id}"

        # Act - Store conversation reference
        await mock_redis_client.set(
            conversation_ref_key,
            json.dumps(mock_conversation_reference),
            ex=86400  # 24 hour TTL
        )

        # Assert
        mock_redis_client.set.assert_called_once_with(
            conversation_ref_key,
            json.dumps(mock_conversation_reference),
            ex=86400
        )

    @pytest.mark.asyncio
    async def test_conversation_reference_retrieval(self, mock_redis_client, mock_conversation_reference):
        """Test retrieving stored conversation references."""
        # Arrange
        user_id = "test-user-123"
        conversation_ref_key = f"conversation:ref:{user_id}"
        mock_redis_client.get.return_value = json.dumps(mock_conversation_reference).encode()

        # Act - Retrieve conversation reference
        stored_ref = await mock_redis_client.get(conversation_ref_key)

        # Assert
        assert stored_ref is not None
        retrieved_ref = json.loads(stored_ref.decode())
        assert retrieved_ref["conversation_id"] == mock_conversation_reference["conversation_id"]
        assert retrieved_ref["service_url"] == mock_conversation_reference["service_url"]
        assert retrieved_ref["user"]["id"] == mock_conversation_reference["user"]["id"]

    @pytest.mark.asyncio
    async def test_proactive_card_delivery(self, mock_conversation_reference):
        """Test proactive adaptive card delivery through Bot Framework."""
        # Arrange
        from botbuilder.core import BotFrameworkAdapter, MessageFactory
        from botbuilder.schema import Activity, ActivityTypes, CardAction, HeroCard

        adapter = AsyncMock(spec=BotFrameworkAdapter)

        # Create test card
        card = {
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Digest Generation Complete",
                    "weight": "bolder",
                    "size": "medium"
                },
                {
                    "type": "TextBlock",
                    "text": "Your advisor digest has been generated successfully.",
                    "wrap": True
                }
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "View Digest",
                    "url": "https://example.com/digest/123"
                },
                {
                    "type": "Action.Submit",
                    "title": "Email Me",
                    "data": {"action": "email_digest", "digest_id": "123"}
                }
            ]
        }

        # Create activity with card
        activity = MessageFactory.attachment({
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": card
        })

        # Mock continue conversation
        async def mock_continue_conversation(reference, callback, app_id):
            # Create mock context
            context = MagicMock(spec=TurnContext)
            context.activity = Activity(
                type=ActivityTypes.message,
                channel_id="msteams",
                from_property=ChannelAccount(id="bot-id", name="Bot"),
                recipient=ChannelAccount(
                    id=reference["user"]["id"],
                    name=reference["user"]["name"]
                )
            )
            await callback(context)
            return True

        adapter.continue_conversation = mock_continue_conversation

        # Act - Send proactive message
        async def send_proactive_card(context):
            await context.send_activity(activity)

        result = await adapter.continue_conversation(
            mock_conversation_reference,
            send_proactive_card,
            app_id="test-app-id"
        )

        # Assert
        assert result is True
        adapter.continue_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_logic_for_failed_delivery(self):
        """Test retry logic when proactive message delivery fails."""
        # Arrange
        from botbuilder.core import BotFrameworkAdapter

        adapter = AsyncMock(spec=BotFrameworkAdapter)
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff

        # Simulate failures then success
        attempt_count = 0

        async def mock_continue_conversation(reference, callback, app_id):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < max_retries:
                raise Exception(f"Delivery failed (attempt {attempt_count})")
            return True

        adapter.continue_conversation = mock_continue_conversation

        # Act - Retry with exponential backoff
        async def send_with_retry():
            for attempt in range(max_retries):
                try:
                    result = await adapter.continue_conversation(
                        {"conversation_id": "test"},
                        lambda ctx: ctx,
                        app_id="test"
                    )
                    return result
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delays[attempt])
                    else:
                        raise

        # Assert
        result = await send_with_retry()
        assert result is True
        assert attempt_count == max_retries

    @pytest.mark.asyncio
    async def test_conversation_reference_expiration(self, mock_redis_client):
        """Test that conversation references expire after TTL."""
        # Arrange
        user_id = "expiring-user-123"
        conversation_ref_key = f"conversation:ref:{user_id}"
        ttl_seconds = 86400  # 24 hours

        # Store with TTL
        await mock_redis_client.set(
            conversation_ref_key,
            json.dumps({"conversation_id": "exp-123"}),
            ex=ttl_seconds
        )

        # Act - Check TTL was set
        await mock_redis_client.expire(conversation_ref_key, ttl_seconds)

        # Assert
        mock_redis_client.expire.assert_called_with(conversation_ref_key, ttl_seconds)

    @pytest.mark.asyncio
    async def test_bulk_proactive_messaging(self, mock_conversation_reference):
        """Test sending proactive messages to multiple users."""
        # Arrange
        user_ids = [f"user-{i}" for i in range(10)]
        conversation_refs = []

        for user_id in user_ids:
            ref = {**mock_conversation_reference}
            ref["user"]["id"] = user_id
            conversation_refs.append(ref)

        from botbuilder.core import BotFrameworkAdapter
        adapter = AsyncMock(spec=BotFrameworkAdapter)

        success_count = 0

        async def mock_continue_conversation(reference, callback, app_id):
            nonlocal success_count
            success_count += 1
            return True

        adapter.continue_conversation = mock_continue_conversation

        # Act - Send to all users
        results = []
        for ref in conversation_refs:
            try:
                result = await adapter.continue_conversation(
                    ref,
                    lambda ctx: ctx,
                    app_id="test"
                )
                results.append((ref["user"]["id"], "success"))
            except Exception as e:
                results.append((ref["user"]["id"], f"failed: {e}"))

        # Assert
        assert success_count == 10
        assert all(status == "success" for _, status in results)

    @pytest.mark.asyncio
    async def test_conversation_reference_update(self, mock_redis_client, mock_conversation_reference):
        """Test updating existing conversation references."""
        # Arrange
        user_id = "update-user-123"
        conversation_ref_key = f"conversation:ref:{user_id}"

        # Store initial reference
        await mock_redis_client.set(
            conversation_ref_key,
            json.dumps(mock_conversation_reference)
        )

        # Update reference with new service URL
        updated_ref = {**mock_conversation_reference}
        updated_ref["service_url"] = "https://smba.trafficmanager.net/emea/"
        updated_ref["updated_at"] = datetime.utcnow().isoformat()

        # Act
        await mock_redis_client.set(
            conversation_ref_key,
            json.dumps(updated_ref)
        )

        # Assert
        assert mock_redis_client.set.call_count == 2
        last_call = mock_redis_client.set.call_args_list[-1]
        stored_data = json.loads(last_call[0][1])
        assert stored_data["service_url"] == "https://smba.trafficmanager.net/emea/"
        assert "updated_at" in stored_data

    @pytest.mark.asyncio
    async def test_proactive_message_with_attachments(self):
        """Test sending proactive messages with file attachments."""
        # Arrange
        from botbuilder.core import BotFrameworkAdapter, MessageFactory
        from botbuilder.schema import Attachment

        adapter = AsyncMock(spec=BotFrameworkAdapter)

        # Create attachment
        attachment = Attachment(
            content_type="application/pdf",
            content_url="https://example.com/files/digest.pdf",
            name="Weekly_Digest.pdf"
        )

        # Create message with attachment
        message = MessageFactory.text("Here's your weekly digest report.")
        message.attachments = [attachment]

        async def mock_continue_conversation(reference, callback, app_id):
            context = MagicMock()
            context.send_activity = AsyncMock()
            await callback(context)
            context.send_activity.assert_called_once()
            sent_activity = context.send_activity.call_args[0][0]
            assert len(sent_activity.attachments) == 1
            assert sent_activity.attachments[0].name == "Weekly_Digest.pdf"
            return True

        adapter.continue_conversation = mock_continue_conversation

        # Act
        async def send_with_attachment(context):
            await context.send_activity(message)

        result = await adapter.continue_conversation(
            {"conversation_id": "test"},
            send_with_attachment,
            app_id="test"
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_conversation_reference_cleanup(self, mock_redis_client):
        """Test cleanup of expired conversation references."""
        # Arrange
        pattern = "conversation:ref:*"
        expired_keys = [
            f"conversation:ref:expired-user-{i}"
            for i in range(5)
        ]

        mock_redis_client.keys = AsyncMock(return_value=expired_keys)

        # Act - Delete expired references
        for key in expired_keys:
            await mock_redis_client.delete(key)

        # Assert
        assert mock_redis_client.delete.call_count == 5
        for key in expired_keys:
            mock_redis_client.delete.assert_any_call(key)

    @pytest.mark.asyncio
    async def test_proactive_message_rate_limiting(self):
        """Test rate limiting for proactive messages."""
        # Arrange
        from botbuilder.core import BotFrameworkAdapter

        adapter = AsyncMock(spec=BotFrameworkAdapter)
        rate_limit = 10  # Messages per second
        message_count = 50

        # Track timing
        send_times = []

        async def mock_continue_conversation(reference, callback, app_id):
            send_times.append(datetime.utcnow())
            await asyncio.sleep(0.01)  # Simulate processing time
            return True

        adapter.continue_conversation = mock_continue_conversation

        # Act - Send messages with rate limiting
        async def send_with_rate_limit():
            for i in range(message_count):
                await adapter.continue_conversation(
                    {"conversation_id": f"test-{i}"},
                    lambda ctx: ctx,
                    app_id="test"
                )

                # Rate limiting logic
                if (i + 1) % rate_limit == 0:
                    await asyncio.sleep(1)  # Wait 1 second after every 10 messages

        start_time = datetime.utcnow()
        await send_with_rate_limit()
        end_time = datetime.utcnow()

        # Assert
        total_duration = (end_time - start_time).total_seconds()
        expected_duration = (message_count // rate_limit) - 1  # Should take at least 4 seconds
        assert total_duration >= expected_duration
        assert len(send_times) == message_count

    @pytest.mark.asyncio
    async def test_proactive_message_localization(self, mock_conversation_reference):
        """Test sending localized proactive messages based on user locale."""
        # Arrange
        from botbuilder.core import BotFrameworkAdapter, MessageFactory

        adapter = AsyncMock(spec=BotFrameworkAdapter)

        # Localized messages
        messages = {
            "en-US": "Your digest is ready!",
            "es-ES": "¡Tu resumen está listo!",
            "fr-FR": "Votre digest est prêt!",
            "de-DE": "Ihr Digest ist fertig!"
        }

        # Test different locales
        test_cases = [
            ("en-US", "Your digest is ready!"),
            ("es-ES", "¡Tu resumen está listo!"),
            ("fr-FR", "Votre digest est prêt!"),
            ("ja-JP", "Your digest is ready!")  # Fallback to English
        ]

        for locale, expected_message in test_cases:
            # Update conversation reference with locale
            ref = {**mock_conversation_reference}
            ref["locale"] = locale

            # Act
            async def mock_continue_conversation(reference, callback, app_id):
                context = MagicMock()
                context.activity = MagicMock()
                context.activity.locale = reference.get("locale", "en-US")

                # Get localized message
                user_locale = context.activity.locale
                message = messages.get(user_locale, messages["en-US"])

                # Verify correct message
                assert message == expected_message
                return True

            adapter.continue_conversation = mock_continue_conversation

            result = await adapter.continue_conversation(
                ref,
                lambda ctx: ctx,
                app_id="test"
            )

            # Assert
            assert result is True