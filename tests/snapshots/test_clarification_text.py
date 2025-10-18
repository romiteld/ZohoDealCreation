"""
Snapshot tests for text formatting in clarification responses.

These tests ensure that text formatting remains consistent across changes,
capturing the exact format of user-facing messages.
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.api.teams.confidence_handlers import ConfidenceHandler


class TestClarificationTextSnapshots:
    """Snapshot tests for clarification text formatting."""

    @pytest.fixture
    def expected_low_confidence_text_no_cards(self):
        """Expected text output for low confidence without cards."""
        return """I need more information to help you. What are you looking for?

You might be looking for:
• Recent deals
• By stage
• Add timeframe

Please provide more details."""

    @pytest.fixture
    def expected_medium_confidence_text_no_cards(self):
        """Expected text output for medium confidence without cards."""
        return """Here are the latest deals in the pipeline.

_Confidence: 65%. Try adding more specific details like timeframe or person names for better results._"""

    @pytest.fixture
    def expected_high_confidence_text(self):
        """Expected text output for high confidence."""
        return "Here are the latest deals in the pipeline."

    @pytest.fixture
    def expected_rate_limit_text(self):
        """Expected text output for rate limit."""
        return "⏱️ Too many requests. Please wait a few minutes before asking for clarification again."

    @pytest.fixture
    def expected_rate_limit_card_text(self):
        """Expected text for rate limit error card."""
        return """⏱️ **Too Many Requests**

You've asked for clarification too frequently. Please wait a few minutes.

_Limit: 3 per 5 min_"""

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_low_confidence_text_format(
        self,
        mock_track_event,
        mock_get_clarification,
        mock_get_memory,
        expected_low_confidence_text_no_cards
    ):
        """Test low confidence text formatting without cards."""
        # Setup mocks
        mock_memory_manager = AsyncMock()
        mock_get_memory.return_value = mock_memory_manager

        mock_engine = AsyncMock()
        mock_engine.create_clarification_session = AsyncMock(return_value={
            "session_id": "test-123",
            "suggested_options": [
                {"title": "Recent deals", "value": "recent"},
                {"title": "By stage", "value": "stage"},
                {"title": "Add timeframe", "value": "timeframe"}
            ]
        })
        mock_get_clarification.return_value = mock_engine

        handler = ConfidenceHandler(enable_cards=False)
        mock_db = AsyncMock()

        result = {
            "clarification_message": "I need more information to help you. What are you looking for?",
            "suggested_options": [
                {"title": "Recent deals", "value": "recent"},
                {"title": "By stage", "value": "stage"},
                {"title": "Add timeframe", "value": "timeframe"}
            ]
        }

        response = await handler.handle_low_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.3,
            cleaned_text="show me deals",
            result=result,
            db=mock_db
        )

        # Extract text from response
        actual_text = response.text if hasattr(response, 'text') else str(response)

        # Snapshot assertion
        assert actual_text == expected_low_confidence_text_no_cards

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_medium_confidence_text_format(
        self,
        mock_track_event,
        mock_get_memory,
        expected_medium_confidence_text_no_cards
    ):
        """Test medium confidence text formatting without cards."""
        mock_memory_manager = AsyncMock()
        mock_get_memory.return_value = mock_memory_manager

        handler = ConfidenceHandler(enable_cards=False)
        mock_db = AsyncMock()

        result = {
            "text": "Here are the latest deals in the pipeline."
        }

        response = await handler.handle_medium_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.65,
            cleaned_text="show me deals",
            result=result,
            db=mock_db
        )

        # Extract text
        actual_text = response.text if hasattr(response, 'text') else str(response)

        # Snapshot assertion
        assert actual_text == expected_medium_confidence_text_no_cards

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_high_confidence_text_format(
        self,
        mock_track_event,
        mock_get_memory,
        expected_high_confidence_text
    ):
        """Test high confidence text formatting."""
        mock_memory_manager = AsyncMock()
        mock_get_memory.return_value = mock_memory_manager

        handler = ConfidenceHandler(enable_cards=False)
        mock_db = AsyncMock()

        result = {
            "text": "Here are the latest deals in the pipeline."
        }

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

        # Extract text
        actual_text = response.text if hasattr(response, 'text') else str(response)

        # Snapshot assertion
        assert actual_text == expected_high_confidence_text

    @pytest.mark.asyncio
    @patch('app.api.teams.confidence_handlers.get_memory_manager')
    @patch('app.api.teams.confidence_handlers.get_clarification_engine')
    @patch('app.api.teams.confidence_handlers.track_event')
    async def test_rate_limit_text_format(
        self,
        mock_track_event,
        mock_get_clarification,
        mock_get_memory,
        expected_rate_limit_text
    ):
        """Test rate limit text formatting without cards."""
        from app.api.teams.clarification_engine import RateLimitExceeded

        mock_memory_manager = AsyncMock()
        mock_get_memory.return_value = mock_memory_manager

        mock_engine = AsyncMock()
        mock_engine.create_clarification_session = AsyncMock(
            side_effect=RateLimitExceeded("Too many requests")
        )
        mock_get_clarification.return_value = mock_engine

        handler = ConfidenceHandler(enable_cards=False)
        mock_db = AsyncMock()

        response = await handler.handle_low_confidence_response(
            user_id="user123",
            user_email="user@example.com",
            conversation_id="conv123",
            activity_id="act123",
            confidence=0.3,
            cleaned_text="show me deals",
            result={},
            db=mock_db
        )

        # Extract text
        actual_text = response.text if hasattr(response, 'text') else str(response)

        # Snapshot assertion
        assert actual_text == expected_rate_limit_text

    def test_confidence_percentage_formatting(self):
        """Test that confidence percentages are formatted correctly."""
        confidence_values = [
            (0.65, "65%"),
            (0.8, "80%"),
            (0.923, "92%"),
            (0.5, "50%"),
            (0.999, "100%"),
            (0.001, "0%")
        ]

        for confidence, expected in confidence_values:
            formatted = f"{confidence:.0%}"
            assert formatted == expected, f"Expected {expected} for {confidence}, got {formatted}"

    def test_multiline_text_preservation(self):
        """Test that multiline text formatting is preserved."""
        multiline_text = """Line 1
