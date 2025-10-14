"""
Unit tests for ProactiveMessagingService

Tests the Teams Bot proactive messaging functionality including:
- Sending cards to conversations
- Sending text messages
- Storing and retrieving conversation references
- Retry logic and error handling
"""

import pytest
import json
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from teams_bot.app.services.proactive_messaging import (
    ProactiveMessagingService,
    create_proactive_messaging_service
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ConversationReference,
    ChannelAccount,
    ConversationAccount
)


@pytest.fixture
def mock_app_credentials():
    """Mock Microsoft App credentials."""
    return {
        "app_id": "test-app-id-123",
        "app_password": "test-password-456",
        "tenant_id": "test-tenant-789"
    }


@pytest.fixture
def mock_conversation_data():
    """Mock conversation data for testing."""
    return {
        "conversation_id": "test-conversation-123",
        "service_url": "https://smba.trafficmanager.net/amer/",
        "tenant_id": "test-tenant-789",
        "user_id": "test-user-456",
        "user_email": "test.user@example.com",
        "channel_id": "msteams"
    }


@pytest.fixture
def mock_adaptive_card():
    """Mock adaptive card JSON."""
    return {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Test Card",
                "size": "Large",
                "weight": "Bolder"
            },
            {
                "type": "TextBlock",
                "text": "This is a test card for unit testing."
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Test Action",
                "data": {
                    "action": "test_action"
                }
            }
        ]
    }


@pytest.fixture
def mock_activity(mock_conversation_data):
    """Mock Teams activity."""
    activity = Activity(
        type=ActivityTypes.message,
        id="test-activity-123",
        channel_id=mock_conversation_data["channel_id"],
        service_url=mock_conversation_data["service_url"],
        text="Test message"
    )

    # Set conversation
    activity.conversation = ConversationAccount(
        id=mock_conversation_data["conversation_id"],
        tenant_id=mock_conversation_data["tenant_id"],
        conversation_type="personal"
    )

    # Set from property
    activity.from_property = ChannelAccount(
        id=mock_conversation_data["user_id"],
        name="Test User",
        aad_object_id="test-aad-123"
    )
    activity.from_property.additional_properties = {
        "email": mock_conversation_data["user_email"]
    }

    # Set recipient (bot)
    activity.recipient = ChannelAccount(
        id="test-bot-id",
        name="TalentWell"
    )

    return activity


@pytest.fixture
async def service(mock_app_credentials):
    """Create ProactiveMessagingService instance."""
    return ProactiveMessagingService(
        app_id=mock_app_credentials["app_id"],
        app_password=mock_app_credentials["app_password"],
        tenant_id=mock_app_credentials["tenant_id"]
    )


