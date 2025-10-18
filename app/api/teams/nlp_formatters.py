"""
Text-only formatting helpers for Teams Bot NLP responses.
Enforces conversational AI experience without adaptive cards for natural language queries.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def format_clarification_text(
    options: List[Dict[str, str]],
    context: str,
    question: str = "Could you clarify what you mean?"
) -> str:
    """
    Format clarification options as numbered text with flexible reply syntax.

    Args:
        options: List of {"title": str, "value": str} options
        context: Original user query for context
        question: Clarification question to ask

    Returns:
        Formatted text response with numbered options

    Example output:
        🤔 I need a bit more information...

        You asked: "show me recent activity"

        Could you clarify what you mean?

        1️⃣ Search by candidate name
        2️⃣ Search by company
        3️⃣ View recent deal activity
        4️⃣ Show recent meetings

        💡 Reply with a number (1-4) or type your specific request
    """
    # Header with context
    text_parts = [
        "🤔 **I need a bit more information...**\n",
        f"_You asked: \"{context}\"_\n",
        f"{question}\n"
    ]

    # Format options with emoji numbers for visual hierarchy
    emoji_numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for i, option in enumerate(options[:10]):  # Limit to 10 options
        emoji = emoji_numbers[i] if i < len(emoji_numbers) else f"{i+1}."
        text_parts.append(f"{emoji} {option['title']}")

    # Add helpful footer
    text_parts.append("\n💡 _Reply with a number (1-{}) or type your specific request_".format(len(options)))

    return "\n".join(text_parts)


def format_suggestions_as_text(
    suggestions: List[str],
    confidence: float,
    original_query: str
) -> str:
    """
    Convert low-confidence suggestions to conversational text format.

    Args:
        suggestions: List of suggested queries or actions
        confidence: Confidence score (0.0-1.0)
        original_query: User's original query

    Returns:
        Formatted text with suggestions

    Example output:
        🤷 I'm not quite sure what you're looking for...

        You asked: "show me the good ones"

        Did you mean one of these?
        • View top performing advisors
        • Show highly rated candidates
        • Display deals with high probability
        • View candidates with strong credentials

        💡 Try rephrasing or pick one of the suggestions above
    """
    confidence_percent = int(confidence * 100)

    text_parts = [
        f"🤷 **I'm {confidence_percent}% confident about your request...**\n",
        f"_You asked: \"{original_query}\"_\n",
        "**Did you mean one of these?**"
    ]

    # Format suggestions as bullet points
    for suggestion in suggestions[:5]:  # Limit suggestions
        text_parts.append(f"• {suggestion}")

    text_parts.append("\n💡 _Try rephrasing or pick one of the suggestions above_")

    return "\n".join(text_parts)


def format_results_as_text(
    results: Dict[str, Any],
    query: str,
    result_type: str = "search"
) -> str:
    """
    Format query results as readable text instead of cards.

    Args:
        results: Query results dictionary
        query: Original user query
        result_type: Type of result (search, deal, candidate, etc.)

    Returns:
        Formatted text response

    Example output:
        ✅ Found 3 candidates matching your search

        1. **John Smith** - Senior Advisor
           📍 New York, NY | 💰 $500K comp
           📊 $2.5M AUM | Available Q1 2025

        2. **Jane Doe** - Portfolio Manager
           📍 Chicago, IL | 💰 $750K comp
           📊 $5M AUM | Available immediately
    """
    # Extract key information from results
    if "items" in results:
        items = results["items"]
        total_count = len(items)

        text_parts = [
            f"✅ **Found {total_count} {result_type}(s) matching your search**\n"
        ]

        # Format each item
        for i, item in enumerate(items[:10], 1):  # Limit to 10 items
            text_parts.append(_format_single_result(item, i, result_type))

        if total_count > 10:
            text_parts.append(f"\n_...and {total_count - 10} more results_")

    elif "text" in results:
        # Simple text response
        text_parts = [results["text"]]

    else:
        # Fallback for unknown format
        text_parts = [
            "✅ **Query processed successfully**",
            f"_Results for: \"{query}\"_"
        ]

    return "\n\n".join(text_parts)


def _format_single_result(item: Dict[str, Any], index: int, result_type: str) -> str:
    """Format a single result item as text."""

    if result_type == "candidate":
        name = item.get("name", "Unknown")
        title = item.get("title", "N/A")
        location = item.get("location", "N/A")
        comp = item.get("compensation", "N/A")
        aum = item.get("aum", "N/A")
        availability = item.get("availability", "N/A")

        return (
            f"**{index}. {name}** - {title}\n"
            f"   📍 {location} | 💰 {comp}\n"
            f"   📊 {aum} AUM | {availability}"
        )

    elif result_type == "deal":
        name = item.get("name", "Unknown")
        stage = item.get("stage", "N/A")
        owner = item.get("owner", "N/A")
        probability = item.get("probability", 0)
        amount = item.get("amount", "N/A")

        return (
            f"**{index}. {name}**\n"
            f"   📈 {stage} | 👤 {owner}\n"
            f"   🎯 {probability}% probability | 💵 {amount}"
        )

    elif result_type == "meeting":
        title = item.get("title", "Unknown")
        date = item.get("date", "N/A")
        participants = item.get("participants", [])

        return (
            f"**{index}. {title}**\n"
            f"   📅 {date}\n"
            f"   👥 {', '.join(participants[:3])}"
        )

    else:
        # Generic format
        title = item.get("title") or item.get("name") or "Item"
        description = item.get("description", "")

        return f"**{index}. {title}**\n   {description}" if description else f"**{index}. {title}**"


def format_medium_confidence_text(
    result: Dict[str, Any],
    confidence: float,
    query: str
) -> str:
    """
    Format medium confidence results with inline refinement suggestion.

    Args:
        result: Query result
        confidence: Confidence score (0.5-0.8)
        query: Original query

    Returns:
        Formatted text with gentle suggestion to refine
    """
    confidence_percent = int(confidence * 100)

    # Get the main response text
    response_text = result.get("text", "I processed your query but I'm not fully confident about the results.")

    # Add confidence indicator and suggestion
    text_parts = [
        response_text,
        "",
        f"💡 _I'm {confidence_percent}% confident about this response._",
        "_If this isn't what you're looking for, try being more specific or rephrase your question._"
    ]

    return "\n".join(text_parts)


def format_error_text(error_type: str = "general", details: str = "") -> str:
    """
    Format error messages in conversational text.

    Args:
        error_type: Type of error (rate_limit, auth, general, etc.)
        details: Optional error details

    Returns:
        Formatted error text
    """
    error_formats = {
        "rate_limit": (
            "⏱️ **Too Many Requests**\n\n"
            "You've been asking questions pretty quickly! "
            "Please wait a few minutes before trying again.\n\n"
            "_Rate limit: 3 clarifications per 5 minutes_"
        ),
        "auth": (
            "🔒 **Authentication Required**\n\n"
            "I need to verify your identity to access this information. "
            "Please sign in or contact your administrator."
        ),
        "not_found": (
            "🔍 **No Results Found**\n\n"
            "I couldn't find anything matching your request. "
            "Try different search terms or check the spelling."
        ),
        "general": (
            "❌ **Something went wrong**\n\n"
            "I encountered an error processing your request. "
            "Please try again or contact support if the issue persists."
        )
    }

    base_text = error_formats.get(error_type, error_formats["general"])

    if details:
        base_text += f"\n\n_Details: {details}_"

    return base_text


def format_help_text() -> str:
    """
    Format help information as conversational text.

    Returns:
        Formatted help text
    """
    return """
