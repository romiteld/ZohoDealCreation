"""
Confidence response handlers for Teams Bot natural language processing.
Extracts and modularizes confidence-based response logic from routes.

This module provides handlers for different confidence levels (low, medium, high)
with support for feature-flagged card generation and structured telemetry tracking.
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncpg

from botbuilder.core import MessageFactory, CardFactory
from botbuilder.schema import Activity

from app.api.teams.adaptive_cards import (
    create_clarification_card,
    create_suggestion_card,
    create_error_card
)
from app.api.teams.clarification_engine import get_clarification_engine, RateLimitExceeded
from app.api.teams.conversation_memory import get_memory_manager
from app.config.feature_flags import ENABLE_NLP_CARDS
from app.telemetry import track_event

logger = logging.getLogger(__name__)


class ConfidenceHandler:
    """
    Handles confidence-based responses for natural language queries.

    This class provides methods to handle different confidence levels
    with consistent telemetry tracking and feature flag support.
    """

    def __init__(self, enable_cards: Optional[bool] = None):
        """
        Initialize confidence handler.

        Args:
            enable_cards: Override for card generation feature flag.
                         If None, uses global ENABLE_NLP_CARDS flag.
        """
        self.enable_cards = enable_cards if enable_cards is not None else ENABLE_NLP_CARDS
        self.correlation_id = str(uuid.uuid4())

    async def handle_low_confidence_response(
        self,
        user_id: str,
        user_email: str,
        conversation_id: str,
        activity_id: str,
        confidence: float,
        cleaned_text: str,
        result: Dict[str, Any],
        db: asyncpg.Connection
    ) -> Any:
        """
        Handle low confidence responses with clarification flow.

        Low confidence (< 0.5) triggers a clarification dialog where the bot
        asks for more information to better understand the user's intent.

        Args:
            user_id: Teams user ID
            user_email: User's email address
            conversation_id: Teams conversation ID
            activity_id: Current activity ID
            confidence: Confidence score (0.0 - 1.0)
            cleaned_text: Normalized user query
            result: Query processing result with intent and entities
            db: Database connection

        Returns:
            MessageFactory response with clarification card or text

        Raises:
            RateLimitExceeded: If user has requested too many clarifications
        """
        logger.info(f"Low confidence ({confidence:.2f}) - triggering clarification for user {user_id}")

        # Track telemetry
        track_event("nlp_confidence_response", {
            "confidence_bucket": "low",
            "confidence_score": confidence,
            "enable_cards": self.enable_cards,
            "user_id": user_id,
            "correlation_id": self.correlation_id,
            "query_length": len(cleaned_text)
        })

        # Store in conversation memory
        memory_manager = await get_memory_manager()
        await memory_manager.add_message(
            user_id=user_id,
            role="user",
            content=cleaned_text,
            confidence_score=confidence,
            db=db
        )

        # Update conversation record
        await db.execute("""
            UPDATE teams_conversations
            SET bot_response = $1, confidence_score = $2
            WHERE conversation_id = $3 AND activity_id = $4
        """, "low_confidence_clarification", confidence, conversation_id, activity_id)

        # Get clarification engine
        clarification_engine = await get_clarification_engine()

        try:
            # Create clarification session
            session = await clarification_engine.create_clarification_session(
                user_id=user_id,
                query=cleaned_text,
                intent=result.get("intent", {"intent_type": "unknown", "entities": {}}),
                ambiguity_type=result.get("ambiguity_type", "low_confidence"),
                suggested_options=result.get("suggested_options", [])
            )

            # Build response based on feature flag
            if self.enable_cards:
                # Generate clarification card
                card = create_clarification_card(
                    question=result.get("clarification_message",
                                       "I need more information to help you. What are you looking for?"),
                    options=session["suggested_options"],
                    session_id=session["session_id"],
                    original_query=cleaned_text
                )
                attachment = CardFactory.adaptive_card(card["content"])
                response = MessageFactory.attachment(attachment)

                # Track card generation
                track_event("nlp_card_generated", {
                    "card_type": "clarification",
                    "confidence_bucket": "low",
                    "correlation_id": self.correlation_id
                })
            else:
                # Text-only response
                options_text = "\n".join([
                    f"• {opt['title']}"
                    for opt in session["suggested_options"][:3]
                ])
                response_text = (
                    f"{result.get('clarification_message', 'I need more information to help you.')}\n\n"
                    f"You might be looking for:\n{options_text}\n\n"
                    f"Please provide more details."
                )
                response = MessageFactory.text(response_text)

            return response

        except RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded for {user_id}: {e}")

            # Track rate limit
            track_event("nlp_rate_limit", {
                "user_id": user_id,
                "confidence_bucket": "low",
                "correlation_id": self.correlation_id
            })

            if self.enable_cards:
                error_card = create_error_card(
                    "⏱️ **Too Many Requests**\n\n"
                    "You've asked for clarification too frequently. "
                    "Please wait a few minutes.\n\n_Limit: 3 per 5 min_"
                )
                return MessageFactory.attachment(CardFactory.adaptive_card(error_card["content"]))
            else:
                return MessageFactory.text(
                    "⏱️ Too many requests. Please wait a few minutes before asking for clarification again."
                )

    async def handle_medium_confidence_response(
        self,
        user_id: str,
        user_email: str,
        conversation_id: str,
        activity_id: str,
        confidence: float,
        cleaned_text: str,
        result: Dict[str, Any],
        db: asyncpg.Connection
    ) -> Any:
        """
        Handle medium confidence responses with suggestions.

        Medium confidence (0.5 - 0.8) returns the result but offers
        refinement options to improve the query if needed.

        Args:
            user_id: Teams user ID
            user_email: User's email address
            conversation_id: Teams conversation ID
            activity_id: Current activity ID
            confidence: Confidence score (0.0 - 1.0)
            cleaned_text: Normalized user query
            result: Query processing result
            db: Database connection

        Returns:
            MessageFactory response with suggestion card or text
        """
        logger.info(f"Medium confidence ({confidence:.2f}) - showing suggestion for user {user_id}")

        # Track telemetry
        track_event("nlp_confidence_response", {
            "confidence_bucket": "medium",
            "confidence_score": confidence,
            "enable_cards": self.enable_cards,
            "user_id": user_id,
            "correlation_id": self.correlation_id,
            "query_length": len(cleaned_text)
        })

        # Store in conversation memory
        memory_manager = await get_memory_manager()
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

        # Update conversation record
        await db.execute("""
            UPDATE teams_conversations
            SET bot_response = $1, confidence_score = $2
            WHERE conversation_id = $3 AND activity_id = $4
        """, "medium_confidence_query", confidence, conversation_id, activity_id)

        # Build response based on feature flag
        if self.enable_cards:
            # Create suggestion card with refinement options
            suggestion_card = create_suggestion_card(
                result=result,
                confidence=confidence,
                user_query=cleaned_text
            )
            attachment = CardFactory.adaptive_card(suggestion_card["content"])
            response = MessageFactory.attachment(attachment)
            response.text = response_text

            # Track card generation
            track_event("nlp_card_generated", {
                "card_type": "suggestion",
                "confidence_bucket": "medium",
                "correlation_id": self.correlation_id
            })
        else:
            # Text-only response with inline suggestion
            response = MessageFactory.text(
                f"{response_text}\n\n"
                f"_Confidence: {confidence:.0%}. "
                f"Try adding more specific details like timeframe or person names for better results._"
            )

        return response

    async def handle_high_confidence_response(
        self,
        user_id: str,
        user_email: str,
        conversation_id: str,
        activity_id: str,
        confidence: float,
        cleaned_text: str,
        result: Dict[str, Any],
        db: asyncpg.Connection
    ) -> Any:
        """
        Handle high confidence responses with direct execution.

        High confidence (>= 0.8) executes the query directly without
        additional prompts or suggestions.

        Args:
            user_id: Teams user ID
            user_email: User's email address
            conversation_id: Teams conversation ID
            activity_id: Current activity ID
            confidence: Confidence score (0.0 - 1.0)
            cleaned_text: Normalized user query
            result: Query processing result
            db: Database connection

        Returns:
            MessageFactory response with result card or text
        """
        logger.info(f"High confidence ({confidence:.2f}) - executing directly for user {user_id}")

        # Track telemetry
        track_event("nlp_confidence_response", {
            "confidence_bucket": "high",
            "confidence_score": confidence,
            "enable_cards": self.enable_cards,
            "user_id": user_id,
            "correlation_id": self.correlation_id,
            "query_length": len(cleaned_text),
            "has_card": bool(result.get("card"))
        })

        # Store in conversation memory
        memory_manager = await get_memory_manager()
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

        # Update conversation record
        await db.execute("""
            UPDATE teams_conversations
            SET bot_response = $1, confidence_score = $2
            WHERE conversation_id = $3 AND activity_id = $4
        """, "natural_language_query", confidence, conversation_id, activity_id)

        # Return response based on available content and feature flag
        if result.get("card") and self.enable_cards:
            # We have a card and cards are enabled
            attachment = CardFactory.adaptive_card(result["card"]["content"])
            response = MessageFactory.attachment(attachment)
            if result.get("text"):
                response.text = result["text"]

            # Track card generation
            track_event("nlp_card_generated", {
                "card_type": "result",
                "confidence_bucket": "high",
                "correlation_id": self.correlation_id
            })
        else:
            # Text-only response
            response = MessageFactory.text(response_text)

        return response


async def get_confidence_handler(enable_cards: Optional[bool] = None) -> ConfidenceHandler:
    """
    Factory function to get a confidence handler instance.

    Args:
        enable_cards: Optional override for card generation feature flag

    Returns:
        ConfidenceHandler instance
    """
    return ConfidenceHandler(enable_cards=enable_cards)