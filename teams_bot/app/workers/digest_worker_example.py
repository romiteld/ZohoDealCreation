"""
Example Digest Worker using ProactiveMessagingService

This example demonstrates how to use the ProactiveMessagingService
to send digest results to Teams users proactively.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from teams_bot.app.services import create_proactive_messaging_service
from teams_bot.app.api.teams.adaptive_cards import create_digest_preview_card
from teams_bot.app.jobs.talentwell_curator import TalentWellCurator
from well_shared.database.connection import get_connection_manager

logger = logging.getLogger(__name__)


async def handle_digest_complete(message_data: Dict[str, Any]):
    """
    Handle a completed digest and send it to the user via Teams.

    Args:
        message_data: Message containing digest data and conversation info
            Expected keys:
            - conversation_id: Teams conversation ID
            - service_url: Teams service URL
            - tenant_id: Azure AD tenant ID
            - user_email: User's email address
            - digest_request_id: ID of the digest request
            - audience: Target audience (advisors/c_suite/global)
    """
    try:
        # Initialize proactive messaging service
        proactive_messaging = await create_proactive_messaging_service()

        # Get digest results from database
        manager = await get_connection_manager()
        async with manager.get_connection() as conn:
            # Fetch digest request details
            digest = await conn.fetchrow("""
                SELECT
                    request_id,
                    user_id,
                    user_email,
                    audience,
                    cards_metadata,
                    cards_generated,
                    total_candidates,
                    execution_time_ms,
                    status
                FROM teams_digest_requests
                WHERE request_id = $1
            """, message_data["digest_request_id"])

            if not digest:
                logger.error(f"Digest request not found: {message_data['digest_request_id']}")
                return

            # Check if digest was successful
            if digest["status"] != "completed":
                logger.warning(
                    f"Digest request {message_data['digest_request_id']} "
                    f"has status {digest['status']}, not sending"
                )
                return

            # Parse cards metadata
            import json
            cards_metadata = json.loads(digest["cards_metadata"]) if digest["cards_metadata"] else []

        # Create adaptive card with digest preview
        result_card = create_digest_preview_card(
            cards_metadata=cards_metadata,
            audience=digest["audience"],
            request_id=digest["request_id"]
        )

        # Send the card to the user's conversation
        success = await proactive_messaging.send_card_to_conversation(
            conversation_id=message_data["conversation_id"],
            service_url=message_data["service_url"],
            tenant_id=message_data.get("tenant_id"),
            card_json=result_card["content"],
            correlation_id=message_data["digest_request_id"]
        )

        if success:
            logger.info(
                f"Successfully sent digest {message_data['digest_request_id']} "
                f"to {message_data['user_email']}"
            )

            # Update delivery status in database
            async with manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE teams_digest_requests
                    SET delivered_at = CURRENT_TIMESTAMP
                    WHERE request_id = $1
                """, message_data["digest_request_id"])
        else:
            logger.error(
                f"Failed to send digest {message_data['digest_request_id']} "
                f"to {message_data['user_email']}"
            )

    except Exception as e:
        logger.error(
            f"Error handling digest completion for {message_data.get('digest_request_id')}: {e}",
            exc_info=True
        )


