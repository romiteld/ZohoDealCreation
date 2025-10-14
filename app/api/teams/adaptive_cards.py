"""
Adaptive Cards for Microsoft Teams Bot
Creates rich, interactive cards for TalentWell digest previews.
"""
import json
from typing import List, Dict, Any, Optional


def create_welcome_card(user_name: str = "there") -> Dict[str, Any]:
    """
    Create welcome card shown when bot is first added or user says hello.
    Enhanced with brand colors and visual hierarchy.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"👋 Hi {user_name}!",
                    "size": "ExtraLarge",
                    "weight": "Bolder",
                    "color": "Accent"
                },
                {
                    "type": "TextBlock",
                    "text": "I'm your TalentWell Assistant. I can help you:",
                    "wrap": True,
                    "size": "Medium",
                    "spacing": "Small"
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📊 Generate Digests", "value": "Create candidate summaries for your team"},
                                {"title": "🔍 Apply Filters", "value": "Filter by audience, owner, date range"},
                                {"title": "⚙️ Manage Preferences", "value": "Set your default audience and notification settings"},
                                {"title": "📈 View Analytics", "value": "See your usage stats and trends"}
                            ]
                        }
                    ]
                },
                {
                    "type": "TextBlock",
                    "text": "**Quick Start Commands:**",
                    "weight": "Bolder",
                    "color": "Accent",
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
                            "text": "• `help` - Show detailed help",
                            "wrap": True
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "📊 Generate Digest",
                    "data": {
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "generate_digest_preview",
                                "audience": "global"
                            }
                        }
                    }
                }
            ]
        }
    }


def create_help_card() -> Dict[str, Any]:
    """
    Create help card with detailed command documentation.
    Uses Microsoft Teams best practices: visual hierarchy, containers, spacing.
    Enhanced with brand colors and visual hierarchy.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "📚 TalentWell Bot Guide",
                    "size": "ExtraLarge",
                    "weight": "Bolder",
                    "color": "Accent"
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
                            ]
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
                            ]
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
                            ]
                        }
                    ]
                },
                # Natural Language Queries Section
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "💬 Natural Language Queries",
                            "weight": "Bolder",
                            "size": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Ask questions in plain English! Available to all users:",
                            "wrap": True,
                            "isSubtle": True,
                            "spacing": "Small"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Executives", "value": "Full access to all business data and analytics"},
                                {"title": "Recruiters", "value": "Access to your own Zoho deals, notes, and meetings"},
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": "**Example queries:**",
                            "weight": "Bolder",
                            "spacing": "Small"
                        },
                        {
                            "type": "TextBlock",
                            "text": "• \"How many interviews last week?\"\n• \"Show me my deals from Q4\"\n• \"What's the status of John Smith?\"\n• \"Summarize financial advisor candidates\"",
                            "wrap": True,
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
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "generate_digest_preview",
                                "audience": "global"
                            }
                        }
                    }
                },
                {
                    "type": "Action.Submit",
                    "title": "⚙️ My Preferences",
                    "data": {
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "show_preferences"
                            }
                        }
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
    Enhanced with brand colors and visual containers.
    """
    # Build candidate items (show first 3)
    candidate_items = []

    for i, card in enumerate(cards_metadata[:3]):
        # Each candidate in styled container
        candidate_container = {
            "type": "Container",
            "spacing": "Medium" if i > 0 else "Default",
            "separator": i > 0,
            "items": [
                {
                    "type": "TextBlock",
                    "text": f"**‼️ {card['candidate_name']}**",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "Accent"
                },
                {
                    "type": "TextBlock",
                    "text": f"{card['job_title']} at {card['company']}",
                    "weight": "Bolder",
                    "size": "Small",
                    "spacing": "None"
                },
                {
                    "type": "TextBlock",
                    "text": f"📍 {card['location']}",
                    "size": "Small",
                    "isSubtle": True,
                    "spacing": "Small"
                }
            ]
        }

        # Add bullets
        bullets_text = "\n".join([f"• {bullet['text']}" for bullet in card['bullets'][:5]])
        candidate_container["items"].append({
            "type": "TextBlock",
            "text": bullets_text,
            "wrap": True,
            "spacing": "Small"
        })

        # Sentiment if available
        if card.get('sentiment_label'):
            sentiment_color = "Good" if card['sentiment_label'] == 'positive' else "Warning" if card['sentiment_label'] == 'neutral' else "Attention"
            sentiment_emoji = "😊" if card['sentiment_label'] == 'positive' else "😐" if card['sentiment_label'] == 'neutral' else "😟"
            candidate_container["items"].append({
                "type": "TextBlock",
                "text": f"{sentiment_emoji} {card['sentiment_label'].title()} | Enthusiasm: {card.get('enthusiasm_score', 0):.0%}",
                "size": "Small",
                "color": sentiment_color,
                "weight": "Bolder",
                "spacing": "Small"
            })

        candidate_items.append(candidate_container)

    # Summary stats
    total_candidates = len(cards_metadata)
    showing = min(3, total_candidates)

    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"📊 Digest Preview: {audience.replace('_', ' ').title()}",
                    "size": "ExtraLarge",
                    "weight": "Bolder",
                    "color": "Accent"
                },
                {
                    "type": "TextBlock",
                    "text": f"Showing {showing} of {total_candidates} top-ranked candidates",
                    "size": "Medium",
                    "color": "Good",
                    "weight": "Bolder",
                    "spacing": "None"
                },
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": candidate_items
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**🎯 Next Steps:**",
                            "weight": "Bolder"
                        },
                        {
                            "type": "TextBlock",
                            "text": "• Click 'Generate Full Digest' to create the complete email report\n• Use 'Apply Filters' to refine your search\n• Candidates ranked by composite score (financial metrics, evidence quality, sentiment)",
                            "wrap": True,
                            "size": "Small"
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "✅ Generate Full Digest",
                    "data": {
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "generate_digest",
                                "audience": audience,
                                "request_id": request_id,
                                "dry_run": False
                            }
                        }
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
                                    "msteams": {
                                        "type": "invoke",
                                        "value": {
                                            "action": "apply_filters"
                                        }
                                    }
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
            "version": "1.2",
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
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "generate_digest_preview",
                                "audience": "global"
                            }
                        }
                    }
                }
            ]
        }
    }


def create_preferences_card(
    current_audience: str = "global",
    digest_frequency: str = "weekly",
    notifications_enabled: bool = True,
    subscription_active: bool = False,
    delivery_email: str = "",
    max_candidates: int = 6
) -> Dict[str, Any]:
    """
    Create preferences card for user settings.
    Enhanced with brand colors, visual hierarchy, and email subscription fields.
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "⚙️ Your Preferences",
                    "size": "ExtraLarge",
                    "weight": "Bolder",
                    "color": "Accent"
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Default Audience**",
                            "weight": "Bolder",
                            "color": "Accent"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Choose which type of candidates to include when you type `digest` without specifying:\n• **Advisors** - Financial/Wealth/Investment Advisors\n• **C-Suite** - CEOs, CFOs, VPs, Directors, Executives\n• **Global** - All candidates (both types)",
                            "wrap": True,
                            "size": "Small",
                            "isSubtle": True,
                            "spacing": "Small"
                        }
                    ]
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
                    "type": "Container",
                    "spacing": "Medium",
                    "separator": True,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Digest Frequency**",
                            "weight": "Bolder",
                            "color": "Accent"
                        },
                        {
                            "type": "Input.ChoiceSet",
                            "id": "digest_frequency",
                            "label": "How often to receive digests",
                            "value": digest_frequency,
                            "choices": [
                                {"title": "Daily", "value": "daily"},
                                {"title": "Weekly", "value": "weekly"},
                                {"title": "Monthly", "value": "monthly"}
                            ]
                        }
                    ]
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "separator": True,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Notifications**",
                            "weight": "Bolder",
                            "color": "Accent"
                        },
                        {
                            "type": "Input.Toggle",
                            "id": "notification_enabled",
                            "label": "Enable bot notifications",
                            "value": "true" if notifications_enabled else "false",
                            "valueOn": "true",
                            "valueOff": "false"
                        }
                    ]
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "separator": True,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "📧 Weekly Email Subscription",
                            "size": "Large",
                            "weight": "Bolder",
                            "color": "Accent",
                            "spacing": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Receive automatic weekly digests via email. You'll get a confirmation email when you save these settings.",
                            "wrap": True,
                            "size": "Small",
                            "isSubtle": True,
                            "spacing": "Small"
                        }
                    ]
                },
                {
                    "type": "Input.Toggle",
                    "id": "subscription_active",
                    "label": "Subscribe to weekly email digests",
                    "value": "true" if subscription_active else "false",
                    "valueOn": "true",
                    "valueOff": "false"
                },
                {
                    "type": "Input.Text",
                    "id": "delivery_email",
                    "label": "Email Address",
                    "placeholder": "your.email@company.com",
                    "value": delivery_email,
                    "isRequired": False,
                    "spacing": "Small"
                },
                {
                    "type": "Input.Number",
                    "id": "max_candidates",
                    "label": "Max Candidates Per Digest",
                    "value": max_candidates,
                    "min": 1,
                    "max": 20,
                    "spacing": "Small"
                },
                {
                    "type": "TextBlock",
                    "text": "💡 **Tip:** Leave email blank to use your Teams email address. You can choose 1-20 candidates per digest.",
                    "wrap": True,
                    "size": "Small",
                    "isSubtle": True,
                    "spacing": "Small"
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "💾 Save Preferences",
                    "data": {
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "save_preferences"
                            }
                        }
                    }
                }
            ]
        }
    }


