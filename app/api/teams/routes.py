"""
Microsoft Teams Bot Framework webhook endpoints for TalentWell.
Handles Teams activities, user preferences, and digest generation with database tracking.
"""
import logging
import uuid
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import asyncpg

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


# Database dependency
async def get_db_connection():
    """Get database connection for Teams integration."""
    try:
        conn = await get_database_connection()
        yield conn
    finally:
        if conn:
            await conn.close()


# Main webhook endpoint
@router.post("/webhook")
async def teams_webhook(
    activity: TeamsActivity,
    request: Request,
    db: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Microsoft Teams Bot Framework webhook endpoint.
    Handles all incoming Teams activities (messages, invokes, conversation updates).

    No API key required - uses Azure AD authentication from Bot Framework.
    """
    try:
        logger.info(f"Received Teams activity: {activity.type}")

        # Route activity based on type
        if activity.type == "message":
            return await handle_message_activity(activity, db)
        elif activity.type == "invoke":
            return await handle_invoke_activity(activity, db)
        elif activity.type == "conversationUpdate":
            return await handle_conversation_update(activity, db)
        else:
            logger.warning(f"Unhandled activity type: {activity.type}")
            return {"status": "ignored"}

    except Exception as e:
        logger.error(f"Error in Teams webhook: {e}", exc_info=True)
        error_card = create_error_card(f"An error occurred: {str(e)}")
        return {
            "type": "message",
            "attachments": [error_card]
        }


async def handle_message_activity(
    activity: TeamsActivity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle incoming text message from Teams user."""

    # Extract user info
    user_id = activity.from_.get("id", "") if activity.from_ else ""
    user_name = activity.from_.get("name", "") if activity.from_ else ""
    user_email = activity.from_.get("userPrincipalName", "") if activity.from_ else ""
    conversation_id = activity.conversation.get("id", "") if activity.conversation else ""

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
    if any(greeting in message_text for greeting in ["hello", "hi", "hey", "help"]):
        card = create_welcome_card(user_name.split()[0] if user_name else "there")
        return {
            "type": "message",
            "attachments": [card]
        }

    elif message_text.startswith("help"):
        card = create_help_card()
        return {
            "type": "message",
            "attachments": [card]
        }

    elif message_text.startswith("digest"):
        # Parse audience from message (e.g., "digest steve_perry")
        parts = message_text.split()
        audience = parts[1] if len(parts) > 1 else "global"

        return await generate_digest_preview(
            user_id=user_id,
            user_email=user_email,
            conversation_id=conversation_id,
            audience=audience,
            db=db
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

        return {
            "type": "message",
            "text": "I didn't understand that command. Here's what I can do:",
            "attachments": [card]
        }


async def handle_invoke_activity(
    activity: TeamsActivity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle Adaptive Card button clicks (invoke actions)."""

    try:
        # Extract action data
        action_data = activity.value or {}
        action = action_data.get("action", "")

        user_id = activity.from_.get("id", "") if activity.from_ else ""
        user_email = activity.from_.get("userPrincipalName", "") if activity.from_ else ""
        conversation_id = activity.conversation.get("id", "") if activity.conversation else ""

        logger.info(f"Invoke action: {action} from user {user_email}")

        if action == "generate_digest_preview":
            audience = action_data.get("audience", "global")
            return await generate_digest_preview(
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

            return await generate_full_digest(
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

            return await generate_digest_preview(
                user_id=user_id,
                user_email=user_email,
                conversation_id=conversation_id,
                audience=filters["audience"],
                db=db,
                filters=filters
            )

        elif action == "save_preferences":
            # Save user preferences
            return await save_user_preferences(
                user_id=user_id,
                user_email=user_email,
                preferences=action_data,
                db=db
            )

        else:
            logger.warning(f"Unknown invoke action: {action}")
            return {
                "type": "message",
                "text": f"Unknown action: {action}"
            }

    except Exception as e:
        logger.error(f"Error handling invoke: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        return {
            "type": "message",
            "attachments": [error_card]
        }


async def handle_conversation_update(
    activity: TeamsActivity,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Handle conversation updates (bot added/removed)."""

    # Bot was added to conversation
    if activity.membersAdded:
        for member in activity.membersAdded:
            if member.get("id") != activity.recipient.get("id"):
                # User added bot
                user_name = member.get("name", "there")
                card = create_welcome_card(user_name)

                return {
                    "type": "message",
                    "attachments": [card]
                }

    return {"status": "ok"}


async def generate_digest_preview(
    user_id: str,
    user_email: str,
    conversation_id: str,
    audience: str,
    db: asyncpg.Connection,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate digest preview with top candidates."""

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

        # Create preview card
        card = create_digest_preview_card(
            cards_metadata=cards_metadata,
            audience=audience,
            request_id=request_id
        )

        return {
            "type": "message",
            "attachments": [card]
        }

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
        return {
            "type": "message",
            "attachments": [error_card]
        }


async def generate_full_digest(
    user_id: str,
    user_email: str,
    request_id: str,
    audience: str,
    dry_run: bool,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """Generate full HTML digest email."""

    try:
        # Get request details
        request = await db.fetchrow("""
            SELECT * FROM teams_digest_requests
            WHERE request_id = $1
        """, request_id)

        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Run curator with dry_run=False
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
        """, result.get("html_content"), result.get("subject_line"), request_id)

        return {
            "type": "message",
            "text": f"✅ Digest generated successfully!\n\nSubject: {result.get('subject_line')}\n\n{len(result.get('cards', []))} candidates included."
        }

    except Exception as e:
        logger.error(f"Error generating full digest: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        return {
            "type": "message",
            "attachments": [error_card]
        }


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

        # Create preferences card
        card = create_preferences_card(
            current_audience=prefs["default_audience"],
            digest_frequency=prefs["digest_frequency"],
            notifications_enabled=prefs["notification_enabled"]
        )

        return {
            "type": "message",
            "attachments": [card]
        }

    except Exception as e:
        logger.error(f"Error showing preferences: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        return {
            "type": "message",
            "attachments": [error_card]
        }


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

        # Format analytics message
        analytics_text = f"""
📊 **Your TalentWell Analytics**

**Activity Summary:**
• Total conversations: {activity['conversation_count']}
• Digest requests: {activity['digest_request_count']}
• Last activity: {activity['last_conversation_at'].strftime('%Y-%m-%d %H:%M') if activity['last_conversation_at'] else 'N/A'}

**Recent Digests:**
"""

        for req in recent_requests:
            analytics_text += f"\n• {req['audience']}: {req['cards_generated']} cards ({req['execution_time_ms']}ms) - {req['created_at'].strftime('%Y-%m-%d')}"

        return {
            "type": "message",
            "text": analytics_text
        }

    except Exception as e:
        logger.error(f"Error showing analytics: {e}", exc_info=True)
        error_card = create_error_card(str(e))
        return {
            "type": "message",
            "attachments": [error_card]
        }


# REST API endpoints for external access

@router.get("/health")
async def teams_health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "teams-integration",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/analytics")
async def get_analytics_data(
    user_email: str,
    timeframe: str = "7d",
    db: asyncpg.Connection = Depends(get_db_connection)
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
