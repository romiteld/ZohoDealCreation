"""
Clarification Engine for Teams Bot - Handles ambiguous queries with multi-turn dialogue.
Uses GPT-5 for intelligent question generation and template-based clarifications.
"""
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

from openai import AsyncOpenAI
from well_shared.config.voit_config import VoITConfig
from app.monitoring import monitoring
from .conversation_state import (
    ClarificationSession,
    CONFIDENCE_THRESHOLD_LOW,
    CONFIDENCE_THRESHOLD_MED,
    ConversationState
)
from .adaptive_cards import create_clarification_card

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Rate limit exceeded."""
    pass


class ClarificationEngine:
    """
    Manages clarification dialogues for ambiguous user queries.

    Features:
    - Template-based clarifications for common ambiguities
    - GPT-5 generated follow-up questions for complex cases
    - Adaptive Cards with interactive options
    - Session tracking with 5-minute expiry
    """

    # Template-based clarification messages
    CLARIFICATION_TEMPLATES = {
        "missing_timeframe": {
            "message": "I can help you with that! What timeframe are you interested in?",
            "options": [
                {"title": "Today", "value": "today"},
                {"title": "This Week", "value": "this_week"},
                {"title": "This Month", "value": "this_month"},
                {"title": "Last 7 Days", "value": "last_7_days"},
                {"title": "Last 30 Days", "value": "last_30_days"},
                {"title": "All Time", "value": "all_time"}
            ]
        },
        "missing_entity": {
            "message": "Which candidate or deal are you asking about?",
            "options": []  # Populated dynamically from search results
        },
        "vague_search": {
            "message": "Could you provide more details? For example:",
            "options": [
                {"title": "Search by Name", "value": "search_name"},
                {"title": "Search by Company", "value": "search_company"},
                {"title": "Search by Stage", "value": "search_stage"},
                {"title": "Recent Activity", "value": "recent_activity"}
            ]
        },
        "multiple_matches": {
            "message": "I found multiple matches. Which one did you mean?",
            "options": []  # Populated dynamically from search results
        },
        "ambiguous_query": {
            "message": "Your query could mean multiple things. Which did you intend?",
            "options": []  # Populated by GPT-5
        },
        "multiple_intents": {
            "message": "I detected multiple requests. Let's focus on one:",
            "options": []  # Populated by GPT-5
        }
    }

    def __init__(self):
        self.openai_client = AsyncOpenAI()
        self.model = VoITConfig.get_actual_model_name("gpt-5-mini")
        self.active_sessions: Dict[str, ClarificationSession] = {}
        self.user_session_counts: Dict[str, List[datetime]] = {}  # NEW: Rate limiting

    async def needs_clarification(
        self,
        query: str,
        intent: Dict[str, Any],
        confidence: float,
        conversation_state: Optional[ConversationState] = None
    ) -> bool:
        """
        Determine if query needs clarification based on confidence and missing entities.

        Args:
            query: User's query
            intent: Classified intent with entities
            confidence: Classification confidence (0.0-1.0)
            conversation_state: Optional conversation context

        Returns:
            True if clarification needed, False if can proceed
        """
        # Low confidence always needs clarification
        if confidence < CONFIDENCE_THRESHOLD_LOW:
            return True

        # Check for missing required entities
        intent_type = intent.get("intent_type")
        entities = intent.get("entities", {})

        # CRITICAL FIX: Check generic intents from classifier (not semantic categories)
        # Timeframe-sensitive queries without timeframe
        timeframe_sensitive = ["list", "count", "aggregate", "search"]
        if intent_type in timeframe_sensitive:
            if not entities.get("timeframe") and not entities.get("candidate_name"):
                return True

        # Search queries without entity
        if intent_type == "search":
            if not entities.get("candidate_name") and not entities.get("company_name"):
                return True

        # Medium confidence with vague query
        if confidence < CONFIDENCE_THRESHOLD_MED:
            if len(query.split()) < 3:  # Very short query
                return True

        return False

    def detect_ambiguity_type(
        self,
        query: str,
        intent: Dict[str, Any],
        confidence: float
    ) -> str:
        """
        Classify the type of ambiguity in the query.

        Returns:
            "missing_timeframe" | "missing_entity" | "vague_search" | "multiple_matches"
        """
        intent_type = intent.get("intent_type")
        entities = intent.get("entities", {})

        # Check for missing timeframe
        if intent_type in ["list_deals", "list_meetings", "analytics"]:
            if not entities.get("timeframe"):
                return "missing_timeframe"

        # Check for missing entity in search
        if intent_type == "search":
            if not entities.get("candidate_name") and not entities.get("company_name"):
                return "missing_entity"

        # Check for multiple matches (would need search results)
        # This is determined later after database query

        # Default to vague search
        return "vague_search"

    async def generate_clarification_question(
        self,
        query: str,
        intent: Dict[str, Any],
        ambiguity_type: str,
        conversation_state: Optional[ConversationState] = None
    ) -> str:
        """
        Generate clarification question using GPT-5 or templates.

        Args:
            query: Original user query
            intent: Classified intent
            ambiguity_type: Type of ambiguity detected
            conversation_state: Optional conversation context

        Returns:
            Clarification question text
        """
        # Use template if available
        template = self.CLARIFICATION_TEMPLATES.get(ambiguity_type)
        if template:
            return template["message"]

        # Generate with GPT-5 for complex cases
        try:
            context = ""
            if conversation_state:
                recent_messages = conversation_state.get("conversation_history", [])[-3:]
                if recent_messages:
                    context = "\n".join([
                        f"{msg['role']}: {msg['content']}"
                        for msg in recent_messages
                    ])

            system_prompt = """You are a helpful assistant that generates clarification questions.
