"""
Proactive Messaging Service for Teams Bot Framework

This service enables sending messages to Teams users without an incoming request,
storing conversation references for later use, and managing proactive communications.
"""

import logging
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid

# Bot Framework imports
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
    MessageFactory,
    CardFactory
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ConversationReference,
    ChannelAccount
)
from botframework.connector.auth import MicrosoftAppCredentials

# Database imports
import asyncpg
from well_shared.database.connection import get_connection_manager

# Error handling
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)


class ProactiveMessagingService:
    """
    Service for sending proactive messages to Teams users.

    Features:
    - Send adaptive cards to conversations
    - Send text messages to conversations
    - Store and retrieve conversation references
    - Retry logic for failed deliveries
    - Correlation ID tracking for debugging
    """

    def __init__(
        self,
        app_id: str,
        app_password: str,
        tenant_id: Optional[str] = None
    ):
        """
        Initialize the proactive messaging service.

        Args:
            app_id: Microsoft App ID for the bot
            app_password: Microsoft App Password for the bot
            tenant_id: Optional tenant ID for single-tenant apps
        """
        self.app_id = app_id
        self.app_password = app_password
        self.tenant_id = tenant_id

        # Create Bot Framework adapter
        settings = BotFrameworkAdapterSettings(
            app_id=app_id,
            app_password=app_password,
            channel_auth_tenant=tenant_id  # For single-tenant apps
        )
        self.adapter = BotFrameworkAdapter(settings)

        # Configure Microsoft App credentials
        MicrosoftAppCredentials.microsoft_app_id = app_id
        MicrosoftAppCredentials.microsoft_app_password = app_password

        logger.info(f"ProactiveMessagingService initialized for app_id: {app_id}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def send_card_to_conversation(
        self,
        conversation_id: str,
        service_url: str,
        tenant_id: Optional[str],
        card_json: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Send an adaptive card to a Teams conversation.

        Args:
            conversation_id: Teams conversation ID
            service_url: Service URL for the Teams channel
            tenant_id: Tenant ID for the conversation
            card_json: Adaptive card JSON content
            correlation_id: Optional correlation ID for tracking

        Returns:
            True if successful, False otherwise
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        logger.info(
            f"[{correlation_id}] Sending card to conversation {conversation_id} "
            f"via {service_url}"
        )

        try:
            # Trust the service URL
            MicrosoftAppCredentials.trust_service_url(service_url)

            # Create conversation reference
            conversation_ref = ConversationReference(
                channel_id="msteams",
                service_url=service_url,
                conversation={
                    "id": conversation_id,
                    "tenant_id": tenant_id or self.tenant_id,
                    "conversation_type": "personal"
                },
                bot={
                    "id": self.app_id,
                    "name": "TalentWell"
                }
            )

            # Success flag to capture result
            send_success = False
            send_error = None

            async def send_activity_callback(turn_context: TurnContext):
                """Callback to send the card within the conversation context."""
                nonlocal send_success, send_error
                try:
                    # Create adaptive card attachment
                    attachment = CardFactory.adaptive_card(card_json)

                    # Create message activity with the card
                    message = MessageFactory.attachment(attachment)

                    # Send the activity
                    response = await turn_context.send_activity(message)

                    logger.info(
                        f"[{correlation_id}] Card sent successfully. "
                        f"Response ID: {response.id if response else 'None'}"
                    )
                    send_success = True

                except Exception as e:
                    logger.error(
                        f"[{correlation_id}] Error in send callback: {e}",
                        exc_info=True
                    )
                    send_error = e
                    raise

            # Use adapter's continue_conversation to send proactive message
            await self.adapter.continue_conversation(
                conversation_ref,
                send_activity_callback,
                self.app_id
            )

            if send_error:
                raise send_error

            return send_success

        except Exception as e:
            logger.error(
                f"[{correlation_id}] Failed to send card to conversation: {e}",
                exc_info=True
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def send_text_message(
        self,
        conversation_id: str,
        service_url: str,
        text: str,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Send a text message to a Teams conversation.

        Args:
            conversation_id: Teams conversation ID
            service_url: Service URL for the Teams channel
            text: Text message to send
            tenant_id: Optional tenant ID for the conversation
            correlation_id: Optional correlation ID for tracking

        Returns:
            True if successful, False otherwise
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        logger.info(
            f"[{correlation_id}] Sending text message to conversation {conversation_id}"
        )

        try:
            # Trust the service URL
            MicrosoftAppCredentials.trust_service_url(service_url)

            # Create conversation reference
            conversation_ref = ConversationReference(
                channel_id="msteams",
                service_url=service_url,
                conversation={
                    "id": conversation_id,
                    "tenant_id": tenant_id or self.tenant_id,
                    "conversation_type": "personal"
                },
                bot={
                    "id": self.app_id,
                    "name": "TalentWell"
                }
            )

            # Success flag
            send_success = False
            send_error = None

            async def send_text_callback(turn_context: TurnContext):
                """Callback to send text within the conversation context."""
                nonlocal send_success, send_error
                try:
                    # Create and send text message
                    message = MessageFactory.text(text)
                    response = await turn_context.send_activity(message)

                    logger.info(
                        f"[{correlation_id}] Text message sent successfully. "
                        f"Response ID: {response.id if response else 'None'}"
                    )
                    send_success = True

                except Exception as e:
                    logger.error(
                        f"[{correlation_id}] Error sending text: {e}",
                        exc_info=True
                    )
                    send_error = e
                    raise

            # Use adapter's continue_conversation
            await self.adapter.continue_conversation(
                conversation_ref,
                send_text_callback,
                self.app_id
            )

            if send_error:
                raise send_error

            return send_success

        except Exception as e:
            logger.error(
                f"[{correlation_id}] Failed to send text message: {e}",
                exc_info=True
            )
            raise

    async def store_conversation_reference(
        self,
        activity: Activity
    ) -> str:
        """
        Store a conversation reference from an incoming activity.

        Args:
            activity: Bot Framework Activity containing conversation info

        Returns:
            Conversation reference ID
        """
        try:
            # Extract user email from activity
            user_email = self._extract_user_email(activity)

            # Create conversation reference from activity
            conversation_ref = TurnContext.get_conversation_reference(activity)

            # Serialize conversation reference
            reference_json = {
                "channel_id": conversation_ref.channel_id,
                "service_url": conversation_ref.service_url,
                "conversation": {
                    "id": conversation_ref.conversation.id if conversation_ref.conversation else None,
                    "tenant_id": getattr(conversation_ref.conversation, 'tenant_id', None) if conversation_ref.conversation else None,
                    "conversation_type": getattr(conversation_ref.conversation, 'conversation_type', 'personal') if conversation_ref.conversation else 'personal'
                },
                "user": {
                    "id": conversation_ref.user.id if conversation_ref.user else None,
                    "name": conversation_ref.user.name if conversation_ref.user else None,
                    "aad_object_id": getattr(conversation_ref.user, 'aad_object_id', None) if conversation_ref.user else None
                },
                "bot": {
                    "id": conversation_ref.bot.id if conversation_ref.bot else self.app_id,
                    "name": conversation_ref.bot.name if conversation_ref.bot else "TalentWell"
                },
                "locale": conversation_ref.locale,
                "activity_id": conversation_ref.activity_id
            }

            # Get database connection
            manager = await get_connection_manager()
            async with manager.get_connection() as conn:
                # Upsert conversation reference
                result = await conn.fetchval("""
                    INSERT INTO conversation_references (
                        conversation_id,
                        service_url,
                        tenant_id,
                        user_id,
                        user_email,
                        channel_id,
                        bot_id,
                        reference_json,
                        created_at,
                        updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        service_url = EXCLUDED.service_url,
                        tenant_id = EXCLUDED.tenant_id,
                        user_id = EXCLUDED.user_id,
                        user_email = EXCLUDED.user_email,
                        reference_json = EXCLUDED.reference_json,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """,
                    conversation_ref.conversation.id if conversation_ref.conversation else None,
                    conversation_ref.service_url,
                    getattr(conversation_ref.conversation, 'tenant_id', None) if conversation_ref.conversation else None,
                    conversation_ref.user.id if conversation_ref.user else None,
                    user_email,
                    conversation_ref.channel_id,
                    self.app_id,
                    json.dumps(reference_json)
                )

                logger.info(
                    f"Stored conversation reference {result} for "
                    f"conversation {conversation_ref.conversation.id if conversation_ref.conversation else 'None'}"
                )

                return str(result)

        except Exception as e:
            logger.error(f"Failed to store conversation reference: {e}", exc_info=True)
            raise

    async def get_conversation_reference(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a stored conversation reference.

        Args:
            conversation_id: Teams conversation ID

        Returns:
            Conversation reference data or None if not found
        """
        try:
            # Get database connection
            manager = await get_connection_manager()
            async with manager.get_connection() as conn:
                # Fetch conversation reference
                row = await conn.fetchrow("""
                    SELECT
                        id,
                        conversation_id,
                        service_url,
                        tenant_id,
                        user_id,
                        user_email,
                        channel_id,
                        bot_id,
                        reference_json,
                        created_at,
                        updated_at
                    FROM conversation_references
                    WHERE conversation_id = $1
                """, conversation_id)

                if not row:
                    logger.warning(f"No conversation reference found for {conversation_id}")
                    return None

                # Parse and return reference data
                reference_data = {
                    "id": str(row["id"]),
                    "conversation_id": row["conversation_id"],
                    "service_url": row["service_url"],
                    "tenant_id": row["tenant_id"],
                    "user_id": row["user_id"],
                    "user_email": row["user_email"],
                    "channel_id": row["channel_id"],
                    "bot_id": row["bot_id"],
                    "reference_json": json.loads(row["reference_json"]) if row["reference_json"] else {},
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                }

                logger.info(f"Retrieved conversation reference for {conversation_id}")
                return reference_data

        except Exception as e:
            logger.error(
                f"Failed to retrieve conversation reference for {conversation_id}: {e}",
                exc_info=True
            )
            return None

    async def get_all_conversation_references(
        self,
        user_email: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all stored conversation references, optionally filtered by user.

        Args:
            user_email: Optional email to filter by
            limit: Maximum number of references to return

        Returns:
            List of conversation reference data
        """
        try:
            # Get database connection
            manager = await get_connection_manager()
            async with manager.get_connection() as conn:
                # Build query
                if user_email:
                    rows = await conn.fetch("""
                        SELECT * FROM conversation_references
                        WHERE user_email = $1
                        ORDER BY updated_at DESC
                        LIMIT $2
                    """, user_email, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM conversation_references
                        ORDER BY updated_at DESC
                        LIMIT $1
                    """, limit)

                # Convert rows to dicts
                references = []
                for row in rows:
                    references.append({
                        "id": str(row["id"]),
                        "conversation_id": row["conversation_id"],
                        "service_url": row["service_url"],
                        "tenant_id": row["tenant_id"],
                        "user_id": row["user_id"],
                        "user_email": row["user_email"],
                        "channel_id": row["channel_id"],
                        "bot_id": row["bot_id"],
                        "reference_json": json.loads(row["reference_json"]) if row["reference_json"] else {},
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                    })

                logger.info(f"Retrieved {len(references)} conversation references")
                return references

        except Exception as e:
            logger.error(f"Failed to get conversation references: {e}", exc_info=True)
            return []

    async def delete_conversation_reference(
        self,
        conversation_id: str
    ) -> bool:
        """
        Delete a stored conversation reference.

        Args:
            conversation_id: Teams conversation ID to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            # Get database connection
            manager = await get_connection_manager()
            async with manager.get_connection() as conn:
                # Delete reference
                result = await conn.execute("""
                    DELETE FROM conversation_references
                    WHERE conversation_id = $1
                """, conversation_id)

                deleted = result.split()[-1] != "0"

                if deleted:
                    logger.info(f"Deleted conversation reference for {conversation_id}")
                else:
                    logger.warning(f"No conversation reference found to delete for {conversation_id}")

                return deleted

        except Exception as e:
            logger.error(
                f"Failed to delete conversation reference for {conversation_id}: {e}",
                exc_info=True
            )
            return False

    def _extract_user_email(self, activity: Activity) -> str:
        """
        Extract user email from Teams activity.

        Args:
            activity: Bot Framework Activity

        Returns:
            User email address or empty string if not found
        """
        if not activity or not activity.from_property:
            return ""

        # Extract from additional_properties (correct approach for Teams)
        props = getattr(activity.from_property, "additional_properties", {}) or {}
        user_email = props.get("email") or props.get("userPrincipalName") or ""

        # Fallback to aad_object_id if no email found
        if not user_email:
            user_email = getattr(activity.from_property, "aad_object_id", "")
            if user_email:
                logger.warning(
                    f"Could not extract email from Teams activity, using AAD object ID: {user_email}"
                )

        return user_email


# Factory function for creating service instances
async def create_proactive_messaging_service(
    app_id: Optional[str] = None,
    app_password: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> ProactiveMessagingService:
    """
    Factory function to create a ProactiveMessagingService instance.

    Args:
        app_id: Microsoft App ID (defaults to environment variable)
        app_password: Microsoft App Password (defaults to environment variable)
        tenant_id: Tenant ID (defaults to environment variable)

    Returns:
        Configured ProactiveMessagingService instance
    """
    import os

    # Use provided values or fall back to environment variables
    app_id = app_id or os.getenv("TEAMS_BOT_APP_ID")
    app_password = app_password or os.getenv("TEAMS_BOT_APP_PASSWORD")
    tenant_id = tenant_id or os.getenv("TEAMS_BOT_TENANT_ID")

    if not app_id or not app_password:
        raise ValueError(
            "Microsoft App ID and Password are required. "
            "Set TEAMS_BOT_APP_ID and TEAMS_BOT_APP_PASSWORD environment variables."
        )

    return ProactiveMessagingService(app_id, app_password, tenant_id)


# Export main classes and functions
__all__ = [
    'ProactiveMessagingService',
    'create_proactive_messaging_service'
]