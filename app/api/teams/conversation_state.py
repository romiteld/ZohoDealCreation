"""
Conversation state management for Teams Bot.
Uses LangGraph TypedDict pattern for stateful conversations.
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from datetime import datetime
import operator


class ConversationMessage(TypedDict):
    """Individual message in conversation history."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    intent_type: Optional[str]  # Classified intent for this message
    confidence_score: Optional[float]  # Intent classification confidence
    metadata: Optional[Dict[str, Any]]  # Additional context


class ConversationState(TypedDict):
    """
    State for multi-turn conversational AI with Teams Bot.
    Follows LangGraph TypedDict pattern used in langgraph_manager.py.
    """
    # User identification
    user_id: str
    user_email: str
    conversation_id: str

    # Conversation history (last 10 messages)
    # Using Annotated with operator.add for message accumulation
    conversation_history: Annotated[List[ConversationMessage], operator.add]

    # Current query processing
    current_query: Optional[str]
    current_intent: Optional[Dict[str, Any]]  # Latest classified intent
    confidence_score: Optional[float]  # Confidence of current intent (0.0-1.0)

    # Clarification flow
    clarification_needed: bool
    clarification_session_id: Optional[str]  # Track multi-turn clarification
    awaiting_clarification_response: bool
    clarification_context: Optional[Dict[str, Any]]  # Stored context for merging

    # Extracted entities from conversation
    context_entities: Dict[str, Any]  # Accumulated entities across turns
    # Examples:
    # {
    #   "timeframe": "last week",
    #   "candidate_type": "advisors",
    #   "entity_name": "John Smith",
    #   "stage": "Meeting Booked"
    # }

    # Session metadata
    session_start_time: datetime
    last_activity_time: datetime
    message_count: int

    # Query results cache (for "show me more" follow-ups)
    last_query_results: Optional[List[Dict[str, Any]]]
    last_query_table: Optional[str]  # "vault_candidates", "deals", "meetings"

    # Error tracking
    errors: Optional[List[str]]

    # Feature flags
    memory_enabled: bool
    clarification_enabled: bool


class ClarificationSession(TypedDict):
    """Tracks active clarification dialogue."""
    session_id: str
    user_id: str
    original_query: str
    ambiguity_type: str  # "missing_timeframe", "missing_entity", "vague_search", "multiple_matches"
    suggested_options: List[Dict[str, str]]  # List of clarification options
    created_at: datetime
    expires_at: datetime
    partial_intent: Dict[str, Any]  # Partial intent to merge with clarification response


# Confidence thresholds for clarification
CONFIDENCE_THRESHOLD_LOW = 0.3   # Below this: Always ask clarification (lowered from 0.5 for better UX)
CONFIDENCE_THRESHOLD_MED = 0.7   # 0.3-0.7: Suggest options but proceed (lowered from 0.8)
# Above 0.8: Execute directly (no separate HIGH threshold needed)

# Conversation memory limits
MAX_CONVERSATION_HISTORY = 10  # Store last 10 messages
CONVERSATION_TTL_SECONDS = 300  # 5 minutes for hot storage (Redis)
MESSAGE_SUMMARIZATION_THRESHOLD = 10  # Summarize when exceeding this limit