🤖 **Here's what I can help you with:**

**📊 Data Queries**
• "Show me deals closing this month"
• "Find candidates in New York"
• "What meetings do I have this week?"

**🔍 Search**
• "Search for John Smith"
• "Find advisors with $5M+ AUM"
• "Look up recent activity"

**📈 Analytics**
• "Show my team's performance"
• "What's our pipeline status?"
• "Give me conversion metrics"

**⚡ Quick Commands**
• `/help` - Show this help message
• `/digest` - Generate candidate digest
• `/preferences` - Manage your settings
• `/analytics` - View usage statistics

💡 **Tips:**
• Be specific with names and dates
• Use quotes for exact matches ("John Smith")
• Ask follow-up questions to refine results

_Just type your question naturally and I'll help you find what you need!_
"""


def format_confirmation_text(
    action: str,
    details: Dict[str, Any],
    success: bool = True
) -> str:
    """
    Format action confirmation messages.

    Args:
        action: Action that was performed
        details: Details about the action
        success: Whether action succeeded

    Returns:
        Formatted confirmation text
    """
    if success:
        emoji = "✅"
        status = "completed successfully"
    else:
        emoji = "⚠️"
        status = "couldn't be completed"

    confirmations = {
        "digest_sent": f"{emoji} **Digest {status}**\n\nSent to {details.get('recipient', 'team')} with {details.get('count', 0)} candidates.",
        "preferences_updated": f"{emoji} **Preferences {status}**\n\nYour settings have been updated.",
        "subscription_confirmed": f"{emoji} **Subscription {status}**\n\nYou'll receive {details.get('frequency', 'weekly')} updates at {details.get('email', 'your email')}.",
        "search_refined": f"{emoji} **Search refined**\n\nShowing results for: \"{details.get('refined_query', 'your search')}\"",
    }

    return confirmations.get(action, f"{emoji} **Action {status}**")