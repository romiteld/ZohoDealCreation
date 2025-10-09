"""
Conversation Memory Manager for Teams Bot.
Hybrid storage: Redis (hot) + PostgreSQL (cold) for optimal performance.
"""
import json
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncpg

from well_shared.cache.redis_manager import get_cache_manager
from app.monitoring import monitoring
from .conversation_state import (
    ConversationMessage,
    ConversationState,
    MAX_CONVERSATION_HISTORY,
    CONVERSATION_TTL_SECONDS
)

logger = logging.getLogger(__name__)


class ConversationMemoryManager:
    """
    Manages conversation history with hybrid Redis + PostgreSQL storage.

    Storage Strategy:
    - Hot Storage (Redis): Last 10 messages per user (5 min TTL) for fast access
    - Cold Storage (PostgreSQL): All messages in `teams_conversations` table for analytics

    Features:
    - Message persistence across bot restarts
    - Automatic message summarization when limit exceeded
    - Context window building for GPT-5 prompts
    """

    def __init__(self):
        self.cache_manager = None
        self.redis_client = None
        self.initialized = False

    async def initialize(self):
        """Initialize Redis connection."""
        if self.initialized:
            return

        self.cache_manager = await get_cache_manager()
        if self.cache_manager:
            self.redis_client = self.cache_manager.client
            logger.info("ConversationMemoryManager initialized with Redis")
        else:
            logger.warning("Redis not available - conversation memory will be PostgreSQL-only")

        self.initialized = True

    async def get_conversation_history(
        self,
        user_id: str,
        limit: int = MAX_CONVERSATION_HISTORY,
        db: Optional[asyncpg.Connection] = None
    ) -> List[ConversationMessage]:
        """
        Retrieve recent conversation history for user.

        Args:
            user_id: Teams user ID
            limit: Maximum number of messages to return (default: 10)
            db: Optional database connection for cold storage fallback

        Returns:
            List of ConversationMessage dicts, ordered by timestamp (oldest first)
        """
        if not self.initialized:
            await self.initialize()

        # Try hot storage (Redis) first
        if self.redis_client:
            cache_key = f"conversation:history:{user_id}"
            try:
                cached_history = await self.redis_client.get(cache_key)
                if cached_history:
                    messages = json.loads(cached_history)
                    logger.debug(f"Retrieved {len(messages)} messages from Redis for {user_id}")
                    return messages[-limit:]  # Return last N messages
            except Exception as e:
                logger.warning(f"Redis retrieval failed: {e}, falling back to PostgreSQL")
                # Telemetry
                monitoring.gpt_request_counter.add(1, {
                    "operation": "redis_fallback",
                    "user_id": user_id[:8]  # Truncate for privacy
                })

        # Fallback to cold storage (PostgreSQL)
        if db:
            try:
                rows = await db.fetch("""
                    SELECT
                        CASE WHEN message_text IS NOT NULL THEN 'user' ELSE 'assistant' END as role,
                        COALESCE(message_text, bot_response) as content,
                        created_at as timestamp,
                        NULL as intent_type,
                        NULL as confidence_score,
                        NULL as metadata
                    FROM teams_conversations
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)

                messages = [
                    {
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["timestamp"],
                        "intent_type": None,
                        "confidence_score": None,
                        "metadata": None
                    }
                    for row in reversed(rows)  # Reverse to get chronological order
                ]

                logger.debug(f"Retrieved {len(messages)} messages from PostgreSQL for {user_id}")
                return messages
            except Exception as e:
                logger.error(f"PostgreSQL retrieval failed: {e}")

        return []

    async def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        intent_type: Optional[str] = None,
        confidence_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[asyncpg.Connection] = None
    ):
        """
        Add a message to conversation history (hot + cold storage).

        Args:
            user_id: Teams user ID
            role: 'user' or 'assistant'
            content: Message content
            intent_type: Classified intent (for user messages)
            confidence_score: Intent classification confidence (0.0-1.0)
            metadata: Additional context
            db: Database connection for cold storage
        """
        if not self.initialized:
            await self.initialize()

        message: ConversationMessage = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
            "intent_type": intent_type,
            "confidence_score": confidence_score,
            "metadata": metadata
        }

        # Update hot storage (Redis)
        if self.redis_client:
            cache_key = f"conversation:history:{user_id}"
            try:
                # Get existing history
                cached_history = await self.redis_client.get(cache_key)
                messages = json.loads(cached_history) if cached_history else []

                # Append new message
                # Convert datetime to ISO string for JSON serialization
                serializable_message = {
                    **message,
                    "timestamp": message["timestamp"].isoformat()
                }
                messages.append(serializable_message)

                # Trim to limit
                if len(messages) > MAX_CONVERSATION_HISTORY:
                    # Summarize old messages if needed
                    messages = messages[-MAX_CONVERSATION_HISTORY:]

                # Store with TTL
                await self.redis_client.setex(
                    cache_key,
                    CONVERSATION_TTL_SECONDS,
                    json.dumps(messages)
                )
                logger.debug(f"Stored message in Redis for {user_id} (total: {len(messages)})")
            except Exception as e:
                logger.warning(f"Redis storage failed: {e}")

        # Update cold storage (PostgreSQL) - handled by routes.py INSERT

    async def get_context_for_query(
        self,
        user_id: str,
        current_query: str,
        db: Optional[asyncpg.Connection] = None
    ) -> str:
        """
        Build context window for GPT-5 prompt including conversation history.

        Args:
            user_id: Teams user ID
            current_query: Current user query
            db: Database connection

        Returns:
            Formatted context string for GPT-5 prompt
        """
        messages = await self.get_conversation_history(user_id, limit=3, db=db)

        if not messages:
            return current_query

        # Build context from last 3 messages
        context_parts = ["Previous conversation context:"]
        for msg in messages[-3:]:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg['content']}")

        context_parts.append(f"\nCurrent query: {current_query}")
        return "\n".join(context_parts)

    async def clear_conversation(self, user_id: str):
        """Clear conversation history for user (hot storage only)."""
        if not self.initialized:
            await self.initialize()

        if self.redis_client:
            cache_key = f"conversation:history:{user_id}"
            try:
                await self.redis_client.delete(cache_key)
                logger.info(f"Cleared conversation history for {user_id}")
            except Exception as e:
                logger.error(f"Failed to clear conversation: {e}")

    async def summarize_old_messages(
        self,
        messages: List[ConversationMessage],
        keep_recent: int = 5
    ) -> List[ConversationMessage]:
        """
        Summarize old messages to stay within token limits.
        Keep last N messages, summarize older ones using GPT-5-nano.

        Args:
            messages: Full message list
            keep_recent: Number of recent messages to keep verbatim

        Returns:
            Compressed message list with summary
        """
        if len(messages) <= keep_recent:
            return messages

        # Messages to summarize (oldest ones)
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Build summary prompt
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in old_messages
        ])

        try:
            from openai import AsyncOpenAI
            from well_shared.config.voit_config import VoITConfig

            client = AsyncOpenAI()
            model = VoITConfig.get_actual_model_name("gpt-5-nano")

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Summarize the following conversation history concisely, preserving key entities and context."},
                    {"role": "user", "content": conversation_text}
                ],
                temperature=1,
                max_tokens=200
            )

            summary = response.choices[0].message.content

            # Create summary message
            summary_message: ConversationMessage = {
                "role": "assistant",
                "content": f"[Summary of previous conversation]: {summary}",
                "timestamp": old_messages[-1]["timestamp"],
                "intent_type": "summary",
                "confidence_score": 1.0,
                "metadata": {"summarized_count": len(old_messages)}
            }

            return [summary_message] + recent_messages

        except Exception as e:
            logger.error(f"Message summarization failed: {e}, returning recent messages only")
            return recent_messages

    async def get_or_create_session(
        self,
        user_id: str,
        conversation_id: str,
        user_email: str
    ) -> ConversationState:
        """
        Get existing conversation state or create new session.

        Args:
            user_id: Teams user ID
            conversation_id: Teams conversation ID
            user_email: User email address

        Returns:
            ConversationState dict
        """
        if not self.initialized:
            await self.initialize()

        # Check for existing session in Redis
        if self.redis_client:
            session_key = f"conversation:session:{user_id}"
            try:
                cached_session = await self.redis_client.get(session_key)
                if cached_session:
                    session = json.loads(cached_session)
                    logger.debug(f"Retrieved existing session for {user_id}")
                    return session
            except Exception as e:
                logger.warning(f"Session retrieval failed: {e}")

        # Create new session
        now = datetime.now(timezone.utc)
        session: ConversationState = {
            "user_id": user_id,
            "user_email": user_email,
            "conversation_id": conversation_id,
            "conversation_history": [],
            "current_query": None,
            "current_intent": None,
            "confidence_score": None,
            "clarification_needed": False,
            "clarification_session_id": None,
            "awaiting_clarification_response": False,
            "clarification_context": None,
            "context_entities": {},
            "session_start_time": now,
            "last_activity_time": now,
            "message_count": 0,
            "last_query_results": None,
            "last_query_table": None,
            "errors": None,
            "memory_enabled": True,
            "clarification_enabled": True
        }

        # Store in Redis
        if self.redis_client:
            session_key = f"conversation:session:{user_id}"
            try:
                # Serialize datetime objects
                serializable_session = {
                    **session,
                    "session_start_time": session["session_start_time"].isoformat(),
                    "last_activity_time": session["last_activity_time"].isoformat()
                }
                await self.redis_client.setex(
                    session_key,
                    CONVERSATION_TTL_SECONDS,
                    json.dumps(serializable_session)
                )
                logger.info(f"Created new conversation session for {user_id}")
            except Exception as e:
                logger.error(f"Failed to store session: {e}")

        return session

    async def update_session(
        self,
        user_id: str,
        session: ConversationState
    ):
        """Update conversation session in Redis."""
        if not self.initialized:
            await self.initialize()

        if self.redis_client:
            session_key = f"conversation:session:{user_id}"
            try:
                # Update last activity time
                session["last_activity_time"] = datetime.now(timezone.utc)

                # Serialize datetime objects
                serializable_session = {
                    **session,
                    "session_start_time": session["session_start_time"].isoformat() if isinstance(session["session_start_time"], datetime) else session["session_start_time"],
                    "last_activity_time": session["last_activity_time"].isoformat()
                }

                await self.redis_client.setex(
                    session_key,
                    CONVERSATION_TTL_SECONDS,
                    json.dumps(serializable_session)
                )
                logger.debug(f"Updated session for {user_id}")
            except Exception as e:
                logger.error(f"Failed to update session: {e}")


# Singleton instance
_memory_manager: Optional[ConversationMemoryManager] = None


async def get_memory_manager() -> ConversationMemoryManager:
    """Get or create singleton memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = ConversationMemoryManager()
        await _memory_manager.initialize()
    return _memory_manager
