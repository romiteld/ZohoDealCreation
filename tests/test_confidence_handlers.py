"""
Unit tests for confidence response handlers.

Tests the confidence handler module that processes natural language queries
based on confidence scores, with and without card generation.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import uuid

import asyncpg
from botbuilder.core import MessageFactory, CardFactory
from botbuilder.schema import Activity

from app.api.teams.confidence_handlers import (
    ConfidenceHandler,
    get_confidence_handler
)
from app.api.teams.clarification_engine import RateLimitExceeded


class TestConfidenceHandler:
    """Test suite for ConfidenceHandler class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        db = AsyncMock(spec=asyncpg.Connection)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_memory_manager(self):
        """Create a mock memory manager."""
        manager = AsyncMock()
        manager.add_message = AsyncMock()
        return manager

    @pytest.fixture
    def mock_clarification_engine(self):
        """Create a mock clarification engine."""
        engine = AsyncMock()
        engine.create_clarification_session = AsyncMock(return_value={
            "session_id": "test-session-123",
            "suggested_options": [
                {"title": "Add timeframe", "value": "add_timeframe"},
                {"title": "Specify person", "value": "add_person"}
            ]
        })
        return engine

    @pytest.fixture
    def sample_result(self):
        """Create a sample query result."""
        return {
            "text": "Here are the latest deals in the pipeline.",
            "intent": {
                "intent_type": "query_deals",
                "entities": {}
            },
            "clarification_message": "What specific information are you looking for?",
            "ambiguity_type": "vague_search",
            "suggested_options": [
                {"title": "Recent deals", "value": "recent"},
                {"title": "By stage", "value": "stage"}
            ],
            "card": {
                "content": {
                    "type": "AdaptiveCard",
                    "body": [{"type": "TextBlock", "text": "Sample card"}]
                }
            }
        }

    @pytest.mark.asyncio
    async def test_handler_with_cards_enabled(self):
        """Test handler initialization with cards enabled."""
        handler = ConfidenceHandler(enable_cards=True)
        assert handler.enable_cards is True
        assert handler.correlation_id is not None

    @pytest.mark.asyncio
    async def test_handler_with_cards_disabled(self):
        """Test handler initialization with cards disabled."""
        handler = ConfidenceHandler(enable_cards=False)
        assert handler.enable_cards is False

    @pytest.mark.asyncio
    async def test_handler_uses_global_flag_by_default(self):
        """Test handler uses global feature flag when not specified."""
        with patch('app.api.teams.confidence_handlers.ENABLE_NLP_CARDS', False):
            handler = ConfidenceHandler()
            assert handler.enable_cards is False

        with patch('app.api.teams.confidence_handlers.ENABLE_NLP_CARDS', True):
            handler = ConfidenceHandler()
            assert handler.enable_cards is True

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    @patch('app.api.teams.confidence_handlers.track_event')
    @patch('app.api.teams.confidence_handlers.create_clarification_card')
    async def test_low_confidence_with_cards(
        self,
        mock_create_card,
        mock_track_event,
        mock_get_clarification,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        mock_clarification_engine,
        sample_result
    ):
        """Test low confidence response with cards enabled."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager
        mock_get_clarification.return_value = mock_clarification_engine
        mock_create_card.return_value = {
            "content": {"type": "AdaptiveCard", "body": []}
        }

        handler = ConfidenceHandler(enable_cards=True)

        response = await handler.handle_low_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.3,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify telemetry tracked
        mock_track_event.assert_any_call("nlp_confidence_response", {
            "confidence_bucket": "low",
            "confidence_score": 0.3,
            "enable_cards": True,
            "user_id": "user123",
            "correlation_id": handler.correlation_id,
            "query_length": 13
        })

        # Verify card was generated
        mock_track_event.assert_any_call("nlp_card_generated", {
            "card_type": "clarification",
            "confidence_bucket": "low",
            "correlation_id": handler.correlation_id
        })

        # Verify memory manager was called
        mock_memory_manager.add_message.assert_called_once()

        # Verify database update
        mock_db.execute.assert_called_once()

        # Verify response is a MessageFactory with attachment
        assert response is not None

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_low_confidence_without_cards(
        self,
        mock_track_event,
        mock_get_clarification,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        mock_clarification_engine,
        sample_result
    ):
        """Test low confidence response with cards disabled."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager
        mock_get_clarification.return_value = mock_clarification_engine

        handler = ConfidenceHandler(enable_cards=False)

        response = await handler.handle_low_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.3,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify no card generation event
        card_events = [
            call for call in mock_track_event.call_args_list
            if call[0][0] == "nlp_card_generated"
        ]
        assert len(card_events) == 0

        # Verify response is text-only
        assert response is not None

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    @patch('app.api.teams.confidence_handlers.track_event')
    @patch('app.api.teams.confidence_handlers.create_error_card')
    async def test_low_confidence_rate_limit_with_cards(
        self,
        mock_create_error_card,
        mock_track_event,
        mock_get_clarification,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        sample_result
    ):
        """Test low confidence with rate limit exceeded and cards enabled."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager
        mock_engine = AsyncMock()
        mock_engine.create_clarification_session = AsyncMock(
            side_effect=RateLimitExceeded("Too many requests")
        )
        mock_get_clarification.return_value = mock_engine
        mock_create_error_card.return_value = {
            "content": {"type": "AdaptiveCard", "body": []}
        }

        handler = ConfidenceHandler(enable_cards=True)

        response = await handler.handle_low_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.3,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify rate limit tracked
        mock_track_event.assert_any_call("nlp_rate_limit", {
            "user_id": "user123",
            "confidence_bucket": "low",
            "correlation_id": handler.correlation_id
        })

        # Verify error card was created
        mock_create_error_card.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    @patch('app.api.teams.confidence_handlers.create_suggestion_card')
    async def test_medium_confidence_with_cards(
        self,
        mock_create_card,
        mock_track_event,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        sample_result
    ):
        """Test medium confidence response with cards enabled."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager
        mock_create_card.return_value = {
            "content": {"type": "AdaptiveCard", "body": []}
        }

        handler = ConfidenceHandler(enable_cards=True)

        response = await handler.handle_medium_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.65,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify telemetry
        mock_track_event.assert_any_call("nlp_confidence_response", {
            "confidence_bucket": "medium",
            "confidence_score": 0.65,
            "enable_cards": True,
            "user_id": "user123",
            "correlation_id": handler.correlation_id,
            "query_length": 13
        })

        # Verify suggestion card created
        mock_create_card.assert_called_once()

        # Verify both user and assistant messages stored
        assert mock_memory_manager.add_message.call_count == 2

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_medium_confidence_without_cards(
        self,
        mock_track_event,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        sample_result
    ):
        """Test medium confidence response with cards disabled."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager

        handler = ConfidenceHandler(enable_cards=False)

        response = await handler.handle_medium_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.65,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify response has inline text suggestion
        assert response is not None

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_high_confidence_with_cards_and_result_card(
        self,
        mock_track_event,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        sample_result
    ):
        """Test high confidence with cards enabled and result has a card."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager

        handler = ConfidenceHandler(enable_cards=True)

        response = await handler.handle_high_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.92,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify telemetry
        mock_track_event.assert_any_call("nlp_confidence_response", {
            "confidence_bucket": "high",
            "confidence_score": 0.92,
            "enable_cards": True,
            "user_id": "user123",
            "correlation_id": handler.correlation_id,
            "query_length": 13,
            "has_card": True
        })

        # Verify card generation tracked
        mock_track_event.assert_any_call("nlp_card_generated", {
            "card_type": "result",
            "confidence_bucket": "high",
            "correlation_id": handler.correlation_id
        })

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_high_confidence_without_cards(
        self,
        mock_track_event,
        mock_get_memory,
        mock_db,
        mock_memory_manager,
        sample_result
    ):
        """Test high confidence with cards disabled."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager

        handler = ConfidenceHandler(enable_cards=False)

        response = await handler.handle_high_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.92,
            cleaned_text="show me deals",
            result=sample_result,
            db=mock_db
        )

        # Verify no card generation event
        card_events = [
            call for call in mock_track_event.call_args_list
            if call[0][0] == "nlp_card_generated"
        ]
        assert len(card_events) == 0

        # Verify text-only response
        assert response is not None

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_high_confidence_no_result_card(
        self,
        mock_track_event,
        mock_get_memory,
        mock_db,
        mock_memory_manager
    ):
        """Test high confidence when result has no card."""
        # Setup mocks
        mock_get_memory.return_value = mock_memory_manager

        # Result without card
        result = {
            "text": "Here are the deals.",
            "intent": {"intent_type": "query_deals", "entities": {}}
        }

        handler = ConfidenceHandler(enable_cards=True)

        response = await handler.handle_high_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.92,
            cleaned_text="show me deals",
            result=result,
            db=mock_db
        )

        # Verify no card generation event (no card in result)
        card_events = [
            call for call in mock_track_event.call_args_list
            if call[0][0] == "nlp_card_generated"
        ]
        assert len(card_events) == 0

    @pytest.mark.asyncio
    async def test_get_confidence_handler_factory(self):
        """Test the factory function for creating handlers."""
        # Test with explicit True
        handler = await get_confidence_handler(enable_cards=True)
        assert handler.enable_cards is True

        # Test with explicit False
        handler = await get_confidence_handler(enable_cards=False)
        assert handler.enable_cards is False

        # Test with None (uses global flag)
        with patch('app.api.teams.confidence_handlers.ENABLE_NLP_CARDS', True):
            handler = await get_confidence_handler()
            assert handler.enable_cards is True

    @pytest.mark.asyncio
    async def test_correlation_id_uniqueness(self):
        """Test that each handler gets a unique correlation ID."""
        handler1 = ConfidenceHandler()
        handler2 = ConfidenceHandler()

        assert handler1.correlation_id != handler2.correlation_id
        assert len(handler1.correlation_id) == 36  # UUID format
        assert len(handler2.correlation_id) == 36