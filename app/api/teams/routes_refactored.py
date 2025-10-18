"""
Refactored sections of routes.py to use text-only responses for NLP queries.
This file shows the modified sections that replace adaptive cards with text formatting.
"""

# Add these imports at the top of routes.py
from app.api.teams.nlp_formatters import (
    format_clarification_text,
    format_suggestions_as_text,
    format_results_as_text,
    format_medium_confidence_text,
    format_error_text,
    format_help_text
)
from app.api.teams.nlp_parser import (
    parse_clarification_response,
    extract_candidate_reference,
    parse_refinement_input
)

# Import for clarification tracking
import asyncpg


async def track_clarification_interaction(
    db: asyncpg.Connection,
    user_id: str,
    conversation_id: str,
    original_query: str,
    confidence: float,
    clarification_question: str,
    clarification_type: str,
    options: List[Dict[str, str]],
    session_id: str
) -> None:
    """Track clarification interaction in database for analytics."""
    try:
        await db.execute("""
            INSERT INTO conversation_clarifications (
                user_id,
                conversation_id,
                original_query,
                query_confidence,
                clarification_question,
                clarification_type,
                options_presented,
                options_count,
                session_id,
                presented_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        """,
            user_id,
            conversation_id,
            original_query,
            confidence,
            clarification_question,
            clarification_type,
            json.dumps(options),
            len(options),
            session_id
        )
    except Exception as e:
        logger.warning(f"Failed to track clarification: {e}")


async def update_clarification_response(
    db: asyncpg.Connection,
    session_id: str,
    user_response: str,
    chosen_index: Optional[int],
    chosen_value: Optional[str],
    response_method: str,
    was_successful: bool
) -> None:
    """Update clarification record with user's response."""
    try:
        await db.execute("""
            UPDATE conversation_clarifications
            SET
                user_response = $1,
                chosen_option_index = $2,
                chosen_option_value = $3,
                response_method = $4,
                responded_at = NOW(),
                was_successful = $5,
                updated_at = NOW()
            WHERE session_id = $6
        """,
            user_response,
            chosen_index,
            chosen_value,
            response_method,
            was_successful,
            session_id
        )
    except Exception as e:
        logger.warning(f"Failed to update clarification response: {e}")


