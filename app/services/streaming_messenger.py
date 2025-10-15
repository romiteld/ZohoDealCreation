"""
Teams Streaming Messenger

Sends progressive updates to Microsoft Teams during long-running operations.
Used for streaming progress during vault candidate analysis.
"""

import logging
from typing import Dict, Any, Optional
from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ActivityTypes

logger = logging.getLogger(__name__)


class TeamsStreamingMessenger:
    """Send progressive updates to Teams during async operations."""

    def __init__(self, turn_context: TurnContext):
        """
        Initialize streaming messenger.

        Args:
            turn_context: Teams bot turn context for sending activities
        """
        self.turn_context = turn_context
        self.conversation_id = turn_context.activity.conversation.id if turn_context.activity.conversation else None
        self.user_id = turn_context.activity.from_property.id if turn_context.activity.from_property else None
        self.last_activity_id = None

    async def send_progress(self, text: str, emoji: str = "⚡") -> bool:
        """
        Send a progress update message to Teams.

        Args:
            text: Progress message text
            emoji: Emoji prefix (default: ⚡)

        Returns:
            True if successful, False otherwise
        """
        try:
            message = f"{emoji} {text}"
            activity = Activity(
                type=ActivityTypes.message,
                text=message
            )

            result = await self.turn_context.send_activity(activity)
            if result:
                self.last_activity_id = result.id

            logger.info(f"Sent progress update to {self.user_id}: {message}")
            return True

        except Exception as e:
            logger.error(f"Failed to send progress update: {e}")
            return False

    async def send_final_card(self, card_data: Dict[str, Any]) -> bool:
        """
        Send final adaptive card with results.

        Args:
            card_data: Adaptive card JSON data

        Returns:
            True if successful, False otherwise
        """
        try:
            activity = Activity(
                type=ActivityTypes.message,
                attachments=[{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card_data
                }]
            )

            result = await self.turn_context.send_activity(activity)
            if result:
                self.last_activity_id = result.id

            logger.info(f"Sent final card to {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send final card: {e}")
            return False

    async def send_error(self, error_message: str) -> bool:
        """
        Send error message to Teams.

        Args:
            error_message: Error description

        Returns:
            True if successful, False otherwise
        """
        try:
            message = f"❌ {error_message}"
            activity = Activity(
                type=ActivityTypes.message,
                text=message
            )

            result = await self.turn_context.send_activity(activity)
            if result:
                self.last_activity_id = result.id

            logger.warning(f"Sent error message to {self.user_id}: {message}")
            return True

        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
            return False

    async def send_completion(self, text: str, emoji: str = "✅") -> bool:
        """
        Send completion message.

        Args:
            text: Completion message text
            emoji: Emoji prefix (default: ✅)

        Returns:
            True if successful, False otherwise
        """
        try:
            message = f"{emoji} {text}"
            activity = Activity(
                type=ActivityTypes.message,
                text=message
            )

            result = await self.turn_context.send_activity(activity)
            if result:
                self.last_activity_id = result.id

            logger.info(f"Sent completion message to {self.user_id}: {message}")
            return True

        except Exception as e:
            logger.error(f"Failed to send completion message: {e}")
            return False


def create_marketable_candidates_card(candidates: list, total_analyzed: int) -> Dict[str, Any]:
    """
    Create adaptive card for top N marketable candidates.

    Args:
        candidates: List of candidate dicts with:
            - candidate_locator (str): TWAV code
            - score (float): Marketability score
            - location (str): Anonymized location
            - key_bullet (str): Top achievement
            - firm_type (str): Anonymized firm type
            - availability (str): When available
        total_analyzed: Total number of candidates analyzed

    Returns:
        Adaptive card JSON
    """
    # Build candidate items
    candidate_items = []

    for idx, candidate in enumerate(candidates, 1):
        score = candidate.get('score', 0)
        twav = candidate.get('candidate_locator', 'Unknown')
        location = candidate.get('location', 'Unknown')
        key_bullet = candidate.get('key_bullet', 'No details available')
        firm_type = candidate.get('firm_type', 'Advisory firm')
        availability = candidate.get('availability', 'TBD')

        # Score emoji (⭐ for top 3, 🌟 for rest)
        score_emoji = "⭐" if idx <= 3 else "🌟"

        candidate_items.append({
            "type": "Container",
            "separator": True,
            "spacing": "Medium",
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"**{idx}.**",
                                    "weight": "Bolder",
                                    "size": "Large"
                                }
                            ]
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"{score_emoji} **{score:.0f}/100** - {twav}",
                                    "weight": "Bolder",
                                    "color": "Accent"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"📍 {location}",
                                    "isSubtle": True,
                                    "spacing": "Small"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": key_bullet,
                                    "wrap": True,
                                    "spacing": "Small"
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        {"title": "Firm Type:", "value": firm_type},
                                        {"title": "Availability:", "value": availability}
                                    ],
                                    "spacing": "Small"
                                }
                            ]
                        }
                    ]
                }
            ]
        })

    # Build complete card
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "🏆 Top Marketable Vault Candidates",
                "weight": "Bolder",
                "size": "ExtraLarge",
                "color": "Accent"
            },
            {
                "type": "TextBlock",
                "text": f"Analyzed {total_analyzed} candidates from Zoho CRM",
                "isSubtle": True,
                "spacing": "None"
            },
            {
                "type": "TextBlock",
                "text": "---",
                "spacing": "Medium"
            }
        ] + candidate_items,
        "actions": [
            {
                "type": "Action.Submit",
                "title": "📧 Email Full Report",
                "data": {
                    "action": "email_marketability_report",
                    "candidate_ids": [c.get('candidate_locator') for c in candidates]
                }
            }
        ]
    }

    return card
