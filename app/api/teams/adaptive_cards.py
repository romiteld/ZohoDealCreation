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
    Uses Microsoft Teams best practices: visual hierarchy, containers, spacing.
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
                    "text": "📚 TalentWell Bot Guide",
                    "size": "Large",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "Use these commands to generate candidate digests, manage settings, and view analytics.",
                    "wrap": True,
                    "isSubtle": True,
                    "spacing": "Small"
                },
                # Digest Generation Section
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "📊 Digest Generation",
                            "weight": "Bolder",
                            "size": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Generate candidate summaries filtered by audience type:",
                            "wrap": True,
                            "isSubtle": True,
                            "spacing": "Small"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "`digest`", "value": "Use your default audience"},
                                {"title": "`digest advisors`", "value": "Financial advisors only"},
                                {"title": "`digest c_suite`", "value": "Executives only (CEO, CFO, VP, etc.)"},
                                {"title": "`digest global`", "value": "All candidates"},
                                {"title": "`digest <email>`", "value": "Test mode - sends to your email"}
                            ],
                            "spacing": "Small"
                        }
                    ]
                },
                # Preferences Section
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "⚙️ Preferences",
                            "weight": "Bolder",
                            "size": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Manage your default settings and notification preferences:",
                            "wrap": True,
                            "isSubtle": True,
                            "spacing": "Small"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "`preferences`", "value": "View and edit your settings"}
                            ],
                            "spacing": "Small"
                        }
                    ]
                },
                # Analytics Section
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "📈 Analytics",
                            "weight": "Bolder",
                            "size": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": "View your usage statistics and activity history:",
                            "wrap": True,
                            "isSubtle": True,
                            "spacing": "Small"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "`analytics`", "value": "Show conversation count, digest requests, and recent activity"}
                            ],
                            "spacing": "Small"
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "📊 Generate Digest",
                    "data": {
                        "action": "generate_digest_preview",
                        "audience": "global"
                    }
                },
                {
                    "type": "Action.Submit",
                    "title": "⚙️ My Preferences",
                    "data": {
                        "action": "show_preferences"
                    }
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
                    "type": "TextBlock",
                    "text": "**Default Audience** - Choose which type of candidates to include when you type `digest` without specifying. Filters by job title:\n• **Advisors** - Financial/Wealth/Investment Advisors\n• **C-Suite** - CEOs, CFOs, VPs, Directors, Executives\n• **Global** - All candidates (both types)",
                    "wrap": True,
                    "size": "Small",
                    "isSubtle": True,
                    "spacing": "Medium"
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "default_audience",
                    "label": "Default Audience",
                    "value": current_audience if current_audience != "steve_perry" else "advisors",
                    "choices": [
                        {"title": "Advisors (Financial Advisors)", "value": "advisors"},
                        {"title": "C-Suite (Executives)", "value": "c_suite"},
                        {"title": "Global (All Candidates)", "value": "global"}
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