def create_clarification_card(
    question: str,
    options: List[Dict[str, str]],
    session_id: str,
    original_query: str
) -> Dict[str, Any]:
    """
    Create Adaptive Card for clarification dialogue with interactive options.

    Args:
        question: Clarification question text
        options: List of {"title": str, "value": str} options
        session_id: Clarification session ID
        original_query: Original user query for context

    Returns:
        Adaptive Card JSON
    """
    body_elements = [
        {
            "type": "TextBlock",
            "text": "🤔 Need Clarification",
            "weight": "Bolder",
            "size": "Large",
            "wrap": True
        },
        {
            "type": "TextBlock",
            "text": question,
            "wrap": True,
            "spacing": "Medium"
        }
    ]

    # Add original query context
    if original_query:
        body_elements.append({
            "type": "TextBlock",
            "text": f"Your question: \"{original_query}\"",
            "wrap": True,
            "isSubtle": True,
            "size": "Small",
            "spacing": "Small"
        })

    # Add options as Input.ChoiceSet if available
    if options:
        choices = [
            {"title": opt["title"], "value": opt["value"]}
            for opt in options
        ]
        body_elements.append({
            "type": "Input.ChoiceSet",
            "id": "clarification_response",
            "choices": choices,
            "style": "expanded",
            "spacing": "Medium"
        })
    else:
        # Fallback to text input
        body_elements.append({
            "type": "Input.Text",
            "id": "clarification_response",
            "placeholder": "Type your answer here...",
            "isMultiline": False,
            "spacing": "Medium"
        })

    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": body_elements,
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "✅ Submit",
                    "data": {
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "submit_clarification",
                                "session_id": session_id
                            }
                        }
                    }
                }
            ]
        }
    }