Generate a single, concise follow-up question to clarify the user's intent.
Be friendly and specific. Keep it under 20 words."""

            user_prompt = f"""User query: {query}
Detected intent: {intent.get('intent_type')}
Missing information: {ambiguity_type}

{f"Recent conversation:{context}" if context else ""}

Generate a clarification question:"""

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=1,
                max_tokens=100
            )

            clarification = response.choices[0].message.content.strip()
            logger.info(f"Generated clarification question: {clarification}")
            return clarification

        except Exception as e:
            logger.error(f"Failed to generate clarification question: {e}")
            return "Could you provide more details about what you're looking for?"

    def get_clarification_options(
        self,
        ambiguity_type: str,
        search_results: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, str]]:
        """
        Get clarification options for Adaptive Card.

        Args:
            ambiguity_type: Type of ambiguity
            search_results: Optional search results for dynamic options

        Returns:
            List of {"title": str, "value": str} options
        """
        template = self.CLARIFICATION_TEMPLATES.get(ambiguity_type)
        if template and template["options"]:
            return template["options"]

        # Generate dynamic options from search results
        if search_results and ambiguity_type == "multiple_matches":
            return [
                {
                    "title": f"{result.get('name', 'Unknown')} ({result.get('company', 'No company')})",
                    "value": str(result.get("id"))
                }
                for result in search_results[:5]  # Limit to 5 options
            ]

        return []

    async def create_clarification_session(
        self,
        user_id: str,
        query: str,
        intent: Dict[str, Any],
        ambiguity_type: str,
        suggested_options: List[Dict[str, str]],
        conversation_state: Optional[ConversationState] = None
    ) -> ClarificationSession:
        """
        Create and track a new clarification session.

        Args:
            user_id: Teams user ID
            query: Original query
            intent: Partial intent to merge with clarification
            ambiguity_type: Type of ambiguity
            suggested_options: Options for user selection
            conversation_state: Optional conversation context

        Returns:
            ClarificationSession dict
        """
        # CRITICAL: Rate limiting check (3 per 5 minutes)
        now = datetime.now(timezone.utc)
        user_sessions = self.user_session_counts.get(user_id, [])
        recent = [ts for ts in user_sessions if now - ts < timedelta(minutes=5)]

        if len(recent) >= 3:
            logger.warning(f"Rate limit for {user_id}: {len(recent)} recent sessions")
            raise RateLimitExceeded(f"User {user_id} exceeded limit")

        # Update rate limit tracking
        self.user_session_counts[user_id] = recent + [now]

        # Create session
        session_id = str(uuid.uuid4())

        session: ClarificationSession = {
            "session_id": session_id,
            "user_id": user_id,
            "original_query": query,
            "ambiguity_type": ambiguity_type,
            "suggested_options": suggested_options,
            "created_at": now,
            "expires_at": now + timedelta(minutes=5),
            "partial_intent": intent
        }

        # Store in memory
        self.active_sessions[session_id] = session

        # Cleanup expired sessions
        self._cleanup_expired_sessions()

        # Telemetry
        monitoring.gpt_request_counter.add(1, {
            "operation": "clarification_triggered",
            "ambiguity_type": ambiguity_type
        })

        logger.info(f"Created clarification session {session_id} for user {user_id}")
        return session

    def get_clarification_session(self, session_id: str) -> Optional[ClarificationSession]:
        """Retrieve active clarification session."""
        session = self.active_sessions.get(session_id)
        if session and datetime.now(timezone.utc) < session["expires_at"]:
            return session
        return None

    def merge_clarification_response(
        self,
        session: ClarificationSession,
        user_response: str
    ) -> Dict[str, Any]:
        """
        Merge user's clarification response with partial intent.

        Args:
            session: Active clarification session
            user_response: User's response to clarification question

        Returns:
            Updated intent with merged entities
        """
        partial_intent = session["partial_intent"]
        ambiguity_type = session["ambiguity_type"]

        # Clone partial intent
        merged_intent = partial_intent.copy()
        entities = merged_intent.get("entities", {}).copy()

        # Merge based on ambiguity type
        if ambiguity_type == "missing_timeframe":
            entities["timeframe"] = user_response
        elif ambiguity_type == "missing_entity":
            # Try to determine if it's a name or company
            if " " in user_response:
                entities["candidate_name"] = user_response
            else:
                entities["company_name"] = user_response
        elif ambiguity_type == "multiple_matches":
            entities["selected_id"] = user_response

        merged_intent["entities"] = entities
        merged_intent["confidence_score"] = 1.0  # User clarified, now certain

        # Telemetry
        monitoring.gpt_request_counter.add(1, {
            "operation": "clarification_resolved",
            "ambiguity_type": ambiguity_type
        })

        logger.info(f"Merged clarification response: {entities}")
        return merged_intent

    def clear_clarification_session(self, session_id: str):
        """Remove clarification session after resolution."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.debug(f"Cleared clarification session {session_id}")

    def _cleanup_expired_sessions(self):
        """Remove expired clarification sessions."""
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, session in self.active_sessions.items()
            if now >= session["expires_at"]
        ]
        for sid in expired:
            del self.active_sessions[sid]
        if expired:
            # Telemetry
            monitoring.gpt_request_counter.add(len(expired), {
                "operation": "clarification_expired"
            })
            logger.info(f"Cleaned up {len(expired)} expired clarification sessions")


# Singleton instance
_clarification_engine: Optional[ClarificationEngine] = None


async def get_clarification_engine() -> ClarificationEngine:
    """Get or create singleton clarification engine instance."""
    global _clarification_engine
    if _clarification_engine is None:
        _clarification_engine = ClarificationEngine()
    return _clarification_engine