async def send_weekly_digest_to_subscribers():
    """
    Send weekly digests to all active subscribers.

    This function:
    1. Queries for active subscriptions
    2. Generates digests for each subscriber
    3. Sends digests via proactive messaging
    """
    try:
        # Initialize services
        proactive_messaging = await create_proactive_messaging_service()
        curator = TalentWellCurator()
        await curator.initialize()

        # Get database connection
        manager = await get_connection_manager()
        async with manager.get_connection() as conn:
            # Get active subscriptions with stored conversation references
            subscriptions = await conn.fetch("""
                SELECT
                    p.user_id,
                    p.user_email,
                    p.delivery_email,
                    p.default_audience,
                    p.max_candidates_per_digest,
                    c.conversation_id,
                    c.service_url,
                    c.tenant_id
                FROM teams_user_preferences p
                INNER JOIN conversation_references c ON c.user_email = p.user_email
                WHERE p.subscription_active = true
                    AND p.digest_frequency = 'weekly'
                    AND c.conversation_id IS NOT NULL
                ORDER BY p.user_id
            """)

            logger.info(f"Found {len(subscriptions)} active weekly digest subscriptions")

            # Process each subscription
            for sub in subscriptions:
                try:
                    logger.info(f"Processing digest for {sub['user_email']}")

                    # Generate digest
                    result = await curator.run_weekly_digest(
                        audience=sub["default_audience"],
                        max_cards=sub["max_candidates_per_digest"],
                        dry_run=False
                    )

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

                    # Create preview card
                    digest_card = create_digest_preview_card(
                        cards_metadata=cards_metadata,
                        audience=sub["default_audience"],
                        request_id=None  # No specific request ID for scheduled digests
                    )

                    # Send via proactive messaging
                    success = await proactive_messaging.send_card_to_conversation(
                        conversation_id=sub["conversation_id"],
                        service_url=sub["service_url"],
                        tenant_id=sub["tenant_id"],
                        card_json=digest_card["content"],
                        correlation_id=f"weekly-{sub['user_id']}-{datetime.now().isoformat()}"
                    )

                    if success:
                        logger.info(f"Sent weekly digest to {sub['user_email']}")

                        # Track delivery
                        await conn.execute("""
                            INSERT INTO weekly_digest_deliveries (
                                user_id,
                                user_email,
                                delivery_email,
                                audience,
                                cards_generated,
                                delivered_at,
                                success
                            ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, true)
                        """, sub["user_id"], sub["user_email"], sub["delivery_email"],
                            sub["default_audience"], len(cards_metadata))
                    else:
                        logger.error(f"Failed to send digest to {sub['user_email']}")

                except Exception as sub_error:
                    logger.error(
                        f"Error processing subscription for {sub['user_email']}: {sub_error}",
                        exc_info=True
                    )

        await curator.close()
        logger.info("Completed weekly digest distribution")

    except Exception as e:
        logger.error(f"Error in weekly digest distribution: {e}", exc_info=True)


async def send_proactive_notification(
    user_email: str,
    message: str,
    card_json: Dict[str, Any] = None
):
    """
    Send a proactive notification to a specific user.

    Args:
        user_email: Email of the user to notify
        message: Text message to send (used if card_json is None)
        card_json: Optional adaptive card JSON to send instead of text
    """
    try:
        # Initialize service
        proactive_messaging = await create_proactive_messaging_service()

        # Get conversation reference for user
        manager = await get_connection_manager()
        async with manager.get_connection() as conn:
            ref = await conn.fetchrow("""
                SELECT
                    conversation_id,
                    service_url,
                    tenant_id
                FROM conversation_references
                WHERE user_email = $1
                ORDER BY updated_at DESC
                LIMIT 1
            """, user_email)

            if not ref:
                logger.warning(f"No conversation reference found for {user_email}")
                return False

        # Send message or card
        if card_json:
            success = await proactive_messaging.send_card_to_conversation(
                conversation_id=ref["conversation_id"],
                service_url=ref["service_url"],
                tenant_id=ref["tenant_id"],
                card_json=card_json
            )
        else:
            success = await proactive_messaging.send_text_message(
                conversation_id=ref["conversation_id"],
                service_url=ref["service_url"],
                text=message,
                tenant_id=ref["tenant_id"]
            )

        if success:
            logger.info(f"Sent proactive notification to {user_email}")
        else:
            logger.error(f"Failed to send notification to {user_email}")

        return success

    except Exception as e:
        logger.error(f"Error sending proactive notification to {user_email}: {e}", exc_info=True)
        return False


# Example usage for testing
async def main():
    """Example usage of the digest worker functions."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example 1: Send a test notification
    await send_proactive_notification(
        user_email="test.user@emailthewell.com",
        message="This is a test proactive notification from the digest worker!"
    )

    # Example 2: Handle a digest completion (would typically come from message queue)
    test_message = {
        "conversation_id": "test-conversation-123",
        "service_url": "https://smba.trafficmanager.net/amer/",
        "tenant_id": os.getenv("TEAMS_BOT_TENANT_ID"),
        "user_email": "test.user@emailthewell.com",
        "digest_request_id": "test-digest-456",
        "audience": "global"
    }

    # await handle_digest_complete(test_message)

    # Example 3: Send weekly digests (would typically be scheduled)
    # await send_weekly_digest_to_subscribers()


if __name__ == "__main__":
    asyncio.run(main())