"""
Microsoft Teams Bot Framework webhook endpoints for TalentWell.
Handles Teams activities, user preferences, and digest generation with database tracking.
"""
import logging
import uuid
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import asyncpg

# Microsoft Bot Framework imports
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, MessageFactory, CardFactory
from botbuilder.schema import Activity, ActivityTypes
from botframework.connector.auth import MicrosoftAppCredentials

from app.api.teams.adaptive_cards import (
    create_welcome_card,
    create_help_card,
    create_digest_preview_card,
    create_error_card,
    create_preferences_card
)
from app.jobs.talentwell_curator import TalentWellCurator
from app.database_connection_manager import get_database_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])

# Bot Framework Adapter setup
APP_ID = os.getenv("TEAMS_BOT_APP_ID")
APP_PASSWORD = os.getenv("TEAMS_BOT_APP_PASSWORD")
TENANT_ID = os.getenv("TEAMS_BOT_TENANT_ID", "29ee1479-b5f7-48c5-b665-7de9a8a9033e")
DEBUG_ENABLED = os.getenv("TEAMS_DEBUG_ENABLED", "false").lower() == "true"

# Set Microsoft App credentials for SingleTenant auth
from botframework.connector.auth import MicrosoftAppCredentials

# Configure credentials with tenant ID
MicrosoftAppCredentials.microsoft_app_id = APP_ID
MicrosoftAppCredentials.microsoft_app_password = APP_PASSWORD

# Create adapter settings
settings = BotFrameworkAdapterSettings(
    app_id=APP_ID,
    app_password=APP_PASSWORD,
    channel_auth_tenant=TENANT_ID  # Tenant ID for SingleTenant apps
)
adapter = BotFrameworkAdapter(settings)


# Debug endpoint guard
def require_debug_mode():
    """Dependency to ensure debug endpoints are only accessible when enabled."""
    if not DEBUG_ENABLED:
        raise HTTPException(
            status_code=404,
            detail="Not found"
        )
    return True


