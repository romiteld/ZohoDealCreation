"""
Adaptive Cards for Microsoft Teams Bot
Creates rich, interactive cards for TalentWell digest previews.
"""
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
    request_id: str,
    test_recipient_email: Optional[str] = None
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

    card = {
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

    if test_recipient_email:
        # Insert a reminder banner near the top of the card body
        banner = {
            "type": "TextBlock",
            "text": f"⚠️ Test mode: the digest email will be sent to {test_recipient_email}",
            "wrap": True,
            "spacing": "Small",
            "color": "Warning"
        }
        card["content"]["body"].insert(1, banner)

        # Propagate test recipient metadata on all submit actions
        def _add_test_recipient_to_action(action: Dict[str, Any]) -> None:
            if action.get("type") != "Action.Submit":
                return
            action.setdefault("data", {}).setdefault("msteams", {}).setdefault("value", {})[
                "test_recipient_email"
            ] = test_recipient_email

        for action in card["content"].get("actions", []):
            _add_test_recipient_to_action(action)
            if action.get("type") == "Action.ShowCard":
                inner_card = action.get("card", {}) or {}
                for inner_action in inner_card.get("actions", []):
                    _add_test_recipient_to_action(inner_action)

    return card


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