class TestProactiveMessagingService:
    """Test suite for ProactiveMessagingService."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_app_credentials):
        """Test service initialization with credentials."""
        service = ProactiveMessagingService(
            app_id=mock_app_credentials["app_id"],
            app_password=mock_app_credentials["app_password"],
            tenant_id=mock_app_credentials["tenant_id"]
        )

        assert service.app_id == mock_app_credentials["app_id"]
        assert service.app_password == mock_app_credentials["app_password"]
        assert service.tenant_id == mock_app_credentials["tenant_id"]
        assert service.adapter is not None

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.MicrosoftAppCredentials')
    async def test_send_card_to_conversation_success(
        self,
        mock_credentials,
        service,
        mock_conversation_data,
        mock_adaptive_card
    ):
        """Test successfully sending a card to a conversation."""
        # Mock the adapter's continue_conversation method
        service.adapter.continue_conversation = AsyncMock()

        # Call send_card_to_conversation
        result = await service.send_card_to_conversation(
            conversation_id=mock_conversation_data["conversation_id"],
            service_url=mock_conversation_data["service_url"],
            tenant_id=mock_conversation_data["tenant_id"],
            card_json=mock_adaptive_card
        )

        # Verify the result
        assert result is True

        # Verify adapter was called
        service.adapter.continue_conversation.assert_called_once()

        # Verify service URL was trusted
        mock_credentials.trust_service_url.assert_called_with(
            mock_conversation_data["service_url"]
        )

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.MicrosoftAppCredentials')
    async def test_send_text_message_success(
        self,
        mock_credentials,
        service,
        mock_conversation_data
    ):
        """Test successfully sending a text message."""
        # Mock the adapter
        service.adapter.continue_conversation = AsyncMock()

        # Send text message
        result = await service.send_text_message(
            conversation_id=mock_conversation_data["conversation_id"],
            service_url=mock_conversation_data["service_url"],
            text="Test message",
            tenant_id=mock_conversation_data["tenant_id"]
        )

        # Verify result
        assert result is True

        # Verify adapter was called
        service.adapter.continue_conversation.assert_called_once()

        # Verify service URL was trusted
        mock_credentials.trust_service_url.assert_called_with(
            mock_conversation_data["service_url"]
        )

    @pytest.mark.asyncio
    async def test_send_card_with_retry_on_failure(
        self,
        service,
        mock_conversation_data,
        mock_adaptive_card
    ):
        """Test retry logic when sending a card fails."""
        # Mock adapter to fail twice then succeed
        call_count = 0

        async def mock_continue_conversation(ref, callback, app_id):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            # Call the callback on success
            turn_context = Mock()
            turn_context.send_activity = AsyncMock(return_value=Mock(id="response-123"))
            await callback(turn_context)

        service.adapter.continue_conversation = mock_continue_conversation

        # Should succeed after retries
        with patch('teams_bot.app.services.proactive_messaging.MicrosoftAppCredentials'):
            result = await service.send_card_to_conversation(
                conversation_id=mock_conversation_data["conversation_id"],
                service_url=mock_conversation_data["service_url"],
                tenant_id=mock_conversation_data["tenant_id"],
                card_json=mock_adaptive_card
            )

        assert result is True
        assert call_count == 3  # Two failures + one success

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.get_connection_manager')
    async def test_store_conversation_reference(
        self,
        mock_get_connection_manager,
        service,
        mock_activity
    ):
        """Test storing a conversation reference from an activity."""
        # Mock database connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=123)

        mock_manager = AsyncMock()
        mock_manager.get_connection = MagicMock()
        mock_manager.get_connection().__aenter__.return_value = mock_conn
        mock_manager.get_connection().__aexit__.return_value = None

        mock_get_connection_manager.return_value = mock_manager

        # Store conversation reference
        ref_id = await service.store_conversation_reference(mock_activity)

        # Verify result
        assert ref_id == "123"

        # Verify database was called
        mock_conn.fetchval.assert_called_once()

        # Check the SQL query contains the right table
        call_args = mock_conn.fetchval.call_args[0][0]
        assert "INSERT INTO conversation_references" in call_args
        assert "ON CONFLICT (conversation_id) DO UPDATE" in call_args

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.get_connection_manager')
    async def test_get_conversation_reference(
        self,
        mock_get_connection_manager,
        service,
        mock_conversation_data
    ):
        """Test retrieving a stored conversation reference."""
        # Mock database response
        mock_row = {
            "id": 123,
            "conversation_id": mock_conversation_data["conversation_id"],
            "service_url": mock_conversation_data["service_url"],
            "tenant_id": mock_conversation_data["tenant_id"],
            "user_id": mock_conversation_data["user_id"],
            "user_email": mock_conversation_data["user_email"],
            "channel_id": mock_conversation_data["channel_id"],
            "bot_id": "test-bot-id",
            "reference_json": json.dumps({"test": "data"}),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_manager = AsyncMock()
        mock_manager.get_connection = MagicMock()
        mock_manager.get_connection().__aenter__.return_value = mock_conn
        mock_manager.get_connection().__aexit__.return_value = None

        mock_get_connection_manager.return_value = mock_manager

        # Get conversation reference
        result = await service.get_conversation_reference(
            mock_conversation_data["conversation_id"]
        )

        # Verify result
        assert result is not None
        assert result["conversation_id"] == mock_conversation_data["conversation_id"]
        assert result["service_url"] == mock_conversation_data["service_url"]
        assert result["user_email"] == mock_conversation_data["user_email"]
        assert result["reference_json"]["test"] == "data"

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.get_connection_manager')
    async def test_get_conversation_reference_not_found(
        self,
        mock_get_connection_manager,
        service
    ):
        """Test getting a conversation reference that doesn't exist."""
        # Mock database to return None
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_manager = AsyncMock()
        mock_manager.get_connection = MagicMock()
        mock_manager.get_connection().__aenter__.return_value = mock_conn
        mock_manager.get_connection().__aexit__.return_value = None

        mock_get_connection_manager.return_value = mock_manager

        # Try to get non-existent reference
        result = await service.get_conversation_reference("non-existent-id")

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.get_connection_manager')
    async def test_get_all_conversation_references(
        self,
        mock_get_connection_manager,
        service
    ):
        """Test getting all conversation references."""
        # Mock database response
        mock_rows = [
            {
                "id": 1,
                "conversation_id": "conv-1",
                "service_url": "https://service1.com",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "user_email": "user1@example.com",
                "channel_id": "msteams",
                "bot_id": "bot-1",
                "reference_json": json.dumps({"data": 1}),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "id": 2,
                "conversation_id": "conv-2",
                "service_url": "https://service2.com",
                "tenant_id": "tenant-2",
                "user_id": "user-2",
                "user_email": "user2@example.com",
                "channel_id": "msteams",
                "bot_id": "bot-2",
                "reference_json": json.dumps({"data": 2}),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_manager = AsyncMock()
        mock_manager.get_connection = MagicMock()
        mock_manager.get_connection().__aenter__.return_value = mock_conn
        mock_manager.get_connection().__aexit__.return_value = None

        mock_get_connection_manager.return_value = mock_manager

        # Get all references
        results = await service.get_all_conversation_references()

        # Verify results
        assert len(results) == 2
        assert results[0]["conversation_id"] == "conv-1"
        assert results[1]["conversation_id"] == "conv-2"

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.get_connection_manager')
    async def test_delete_conversation_reference(
        self,
        mock_get_connection_manager,
        service,
        mock_conversation_data
    ):
        """Test deleting a conversation reference."""
        # Mock database response
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        mock_manager = AsyncMock()
        mock_manager.get_connection = MagicMock()
        mock_manager.get_connection().__aenter__.return_value = mock_conn
        mock_manager.get_connection().__aexit__.return_value = None

        mock_get_connection_manager.return_value = mock_manager

        # Delete reference
        result = await service.delete_conversation_reference(
            mock_conversation_data["conversation_id"]
        )

        # Verify result
        assert result is True

        # Verify database was called
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0][0]
        assert "DELETE FROM conversation_references" in call_args

    @pytest.mark.asyncio
    async def test_extract_user_email(self, service, mock_activity):
        """Test extracting user email from activity."""
        # Test with email in additional_properties
        email = service._extract_user_email(mock_activity)
        assert email == "test.user@example.com"

        # Test with no email but AAD object ID
        mock_activity.from_property.additional_properties = {}
        email = service._extract_user_email(mock_activity)
        assert email == "test-aad-123"

        # Test with no from_property
        mock_activity.from_property = None
        email = service._extract_user_email(mock_activity)
        assert email == ""

    @pytest.mark.asyncio
    @patch.dict('os.environ', {
        'TEAMS_BOT_APP_ID': 'env-app-id',
        'TEAMS_BOT_APP_PASSWORD': 'env-password',
        'TEAMS_BOT_TENANT_ID': 'env-tenant'
    })
    async def test_create_service_factory(self):
        """Test factory function for creating service."""
        # Create service using factory
        service = await create_proactive_messaging_service()

        # Verify it uses environment variables
        assert service.app_id == 'env-app-id'
        assert service.app_password == 'env-password'
        assert service.tenant_id == 'env-tenant'

        # Test with explicit parameters
        service2 = await create_proactive_messaging_service(
            app_id="custom-id",
            app_password="custom-pass",
            tenant_id="custom-tenant"
        )

        assert service2.app_id == "custom-id"
        assert service2.app_password == "custom-pass"
        assert service2.tenant_id == "custom-tenant"

    @pytest.mark.asyncio
    async def test_create_service_factory_missing_credentials(self):
        """Test factory function raises error when credentials are missing."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="Microsoft App ID and Password are required"):
                await create_proactive_messaging_service()


class TestIntegrationScenarios:
    """Integration test scenarios for proactive messaging."""

    @pytest.mark.asyncio
    @patch('teams_bot.app.services.proactive_messaging.get_connection_manager')
    @patch('teams_bot.app.services.proactive_messaging.MicrosoftAppCredentials')
    async def test_store_and_send_workflow(
        self,
        mock_credentials,
        mock_get_connection_manager,
        service,
        mock_activity,
        mock_adaptive_card
    ):
        """Test complete workflow: store reference, retrieve it, and send a message."""
        # Setup database mocks
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=123)  # Store returns ID
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": 123,
            "conversation_id": "test-conversation-123",
            "service_url": "https://smba.trafficmanager.net/amer/",
            "tenant_id": "test-tenant-789",
            "user_id": "test-user-456",
            "user_email": "test.user@example.com",
            "channel_id": "msteams",
            "bot_id": "test-bot-id",
            "reference_json": json.dumps({}),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })

        mock_manager = AsyncMock()
        mock_manager.get_connection = MagicMock()
        mock_manager.get_connection().__aenter__.return_value = mock_conn
        mock_manager.get_connection().__aexit__.return_value = None

        mock_get_connection_manager.return_value = mock_manager

        # Mock adapter
        service.adapter.continue_conversation = AsyncMock()

        # Step 1: Store conversation reference
        ref_id = await service.store_conversation_reference(mock_activity)
        assert ref_id == "123"

        # Step 2: Retrieve the reference
        reference = await service.get_conversation_reference("test-conversation-123")
        assert reference is not None
        assert reference["user_email"] == "test.user@example.com"

        # Step 3: Send a proactive message using the reference
        result = await service.send_card_to_conversation(
            conversation_id=reference["conversation_id"],
            service_url=reference["service_url"],
            tenant_id=reference["tenant_id"],
            card_json=mock_adaptive_card
        )

        assert result is True
        service.adapter.continue_conversation.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])