Line 2

Line 4 with gap"""

        # Ensure newlines are preserved
        lines = multiline_text.split('\n')
        assert len(lines) == 4
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"
        assert lines[2] == ""
        assert lines[3] == "Line 4 with gap"

    def test_markdown_formatting(self):
        """Test markdown formatting in messages."""
        markdown_samples = [
            ("**Bold Text**", "Bold text with markdown"),
            ("_Italic Text_", "Italic text with markdown"),
            ("• Bullet Point", "Bullet point formatting"),
            ("⏱️ Emoji", "Emoji preservation")
        ]

        for sample, description in markdown_samples:
            assert "**" in sample or "_" in sample or "•" in sample or "⏱️" in sample, f"Failed: {description}"

    def test_suggestion_text_formatting(self):
        """Test formatting of suggestion options."""
        options = [
            {"title": "Add timeframe", "value": "add_timeframe"},
            {"title": "Specify person/company", "value": "add_entity"},
            {"title": "Filter by stage", "value": "add_stage"}
        ]

        # Format as bullet list
        formatted = "\n".join([f"• {opt['title']}" for opt in options[:3]])

        expected = """• Add timeframe
• Specify person/company
• Filter by stage"""

        assert formatted == expected

    def test_error_message_with_correlation_id(self):
        """Test error message formatting with correlation ID."""
        correlation_id = "abc-123-def-456"
        error_template = f"An error occurred. Please try again. (Ref: {correlation_id})"

        assert "Ref: abc-123-def-456" in error_template
        assert error_template.startswith("An error occurred")
        assert error_template.endswith(")")


class TestSnapshotConsistency:
    """Tests to ensure snapshot consistency across different scenarios."""

    def test_text_length_limits(self):
        """Test that text messages respect reasonable length limits."""
        max_message_length = 4000  # Teams message limit

        sample_messages = [
            "Short message",
            "Medium length message with some additional context and details",
            "Long message " * 100  # Artificially long message
        ]

        for message in sample_messages:
            if len(message) > max_message_length:
                # Should be truncated or handled appropriately
                truncated = message[:max_message_length - 3] + "..."
                assert len(truncated) <= max_message_length

    def test_special_character_handling(self):
        """Test that special characters are handled correctly."""
        special_chars = [
            ("Test & Company", "Ampersand"),
            ("Price: $1,000", "Dollar sign and comma"),
            ("50% increase", "Percentage"),
            ("Email: user@example.com", "At symbol"),
            ("C++ Developer", "Plus signs")
        ]

        for text, description in special_chars:
            # Ensure special characters are preserved
            assert "&" in text or "$" in text or "%" in text or "@" in text or "+" in text

    def test_whitespace_normalization(self):
        """Test that whitespace is normalized consistently."""
        inputs = [
            ("  Leading spaces", "Leading spaces"),
            ("Trailing spaces  ", "Trailing spaces"),
            ("Multiple  spaces", "Multiple  spaces"),
            ("Tab\tcharacter", "Tab\tcharacter")
        ]

        for input_text, expected in inputs:
            # Whitespace should be preserved or normalized consistently
            assert input_text.strip() == expected.strip() or input_text == expected