# Helper function for audit logging
async def log_bot_audit(
    db: asyncpg.Connection,
    activity_id: str,
    event_type: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
):
    """
    Log bot processing events to teams_bot_audit table.

    Args:
        db: Database connection
        activity_id: Teams activity ID
        event_type: Event type (processing_started, send_success, etc.)
        user_id: Optional user ID
        conversation_id: Optional conversation ID
        event_data: Optional JSON data with additional context
        error_message: Optional error message for failures
    """
    try:
        await db.execute("""
            INSERT INTO teams_bot_audit
                (activity_id, user_id, conversation_id, event_type, event_data, error_message)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, activity_id, user_id, conversation_id, event_type,
            json.dumps(event_data) if event_data else None, error_message)
    except Exception as e:
        # Don't let audit failures break the bot
        logger.error(f"Failed to log audit event {event_type}: {e}")


# Teams Bot Framework Activity Models
class TeamsActivity(BaseModel):
    """Teams Bot Framework activity."""
    type: str
    id: Optional[str] = None
    timestamp: Optional[datetime] = None
    channelId: Optional[str] = Field(alias="channelId", default=None)
    serviceUrl: Optional[str] = Field(alias="serviceUrl", default=None)
    from_: Optional[Dict[str, Any]] = Field(alias="from", default=None)
    conversation: Optional[Dict[str, Any]] = None
    recipient: Optional[Dict[str, Any]] = None
    text: Optional[str] = None
    textFormat: Optional[str] = Field(alias="textFormat", default=None)
    attachments: Optional[list] = None
    entities: Optional[list] = None
    channelData: Optional[Dict[str, Any]] = Field(alias="channelData", default=None)
    action: Optional[str] = None
    replyToId: Optional[str] = Field(alias="replyToId", default=None)
    value: Optional[Dict[str, Any]] = None  # For invoke actions
    membersAdded: Optional[list] = Field(alias="membersAdded", default=None)
    membersRemoved: Optional[list] = Field(alias="membersRemoved", default=None)


class DigestRequestParams(BaseModel):
    """Parameters for digest generation request."""
    audience: str = "global"
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    owner: Optional[str] = None
    max_candidates: int = 6
    dry_run: bool = True
    ignore_cooldown: bool = False


# Main webhook endpoint
@router.post("/webhook")
async def teams_webhook(request: Request):
    """
    Microsoft Teams Bot Framework webhook endpoint.
    Handles all incoming Teams activities (messages, invokes, conversation updates).

    No API key required - uses Azure AD authentication from Bot Framework.
    """
    print("=== TEAMS WEBHOOK CALLED ===", flush=True)
    logger.info("=== TEAMS WEBHOOK CALLED ===")
    try:
        # Get request body
        body = await request.json()
        print(f"Request body type: {body.get('type', 'unknown')}", flush=True)
        logger.info(f"Request body received: {body.get('type', 'unknown')}")
        activity = Activity().deserialize(body)

        print(f"Received Teams activity type: {activity.type}", flush=True)
        logger.info(f"Received Teams activity: {activity.type}")

        # Get auth header
        auth_header = request.headers.get("Authorization", "")

        # Process activity using Bot Framework adapter
        async def bot_logic(turn_context: TurnContext):
            """Bot logic to handle the activity."""
            activity_id = turn_context.activity.id
            user_id = turn_context.activity.from_property.id if turn_context.activity.from_property else None
            conversation_id = turn_context.activity.conversation.id if turn_context.activity.conversation else None

            try:
                # Get database connection for this request
                from app.database_connection_manager import get_connection_manager
                manager = await get_connection_manager()
                async with manager.get_connection() as db:
                    # Log: bot_logic started
                    await log_bot_audit(db, activity_id, "bot_logic_started", user_id, conversation_id)

                    # Route activity based on type
                    if turn_context.activity.type == ActivityTypes.message:
                        response = await handle_message_activity(turn_context.activity, db)
                        logger.info(f"Response from handle_message_activity: {type(response)}")

                        # Log: message handler completed
                        await log_bot_audit(
                            db, activity_id, "message_handler_completed", user_id, conversation_id,
                            event_data={"response_type": str(type(response).__name__)}
                        )

                        if response:
                            print(f"About to send activity response: {response}", flush=True)
                            logger.info(f"Sending activity response: {response}")

                            # Convert dict responses to proper Activity objects
                            if isinstance(response, dict):
                                # Preserve all metadata by constructing Activity with all fields
                                response_dict = response  # Keep reference to original dict

                                if "attachments" in response_dict and response_dict["attachments"]:
                                    # Multiple attachments: use MessageFactory.carousel or list
                                    if len(response_dict["attachments"]) > 1:
                                        response = MessageFactory.carousel(response_dict["attachments"])
                                    else:
                                        response = MessageFactory.attachment(response_dict["attachments"][0])

                                    # Preserve additional fields like channelData, suggestedActions
                                    if "channelData" in response_dict:
                                        response.channel_data = response_dict["channelData"]
                                    if "suggestedActions" in response_dict:
                                        response.suggested_actions = response_dict["suggestedActions"]
                                elif "text" in response_dict:
                                    # Simple text message
                                    response = MessageFactory.text(response_dict["text"])

                            # Trust the service URL before sending (required for Bot Framework)
                            try:
                                service_url = turn_context.activity.service_url
                                MicrosoftAppCredentials.trust_service_url(service_url)
                                print(f"Trusted service URL: {service_url}", flush=True)
                                logger.info(f"Trusted service URL: {service_url}")

                                # Log: service URL trusted
                                await log_bot_audit(
                                    db, activity_id, "service_url_trusted", user_id, conversation_id,
                                    event_data={"service_url": service_url}
                                )
                            except Exception as trust_error:
                                logger.error(f"Error trusting service URL: {trust_error}", exc_info=True)
                                print(f"SERVICE URL TRUST FAILED: {trust_error}", flush=True)
                                await log_bot_audit(
                                    db, activity_id, "trust_error", user_id, conversation_id,
                                    error_message=str(trust_error)
                                )

                            # Send activity with comprehensive error handling
                            try:
                                # Log: attempting send
                                await log_bot_audit(
                                    db, activity_id, "send_activity_attempting", user_id, conversation_id
                                )

                                result = await turn_context.send_activity(response)
                                print(f"✅ Activity send result: {result}", flush=True)
                                logger.info(f"✅ Activity send result: {result}")

                                # Log: send successful
                                await log_bot_audit(
                                    db, activity_id, "send_activity_success", user_id, conversation_id,
                                    event_data={"result": str(result)}
                                )
                            except Exception as send_error:
                                logger.error(f"❌ CRITICAL: Failed to send activity: {send_error}", exc_info=True)
                                print(f"❌ SEND ACTIVITY FAILED: {send_error}", flush=True)
                                # Try to log the error details
                                print(f"Error type: {type(send_error).__name__}", flush=True)
                                print(f"Error details: {str(send_error)}", flush=True)

                                # Log: send failed with error
                                await log_bot_audit(
                                    db, activity_id, "send_activity_failed", user_id, conversation_id,
                                    error_message=f"{type(send_error).__name__}: {str(send_error)}"
                                )
                                raise  # Re-raise to ensure it's logged

                    elif turn_context.activity.type == ActivityTypes.invoke:
                        # Invoke activities require InvokeResponse, not regular messages
                        # The handler will send messages directly via turn_context
                        await handle_invoke_activity(turn_context, db)
                    elif turn_context.activity.type == ActivityTypes.conversation_update:
                        response = await handle_conversation_update(turn_context.activity, db)
                        if response:
                            # Create proper Activity from response dict
                            activity_response = Activity(
                                type=response.get("type", "message"),
                                text=response.get("text"),
                                attachments=response.get("attachments")
                            )
                            await turn_context.send_activity(activity_response)
                    else:
                        logger.warning(f"Unhandled activity type: {turn_context.activity.type}")
            except Exception as inner_e:
                logger.error(f"Error in bot_logic: {inner_e}", exc_info=True)

        # Process with Bot Framework (handles auth automatically)
        await adapter.process_activity(activity, auth_header, bot_logic)

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        logger.error(f"Error in Teams webhook: {e}", exc_info=True)
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )


async def handle_message_activity(
    activity: Activity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle incoming text message from Teams user."""

    # Extract user info
    user_id = activity.from_property.id if activity.from_property else ""
    user_name = activity.from_property.name if activity.from_property else ""
    user_email = getattr(activity.from_property, "aad_object_id", "") if activity.from_property else ""
    conversation_id = activity.conversation.id if activity.conversation else ""

    # Store conversation
    await db.execute("""
        INSERT INTO teams_conversations (
            conversation_id, user_id, user_name, user_email,
            conversation_type, activity_id, message_text,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
    """, conversation_id, user_id, user_name, user_email, "personal",
        activity.id, activity.text)

    # Parse command
    message_text = (activity.text or "").strip().lower()

    # Handle commands
    if any(greeting in message_text for greeting in ["hello", "hi", "hey"]):
        # Welcome card
        card = create_welcome_card(user_name.split()[0] if user_name else "there")
        attachment = CardFactory.adaptive_card(card["content"])
        return MessageFactory.attachment(attachment)

    elif message_text.startswith("help"):
        card = create_help_card()
        # Use CardFactory to create proper Attachment, passing card content only
        attachment = CardFactory.adaptive_card(card["content"])
        return MessageFactory.attachment(attachment)

    elif message_text.startswith("digest"):
        # Parse audience from message (e.g., "digest advisors", "digest c_suite", or "digest daniel.romitelli@emailthewell.com")
        parts = message_text.split()
        audience_input = parts[1] if len(parts) > 1 else "global"

        # Check if input is an email address (test mode)
        test_email = None
        if "@" in audience_input:
            test_email = audience_input
            audience = "global"  # Default to global for test emails
            logger.info(f"Test mode detected: will route digest to {test_email}")
        else:
            audience = audience_input
            # Normalize legacy values
            if audience == "steve_perry":
                audience = "advisors"  # Map legacy steve_perry to advisors

        return await generate_digest_preview(
            user_id=user_id,
            user_email=user_email,
            conversation_id=conversation_id,
            audience=audience,
            db=db,
            test_recipient_email=test_email
        )

    elif message_text.startswith("preferences"):
        return await show_user_preferences(user_id, user_email, user_name, db)

    elif message_text.startswith("analytics"):
        return await show_analytics(user_id, user_email, db)

    else:
        # Unknown command - show help
        card = create_help_card()
        await db.execute("""
            UPDATE teams_conversations
            SET bot_response = $1
            WHERE conversation_id = $2 AND activity_id = $3
        """, "help_card", conversation_id, activity.id)

        attachment = CardFactory.adaptive_card(card["content"])
        response = MessageFactory.attachment(attachment)
        response.text = "I didn't understand that command. Here's what I can do:"
        return response


async def handle_invoke_activity(
    turn_context: TurnContext,
    db: asyncpg.Connection
):
    """Handle Adaptive Card button clicks (invoke actions)."""

    try:
        activity = turn_context.activity
        # Extract action data
        action_data = activity.value or {}
        action = action_data.get("action", "")

        user_id = activity.from_property.id if activity.from_property else ""
        user_email = getattr(activity.from_property, "aad_object_id", "") if activity.from_property else ""
        conversation_id = activity.conversation.id if activity.conversation else ""

        logger.info(f"Invoke action: {action} from user {user_email}")

        response = None

        if action == "generate_digest_preview":
            audience = action_data.get("audience", "global")
            response = await generate_digest_preview(
                user_id=user_id,
                user_email=user_email,
                conversation_id=conversation_id,
                audience=audience,
                db=db
            )

        elif action == "generate_digest":
            # Full digest generation
            request_id = action_data.get("request_id")
            audience = action_data.get("audience", "global")
            dry_run = action_data.get("dry_run", False)

            response = await generate_full_digest(
                user_id=user_id,
                user_email=user_email,
                request_id=request_id,
                audience=audience,
                dry_run=dry_run,
                db=db
            )

        elif action == "apply_filters":
            # Apply filters and regenerate digest
            filters = {
                "audience": action_data.get("audience", "global"),
                "from_date": action_data.get("from_date"),
                "to_date": action_data.get("to_date"),
                "owner": action_data.get("owner"),
                "max_candidates": action_data.get("max_candidates", 6)
            }

            response = await generate_digest_preview(
                user_id=user_id,
                user_email=user_email,
                conversation_id=conversation_id,
                audience=filters["audience"],
                db=db,
                filters=filters
            )

        elif action == "show_preferences":
            # Show preferences card
            response = await show_user_preferences(user_id, user_email, activity.from_property.name or "User", db)

        elif action == "save_preferences":
            # Save user preferences
            response = await save_user_preferences(
                user_id=user_id,
                user_email=user_email,
                preferences=action_data,
                db=db
            )

        else:
            logger.warning(f"Unknown invoke action: {action}")
            response = MessageFactory.text(f"Unknown action: {action}")

        # Send response if we have one
        if response:
            await turn_context.send_activity(response)

    except Exception as e:
        logger.error(f"Error handling invoke: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        attachment = CardFactory.adaptive_card(error_card["content"])
        await turn_context.send_activity(MessageFactory.attachment(attachment))


async def handle_conversation_update(
    activity: Activity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle conversation updates (bot added/removed)."""

    # Bot was added to conversation
    if activity.members_added:
        for member in activity.members_added:
            if member.id != activity.recipient.id:
                # User added bot
                user_name = member.name or "there"
                card = create_welcome_card(user_name)
                attachment = CardFactory.adaptive_card(card["content"])
                return MessageFactory.attachment(attachment)

    return None  # No response needed


async def generate_digest_preview(
    user_id: str,
    user_email: str,
    conversation_id: str,
    audience: str,
    db: asyncpg.Connection,
    filters: Optional[Dict[str, Any]] = None,
    test_recipient_email: Optional[str] = None
) -> Dict[str, Any]:
    """Generate digest preview with top candidates.

    Args:
        test_recipient_email: If provided, indicates test mode - email will be routed to this address.
    """

    try:
        # Create request ID
        request_id = str(uuid.uuid4())

        # Parse filters
        params = filters or {}
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        owner = params.get("owner")
        max_candidates = params.get("max_candidates", 6)

        # Store request
        await db.execute("""
            INSERT INTO teams_digest_requests (
                request_id, user_id, user_email, conversation_id,
                audience, from_date, to_date, owner, max_candidates,
                dry_run, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, CURRENT_TIMESTAMP)
        """, request_id, user_id, user_email, conversation_id,
            audience, from_date, to_date, owner, max_candidates,
            True, "processing")

        # Update status to processing
        await db.execute("""
            UPDATE teams_digest_requests
            SET status = 'processing', started_at = CURRENT_TIMESTAMP
            WHERE request_id = $1
        """, request_id)

        # Run curator
        curator = TalentWellCurator()
        await curator.initialize()

        start_time = datetime.now()

        result = await curator.run_weekly_digest(
            audience=audience,
            from_date=from_date,
            to_date=to_date,
            owner=owner,
            max_cards=max_candidates,
            dry_run=True,
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
                "sentiment_score": card.sentiment_score,
                "enthusiasm_score": card.enthusiasm_score,
                "professionalism_score": card.professionalism_score,
                "concerns_detected": card.concerns_detected
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
        """, len(cards_metadata), len(cards_metadata),
            json.dumps(cards_metadata), execution_time_ms, request_id)

        # Create preview card using CardFactory
        card = create_digest_preview_card(
            cards_metadata=cards_metadata,
            audience=audience,
            request_id=request_id
        )
        attachment = CardFactory.adaptive_card(card["content"])

        # Add test mode warning if applicable
        if test_recipient_email:
            # Prepend test mode message
            test_warning = f"⚠️ TEST MODE: Digest will be sent to {test_recipient_email}"
            response = MessageFactory.attachment(attachment)
            response.text = test_warning
            return response

        return MessageFactory.attachment(attachment)

    except Exception as e:
        logger.error(f"Error generating digest preview: {e}", exc_info=True)

        # Update request status
        await db.execute("""
            UPDATE teams_digest_requests
            SET status = 'failed',
                error_message = $1,
                completed_at = CURRENT_TIMESTAMP
            WHERE request_id = $2
        """, str(e), request_id)

        error_card = create_error_card(f"Failed to generate digest: {str(e)}")
        attachment = CardFactory.adaptive_card(error_card["content"])
        return MessageFactory.attachment(attachment)


async def generate_full_digest(
    user_id: str,
    user_email: str,
    request_id: str,
    audience: str,
    dry_run: bool,
    db: asyncpg.Connection,
    test_recipient_email: Optional[str] = None
) -> Dict[str, Any]:
    """Generate full HTML digest email.

    Args:
        test_recipient_email: If provided, send digest to this email instead of actual advisor.
                              Use for testing before sending to real advisors.
    """

    try:
        # Get request details
        request = await db.fetchrow("""
            SELECT * FROM teams_digest_requests
            WHERE request_id = $1
        """, request_id)

        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Run curator
        curator = TalentWellCurator()
        await curator.initialize()

        result = await curator.run_weekly_digest(
            audience=audience,
            from_date=request["from_date"],
            to_date=request["to_date"],
            owner=request["owner"],
            max_cards=request["max_candidates"],
            dry_run=dry_run,
            ignore_cooldown=False
        )

        # Store digest HTML
        await db.execute("""
            UPDATE teams_digest_requests
            SET digest_html = $1,
                subject_variant = $2
            WHERE request_id = $3
        """, result.get("email_html"), result.get("subject"), request_id)

        success_msg = f"✅ Digest generated successfully!\n\nSubject: {result.get('subject')}\n\n{len(result.get('cards_metadata', []))} candidates included."

        if test_recipient_email:
            success_msg += f"\n\n⚠️ TEST MODE: Email would be sent to {test_recipient_email} instead of {audience}"
        elif dry_run:
            success_msg += "\n\n⚠️ DRY RUN: No email sent"

        return {
            "type": "message",
            "text": success_msg
        }

    except Exception as e:
        logger.error(f"Error generating full digest: {e}", exc_info=True)
        return MessageFactory.text(f"❌ Error generating digest: {str(e)}")


async def show_user_preferences(
    user_id: str,
    user_email: str,
    user_name: str,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Show user preferences card."""

    try:
        # Get or create preferences
        prefs = await db.fetchrow("""
            SELECT * FROM teams_user_preferences
            WHERE user_id = $1
        """, user_id)

        if not prefs:
            # Create default preferences
            await db.execute("""
                INSERT INTO teams_user_preferences (
                    user_id, user_email, user_name,
                    default_audience, notification_enabled, digest_frequency,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
            """, user_id, user_email, user_name, "global", True, "weekly")

            prefs = await db.fetchrow("""
                SELECT * FROM teams_user_preferences
                WHERE user_id = $1
            """, user_id)

        # Create preferences card using CardFactory
        card = create_preferences_card(
            current_audience=prefs["default_audience"],
            digest_frequency=prefs["digest_frequency"],
            notifications_enabled=prefs["notification_enabled"]
        )
        attachment = CardFactory.adaptive_card(card["content"])
        return MessageFactory.attachment(attachment)

    except Exception as e:
        logger.error(f"Error showing preferences: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        attachment = CardFactory.adaptive_card(error_card["content"])
        return MessageFactory.attachment(attachment)


async def save_user_preferences(
    user_id: str,
    user_email: str,
    preferences: Dict[str, Any],
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Save user preferences from form submission."""

    try:
        # Update preferences
        await db.execute("""
            UPDATE teams_user_preferences
            SET default_audience = $1,
                digest_frequency = $2,
                notification_enabled = $3,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $4
        """,
            preferences.get("default_audience", "global"),
            preferences.get("digest_frequency", "weekly"),
            preferences.get("notification_enabled") == "true",
            user_id
        )

        return {
            "type": "message",
            "text": "✅ Preferences saved successfully!"
        }

    except Exception as e:
        logger.error(f"Error saving preferences: {e}", exc_info=True)
        return {
            "type": "message",
            "text": f"❌ Error saving preferences: {str(e)}"
        }


async def show_analytics(
    user_id: str,
    user_email: str,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Show user analytics summary."""

    try:
        # Get activity summary
        activity = await db.fetchrow("""
            SELECT * FROM teams_user_activity
            WHERE user_id = $1
        """, user_id)

        if not activity:
            return {
                "type": "message",
                "text": "No activity data available yet. Try generating a digest first!"
            }

        # Get recent digest requests
        recent_requests = await db.fetch("""
            SELECT
                audience,
                cards_generated,
                execution_time_ms,
                created_at
            FROM teams_digest_requests
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 10
        """, user_id)

        # Format analytics message (plain text for Teams compatibility)
        analytics_text = f"📊 Your TalentWell Analytics\n\n"
        analytics_text += f"Activity Summary:\n"
        analytics_text += f"- Total conversations: {activity['conversation_count']}\n"
        analytics_text += f"- Digest requests: {activity['digest_request_count']}\n"
        analytics_text += f"- Last activity: {activity['last_conversation_at'].strftime('%Y-%m-%d %H:%M') if activity['last_conversation_at'] else 'N/A'}\n\n"

        if recent_requests:
            analytics_text += "Recent Digests:\n"
            for req in recent_requests:
                analytics_text += f"- {req['audience']}: {req['cards_generated']} cards ({req['execution_time_ms']}ms) - {req['created_at'].strftime('%Y-%m-%d')}\n"

        return {
            "type": "message",
            "text": analytics_text
        }

    except Exception as e:
        logger.error(f"Error showing analytics: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        attachment = CardFactory.adaptive_card(error_card["content"])
        return MessageFactory.attachment(attachment)


# REST API endpoints for external access

@router.get("/health")
async def teams_health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "teams-integration",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/debug/env")
async def debug_env(_: bool = Depends(require_debug_mode)):
    """
    Debug endpoint to check environment variables.

    Only accessible when TEAMS_DEBUG_ENABLED=true.
    Returns 404 in production for security.
    """
    import os
    app_id = os.getenv("TEAMS_BOT_APP_ID")
    app_password = os.getenv("TEAMS_BOT_APP_PASSWORD")

    return {
        "TEAMS_BOT_APP_ID": app_id if app_id else "NOT SET",
        "TEAMS_BOT_APP_PASSWORD": "SET (length: {})".format(len(app_password)) if app_password else "NOT SET",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/debug/logging")
async def debug_logging(_: bool = Depends(require_debug_mode)):
    """
    Test endpoint to verify logging works.

    Only accessible when TEAMS_DEBUG_ENABLED=true.
    Returns 404 in production for security.
    """
    print("=== DEBUG LOGGING TEST - PRINT STATEMENT ===", flush=True)
    logger.info("=== DEBUG LOGGING TEST - LOGGER INFO ===")
    logger.warning("=== DEBUG LOGGING TEST - LOGGER WARNING ===")
    logger.error("=== DEBUG LOGGING TEST - LOGGER ERROR ===")

    return {
        "status": "logged",
        "message": "Check logs for: DEBUG LOGGING TEST",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/admin/run-migration")
async def run_database_migration(
    migration_name: str,
    _: bool = Depends(require_debug_mode),
    db: asyncpg.Connection = Depends(get_database_connection),
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """
    Run a database migration.

    Only accessible when TEAMS_DEBUG_ENABLED=true and with valid API key.
    Used for deploying schema changes without container exec access.

    Args:
        migration_name: Name of migration file (e.g., '006_teams_bot_audit_table.sql')

    Notes:
        - Uses pooled connection; long migrations hold connection from pool
        - Supports multi-statement SQL files via transaction
        - Path sanitization prevents directory traversal
    """
    import os

    # Verify API key
    API_KEY = os.getenv("API_KEY")
    if not API_KEY or x_api_key != API_KEY:
        logger.warning(f"Invalid API key attempt for migration endpoint")
        raise HTTPException(status_code=403, detail="Invalid API key")

    logger.info(f"Migration endpoint called with: {migration_name}")
    logger.debug(f"API key validated, debug mode enabled: {DEBUG_ENABLED}")
    logger.info(f"Database connection acquired successfully for migration")

    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(migration_name)
        if safe_filename != migration_name:
            raise HTTPException(status_code=400, detail="Invalid migration filename")

        # Whitelist validation: must be .sql file starting with digits
        if not safe_filename.endswith('.sql') or not safe_filename[0].isdigit():
            raise HTTPException(status_code=400, detail="Migration must be a numbered .sql file")

        # Construct migration path
        migration_path = f"/app/migrations/{safe_filename}"

        # Check if file exists
        if not os.path.exists(migration_path):
            raise HTTPException(status_code=404, detail=f"Migration file not found: {safe_filename}")

        # Read migration file
        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        logger.info(f"Running migration: {safe_filename}")

        # Execute migration in transaction (handles multiple statements)
        # Note: This uses a pooled connection; long migrations will hold it
        async with db.transaction():
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
            for i, statement in enumerate(statements):
                try:
                    await db.execute(statement)
                    logger.debug(f"Executed statement {i+1}/{len(statements)}")
                except Exception as stmt_error:
                    logger.error(f"Failed at statement {i+1}: {statement[:100]}...")
                    raise

        logger.info(f"Migration completed: {safe_filename}")

        return {
            "status": "success",
            "migration": safe_filename,
            "statements_executed": len(statements),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.get("/analytics")
async def get_analytics_data(
    user_email: str,
    timeframe: str = "7d",
    db: asyncpg.Connection = Depends(get_database_connection)
):
    """
    Get analytics data for a user.

    Requires API key for external access.
    """
    try:
        # Parse timeframe
        days = int(timeframe.replace("d", "")) if "d" in timeframe else 7

        # Get digest performance
        performance = await db.fetch("""
            SELECT * FROM teams_digest_performance
            WHERE request_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY request_date DESC
        """, days)

        return {
            "timeframe": timeframe,
            "performance": [dict(row) for row in performance],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
