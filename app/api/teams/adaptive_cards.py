"""
Adaptive Cards for Microsoft Teams Bot
Creates rich, interactive cards for TalentWell digest previews.
"""
from typing import List, Dict, Any, Optional


def create_welcome_card(user_name: str = "there") -> Dict[str, Any]:
    """
    Create welcome card shown when bot is first added or user says hello.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"👋 Hi {user_name}!",
                    "size": "Large",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "I'm your TalentWell Assistant. I can help you:",
                    "wrap": True
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "📊 Generate Digests", "value": "Create candidate summaries for your team"},
                        {"title": "🔍 Apply Filters", "value": "Filter by audience, owner, date range"},
                        {"title": "⚙️ Manage Preferences", "value": "Set your default audience and notification settings"},
                        {"title": "📈 View Analytics", "value": "See your usage stats and trends"}
                    ]
                },
                {
                    "type": "TextBlock",
                    "text": "**Try these commands:**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "Container",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "• `digest [audience]` - Generate digest preview",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": "• `preferences` - View/edit your settings",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": "• `analytics` - See your usage stats",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": "• `help` - Show this help message",
                            "wrap": True
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Generate Digest",
                    "data": {
                        "action": "generate_digest_preview",
                        "audience": "global"
                    }
                }
            ]
        }
    }


def create_help_card() -> Dict[str, Any]:
    """
    Create help card with detailed command documentation.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "📚 TalentWell Bot Commands",
                    "size": "Large",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "**Digest Generation**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "• `digest` - Generate preview with default settings\n• `digest steve_perry` - Generate for specific audience\n• `digest brandon_hill` - Another audience example",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "**Preferences**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "• `preferences` - View your current settings\n• Use the preference card buttons to update settings",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "**Analytics**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "• `analytics` - View your usage statistics\n• Shows conversation count, digest requests, and activity",
                    "wrap": True
                }
            ]
        }
    }


def create_digest_preview_card(
    cards_metadata: List[Dict[str, Any]],
    audience: str,
    request_id: str
) -> Dict[str, Any]:
    """
    Create digest preview card with candidate summaries.
    Shows top 3 candidates with bullet points.
    """
    # Build candidate items (show first 3)
    candidate_items = []

    for i, card in enumerate(cards_metadata[:3]):
        # Candidate header
        candidate_items.append({
            "type": "TextBlock",
            "text": f"**‼️ {card['candidate_name']} | {card['job_title']}**",
            "weight": "Bolder",
            "size": "Medium",
            "spacing": "Medium" if i > 0 else "Default"
        })

        candidate_items.append({
            "type": "TextBlock",
            "text": f"**🔔 {card['company']} | {card['location']}**",
            "spacing": "Small"
        })

        # Bullets
        bullets_text = "\n".join([f"• {bullet['text']}" for bullet in card['bullets'][:5]])
        candidate_items.append({
            "type": "TextBlock",
            "text": bullets_text,
            "wrap": True,
            "spacing": "Small"
        })

        # Sentiment if available
        if card.get('sentiment_label'):
            sentiment_emoji = "😊" if card['sentiment_label'] == 'positive' else "😐" if card['sentiment_label'] == 'neutral' else "😟"
            candidate_items.append({
                "type": "TextBlock",
                "text": f"{sentiment_emoji} Sentiment: {card['sentiment_label'].title()} | Enthusiasm: {card.get('enthusiasm_score', 0):.0%}",
                "size": "Small",
                "color": "Accent",
                "spacing": "Small"
            })

    # Summary stats
    total_candidates = len(cards_metadata)
    showing = min(3, total_candidates)

    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"📊 Digest Preview: {audience.replace('_', ' ').title()}",
                    "size": "Large",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": f"Showing {showing} of {total_candidates} candidates",
                    "size": "Small",
                    "color": "Accent",
                    "spacing": "None"
                },
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": candidate_items
                },
                {
                    "type": "TextBlock",
                    "text": "**🎯 Next Steps:**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "• Click 'Generate Full Digest' to create the complete email report\n• Use 'Apply Filters' to refine your search\n• Candidates are ranked by composite score (financial metrics, evidence quality, sentiment)",
                    "wrap": True,
                    "size": "Small"
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "✅ Generate Full Digest",
                    "style": "positive",
                    "data": {
                        "action": "generate_digest",
                        "audience": audience,
                        "request_id": request_id,
                        "dry_run": False
                    }
                },
                {
                    "type": "Action.ShowCard",
                    "title": "🔍 Apply Filters",
                    "card": {
                        "type": "AdaptiveCard",
                        "body": [
                            {
                                "type": "Input.Text",
                                "id": "audience",
                                "label": "Audience",
                                "value": audience
                            },
                            {
                                "type": "Input.Date",
                                "id": "from_date",
                                "label": "From Date"
                            },
                            {
                                "type": "Input.Date",
                                "id": "to_date",
                                "label": "To Date"
                            },
                            {
                                "type": "Input.Text",
                                "id": "owner",
                                "label": "Owner Email (optional)"
                            },
                            {
                                "type": "Input.Number",
                                "id": "max_candidates",
                                "label": "Max Candidates",
                                "value": 6,
                                "min": 1,
                                "max": 50
                            }
                        ],
                        "actions": [
                            {
                                "type": "Action.Submit",
                                "title": "Apply",
                                "data": {
                                    "action": "apply_filters"
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }


def create_error_card(error_message: str) -> Dict[str, Any]:
    """
    Create error card for displaying errors to user.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "❌ Error",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Attention"
                },
                {
                    "type": "TextBlock",
                    "text": error_message,
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "Please try again or contact support if the issue persists.",
                    "size": "Small",
                    "spacing": "Medium"
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Try Again",
                    "data": {
                        "action": "generate_digest_preview",
                        "audience": "global"
                    }
                }
            ]
        }
    }


def create_preferences_card(
    current_audience: str = "global",
    digest_frequency: str = "weekly",
    notifications_enabled: bool = True
) -> Dict[str, Any]:
    """
    Create preferences card for user settings.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "⚙️ Your Preferences",
                    "size": "Large",
                    "weight": "Bolder"
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "default_audience",
                    "label": "Default Audience",
                    "value": current_audience,
                    "choices": [
                        {"title": "Global", "value": "global"},
                        {"title": "Steve Perry", "value": "steve_perry"},
                        {"title": "Brandon Hill", "value": "brandon_hill"}
                    ]
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "digest_frequency",
                    "label": "Digest Frequency",
                    "value": digest_frequency,
                    "choices": [
                        {"title": "Daily", "value": "daily"},
                        {"title": "Weekly", "value": "weekly"},
                        {"title": "Monthly", "value": "monthly"}
                    ]
                },
                {
                    "type": "Input.Toggle",
                    "id": "notification_enabled",
                    "label": "Enable Notifications",
                    "value": "true" if notifications_enabled else "false",
                    "valueOn": "true",
                    "valueOff": "false"
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "💾 Save Preferences",
                    "data": {
                        "action": "save_preferences"
                    }
                }
            ]
        }
    }
