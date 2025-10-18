"""
Integration tests for multi-turn conversation flow.

Tests the complete flow of a conversation including:
- Initial query with low confidence
- Clarification dialog
- Follow-up questions
- Context preservation across turns
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import uuid
import json

import asyncpg
from botbuilder.schema import Activity, ActivityTypes
from botbuilder.core import TurnContext

from app.api.teams.conversation_memory import ConversationMemory
from app.api.teams.conversation_state import ConversationState
from app.api.teams.confidence_handlers import ConfidenceHandler


class TestConversationFlow:
    """Integration tests for complete conversation flows."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        db = AsyncMock(spec=asyncpg.Connection)
        db.execute = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        db.fetchrow = AsyncMock(return_value=None)
        return db

    @pytest.fixture
    def mock_memory_manager(self):
        """Create a mock memory manager with state tracking."""
        manager = AsyncMock(spec=ConversationMemory)
        manager.messages = []  # Track messages

        async def add_message_impl(user_id, role, content, confidence_score=None, db=None):
            manager.messages.append({
                "user_id": user_id,
                "role": role,
                "content": content,
                "confidence_score": confidence_score,
                "timestamp": datetime.utcnow()
            })
            return True

        async def get_history_impl(user_id, db=None, limit=10):
            return [
                msg for msg in manager.messages[-limit:]
                if msg["user_id"] == user_id
            ]

        manager.add_message = AsyncMock(side_effect=add_message_impl)
        manager.get_conversation_history = AsyncMock(side_effect=get_history_impl)
        manager.clear_conversation = AsyncMock()

        return manager

    @pytest.fixture
    def mock_conversation_state(self):
        """Create a mock conversation state."""
        state = MagicMock(spec=ConversationState)
        state.sessions = {}  # Track clarification sessions

        def create_session(session_id, user_id, query, intent):
            state.sessions[session_id] = {
                "session_id": session_id,
                "user_id": user_id,
                "original_query": query,
                "intent": intent,
                "responses": [],
                "created_at": datetime.utcnow()
            }
            return state.sessions[session_id]

        def get_session(session_id):
            return state.sessions.get(session_id)

        def update_session(session_id, response):
            if session_id in state.sessions:
                state.sessions[session_id]["responses"].append(response)
                return True
            return False

        state.create_session = create_session
        state.get_session = get_session
        state.update_session = update_session

        return state

    @pytest.fixture
    def sample_activity(self):
        """Create a sample Teams activity."""
        activity = Activity(
            type=ActivityTypes.message,
            id="msg-123",
            from_property=MagicMock(
                id="user-123",
                name="Test User",
                additional_properties={"email": "test@example.com"}
            ),
            conversation=MagicMock(id="conv-123"),
            text="show vault candidates",
            service_url="https://teams.microsoft.com"
        )
        return activity

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_low_confidence_to_clarification_flow(
        self,
        mock_track_event,
        mock_get_clarification,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        mock_conversation_state
    ):
        """Test flow: Low confidence query → Clarification → Refined query."""
        # Setup
        mock_get_memory.return_value = mock_memory_manager

        mock_clarification = AsyncMock()
        mock_clarification.create_clarification_session = AsyncMock(
            return_value={
                "session_id": "clarify-123",
                "suggested_options": [
                    {"title": "Last 7 days", "value": "7_days"},
                    {"title": "Last 30 days", "value": "30_days"},
                    {"title": "All time", "value": "all_time"}
                ]
            }
        )
        mock_get_clarification.return_value = mock_clarification

        # Step 1: Initial low confidence query
        handler = ConfidenceHandler(enable_cards=False)

        initial_response = await handler.handle_low_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-1",
            confidence=0.35,
            cleaned_text="show vault candidates",
            result={
                "clarification_message": "What time period would you like to see?",
                "intent": {"intent_type": "query_vault", "entities": {}}
            },
            db=mock_db
        )

        # Verify initial response
        assert "What time period" in initial_response.text
        assert len(mock_memory_manager.messages) == 1
        assert mock_memory_manager.messages[0]["role"] == "user"
        assert mock_memory_manager.messages[0]["content"] == "show vault candidates"

        # Step 2: User provides clarification
        mock_clarification.process_clarification_response = AsyncMock(
            return_value={
                "refined_query": "show vault candidates from last 7 days",
                "confidence": 0.85,
                "intent": {
                    "intent_type": "query_vault",
                    "entities": {"timeframe": "7_days"}
                }
            }
        )

        # Simulate clarification response
        clarification_response = await mock_clarification.process_clarification_response(
            session_id="clarify-123",
            user_response="7_days",
            db=mock_db
        )

        assert clarification_response["refined_query"] == "show vault candidates from last 7 days"
        assert clarification_response["confidence"] == 0.85

        # Step 3: Process refined query with high confidence
        refined_handler = ConfidenceHandler(enable_cards=False)

        final_response = await refined_handler.handle_high_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-2",
            confidence=0.85,
            cleaned_text="show vault candidates from last 7 days",
            result={
                "text": "Here are 5 vault candidates from the last 7 days:\n1. Candidate A\n2. Candidate B..."
            },
            db=mock_db
        )

        # Verify final response
        assert "5 vault candidates" in final_response.text
        assert len(mock_memory_manager.messages) == 3  # Original + refined + response

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    async def test_multi_turn_context_preservation(
        self,
        mock_get_memory,
        mock_db,
        mock_memory_manager
    ):
        """Test that context is preserved across multiple conversation turns."""
        mock_get_memory.return_value = mock_memory_manager

        # Turn 1: Ask about candidates
        handler1 = ConfidenceHandler(enable_cards=False)
        await handler1.handle_high_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-1",
            confidence=0.9,
            cleaned_text="show me vault candidates",
            result={"text": "Here are 3 vault candidates:\n1. John Doe\n2. Jane Smith\n3. Bob Johnson"},
            db=mock_db
        )

        # Turn 2: Ask for more details about first candidate
        handler2 = ConfidenceHandler(enable_cards=False)
        await handler2.handle_high_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-2",
            confidence=0.88,
            cleaned_text="tell me more about #1",
            result={"text": "John Doe: Senior Advisor at ABC Wealth, $500K production, Available in 30 days"},
            db=mock_db
        )

        # Turn 3: Ask about production
        handler3 = ConfidenceHandler(enable_cards=False)
        await handler3.handle_high_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-3",
            confidence=0.85,
            cleaned_text="what's their production history?",
            result={"text": "John Doe's production history:\n2023: $500K\n2022: $450K\n2021: $400K"},
            db=mock_db
        )

        # Verify conversation history
        history = await mock_memory_manager.get_conversation_history("user-123", db=mock_db)

        assert len(history) == 6  # 3 user messages + 3 assistant responses

        # Check context flow
        user_messages = [msg for msg in history if msg["role"] == "user"]
        assert user_messages[0]["content"] == "show me vault candidates"
        assert user_messages[1]["content"] == "tell me more about #1"
        assert user_messages[2]["content"] == "what's their production history?"

        # Verify responses maintain context
        assistant_messages = [msg for msg in history if msg["role"] == "assistant"]
        assert "3 vault candidates" in assistant_messages[0]["content"]
        assert "John Doe" in assistant_messages[1]["content"]
        assert "production history" in assistant_messages[2]["content"]

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_confidence_progression(
        self,
        mock_track_event,
        mock_get_memory,
        mock_db,
        mock_memory_manager
    ):
        """Test how confidence changes through a conversation."""
        mock_get_memory.return_value = mock_memory_manager

        confidence_sequence = [
            (0.4, "low", "vague query"),
            (0.65, "medium", "partially refined"),
            (0.92, "high", "fully specified")
        ]

        for confidence, bucket, description in confidence_sequence:
            handler = ConfidenceHandler(enable_cards=False)

            if bucket == "low":
                # Patch clarification engine for low confidence
                with patch('app.api.teams.confidence_handlers.get_clarification_engine') as mock_clarify:
                    mock_engine = AsyncMock()
                    mock_engine.create_clarification_session = AsyncMock(
                        return_value={
                            "session_id": f"session-{confidence}",
                            "suggested_options": []
                        }
                    )
                    mock_clarify.return_value = mock_engine

                    await handler.handle_low_confidence_response(
                        user_id="user-123",
                        user_email="test@example.com",
                        conversation_id="conv-123",
                        activity_id=f"msg-{confidence}",
                        confidence=confidence,
                        cleaned_text=description,
                        result={"clarification_message": "Need more info"},
                        db=mock_db
                    )
            elif bucket == "medium":
                await handler.handle_medium_confidence_response(
                    user_id="user-123",
                    user_email="test@example.com",
                    conversation_id="conv-123",
                    activity_id=f"msg-{confidence}",
                    confidence=confidence,
                    cleaned_text=description,
                    result={"text": "Partial results"},
                    db=mock_db
                )
            else:  # high
                await handler.handle_high_confidence_response(
                    user_id="user-123",
                    user_email="test@example.com",
                    conversation_id="conv-123",
                    activity_id=f"msg-{confidence}",
                    confidence=confidence,
                    cleaned_text=description,
                    result={"text": "Complete results"},
                    db=mock_db
                )

        # Verify telemetry tracked confidence progression
        confidence_events = [
            call for call in mock_track_event.call_args_list
            if call[0][0] == "nlp_confidence_response"
        ]

        assert len(confidence_events) == 3
        assert confidence_events[0][0][1]["confidence_bucket"] == "low"
        assert confidence_events[1][0][1]["confidence_bucket"] == "medium"
        assert confidence_events[2][0][1]["confidence_bucket"] == "high"

    @pytest.mark.asyncio
    async def test_memory_and_repository_sync(
        self,
        mock_db,
        mock_memory_manager,
        mock_conversation_state
    ):
        """Test that conversation memory and repository state stay synchronized."""
        # Initialize session
        session_id = "sync-test-123"
        user_id = "user-123"

        # Create clarification session in state
        session = mock_conversation_state.create_session(
            session_id=session_id,
            user_id=user_id,
            query="show deals",
            intent={"intent_type": "query_deals", "entities": {}}
        )

        # Add messages to memory
        await mock_memory_manager.add_message(
            user_id=user_id,
            role="user",
            content="show deals",
            confidence_score=0.4,
            db=mock_db
        )

        # Update session with response
        mock_conversation_state.update_session(session_id, "last_week")

        # Add refined message to memory
        await mock_memory_manager.add_message(
            user_id=user_id,
            role="user",
            content="show deals from last week",
            confidence_score=0.85,
            db=mock_db
        )

        # Verify sync
        memory_messages = await mock_memory_manager.get_conversation_history(user_id)
        session_data = mock_conversation_state.get_session(session_id)

        assert len(memory_messages) == 2
        assert memory_messages[0]["content"] == "show deals"
        assert memory_messages[1]["content"] == "show deals from last week"

        assert session_data is not None
        assert session_data["original_query"] == "show deals"
        assert "last_week" in session_data["responses"]

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    async def test_error_recovery_in_conversation(
        self,
        mock_get_clarification,
        mock_get_memory,
        mock_db,
        mock_memory_manager
    ):
        """Test that conversations can recover from errors gracefully."""
        from app.api.teams.clarification_engine import RateLimitExceeded

        mock_get_memory.return_value = mock_memory_manager

        # Setup clarification engine that fails then succeeds
        mock_engine = AsyncMock()
        mock_engine.create_clarification_session = AsyncMock(
            side_effect=[
                RateLimitExceeded("Too many requests"),
                {
                    "session_id": "retry-123",
                    "suggested_options": []
                }
            ]
        )
        mock_get_clarification.return_value = mock_engine

        handler = ConfidenceHandler(enable_cards=False)

        # First attempt - should hit rate limit
        response1 = await handler.handle_low_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-1",
            confidence=0.3,
            cleaned_text="query 1",
            result={},
            db=mock_db
        )

        assert "Too many requests" in response1.text

        # Second attempt - should succeed
        response2 = await handler.handle_low_confidence_response(
            user_id="user-123",
            user_email="test@example.com",
            conversation_id="conv-123",
            activity_id="msg-2",
            confidence=0.3,
            cleaned_text="query 2",
            result={"clarification_message": "What would you like?"},
            db=mock_db
        )

        assert "What would you like?" in response2.text

        # Verify conversation continues normally
        assert len(mock_memory_manager.messages) == 2  # Both queries recorded