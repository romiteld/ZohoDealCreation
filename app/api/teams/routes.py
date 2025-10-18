"""
Microsoft Teams Bot Framework webhook endpoints for TalentWell.
Handles Teams activities, user preferences, and digest generation with database tracking.
"""
import logging
import uuid
import json
import os
import unicodedata
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import asyncpg

# Microsoft Bot Framework imports
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, MessageFactory, CardFactory
from botbuilder.schema import Activity, ActivityTypes, InvokeResponse
from botframework.connector.auth import MicrosoftAppCredentials
from app.api.teams.invoke_models import (
    InvokeResponseBuilder,
    create_success_response,
    create_error_response
)

from app.api.teams.adaptive_cards import (
    create_welcome_card,
    create_help_card,
    create_digest_preview_card,
    create_digest_acknowledgment_card,
    create_error_card,
    create_preferences_card,
    create_clarification_card,
    create_suggestion_card,
    create_vault_alerts_builder_card
)
from app.api.teams.nlp_formatters import (
    format_medium_confidence_text,
    format_results_as_text,
    format_error_text
)
from app.jobs.talentwell_curator import TalentWellCurator
from app.jobs.vault_alerts_generator import VaultAlertsGenerator
from well_shared.database.connection import get_database_connection
from app.api.teams.query_engine import process_natural_language_query
from app.api.teams.conversation_memory import get_memory_manager
from app.api.teams.clarification_engine import get_clarification_engine, RateLimitExceeded
from app.api.teams.conversation_state import CONFIDENCE_THRESHOLD_LOW, CONFIDENCE_THRESHOLD_MED
from app.services.proactive_messaging import create_proactive_messaging_service

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


# Helper function to extract real user email from Teams activity
def extract_user_email(activity: Activity) -> str:
    """
    Extract user's email/UPN from Teams activity.

    CRITICAL: aad_object_id is an Azure AD GUID, NOT an email address.
    We must use additional_properties to get the real email/UPN.

    Args:
        activity: Teams Activity object

    Returns:
        User's email address (or GUID as fallback with warning)
    """
    if not activity or not activity.from_property:
        return ""

    # Extract email from additional_properties (the correct approach)
    props = getattr(activity.from_property, "additional_properties", {}) or {}
    user_email = props.get("email") or props.get("userPrincipalName") or ""

    # Fallback to aad_object_id only if no email found (logs warning)
    if not user_email:
        user_email = getattr(activity.from_property, "aad_object_id", "")
        if user_email:
            logger.warning(
                f"Could not extract email from Teams activity, using aad_object_id (GUID): {user_email}. "
                f"This may cause access control issues."
            )

    return user_email


# Helper function to strip bot mentions from message text
def remove_mention_text(text: str, entities: Optional[list] = None) -> str:
    """
    Remove bot mention entities from message text.

    Teams includes mentions as <at>BotName</at> in the text.
    This function strips these out to get the actual command.

    Args:
        text: Raw message text from Teams
        entities: Optional list of entity objects from activity

    Returns:
        Cleaned message text without mention tags
    """
    if not text:
        return ""

    # Remove <at>...</at> tags (Teams mention format)
    import re
    cleaned = re.sub(r'<at>.*?</at>', '', text, flags=re.IGNORECASE)

    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())

    return cleaned.strip()


def normalize_command_text(text: str) -> str:
    """Normalize Teams message text for reliable command parsing."""
    if not text:
        return ""

    # Normalize unicode characters (e.g., smart quotes, full-width variants)
    normalized = unicodedata.normalize("NFKC", text)

    # Remove zero-width and formatting characters that can appear in Teams inputs
    normalized = "".join(
        ch for ch in normalized
        if unicodedata.category(ch) != "Cf"
    )

    # Replace non-breaking spaces with regular spaces so strip/split behave consistently
    normalized = normalized.replace("\u00A0", " ")

    # Collapse whitespace and lowercase for command matching
    normalized = " ".join(normalized.split())

    return normalized.strip().lower()