# REFACTORED SECTION: Lines 650-712 (Low confidence handling)
async def handle_low_confidence_nlp_text_only(
    confidence: float,
    cleaned_text: str,
    user_id: str,
    user_email: str,
    conversation_id: str,
    activity: Activity,
    db: asyncpg.Connection,
    memory_manager,
    clarification_engine
):
    """
    Handle low confidence queries with text-only clarification.
    Replaces adaptive cards with conversational text format.
    """
    logger.info(f"Low confidence ({confidence:.2f}) - triggering text clarification")

    try:
        # Generate clarification question
        clarification_question = await clarification_engine.generate_clarification_question(
            query=cleaned_text,
            intent={"intent_type": "search", "entities": {}},
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

        # Format clarification as text (NEW: Text-only response)
        clarification_text = format_clarification_text(
            options=options,
            context=cleaned_text,
            question=clarification_question
        )

        # Store clarification text in memory
        await memory_manager.add_message(
            user_id=user_id,
            role="assistant",
            content=clarification_text,
            intent_type="clarification",
            db=db
        )

        # Track clarification interaction for analytics (NEW)
        await track_clarification_interaction(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            original_query=cleaned_text,
            confidence=confidence,
            clarification_question=clarification_question,
            clarification_type="vague_search",
            options=options,
            session_id=session["session_id"]
        )

        # Return text-only message (NO CARDS)
        return {
            "type": "message",
            "text": clarification_text
        }

    except RateLimitExceeded as e:
        logger.warning(f"Rate limit exceeded for {user_id}: {e}")
        error_text = format_error_text("rate_limit")

        return {
            "type": "message",
            "text": error_text
        }


# REFACTORED SECTION: Lines 713-752 (Medium confidence handling)
async def handle_medium_confidence_nlp_text_only(
    result: Dict[str, Any],
    confidence: float,
    cleaned_text: str,
    user_id: str,
    conversation_id: str,
    activity: Activity,
    db: asyncpg.Connection,
    memory_manager
):
    """
    Handle medium confidence queries with text response and inline suggestion.
    Replaces suggestion card with conversational text format.
    """
    logger.info(f"Medium confidence ({confidence:.2f}) - showing text with suggestion")

    # Store user message and assistant response in memory
    await memory_manager.add_message(
        user_id=user_id,
        role="user",
        content=cleaned_text,
        confidence_score=confidence,
        db=db
    )

    # Format response with inline suggestion (NEW: Text-only)
    response_text = format_medium_confidence_text(
        result=result,
        confidence=confidence,
        query=cleaned_text
    )

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

    # Return text-only message (NO CARDS)
    return {
        "type": "message",
        "text": response_text
    }


# REFACTORED SECTION: Lines 753-795 (High confidence handling)
async def handle_high_confidence_nlp_text_only(
    result: Dict[str, Any],
    confidence: float,
    cleaned_text: str,
    user_id: str,
    conversation_id: str,
    activity: Activity,
    db: asyncpg.Connection,
    memory_manager
):
    """
    Handle high confidence queries with direct text response.
    For NLP queries, always return text instead of cards.
    """
    logger.info(f"High confidence ({confidence:.2f}) - executing directly with text response")

    # Store user message in conversation memory
    await memory_manager.add_message(
        user_id=user_id,
        role="user",
        content=cleaned_text,
        confidence_score=confidence,
        db=db
    )

    # Format results as text (NEW: Always text for NLP queries)
    if "items" in result or "data" in result:
        # Structured results - format as text
        result_type = result.get("type", "search")
        response_text = format_results_as_text(
            results=result,
            query=cleaned_text,
            result_type=result_type
        )
    else:
        # Simple text response
        response_text = result.get("text", "I couldn't process that query.")

    # Store assistant response in conversation memory
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

    # Return text-only response (NO CARDS for NLP queries)
    return {
        "type": "message",
        "text": response_text
    }


# NEW FUNCTION: Handle clarification responses
async def handle_clarification_response_text(
    turn_context: TurnContext,
    db: asyncpg.Connection
):
    """
    Process user's response to a clarification request.
    Parses flexible input formats and updates tracking.
    """
    activity = turn_context.activity
    user_input = activity.text.strip()
    user_id = activity.from_property.id

    try:
        # Get active clarification session
        session = await db.fetchrow("""
            SELECT
                session_id,
                original_query,
                options_presented,
                clarification_type
            FROM conversation_clarifications
            WHERE user_id = $1
                AND responded_at IS NULL
                AND presented_at >= NOW() - INTERVAL '5 minutes'
            ORDER BY presented_at DESC
            LIMIT 1
        """, user_id)

        if not session:
            # No active clarification - treat as new query
            return None

        options = json.loads(session['options_presented'])

        # Parse user's response with flexible matching
        matched_option = parse_clarification_response(user_input, options)

        if matched_option:
            # User selected an option
            chosen_index = options.index(matched_option)
            response_method = "number" if user_input.isdigit() else "text"

            # Update tracking
            await update_clarification_response(
                db=db,
                session_id=session['session_id'],
                user_response=user_input,
                chosen_index=chosen_index,
                chosen_value=matched_option['value'],
                response_method=response_method,
                was_successful=True
            )

            # Process the refined query
            refined_query = f"{session['original_query']} {matched_option['title']}"

            # Return refined query for processing
            return {
                "refined_query": refined_query,
                "original_query": session['original_query'],
                "clarification_value": matched_option['value']
            }

        else:
            # Could not match - ask for retry
            retry_text = (
                "🤔 I didn't understand your selection.\n\n"
                "Please reply with:\n"
                "• A number (1, 2, 3...)\n"
                "• Or type what you're looking for\n\n"
                "_Original question: \"{}\"_"
            ).format(session['original_query'])

            # Mark as unsuccessful but don't close session
            await update_clarification_response(
                db=db,
                session_id=session['session_id'],
                user_response=user_input,
                chosen_index=None,
                chosen_value=None,
                response_method="unmatched",
                was_successful=False
            )

            return {
                "type": "message",
                "text": retry_text,
                "retry": True
            }

    except Exception as e:
        logger.error(f"Error handling clarification response: {e}")
        return None


# MAIN REFACTORED SECTION: Update the natural language processing flow
# This replaces lines 630-810 in the original routes.py
async def handle_natural_language_query_refactored(
    turn_context: TurnContext,
    db: asyncpg.Connection,
    conversation_id: str
):
    """
    Main handler for natural language queries with text-only responses.
    This replaces the card-based responses with conversational text.
    """
    activity = turn_context.activity
    user_id = activity.from_property.id
    user_email = activity.from_property.name or user_id
    cleaned_text = clean_user_message(activity.text)

    # Check if this is a response to a clarification
    clarification_response = await handle_clarification_response_text(turn_context, db)
    if clarification_response:
        if clarification_response.get("retry"):
            return clarification_response
        elif clarification_response.get("refined_query"):
            # Process the refined query
            cleaned_text = clarification_response["refined_query"]

    # Get conversation context
    memory_manager = await get_memory_manager()
    conversation_context = await memory_manager.get_context_for_query(
        user_id=user_id,
        current_query=cleaned_text,
        db=db
    )

    # Execute query ONCE before branching
    result = await process_natural_language_query(
        query=cleaned_text,
        user_email=user_email,
        db=db,
        conversation_context=conversation_context,
        activity=activity
    )

    # Extract confidence score
    confidence = result.get("confidence_score", 0.8)
    logger.info(f"Query classified with confidence: {confidence:.2f}")

    # Get clarification engine
    clarification_engine = await get_clarification_engine()

    # THREE-WAY BRANCH based on confidence - ALL TEXT RESPONSES
    if confidence < CONFIDENCE_THRESHOLD_LOW:  # <0.5
        return await handle_low_confidence_nlp_text_only(
            confidence=confidence,
            cleaned_text=cleaned_text,
            user_id=user_id,
            user_email=user_email,
            conversation_id=conversation_id,
            activity=activity,
            db=db,
            memory_manager=memory_manager,
            clarification_engine=clarification_engine
        )

    elif confidence < CONFIDENCE_THRESHOLD_MED:  # 0.5-0.8
        return await handle_medium_confidence_nlp_text_only(
            result=result,
            confidence=confidence,
            cleaned_text=cleaned_text,
            user_id=user_id,
            conversation_id=conversation_id,
            activity=activity,
            db=db,
            memory_manager=memory_manager
        )

    else:  # >=0.8
        return await handle_high_confidence_nlp_text_only(
            result=result,
            confidence=confidence,
            cleaned_text=cleaned_text,
            user_id=user_id,
            conversation_id=conversation_id,
            activity=activity,
            db=db,
            memory_manager=memory_manager
        )