def create_suggestion_card(
    result: Dict[str, Any],
    confidence: float,
    user_query: str
) -> Dict[str, Any]:
    """
    Inline suggestion card for medium-confidence results (0.5-0.8).
    Shows result with refinement option.

    Args:
        result: Query result dict with text
        confidence: Confidence score (0.0-1.0)
        user_query: Original user query

    Returns:
        Adaptive Card dict for Teams
    """
    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "TextBlock",
                    "text": result.get("text", ""),
                    "wrap": True,
                    "size": "Medium"
                },
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"💡 I'm {int(confidence*100)}% confident. Need to refine?",
                            "isSubtle": True,
                            "size": "Small",
                            "wrap": True
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "🔍 Refine Search",
                    "data": {
                        "msteams": {
                            "type": "invoke",
                            "value": {
                                "action": "refine_query",
                                "original_query": user_query,
                                "confidence": confidence
                            }
                        }
                    }
                }
            ]
        }
    }


def create_vault_alerts_builder_card(
    current_settings: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create vault alerts subscription builder card (executive-only feature).

    Allows executives to customize vault candidate alerts with:
    - Audience selection (advisors/executives/both)
    - Frequency (weekly/biweekly/monthly)
    - Delivery email
    - Max candidates (1-200, unlimited for executives)
    - Custom filters: locations, designations, availability, compensation, date range

    Args:
        current_settings: Existing vault_alerts_settings JSONB from database

    Returns:
        Adaptive Card JSON for vault alerts subscription builder
    """
    # Parse current settings from JSON if necessary
    settings: Dict[str, Any] = current_settings or {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except (json.JSONDecodeError, TypeError):
            settings = {}

    audience = settings.get("audience", "advisors")
    frequency = settings.get("frequency", "weekly")
    delivery_email = settings.get("delivery_email") or ""

    max_candidates = settings.get("max_candidates", 50)
    try:
        max_candidates = int(max_candidates)
    except (TypeError, ValueError):
        max_candidates = 50

    custom_filters = settings.get('custom_filters') or {}
    if isinstance(custom_filters, str):
        try:
            custom_filters = json.loads(custom_filters)
        except (json.JSONDecodeError, TypeError):
            custom_filters = {}

    def _join(items: List[str]) -> str:
        return ', '.join([item for item in items if item])

    locations = _join(custom_filters.get('locations', []))
    designations = _join(custom_filters.get('designations', []))
    availability = custom_filters.get('availability') or ''

    def _to_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            cleaned = str(value).strip()
            return int(cleaned) if cleaned else None
        except (TypeError, ValueError):
            return None

    compensation_min = _to_int(custom_filters.get('compensation_min'))
    compensation_max = _to_int(custom_filters.get('compensation_max'))
    date_range_days = _to_int(custom_filters.get('date_range_days'))
    search_terms = _join(custom_filters.get('search_terms', []))

    def _label(text: str) -> Dict[str, Any]:
        return {
            "type": "TextBlock",
            "text": text,
            "wrap": True,
            "weight": "Bolder",
            "spacing": "Small"
        }

    def _text_input(input_id: str, placeholder: str, value: str) -> Dict[str, Any]:
        return {
            "type": "Input.Text",
            "id": input_id,
            "placeholder": placeholder,
            "value": value,
            "spacing": "Small"
        }

    def _number_input(
        input_id: str,
        placeholder: str,
        min_value: int,
        max_value: Optional[int] = None,
        value: Optional[int] = None
    ) -> Dict[str, Any]:
        element: Dict[str, Any] = {
            "type": "Input.Number",
            "id": input_id,
            "placeholder": placeholder,
            "min": min_value,
            "spacing": "Small"
        }
        if max_value is not None:
            element["max"] = max_value
        if value is not None:
            element["value"] = value
        return element

    body: List[Dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": "🔔 Vault Alerts Subscription",
            "size": "ExtraLarge",
            "weight": "Bolder",
            "color": "Accent"
        },
        {
            "type": "TextBlock",
            "text": "Configure automated weekly vault candidate alerts with custom filtering. You'll receive HTML reports matching your exact criteria via email.",
            "wrap": True,
            "size": "Small",
            "isSubtle": True,
            "spacing": "Small"
        },
        {
            "type": "Container",
            "spacing": "Medium",
            "separator": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": "**Basic Settings**",
                    "weight": "Bolder",
                    "color": "Accent",
                    "size": "Medium"
                }
            ]
        },
        _label("Candidate Audience"),
        {
            "type": "Input.ChoiceSet",
            "id": "audience",
            "value": audience,
            "choices": [
                {"title": "Advisors Only", "value": "advisors"},
                {"title": "Executives Only", "value": "executives"},
                {"title": "Both (Advisors + Executives)", "value": "both"}
            ],
            "spacing": "Small"
        },
        _label("Delivery Frequency"),
        {
            "type": "Input.ChoiceSet",
            "id": "frequency",
            "value": frequency,
            "choices": [
                {"title": "Weekly (every Monday 9 AM)", "value": "weekly"},
                {"title": "Bi-Weekly (every 2 weeks)", "value": "biweekly"},
                {"title": "Monthly (1st of month)", "value": "monthly"}
            ],
            "spacing": "Small"
        },
        _label("📧 Delivery Email"),
        _text_input("delivery_email", "recipient@emailthewell.com", delivery_email),
        _label("Max Candidates Per Alert"),
        _number_input("max_candidates", "50", 1, max_value=200, value=max_candidates),
        {
            "type": "Container",
            "spacing": "Medium",
            "separator": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": "**Custom Filters** (Optional)",
                    "weight": "Bolder",
                    "color": "Accent",
                    "size": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "Refine your alerts with custom filters. Leave blank to include all candidates.",
                    "wrap": True,
                    "size": "Small",
                    "isSubtle": True,
                    "spacing": "Small"
                }
            ]
        },
        _label("📍 Locations (comma-separated)"),
        _text_input("locations", "New York NY, Chicago IL, Dallas TX", locations),
        _label("🎓 Professional Designations (comma-separated)"),
        _text_input("designations", "CFA, CFP, CIMA, CPA", designations),
        _label("⏰ Availability"),
        _text_input("availability", "Immediately, 2 weeks notice, 30 days", availability),
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        _label("💰 Compensation Min ($)"),
                        _number_input("compensation_min", "150000", 0, value=compensation_min)
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        _label("💰 Compensation Max ($)"),
                        _number_input("compensation_max", "250000", 0, value=compensation_max)
                    ]
                }
            ],
            "spacing": "Small"
        },
        _label("📅 Only Include Candidates Added in Last N Days"),
        _number_input("date_range_days", "30", 1, max_value=365, value=date_range_days),
        _label("🔍 Search Terms (comma-separated)"),
        _text_input("search_terms", "portfolio manager, RIA, wealth management", search_terms),
        {
            "type": "Container",
            "spacing": "Medium",
            "separator": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": "💡 **Tips:**",
                    "wrap": True,
                    "weight": "Bolder",
                    "size": "Small",
                    "spacing": "Small"
                },
                {
                    "type": "TextBlock",
                    "text": "• Filters are combined with AND logic (all must match)\n• Leave filters blank to include all candidates\n• Locations: Use full format like 'New York, NY'\n• Compensation: Enter dollar amounts without commas\n• Use Preview to test filters before saving",
                    "wrap": True,
                    "size": "Small",
                    "isSubtle": True,
                    "spacing": "Small"
                }
            ]
        }
    ]

    actions = [
        {
            "type": "Action.Submit",
            "title": "👁️ Preview Alert",
            "data": {
                "msteams": {
                    "type": "invoke",
                    "value": {
                        "action": "preview_vault_alerts"
                    }
                }
            },
            "style": "default"
        },
        {
            "type": "Action.Submit",
            "title": "💾 Save & Subscribe",
            "data": {
                "msteams": {
                    "type": "invoke",
                    "value": {
                        "action": "save_vault_alerts_subscription"
                    }
                }
            },
            "style": "positive"
        }
    ]

    return {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": body,
            "actions": actions
        }
    }