# Helper function for audit logging
async def log_bot_audit(
    db: Optional[asyncpg.Connection],
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
        db: Database connection (optional - if None, skip logging)
        activity_id: Teams activity ID
        event_type: Event type (processing_started, send_success, etc.)
        user_id: Optional user ID
        conversation_id: Optional conversation ID
        event_data: Optional JSON data with additional context
        error_message: Optional error message for failures
    """
    if db is None:
        # Database unavailable, skip audit logging
        return

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

            print(f"BOT_LOGIC: Starting for activity_id={activity_id}, user={user_id}", flush=True)

            try:
                # Try to get database connection (optional)
                db = None
                try:
                    print("BOT_LOGIC: Attempting database connection...", flush=True)
                    from well_shared.database.connection import get_connection_manager
                    manager = await get_connection_manager()
                    db = await manager.get_connection().__aenter__()
                    print("BOT_LOGIC: Database connected successfully", flush=True)
                    # Log: bot_logic started
                    await log_bot_audit(db, activity_id, "bot_logic_started", user_id, conversation_id)
                except Exception as db_error:
                    print(f"BOT_LOGIC: Database connection failed: {db_error}", flush=True)
                    logger.warning(f"Database unavailable, continuing without it: {db_error}")
                    db = None  # Continue without database

                # Continue with bot logic regardless of database status

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


async def handle_slash_command(
    message_text: str,
    user_id: str,
    user_name: str,
    user_email: str,
    conversation_id: str,
    activity: Activity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle slash commands (messages starting with /).

    Supported commands:
    - /help - Show help card
    - /digest [audience] - Generate candidate digest
    - /preferences - User preferences and subscriptions
    - /analytics - Usage statistics
    - /vault_alerts - Vault alerts builder (executives only)

    Args:
        message_text: The normalized message text (with / prefix)
        user_id: User ID from Teams
        user_name: User display name
        user_email: User email address
        conversation_id: Conversation ID
        activity: Full activity object
        db: Database connection

    Returns:
        Response dictionary or MessageFactory object
    """
    # Extract command (remove leading / and get first word)
    command_parts = message_text[1:].split()  # Remove "/" and split
    command = command_parts[0].lower() if command_parts else ""
    args = command_parts[1:] if len(command_parts) > 1 else []

    logger.info(f"Processing slash command: /{command} with args: {args}")

    # Route to appropriate handler
    if command == "help":
        card = create_help_card()
        attachment = CardFactory.adaptive_card(card["content"])
        return MessageFactory.attachment(attachment)

    elif command == "digest":
        # Parse audience from args (e.g., "/digest advisors" or "/digest daniel.romitelli@emailthewell.com")
        audience_input = args[0] if args else "global"

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

        # FEATURE FLAG: USE_ASYNC_DIGEST (Phase 3 - Service Bus integration)
        from app.config.feature_flags import USE_ASYNC_DIGEST

        if USE_ASYNC_DIGEST:
            # ============================================================
            # ASYNC MODE: Publish to Service Bus, return ack immediately
            # ============================================================
            logger.info(f"=== DIGEST COMMAND (ASYNC MODE) ===")
            logger.info(f"Audience: {audience}, User: {user_email}, Conversation: {conversation_id}")
            logger.info(f"Feature flag USE_ASYNC_DIGEST=true, routing to Service Bus")

            try:
                from app.services.message_bus import get_message_bus

                # Get service URL from activity (required for proactive messaging)
                service_url = activity.service_url if activity else ""

                # Store conversation reference so workers can send proactive messages later
                proactive_service = await create_proactive_messaging_service()
                await proactive_service.store_conversation_reference(activity)

                # Publish digest request to Service Bus
                message_bus = get_message_bus()
                request_id = await message_bus.publish_digest_request(
                    conversation_id=conversation_id,
                    service_url=service_url,
                    audience=audience,
                    user_email=user_email,
                    user_name=user_name,
                    tenant_id=None,  # Will use default from worker
                    date_range_days=7,  # Default 7 days
                    include_vault=True,
                    include_deals=True,
                    include_meetings=True,
                    format_type="html",
                    test_recipient_email=test_email  # Support test mode in async flow
                )

                logger.info(f"✅ Published digest request {request_id} to Service Bus queue")

                # Store conversation reference for audit
                await db.execute("""
                    INSERT INTO teams_digest_requests (
                        request_id, user_id, user_email, conversation_id,
                        audience, dry_run, status, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
                """, request_id, user_id, user_email, conversation_id, audience, False, "queued")

                # Return acknowledgment card immediately (< 500ms)
                card = create_digest_acknowledgment_card(
                    audience=audience,
                    request_id=request_id
                )
                attachment = CardFactory.adaptive_card(card["content"])
                return MessageFactory.attachment(attachment)

            except Exception as e:
                logger.error(f"❌ Async digest failed: {e}", exc_info=True)
                logger.warning("Falling back to synchronous digest generation")
                # Fall through to sync mode on failure

        # ============================================================
        # SYNC MODE (LEGACY): Generate digest inline, blocks 5-15s
        # ============================================================
        logger.info(f"=== DIGEST COMMAND (SYNC MODE) ===")
        logger.info(f"Audience: {audience}, User: {user_email}")
        logger.info(f"Feature flag USE_ASYNC_DIGEST={USE_ASYNC_DIGEST}, using synchronous flow")

        return await generate_digest_preview(
            user_id=user_id,
            user_email=user_email,
            conversation_id=conversation_id,
            audience=audience,
            db=db,
            test_recipient_email=test_email
        )

    elif command == "preferences":
        return await show_user_preferences(user_id, user_email, user_name, db)

    elif command == "vault_alerts" or command == "vaultalerts":
        # Executive-only feature
        return await show_vault_alerts_builder(user_id, user_email, user_name, db)

    elif command == "analytics":
        return await show_analytics(user_id, user_email, db)

    else:
        # Unknown slash command
        return {
            "type": "message",
            "text": f"❌ Unknown command: `/{command}`\n\nTry `/help` to see available commands."
        }


async def handle_message_activity(
    activity: Activity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle incoming text message from Teams user with dual-mode support.

    Routing Logic:
    - Messages starting with "/" are treated as slash commands
    - All other messages are processed as natural language queries
    """

    # Extract user info
    user_id = activity.from_property.id if activity.from_property else ""
    user_name = activity.from_property.name if activity.from_property else ""
    user_email = extract_user_email(activity)  # Use helper to get real email, not GUID
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

    # Parse command - strip bot mentions first (handles @TalentWell mentions)
    raw_text = activity.text or ""
    cleaned_text = remove_mention_text(raw_text, activity.entities)
    message_text = normalize_command_text(cleaned_text)

    logger.info(
        "Message received - Raw: '%s' | Cleaned: '%s' | Normalized: '%s' | From: %s",
        raw_text,
        cleaned_text,
        message_text,
        user_email,
    )

    # ========================================
    # NEW ROUTING: Slash commands vs NLP queries
    # ========================================
    if message_text.startswith("/"):
        # Slash command: route to command handler
        logger.info(f"Routing to slash command handler: {message_text}")
        return await handle_slash_command(message_text, user_id, user_name, user_email, conversation_id, activity, db)

    # ========================================
    # SPECIAL CASE: Greetings (for friendly UX)
    # ========================================
    if any(greeting in message_text for greeting in ["hello", "hi", "hey"]):
        # Welcome card
        card = create_welcome_card(user_name.split()[0] if user_name else "there")
        attachment = CardFactory.adaptive_card(card["content"])
        return MessageFactory.attachment(attachment)

    # ========================================
    # DEFAULT: Process as natural language query
    # ========================================
    # All other messages (not starting with /) are treated as NLP queries
    else:
        # All users have full access to data
        logger.info(f"Natural language query from {user_email}: {cleaned_text}")

        # Initialize conversation memory and clarification engine
        memory_manager = await get_memory_manager()
        clarification_engine = await get_clarification_engine()

        # Process query with multi-turn dialogue
        try:
            # Get conversation history for context
            conversation_context = await memory_manager.get_context_for_query(
                user_id=user_id,
                current_query=cleaned_text,
                db=db
            )

            # Execute query ONCE before branching (CRITICAL: no double query)
            result = await process_natural_language_query(
                query=cleaned_text,
                user_email=user_email,
                db=db,
                conversation_context=conversation_context,
                activity=activity  # Pass activity for proactive messaging support
            )

            # Extract confidence score
            confidence = result.get("confidence_score", 0.8)
            logger.info(f"Query classified with confidence: {confidence:.2f}")

            # THREE-WAY BRANCH based on confidence
            if confidence < CONFIDENCE_THRESHOLD_LOW:  # <0.5
                # Low confidence: Clarification flow
                logger.info(f"Low confidence ({confidence:.2f}) - triggering clarification")

                try:
                    # Generate clarification question
                    clarification_question = await clarification_engine.generate_clarification_question(
                        query=cleaned_text,
                        intent={"intent_type": "search", "entities": {}},  # Placeholder intent
                        ambiguity_type="vague_search"
                    )

                    # Get clarification options
                    options = clarification_engine.get_clarification_options("vague_search")

                    # Create clarification session (may raise RateLimitExceeded)
                    session = await clarification_engine.create_clarification_session(
                        user_id=user_id,
                        query=cleaned_text,
                        intent={"intent_type": "search", "entities": {}},
                        ambiguity_type="vague_search",
                        suggested_options=options
                    )

                    # Store user query in memory
                    await memory_manager.add_message(
                        user_id=user_id,
                        role="user",
                        content=cleaned_text,
                        confidence_score=confidence,
                        db=db
                    )

                    # Store clarification question in memory
                    await memory_manager.add_message(
                        user_id=user_id,
                        role="assistant",
                        content=clarification_question,
                        intent_type="clarification",
                        db=db
                    )

                    # Create and return clarification card
                    card = create_clarification_card(
                        question=clarification_question,
                        options=options,
                        session_id=session["session_id"],
                        original_query=cleaned_text
                    )

                    attachment = CardFactory.adaptive_card(card["content"])
                    return MessageFactory.attachment(attachment)

                except RateLimitExceeded as e:
                    # CRITICAL FIX: create_error_card takes SINGLE string parameter
                    logger.warning(f"Rate limit exceeded for {user_id}: {e}")
                    error_card = create_error_card(
                        "⏱️ **Too Many Requests**\n\n"
                        "You've asked for clarification too frequently. "
                        "Please wait a few minutes.\n\n_Limit: 3 per 5 min_"
                    )
                    return MessageFactory.attachment(CardFactory.adaptive_card(error_card["content"]))

            elif confidence < CONFIDENCE_THRESHOLD_MED:  # 0.5-0.8
                # Medium confidence: Return result + suggestion (REUSE result from above)
                logger.info(f"Medium confidence ({confidence:.2f}) - showing suggestion")

                # Store user message and assistant response in memory
                await memory_manager.add_message(
                    user_id=user_id,
                    role="user",
                    content=cleaned_text,
                    confidence_score=confidence,
                    db=db
                )

                response_text = result.get("text", "I couldn't process that query.")
                await memory_manager.add_message(
                    user_id=user_id,
                    role="assistant",
                    content=response_text,
                    db=db
                )

                # Update conversation with response
                await db.execute("""
                    UPDATE teams_conversations
                    SET bot_response = $1
                    WHERE conversation_id = $2 AND activity_id = $3
                """, "medium_confidence_query", conversation_id, activity.id)

                # Format as text-only response with confidence indicator
                formatted_text = format_medium_confidence_text(
                    result=result,
                    confidence=confidence,
                    query=cleaned_text
                )

                return MessageFactory.text(formatted_text)

            else:  # >=0.8
                # High confidence: Direct execution (REUSE result from above)
                logger.info(f"High confidence ({confidence:.2f}) - executing directly")

                # Store user message in conversation memory
                await memory_manager.add_message(
                    user_id=user_id,
                    role="user",
                    content=cleaned_text,
                    confidence_score=confidence,
                    db=db
                )

                # Store assistant response in conversation memory
                response_text = result.get("text", "I couldn't process that query.")
                await memory_manager.add_message(
                    user_id=user_id,
                    role="assistant",
                    content=response_text,
                    db=db
                )

                # Update conversation with response
                await db.execute("""
                    UPDATE teams_conversations
                    SET bot_response = $1
                    WHERE conversation_id = $2 AND activity_id = $3
                """, "natural_language_query", conversation_id, activity.id)

                # Always return text-only response (no cards)
                return MessageFactory.text(response_text)

        except Exception as e:
            logger.error(f"Error processing natural language query: {e}", exc_info=True)
            # Fallback to help card
            card = create_help_card()
            await db.execute("""
                UPDATE teams_conversations
                SET bot_response = $1
                WHERE conversation_id = $2 AND activity_id = $3
            """, "error_fallback", conversation_id, activity.id)

            attachment = CardFactory.adaptive_card(card["content"])
            response = MessageFactory.attachment(attachment)
            response.text = f"I didn't understand that. Here's what I can do:"
            return response


async def handle_invoke_activity(
    turn_context: TurnContext,
    db: asyncpg.Connection
) -> InvokeResponse:
    """
    Handle Adaptive Card button clicks with robust data extraction.

    CRITICAL: This function MUST return an InvokeResponse to prevent HTTP 500 errors.
    Never return None or throw unhandled exceptions.

    Returns:
        InvokeResponse with proper status code and correlation ID
    """
    correlation_id = str(uuid.uuid4())

    try:
        activity = turn_context.activity

        # Step 1: Extract raw payload (preserve ALL data)
        raw_payload = activity.value or {}

        # Step 2: Unwrap action metadata from msteams.value
        action_metadata = {}
        if "msteams" in raw_payload and "value" in raw_payload["msteams"]:
            action_metadata = raw_payload["msteams"]["value"]

        # Step 3: Extract form data (root level, excluding msteams wrapper)
        form_data = {k: v for k, v in raw_payload.items() if k != "msteams"}

        # Step 4: Merge (form data overrides metadata if duplicate keys exist)
        final_data = {**action_metadata, **form_data}

        # Step 5: Get action name
        action = final_data.get("action", "")

        # Enhanced logging for debugging button clicks
        logger.info(f"=== INVOKE ACTIVITY RECEIVED (Correlation: {correlation_id}) ===")
        logger.info(f"Action: {action}")
        logger.info(f"Raw Payload Keys: {list(raw_payload.keys())}")
        logger.info(f"Action Metadata: {action_metadata}")
        logger.info(f"Form Data: {form_data}")
        logger.info(f"Final Merged Data: {json.dumps(final_data, indent=2)}")
        logger.info(f"Correlation ID: {correlation_id}")
        print(f"=== INVOKE: action={action}, final_data={final_data}", flush=True)

        user_id = activity.from_property.id if activity.from_property else ""
        user_email = extract_user_email(activity)  # Use helper to get real email, not GUID
        conversation_id = activity.conversation.id if activity.conversation else ""

        logger.info(f"Invoke action: {action} from user {user_email}")

        # Track telemetry
        from app.telemetry import track_event
        track_event("invoke_action", {"action": action, "correlation_id": correlation_id, "user_email": user_email})

        follow_up_message = None

        if action == "generate_digest_preview":
            audience = final_data.get("audience", "global")
            follow_up_message = await generate_digest_preview(
                user_id=user_id,
                user_email=user_email,
                conversation_id=conversation_id,
                audience=audience,
                db=db
            )

        elif action == "generate_digest":
            # Full digest generation
            request_id = final_data.get("request_id")
            audience = final_data.get("audience", "global")
            dry_run = final_data.get("dry_run", False)

            follow_up_message = await generate_full_digest(
                user_id=user_id,
                user_email=user_email,
                request_id=request_id,
                audience=audience,
                dry_run=dry_run,
                db=db
            )

        elif action == "refine_query":
            # Handle refinement request from medium-confidence suggestion card
            # CRITICAL FIX: Create REAL clarification session (not fake UUID)
            original_query = final_data.get("original_query")
            confidence = final_data.get("confidence", 0.0)

            clarification_engine = await get_clarification_engine()
            memory_manager = await get_memory_manager()

            refinement_options = [
                {"title": "Add timeframe", "value": "add_timeframe"},
                {"title": "Specify person/company", "value": "add_entity"},
                {"title": "Filter by stage", "value": "add_stage"},
                {"title": "Start over", "value": "start_over"}
            ]

            try:
                # Create REAL session using create_clarification_session
                session = await clarification_engine.create_clarification_session(
                    user_id=user_id,
                    query=original_query,
                    intent={"intent_type": "refine", "entities": {}},
                    ambiguity_type="vague_search",
                    suggested_options=refinement_options
                )

                # Create refinement card
                refinement_card = create_clarification_card(
                    question=f"How would you like to refine: \"{original_query}\"?",
                    options=refinement_options,
                    session_id=session["session_id"],  # Real session ID
                    original_query=original_query
                )

                attachment = CardFactory.adaptive_card(refinement_card["content"])
                follow_up_message = MessageFactory.attachment(attachment)

            except RateLimitExceeded as e:
                # Handle rate limit in refine flow too
                logger.warning(f"Rate limit in refine_query for {user_id}: {e}")
                error_card = create_error_card(
                    "⏱️ **Too Many Requests**\n\n"
                    "You've asked for clarification too frequently. "
                    "Please wait a few minutes.\n\n_Limit: 3 per 5 min_"
                )
                follow_up_message = MessageFactory.attachment(CardFactory.adaptive_card(error_card["content"]))

        elif action == "apply_filters":
            # Apply filters and regenerate digest
            filters = {
                "audience": final_data.get("audience", "global"),
                "from_date": final_data.get("from_date"),
                "to_date": final_data.get("to_date"),
                "owner": final_data.get("owner"),
                "max_candidates": final_data.get("max_candidates", 6)
            }

            follow_up_message = await generate_digest_preview(
                user_id=user_id,
                user_email=user_email,
                conversation_id=conversation_id,
                audience=filters["audience"],
                db=db,
                filters=filters
            )

        elif action == "show_preferences":
            # Show preferences card
            follow_up_message = await show_user_preferences(user_id, user_email, activity.from_property.name or "User", db)

        elif action == "save_preferences":
            # Save user preferences
            follow_up_message = await save_user_preferences(
                user_id=user_id,
                user_email=user_email,
                preferences=final_data,
                db=db
            )

        elif action == "save_vault_alerts_subscription":
            # Save vault alerts subscription (executive-only)
            follow_up_message = await save_vault_alerts_subscription(
                user_id=user_id,
                user_email=user_email,
                settings=final_data,
                db=db
            )

        elif action == "preview_vault_alerts":
            # Generate preview of vault alerts with custom filters
            follow_up_message = await preview_vault_alerts(
                user_email=user_email,
                settings=final_data,
                db=db
            )

        elif action == "submit_clarification":
            # CRITICAL FIX: Both fields should be in final_data now (after merge)
            session_id = final_data.get("session_id")
            clarification_response = final_data.get("clarification_response")

            # Guard for missing fields
            if not session_id or not clarification_response:
                logger.warning(f"Missing clarification data: session={session_id}, response={clarification_response}")
                logger.warning(f"Available keys in final_data: {list(final_data.keys())}")
                follow_up_message = MessageFactory.text("❌ Invalid submission. Please try again.")
            else:
                follow_up_message = await handle_clarification_response(
                    user_id=user_id,
                    user_email=user_email,
                    session_id=session_id,
                    clarification_response=clarification_response,
                    db=db
                )

        elif action == "email_marketability_report":
            # Email marketability report to user
            candidate_ids = final_data.get("candidate_ids", [])
            logger.info(f"Email marketability report request from {user_email} for {len(candidate_ids)} candidates")

            follow_up_message = await email_marketability_report(
                user_email=user_email,
                candidate_ids=candidate_ids,
                db=db
            )

        else:
            logger.warning(f"Unknown invoke action: {action}")
            follow_up_message = MessageFactory.text(f"Unknown action: {action}")

        # Send follow-up message if we have one
        if follow_up_message:
            await turn_context.send_activity(follow_up_message)

        # Always return success InvokeResponse (NEVER return None or status 500)
        result = InvokeResponseBuilder(action) \
            .with_success("Action processed successfully") \
            .with_correlation_id(correlation_id) \
            .build()

        return result.to_invoke_response()

    except Exception as e:
        logger.error(f"Error handling invoke: {e}", exc_info=True)
        logger.error(f"Correlation ID: {correlation_id}")

        # Track error telemetry
        from app.telemetry import track_event
        track_event("invoke_error", {
            "action": action if 'action' in locals() else "unknown",
            "correlation_id": correlation_id,
            "error": str(e),
            "error_type": type(e).__name__
        })

        # Send error card as follow-up message
        try:
            error_message = f"An error occurred processing your request.\nReference: {correlation_id}\n\nError: {str(e)}"
            error_card = create_error_card(error_message)
            attachment = CardFactory.adaptive_card(error_card["content"])
            await turn_context.send_activity(MessageFactory.attachment(attachment))
        except Exception as card_error:
            logger.error(f"Failed to send error card: {card_error}")

        # Return error InvokeResponse (do NOT use status 500)
        return create_error_response(
            action=action if 'action' in locals() else "unknown",
            error=e,
            correlation_id=correlation_id
        ).to_invoke_response()


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

        # Create preferences card using CardFactory with subscription fields
        card = create_preferences_card(
            current_audience=prefs["default_audience"],
            digest_frequency=prefs["digest_frequency"],
            notifications_enabled=prefs["notification_enabled"],
            subscription_active=prefs.get("subscription_active", False),
            delivery_email=prefs.get("delivery_email", "") or "",
            max_candidates=prefs.get("max_candidates_per_digest", 6)
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
    """Save user preferences from form submission and send confirmation email."""

    try:
        # Get previous settings for comparison
        previous = await db.fetchrow("""
            SELECT subscription_active, delivery_email, max_candidates_per_digest,
                   default_audience, digest_frequency
            FROM teams_user_preferences
            WHERE user_id = $1
        """, user_id)

        # Extract new settings
        subscription_active = preferences.get("subscription_active") == "true"
        delivery_email = preferences.get("delivery_email", "").strip() or user_email  # Default to Teams email
        max_candidates = int(preferences.get("max_candidates", 6))

        # Update preferences
        await db.execute("""
            UPDATE teams_user_preferences
            SET default_audience = $1,
                digest_frequency = $2,
                notification_enabled = $3,
                subscription_active = $4,
                delivery_email = $5,
                max_candidates_per_digest = $6,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $7
        """,
            preferences.get("default_audience", "global"),
            preferences.get("digest_frequency", "weekly"),
            preferences.get("notification_enabled") == "true",
            subscription_active,
            delivery_email,
            max_candidates,
            user_id
        )

        # Get updated settings with calculated next_digest_scheduled_at
        updated = await db.fetchrow("""
            SELECT subscription_active, delivery_email, max_candidates_per_digest,
                   default_audience, digest_frequency, next_digest_scheduled_at
            FROM teams_user_preferences
            WHERE user_id = $1
        """, user_id)

        # Determine action for confirmation email
        action = None
        if not previous or not previous["subscription_active"]:
            if subscription_active:
                action = "subscribe"
        elif previous["subscription_active"] and not subscription_active:
            action = "unsubscribe"
        elif previous["subscription_active"] and subscription_active:
            # Check if settings changed
            if (previous["delivery_email"] != delivery_email or
                previous["max_candidates_per_digest"] != max_candidates or
                previous["default_audience"] != updated["default_audience"] or
                previous["digest_frequency"] != updated["digest_frequency"]):
                action = "update"

        # Send confirmation email if subscription changed
        if action:
            from app.jobs.weekly_digest_scheduler import WeeklyDigestScheduler
            scheduler = WeeklyDigestScheduler()
            await scheduler.initialize()

            new_settings = {
                "user_email": user_email,
                "default_audience": updated["default_audience"],
                "digest_frequency": updated["digest_frequency"],
                "max_candidates_per_digest": updated["max_candidates_per_digest"],
                "next_digest_scheduled_at": str(updated["next_digest_scheduled_at"]) if updated["next_digest_scheduled_at"] else None
            }

            previous_settings = None
            if previous:
                previous_settings = {
                    "default_audience": previous["default_audience"],
                    "digest_frequency": previous["digest_frequency"],
                    "max_candidates_per_digest": previous["max_candidates_per_digest"]
                }

            try:
                confirmation_id = await scheduler.send_confirmation_email(
                    user_id=user_id,
                    delivery_email=delivery_email,
                    action=action,
                    new_settings=new_settings,
                    previous_settings=previous_settings
                )
                logger.info(f"Confirmation email sent: {confirmation_id}")
                await scheduler.close()

                return {
                    "type": "message",
                    "text": f"✅ Preferences saved! Check {delivery_email} for confirmation."
                }
            except Exception as email_error:
                logger.error(f"Failed to send confirmation email: {email_error}", exc_info=True)
                await scheduler.close()
                return {
                    "type": "message",
                    "text": f"✅ Preferences saved, but confirmation email failed: {str(email_error)}"
                }
        else:
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


async def email_marketability_report(
    user_email: str,
    candidate_ids: List[str],
    db: asyncpg.Connection
) -> Activity:
    """
    Email marketability report to user via Azure Communication Services.

    Args:
        user_email: Email address to send report to
        candidate_ids: List of TWAV candidate IDs
        db: Database connection

    Returns:
        Activity with confirmation message
    """
    try:
        from app.integrations import ZohoApiClient
        from app.jobs.marketability_scorer import MarketabilityScorer
        from app.utils.anonymizer import anonymize_candidate
        from azure.communication.email import EmailClient

        logger.info(f"Generating email report for {len(candidate_ids)} candidates to {user_email}")

        # Step 1: Fetch candidate data from Zoho
        zoho_client = ZohoApiClient()
        scorer = MarketabilityScorer()

        candidates = []
        for twav_id in candidate_ids:
            # Query Zoho for each candidate
            results = await zoho_client.query_candidates(
                candidate_locator=twav_id,
                limit=1
            )
            if results:
                candidate = results[0]
                # Score candidate
                score, breakdown = scorer.score_candidate(candidate)
                candidate['score'] = score
                candidate['score_breakdown'] = breakdown
                candidates.append(candidate)

        if not candidates:
            return MessageFactory.text("❌ Could not fetch candidate data. Please try again.")

        # Step 2: Generate HTML email in boss's format
        html_body = generate_marketability_email_html(candidates)

        # Step 3: Send via Azure Communication Services
        connection_string = os.getenv("ACS_EMAIL_CONNECTION_STRING")
        if not connection_string:
            logger.error("ACS_EMAIL_CONNECTION_STRING not configured")
            return MessageFactory.text("❌ Email service not configured. Please contact administrator.")

        email_client = EmailClient.from_connection_string(connection_string)

        message = {
            "senderAddress": os.getenv("ACS_SENDER_ADDRESS", "DoNotReply@emailthewell.com"),
            "recipients": {
                "to": [{"address": user_email}]
            },
            "content": {
                "subject": f"🏆 Top {len(candidates)} Most Marketable Vault Candidates",
                "html": html_body
            }
        }

        poller = email_client.begin_send(message)
        result = poller.result()

        logger.info(f"Email sent successfully to {user_email}, message_id={result.get('id')}")

        # Return success message
        return MessageFactory.text(
            f"✅ **Email sent successfully!**\n\n"
            f"📧 Sent to: {user_email}\n"
            f"📊 Candidates: {len(candidates)}\n\n"
            f"_Check your inbox for the full marketability report._"
        )

    except Exception as e:
        logger.error(f"Error sending marketability email: {e}", exc_info=True)
        return MessageFactory.text(f"❌ Error sending email: {str(e)}")


def generate_marketability_email_html(candidates: List[Dict[str, Any]]) -> str:
    """
    Generate HTML email body in boss's format.

    Args:
        candidates: List of scored and anonymized candidates

    Returns:
        HTML string
    """
    from app.utils.anonymizer import anonymize_candidate

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px 10px 0 0;
                text-align: center;
            }
            .candidate-card {
                background: white;
                margin: 20px 0;
                padding: 25px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                page-break-inside: avoid;
            }
            .rank-badge {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .score {
                font-size: 24px;
                font-weight: bold;
                color: #667eea;
            }
            .twav-code {
                color: #666;
                font-style: italic;
            }
            .bullet {
                margin: 8px 0;
                padding-left: 20px;
                position: relative;
            }
            .bullet:before {
                content: "•";
                position: absolute;
                left: 0;
                color: #667eea;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏆 Top Marketable Vault Candidates</h1>
            <p>Comprehensive Marketability Analysis</p>
        </div>
    """

    for idx, candidate in enumerate(candidates, 1):
        anonymized = anonymize_candidate(candidate)
        score = candidate.get('score', 0)
        twav = candidate.get('Candidate_Locator', 'Unknown')
        location = anonymized.get('location', 'Unknown')
        aum = anonymized.get('book_size_aum', 'Not disclosed')
        production = anonymized.get('production_l12mo', 'Not disclosed')
        firm = anonymized.get('current_employer', 'Advisory firm')
        availability = candidate.get('When_Available', 'TBD')

        rank_emoji = "⭐" if idx <= 3 else "🌟"

        html += f"""
        <div class="candidate-card">
            <div class="rank-badge">#{idx} {rank_emoji}</div>
            <div class="score">{score:.0f}/100</div>
            <p><strong>📍 {location}</strong></p>
            <div class="bullet">Manages {aum} in client assets at {firm}</div>
            <div class="bullet">Generated {production} in trailing 12-month production</div>
            <div class="bullet">Available: {availability}</div>
            <p class="twav-code">Ref: {twav}</p>
        </div>
        """

    html += """
    </body>
    </html>
    """

    return html


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
            # Execute entire migration as single script to preserve function definitions
            try:
                await db.execute(migration_sql)
                logger.info(f"Migration executed successfully")
            except Exception as exec_error:
                logger.error(f"Migration execution failed: {str(exec_error)}")
                raise

        logger.info(f"Migration completed: {safe_filename}")

        return {
            "status": "success",
            "migration": safe_filename,
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


@router.get("/admin/ping")
async def admin_ping():
    """Simple ping endpoint to verify admin routes are working."""
    return {
        "status": "ok",
        "message": "Admin routes are working",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/admin/zoho-sync-status")
async def get_zoho_sync_status(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Get comprehensive Zoho continuous sync status and metrics.

    Returns:
        - Webhook processing stats (pending, success, failed, conflict)
        - Performance metrics (latency, dedupe hit rate, conflict rate)
        - Per-module sync status and record counts
        - Recent sync history

    Requires API key authentication.

    Example:
        GET /api/teams/admin/zoho-sync-status
        Header: X-API-Key: your-api-key
    """
    # Verify API key (only executives and system admins)
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key or api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    try:
        # Use shared Redis cache manager for 60-second TTL on metrics
        from well_shared.cache.redis_manager import RedisCacheManager
        redis_manager = RedisCacheManager()

        cache_key = "admin:zoho-sync-status:metrics"
        cached_metrics = await redis_manager.client.get(cache_key)

        if cached_metrics:
            logger.debug("Returning cached sync status metrics")
            return json.loads(cached_metrics)

        # Fetch fresh metrics from database
        conn = await get_database_connection()

        try:
            # 1. Webhook processing stats
            webhook_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE processing_status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE processing_status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE processing_status = 'success') as success,
                    COUNT(*) FILTER (WHERE processing_status = 'failed') as failed,
                    COUNT(*) FILTER (WHERE processing_status = 'conflict') as conflict,
                    COUNT(*) as total_received
                FROM zoho_webhook_log
                WHERE received_at >= NOW() - INTERVAL '24 hours'
            """)

            # 2. Performance metrics (last 24 hours)
            performance = await conn.fetchrow("""
                WITH latency_calc AS (
                    SELECT EXTRACT(EPOCH FROM (processed_at - received_at)) as latency_seconds
                    FROM zoho_webhook_log
                    WHERE processing_status = 'success'
                      AND processed_at IS NOT NULL
                      AND received_at >= NOW() - INTERVAL '24 hours'
                )
                SELECT
                    AVG(latency_seconds) * 1000 as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_seconds) * 1000 as p95_latency_ms
                FROM latency_calc
            """)

            # 3. Dedupe hit rate (successful dedupe / total received)
            dedupe_stats = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(dedupe_hit_count), 0) as dedupe_hits,
                    COALESCE(SUM(webhook_count), 0) as total_webhooks
                FROM zoho_sync_metadata
            """)

            dedupe_hit_rate = (
                dedupe_stats["dedupe_hits"] / dedupe_stats["total_webhooks"]
                if dedupe_stats["total_webhooks"] > 0 else 0.0
            )

            # 4. Conflict rate
            conflict_rate = (
                webhook_stats["conflict"] / webhook_stats["total_received"]
                if webhook_stats["total_received"] > 0 else 0.0
            )

            # 5. Per-module status with accurate record counts
            modules = await conn.fetch("""
                SELECT
                    m.sync_type as module,
                    m.sync_status,
                    m.last_successful_sync_at,
                    m.next_sync_at,
                    m.records_synced,
                    m.records_created,
                    m.records_updated,
                    m.records_failed,
                    m.sync_duration_seconds,
                    m.error_message,
                    COALESCE(s.n_live_tup, 0) as record_count
                FROM zoho_sync_metadata m
                LEFT JOIN pg_stat_user_tables s ON s.relname = 'zoho_' || LOWER(m.sync_type)
                WHERE m.sync_type IN ('Leads', 'Deals', 'Contacts', 'Accounts')
                ORDER BY
                    CASE m.sync_type
                        WHEN 'Leads' THEN 1
                        WHEN 'Deals' THEN 2
                        WHEN 'Contacts' THEN 3
                        WHEN 'Accounts' THEN 4
                    END
            """)

            # Build response
            response = {
                "status": "healthy" if webhook_stats["failed"] < 10 else "degraded",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "webhook_stats": {
                    "total_received_24h": webhook_stats["total_received"],
                    "pending": webhook_stats["pending"],
                    "processing": webhook_stats["processing"],
                    "success": webhook_stats["success"],
                    "failed": webhook_stats["failed"],
                    "conflict": webhook_stats["conflict"]
                },
                "performance": {
                    "avg_latency_ms": round(performance["avg_latency_ms"] or 0, 2),
                    "p95_latency_ms": round(performance["p95_latency_ms"] or 0, 2),
                    "dedupe_hit_rate": round(dedupe_hit_rate, 3),
                    "conflict_rate": round(conflict_rate, 4)
                },
                "modules": {
                    row["module"]: {
                        "sync_status": row["sync_status"],
                        "last_sync": row["last_successful_sync_at"].isoformat() + "Z" if row["last_successful_sync_at"] else None,
                        "next_sync": row["next_sync_at"].isoformat() + "Z" if row["next_sync_at"] else None,
                        "records_synced": row["records_synced"] or 0,
                        "records_created": row["records_created"] or 0,
                        "records_updated": row["records_updated"] or 0,
                        "records_failed": row["records_failed"] or 0,
                        "duration_seconds": row["sync_duration_seconds"] or 0,
                        "error_message": row["error_message"],
                        "total_records": row["record_count"] or 0
                    }
                    for row in modules
                },
                "health_checks": {
                    "webhook_receiver": "ok",
                    "service_bus": "ok" if webhook_stats["pending"] < 100 else "degraded",
                    "worker": "ok" if webhook_stats["processing"] < 50 else "degraded",
                    "database": "ok"
                }
            }

            # Cache for 60 seconds
            await redis_manager.client.setex(
                cache_key,
                60,
                json.dumps(response, default=str)
            )

            return response

        finally:
            # Always release connection back to pool
            await conn.close()

    except Exception as e:
        logger.error(f"Error fetching sync status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching sync status: {str(e)}")


@router.post("/admin/test-query-engine")
async def test_query_engine(
    query: str = "count deals from last week",
    user_email: str = "steve@emailthewell.com",
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Test endpoint to verify query engine is working correctly in production.

    Requires API key authentication.

    Example:
        POST /api/teams/admin/test-query-engine?query=show+TWAV115357&user_email=steve@emailthewell.com
    """
    # Verify API key
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key or api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    try:
        from app.api.teams.query_engine import QueryEngine

        logger.info(f"🧪 Testing query engine: query='{query}', user={user_email}")

        # Create query engine instance
        engine = QueryEngine()

        # Get database connection
        manager = await get_connection_manager()
        async with manager.get_connection() as db:
            # Check user role
            role = await engine._check_user_role(user_email, db)

            # Process query
            result = await engine.process_query(
                query=query,
                user_email=user_email,
                db=db
            )

            return {
                "status": "success",
                "test_info": {
                    "query": query,
                    "user_email": user_email,
                    "user_role": role,
                    "llm_available": engine.use_llm,
                    "model": engine.model,
                    "client_type": type(engine.client).__name__ if engine.client else None
                },
                "result": {
                    "text": result.get("text"),
                    "confidence_score": result.get("confidence_score"),
                    "data_count": len(result.get("data", [])) if isinstance(result.get("data"), list) else result.get("data")
                },
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"Query engine test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.post("/admin/test-digest-delivery")
async def test_digest_delivery(
    user_id: str = "test-user-daniel",
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Test endpoint to trigger immediate digest delivery for a specific user.
    Bypasses the scheduled time check.

    Requires API key authentication.
    """
    # Verify API key
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key or api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    try:
        from app.jobs.weekly_digest_scheduler import WeeklyDigestScheduler

        # Create scheduler instance
        scheduler = WeeklyDigestScheduler()
        await scheduler.initialize()

        # Get user preferences
        async with scheduler.db_manager.get_connection() as conn:
            user_prefs = await conn.fetchrow("""
                SELECT
                    user_id, user_email, user_name, delivery_email,
                    default_audience, max_candidates_per_digest, timezone
                FROM teams_user_preferences
                WHERE user_id = $1 AND subscription_active = true
            """, user_id)

            if not user_prefs:
                raise HTTPException(
                    status_code=404,
                    detail=f"No active subscription found for user {user_id}"
                )

            # Convert to dict for processing
            subscription = dict(user_prefs)

        # Process the subscription (this will generate and send the digest)
        logger.info(f"Test delivery triggered for user {user_id}")
        success = await scheduler.process_subscription(subscription)

        await scheduler.close()

        if success:
            return {
                "status": "success",
                "message": f"Digest delivery triggered for {user_id}",
                "user_id": user_id,
                "delivery_email": subscription["delivery_email"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "failed",
                "message": "Digest generation or delivery failed",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test delivery error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test delivery failed: {str(e)}")


@router.post("/admin/send_vault_alerts_to_bosses")
async def send_vault_alerts_to_bosses(
    from_date: Optional[str] = None,
    date_range_days: int = 30,
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Send vault candidate alerts to executives for approval.

    This endpoint generates advisor and executive vault alerts and sends them
    via email to Steve, Brandon, and Daniel for review before broader distribution.

    Args:
        from_date: Optional start date (defaults to 30 days ago, format: YYYY-MM-DD)
        date_range_days: Number of days of candidates to include (default: 30)
        api_key: Required API key for authentication

    Returns:
        JSON with status, emails_sent count, execution_time_ms
    """
    import time

    # Verify API key
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key or api_key != expected_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    start_time = time.time()

    try:
        # Calculate from_date if not provided
        if not from_date:
            from_date = (datetime.now() - timedelta(days=date_range_days)).strftime("%Y-%m-%d")

        # Initialize generator
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # Generate alerts for both audiences
            logger.info(f"Generating vault alerts: from_date={from_date}, range={date_range_days} days")
            results = await generator.generate_alerts(
                custom_filters={'date_range_days': date_range_days},
                save_files=False  # Don't save files for email delivery
            )

            # Extract HTML content
            advisor_html = results.get('advisor_html', '')
            executive_html = results.get('executive_html', '')

            if not advisor_html or not executive_html:
                raise ValueError("Failed to generate HTML content for vault alerts")

            # Boss recipients
            bosses = [
                ('steve@emailthewell.com', 'Steve'),
                ('brandon@emailthewell.com', 'Brandon'),
                ('daniel.romitelli@emailthewell.com', 'Daniel')
            ]

            # Initialize email scheduler
            from app.jobs.weekly_digest_scheduler import WeeklyDigestScheduler
            scheduler = WeeklyDigestScheduler()
            await scheduler.initialize()

            emails_sent = 0

            # Send emails to each boss
            for email, name in bosses:
                subject = f"Vault Alert Approval - {date_range_days} Days ({from_date})"

                # Combine both HTML formats
                full_html = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; }}
                        .section {{ margin-bottom: 40px; }}
                        .section h2 {{ color: #2c5282; border-bottom: 2px solid #2c5282; padding-bottom: 10px; }}
                    </style>
                </head>
                <body>
                    <h1>Vault Candidate Alerts - Awaiting Your Approval</h1>
                    <p>Hi {name},</p>
                    <p>Please review the vault candidate alerts below. Once approved, these will be sent to advisors and executives.</p>

                    <div class="section">
                        <h2>Advisor Format</h2>
                        {advisor_html}
                    </div>

                    <div class="section">
                        <h2>Executive Format</h2>
                        {executive_html}
                    </div>

                    <p>Reply to this email with "Approved" to proceed with distribution.</p>
                </body>
                </html>
                """

                # Send email (SYNCHRONOUS - no await)
                logger.info(f"Sending vault alerts email to {email}")
                scheduler.send_email(
                    to_email=email,
                    subject=subject,
                    html_body=full_html
                )
                emails_sent += 1

            await scheduler.close()

        finally:
            await generator.close()

        execution_time_ms = int((time.time() - start_time) * 1000)

        metadata = results.get('metadata', {})

        return {
            "status": "success",
            "emails_sent": emails_sent,
            "recipients": [email for email, _ in bosses],
            "from_date": from_date,
            "date_range_days": date_range_days,
            "advisor_count": metadata.get('advisor_count', 0),
            "executive_count": metadata.get('executive_count', 0),
            "total_candidates": metadata.get('total_candidates', 0),
            "execution_time_ms": execution_time_ms,
            "data_source": results.get('data_source', 'unknown')
        }

    except Exception as e:
        logger.error(f"Boss email send failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def handle_clarification_response(
    user_id: str,
    user_email: str,
    session_id: str,
    clarification_response: str,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """
    Handle user's response to clarification question and execute refined query.

    Args:
        user_id: Teams user ID
        user_email: User's email
        session_id: Clarification session ID
        clarification_response: User's clarification answer
        db: Database connection

    Returns:
        Response with query results
    """
    logger.info(f"Handling clarification response from {user_email}: session={session_id}, response={clarification_response}")

    try:
        # Get clarification engine and memory manager
        clarification_engine = await get_clarification_engine()
        memory_manager = await get_memory_manager()

        # Retrieve clarification session
        session = clarification_engine.get_clarification_session(session_id)
        if not session:
            return {
                "type": "message",
                "text": "⏱️ That clarification session has expired. Please ask your question again."
            }

        # Store user's clarification response in memory
        await memory_manager.add_message(
            user_id=user_id,
            role="user",
            content=clarification_response,
            db=db
        )

        # Merge clarification response with partial intent
        merged_intent = clarification_engine.merge_clarification_response(
            session=session,
            user_response=clarification_response
        )

        # Build refined query by combining original query with clarification
        original_query = session["original_query"]
        refined_query = f"{original_query} {clarification_response}"

        logger.info(f"Refined query: '{refined_query}' with merged intent: {merged_intent}")

        # Get conversation context
        conversation_context = await memory_manager.get_context_for_query(
            user_id=user_id,
            current_query=refined_query,
            db=db
        )

        # Execute refined query with merged intent (skip classification)
        result = await process_natural_language_query(
            query=refined_query,
            user_email=user_email,
            db=db,
            conversation_context=conversation_context,
            override_intent=merged_intent  # NEW: Skip classification
        )

        # Store assistant response in memory
        response_text = result.get("text", "I couldn't process that query.")
        await memory_manager.add_message(
            user_id=user_id,
            role="assistant",
            content=response_text,
            db=db
        )

        # Clear clarification session
        clarification_engine.clear_clarification_session(session_id)

        # Return response
        if result.get("card"):
            attachment = CardFactory.adaptive_card(result["card"]["content"])
            response = MessageFactory.attachment(attachment)
            if result.get("text"):
                response.text = result["text"]
            return response
        else:
            return {
                "type": "message",
                "text": response_text
            }

    except Exception as e:
        logger.error(f"Error handling clarification response: {e}", exc_info=True)
        return {
            "type": "message",
            "text": f"❌ Error processing your clarification: {str(e)}\n\nPlease try asking your question again."
        }


# ============================================
# Vault Alerts Handlers (Executive-Only Feature)
# ============================================

async def show_vault_alerts_builder(
    user_id: str,
    user_email: str,
    user_name: str,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """
    Show vault alerts subscription builder card (executive-only).

    Args:
        user_id: Teams user ID
        user_email: User's email address
        user_name: User's display name
        db: Database connection

    Returns:
        Message with vault alerts builder adaptive card
    """
    logger.info(f"📧 Showing vault alerts builder for {user_email}")

    # Check if user has vault alerts access (executive-only)
    has_access = await db.fetchval(
        "SELECT has_vault_alerts_access($1)",
        user_email
    )

    if not has_access:
        return {
            "type": "message",
            "text": "⚠️ Vault Alerts is an executive-only feature. Only Steve, Brandon, and Daniel have access to customize and subscribe to vault candidate alerts."
        }

    # Get current vault alerts settings
    current_settings = await db.fetchval(
        """
        SELECT vault_alerts_settings
        FROM teams_user_preferences
        WHERE user_id = $1
        """,
        user_id
    )

    if isinstance(current_settings, str):
        try:
            current_settings = json.loads(current_settings)
        except json.JSONDecodeError:
            current_settings = {}

    # Create and send vault alerts builder card
    card = create_vault_alerts_builder_card(current_settings=current_settings)
    attachment = CardFactory.adaptive_card(card["content"])
    return MessageFactory.attachment(attachment)


async def save_vault_alerts_subscription(
    user_id: str,
    user_email: str,
    settings: Dict[str, Any],
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """
    Save vault alerts subscription settings.

    Args:
        user_id: Teams user ID
        user_email: User's email address
        settings: Form data from adaptive card
        db: Database connection

    Returns:
        Confirmation message
    """
    logger.info(f"💾 Saving vault alerts subscription for {user_email}")

    # Check access
    has_access = await db.fetchval(
        "SELECT has_vault_alerts_access($1)",
        user_email
    )

    if not has_access:
        return {
            "type": "message",
            "text": "❌ You don't have permission to subscribe to vault alerts."
        }

    # Parse form data
    audience = settings.get('audience', 'advisors')
    frequency = settings.get('frequency', 'weekly')
    delivery_email = settings.get('delivery_email', '').strip()
    max_candidates_raw = settings.get('max_candidates', 50)
    try:
        max_candidates = int(max_candidates_raw)
    except (TypeError, ValueError):
        max_candidates = 50
    max_candidates = max(1, min(max_candidates, 200))

    # Parse custom filters
    locations_str = settings.get('locations', '').strip()
    locations = [loc.strip() for loc in locations_str.split(',') if loc.strip()] if locations_str else []

    designations_str = settings.get('designations', '').strip()
    designations = [des.strip() for des in designations_str.split(',') if des.strip()] if designations_str else []

    availability = settings.get('availability', '').strip() or None

    compensation_min_str = settings.get('compensation_min', '')
    compensation_min = int(compensation_min_str) if compensation_min_str and str(compensation_min_str).strip() else None

    compensation_max_str = settings.get('compensation_max', '')
    compensation_max = int(compensation_max_str) if compensation_max_str and str(compensation_max_str).strip() else None

    date_range_days_str = settings.get('date_range_days', '')
    date_range_days = int(date_range_days_str) if date_range_days_str and str(date_range_days_str).strip() else None

    search_terms_str = settings.get('search_terms', '').strip()
    search_terms = [term.strip() for term in search_terms_str.split(',') if term.strip()] if search_terms_str else []

    # Validate required fields
    if not delivery_email:
        return {
            "type": "message",
            "text": "❌ Delivery email is required. Please provide an email address."
        }

    # Build vault_alerts_settings JSONB
    vault_settings = {
        "audience": audience,
        "frequency": frequency,
        "delivery_email": delivery_email,
        "max_candidates": max_candidates,
        "custom_filters": {
            "locations": locations,
            "designations": designations,
            "availability": availability,
            "compensation_min": compensation_min,
            "compensation_max": compensation_max,
            "date_range_days": date_range_days,
            "search_terms": search_terms
        }
    }

    # Save to database
    await db.execute(
        """
        UPDATE teams_user_preferences
        SET vault_alerts_enabled = TRUE,
            vault_alerts_settings = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
        """,
        user_id,
        json.dumps(vault_settings)
    )

    logger.info(f"✅ Vault alerts subscription saved for {user_email}")

    # Build confirmation message
    filters_summary = []
    if locations:
        filters_summary.append(f"📍 Locations: {', '.join(locations[:3])}{'...' if len(locations) > 3 else ''}")
    if designations:
        filters_summary.append(f"🎓 Designations: {', '.join(designations)}")
    if availability:
        filters_summary.append(f"⏰ Availability: {availability}")
    if compensation_min or compensation_max:
        comp_range = f"${compensation_min:,}" if compensation_min else "Any"
        comp_range += f" - ${compensation_max:,}" if compensation_max else " - Any"
        filters_summary.append(f"💰 Compensation: {comp_range}")
    if date_range_days:
        filters_summary.append(f"📅 Last {date_range_days} days")
    if search_terms:
        filters_summary.append(f"🔍 Search: {', '.join(search_terms[:2])}{'...' if len(search_terms) > 2 else ''}")

    filters_text = "\n".join(filters_summary) if filters_summary else "No custom filters (all candidates)"

    confirmation = f"""✅ **Vault Alerts Subscription Saved**

**Basic Settings:**
• Audience: {audience.title()}
• Frequency: {frequency.title()}
• Delivery Email: {delivery_email}
• Max Candidates: {max_candidates}

**Custom Filters:**
{filters_text}

You'll receive your first vault alert on {frequency} schedule. You can update these settings anytime by typing `vault alerts`."""

    return {
        "type": "message",
        "text": confirmation
    }


async def preview_vault_alerts(
    user_email: str,
    settings: Dict[str, Any],
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """
    Generate preview of vault alerts with custom filters.

    Args:
        user_email: User's email address
        settings: Form data from adaptive card
        db: Database connection

    Returns:
        Preview message with metadata
    """
    logger.info(f"👁️ Generating vault alerts preview for {user_email}")

    # Check access
    has_access = await db.fetchval(
        "SELECT has_vault_alerts_access($1)",
        user_email
    )

    if not has_access:
        return {
            "type": "message",
            "text": "❌ You don't have permission to preview vault alerts."
        }

    # Parse custom filters (same as save function)
    locations_str = settings.get('locations', '').strip()
    locations = [loc.strip() for loc in locations_str.split(',') if loc.strip()] if locations_str else []

    designations_str = settings.get('designations', '').strip()
    designations = [des.strip() for des in designations_str.split(',') if des.strip()] if designations_str else []

    availability = settings.get('availability', '').strip() or None

    compensation_min_str = settings.get('compensation_min', '')
    compensation_min = int(compensation_min_str) if compensation_min_str and str(compensation_min_str).strip() else None

    compensation_max_str = settings.get('compensation_max', '')
    compensation_max = int(compensation_max_str) if compensation_max_str and str(compensation_max_str).strip() else None

    date_range_days_str = settings.get('date_range_days', '')
    date_range_days = int(date_range_days_str) if date_range_days_str and str(date_range_days_str).strip() else None

    search_terms_str = settings.get('search_terms', '').strip()
    search_terms = [term.strip() for term in search_terms_str.split(',') if term.strip()] if search_terms_str else []

    max_candidates_raw = settings.get('max_candidates', 50)
    try:
        max_candidates = int(max_candidates_raw)
    except (TypeError, ValueError):
        max_candidates = 50
    max_candidates = max(1, min(max_candidates, 200))
    audience = settings.get('audience', 'advisors')

    # Build custom_filters dict
    custom_filters = {}
    if locations:
        custom_filters['locations'] = locations
    if designations:
        custom_filters['designations'] = designations
    if availability:
        custom_filters['availability'] = availability
    if compensation_min:
        custom_filters['compensation_min'] = compensation_min
    if compensation_max:
        custom_filters['compensation_max'] = compensation_max
    if date_range_days:
        custom_filters['date_range_days'] = date_range_days
    if search_terms:
        custom_filters['search_terms'] = search_terms

    try:
        # Generate vault alerts using VaultAlertsGenerator
        generator = VaultAlertsGenerator()
        result = await generator.generate_alerts(
            custom_filters=custom_filters if custom_filters else None,
            max_candidates=max_candidates,
            save_files=False  # Don't save files for preview
        )

        metadata = result['metadata']
        total_candidates = metadata['total_candidates']
        advisor_count = metadata['advisor_count']
        executive_count = metadata['executive_count']
        cache_hit_rate = metadata['cache_hit_rate']
        generation_time = metadata['generation_time_seconds']

        # Build preview message
        filters_applied = "\n".join([
            f"  • {key}: {value}"
            for key, value in metadata['filters_applied'].items()
            if value
        ]) if metadata['filters_applied'] else "  None (all candidates included)"

        preview_msg = f"""👁️ **Vault Alerts Preview**

**Results:**
• Total Candidates Found: {total_candidates}
• Advisors: {advisor_count}
• Executives: {executive_count}

**Audience Selection:** {audience}
  ↳ You will receive: {"Advisors only" if audience == "advisors" else "Executives only" if audience == "executives" else "Both advisors and executives"}

**Custom Filters Applied:**
{filters_applied}

**Performance:**
• Generation Time: {generation_time}s
• Cache Hit Rate: {cache_hit_rate * 100:.0f}%

💡 If the results look good, click **Save & Subscribe** to activate your vault alerts subscription."""

        return {
            "type": "message",
            "text": preview_msg
        }

    except Exception as e:
        logger.error(f"Error generating vault alerts preview: {e}", exc_info=True)
        return {
            "type": "message",
            "text": f"❌ Error generating preview: {str(e)}\n\nPlease check your filters and try again."
        }
