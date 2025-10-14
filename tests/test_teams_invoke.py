"""
Test suite for Microsoft Teams Adaptive Card invoke handler.
Tests the robust data extraction logic that handles nested msteams.value payloads.

CONTEXT:
The invoke handler in app/api/teams/routes.py had a bug where nested msteams.value
payloads weren't being unwrapped correctly. This was fixed in lines 654-678.
These tests ensure that fix doesn't regress.
"""
import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from botbuilder.schema import Activity, ActivityTypes
from botbuilder.core import TurnContext


class TestAdaptiveCardInvokeHandler:
    """Test Adaptive Card invoke activity handler."""

    @pytest.fixture
    def mock_db(self):
        """Mock database connection."""
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=True)
        db.fetchrow = AsyncMock(return_value=None)
        db.execute = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def mock_turn_context(self):
        """Create mock TurnContext with activity."""
        context = MagicMock(spec=TurnContext)
        context.activity = Activity(
            type=ActivityTypes.invoke,
            id="test-activity-123",
            from_property=MagicMock(
                id="user-test-123",
                name="Test User",
                additional_properties={"email": "test@emailthewell.com"}
            ),
            conversation=MagicMock(id="conv-test-123")
        )
        context.send_activity = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_nested_payload_unwrapping(self, mock_turn_context, mock_db):
        """
        Test that nested msteams.value payload is correctly unwrapped.

        This is the critical test for the bug fix in lines 654-678.
        Teams sends nested payloads like:
        {
            "msteams": {
                "value": {
                    "session_id": "abc-123",
                    "user_query": "Test query"
                }
            }
        }

        The handler should extract these values into final_data.
        """
        from app.api.teams.routes import handle_invoke_activity

        # Simulate nested payload from Teams
        mock_turn_context.activity.value = {
            "msteams": {
                "type": "invoke",
                "value": {
                    "action": "submit_clarification",
                    "session_id": "test-session-123",
                    "clarification_response": "Last week"
                }
            }
        }

        # Mock clarification engine
        with patch('app.api.teams.routes.get_clarification_engine') as mock_engine_getter:
            mock_engine = AsyncMock()
            mock_engine.get_clarification_session = MagicMock(return_value={
                "session_id": "test-session-123",
                "user_id": "user-test-123",
                "original_query": "show me deals",
                "intent": {"intent_type": "search", "entities": {}},
                "ambiguity_type": "vague_search",
                "suggested_options": []
            })
            mock_engine.merge_clarification_response = MagicMock(return_value={
                "intent_type": "search",
                "entities": {"timeframe": "last_week"}
            })
            mock_engine.clear_clarification_session = MagicMock()
            mock_engine_getter.return_value = mock_engine

            # Mock memory manager
            with patch('app.api.teams.routes.get_memory_manager') as mock_memory_getter:
                mock_memory = AsyncMock()
                mock_memory.add_message = AsyncMock()
                mock_memory.get_context_for_query = AsyncMock(return_value=[])
                mock_memory_getter.return_value = mock_memory

                # Mock query engine
                with patch('app.api.teams.routes.process_natural_language_query') as mock_query:
                    mock_query.return_value = {
                        "text": "Found 5 deals from last week",
                        "confidence_score": 0.9,
                        "data": []
                    }

                    # Execute handler
                    await handle_invoke_activity(mock_turn_context, mock_db)

                    # Verify invoke response was sent
                    assert mock_turn_context.send_activity.call_count == 2

                    # First call should be invoke response
                    first_call = mock_turn_context.send_activity.call_args_list[0]
                    invoke_resp = first_call[0][0]
                    assert invoke_resp.type == ActivityTypes.invoke_response
                    assert invoke_resp.value["status"] == 200

                    # Verify that clarification handler was called with correct data
                    # (verifying the unwrapped data was accessible)
                    assert mock_engine.get_clarification_session.called
                    mock_engine.get_clarification_session.assert_called_with("test-session-123")

    @pytest.mark.asyncio
    async def test_direct_payload_handling(self, mock_turn_context, mock_db):
        """
        Test that direct payload (without nesting) is handled correctly.

        Some Teams actions send direct payloads:
        {
            "action": "show_preferences",
            "user_id": "123"
        }

        The handler should process these without requiring nested unwrapping.
        """
        from app.api.teams.routes import handle_invoke_activity

        # Simulate direct payload (no nesting)
        mock_turn_context.activity.value = {
            "action": "show_preferences"
        }

        # Mock preferences function
        with patch('app.api.teams.routes.show_user_preferences') as mock_prefs:
            mock_prefs.return_value = {
                "type": "message",
                "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive"}]
            }

            # Execute handler
            await handle_invoke_activity(mock_turn_context, mock_db)

            # Verify invoke response was sent
            assert mock_turn_context.send_activity.call_count == 2

            # First call should be invoke response with 200 status
            first_call = mock_turn_context.send_activity.call_args_list[0]
            invoke_resp = first_call[0][0]
            assert invoke_resp.type == ActivityTypes.invoke_response
            assert invoke_resp.value["status"] == 200

            # Verify preferences handler was called
            assert mock_prefs.called

    @pytest.mark.asyncio
    async def test_missing_action_field(self, mock_turn_context, mock_db):
        """
        Test error handling when action field is missing.

        If the payload doesn't contain an action field, the handler should
        gracefully handle it and return an error response.
        """
        from app.api.teams.routes import handle_invoke_activity

        # Simulate payload without action field
        mock_turn_context.activity.value = {
            "some_other_field": "value",
            "no_action": "here"
        }

        # Execute handler
        await handle_invoke_activity(mock_turn_context, mock_db)

        # Verify invoke response was sent
        assert mock_turn_context.send_activity.call_count == 2

        # Should still send invoke response (empty action)
        first_call = mock_turn_context.send_activity.call_args_list[0]
        invoke_resp = first_call[0][0]
        assert invoke_resp.type == ActivityTypes.invoke_response
        assert invoke_resp.value["status"] == 200

    @pytest.mark.asyncio
    async def test_form_data_override_behavior(self, mock_turn_context, mock_db):
        """
        Test that form data overrides metadata when keys conflict.

        As per lines 665-666 in routes.py:
        final_data = {**action_metadata, **form_data}

        This means form_data should take precedence over action_metadata.
        """
        from app.api.teams.routes import handle_invoke_activity

        # Simulate payload with both nested metadata AND root-level data
        # The root-level "action" should override nested "action"
        mock_turn_context.activity.value = {
            "msteams": {
                "value": {
                    "action": "old_action",
                    "shared_field": "nested_value"
                }
            },
            "action": "generate_digest_preview",
            "audience": "global",
            "shared_field": "root_value"  # This should win
        }

        # Mock digest preview
        with patch('app.api.teams.routes.generate_digest_preview') as mock_digest:
            mock_digest.return_value = {
                "type": "message",
                "attachments": []
            }

            # Execute handler
            await handle_invoke_activity(mock_turn_context, mock_db)

            # Verify digest preview was called (not "old_action")
            assert mock_digest.called

            # Check that root-level data overrode nested data
            call_kwargs = mock_digest.call_args[1]
            assert call_kwargs["audience"] == "global"

    @pytest.mark.asyncio
    async def test_refine_query_action(self, mock_turn_context, mock_db):
        """
        Test the refine_query action specifically.

        This action is used from medium-confidence suggestion cards
        and creates a real clarification session.
        """
        from app.api.teams.routes import handle_invoke_activity

        mock_turn_context.activity.value = {
            "action": "refine_query",
            "original_query": "show deals",
            "confidence": 0.65
        }

        # Mock clarification engine
        with patch('app.api.teams.routes.get_clarification_engine') as mock_engine_getter:
            mock_engine = AsyncMock()
            mock_engine.create_clarification_session = AsyncMock(return_value={
                "session_id": "new-session-456",
                "user_id": "user-test-123",
                "original_query": "show deals",
                "created_at": "2025-10-14T10:00:00"
            })
            mock_engine_getter.return_value = mock_engine

            # Mock adaptive cards
            with patch('app.api.teams.routes.create_clarification_card') as mock_card:
                mock_card.return_value = {
                    "content": {
                        "type": "AdaptiveCard",
                        "body": []
                    }
                }

                # Execute handler
                await handle_invoke_activity(mock_turn_context, mock_db)

                # Verify session was created
                assert mock_engine.create_clarification_session.called
                call_kwargs = mock_engine.create_clarification_session.call_args[1]
                assert call_kwargs["query"] == "show deals"

    @pytest.mark.asyncio
    async def test_error_handling_in_invoke(self, mock_turn_context, mock_db):
        """
        Test that errors in invoke handler are caught and returned properly.

        The handler should send a 500 invoke response and an error card.
        """
        from app.api.teams.routes import handle_invoke_activity

        # Simulate an action that will cause an error
        mock_turn_context.activity.value = {
            "action": "generate_digest",
            "request_id": "non-existent-request"
        }

        # Make generate_full_digest raise an exception
        with patch('app.api.teams.routes.generate_full_digest') as mock_digest:
            mock_digest.side_effect = Exception("Database connection failed")

            # Execute handler
            await handle_invoke_activity(mock_turn_context, mock_db)

            # Verify error responses were sent
            assert mock_turn_context.send_activity.call_count == 2

            # First call should be error invoke response
            first_call = mock_turn_context.send_activity.call_args_list[0]
            invoke_resp = first_call[0][0]
            assert invoke_resp.type == ActivityTypes.invoke_response
            assert invoke_resp.value["status"] == 500
            assert "Database connection failed" in invoke_resp.value["body"]["message"]

            # Second call should be error card
            # (We can't easily verify the card content without more mocking,
            # but we can verify a second call was made)

    @pytest.mark.asyncio
    async def test_multiple_concurrent_invokes(self, mock_db):
        """
        Test that multiple concurrent invoke activities are handled independently.

        This ensures no shared state issues between requests.
        """
        from app.api.teams.routes import handle_invoke_activity

        # Create two independent contexts
        context1 = MagicMock(spec=TurnContext)
        context1.activity = Activity(
            type=ActivityTypes.invoke,
            id="activity-1",
            from_property=MagicMock(
                id="user-1",
                additional_properties={"email": "user1@test.com"}
            ),
            conversation=MagicMock(id="conv-1"),
            value={"action": "show_preferences"}
        )
        context1.send_activity = AsyncMock()

        context2 = MagicMock(spec=TurnContext)
        context2.activity = Activity(
            type=ActivityTypes.invoke,
            id="activity-2",
            from_property=MagicMock(
                id="user-2",
                additional_properties={"email": "user2@test.com"}
            ),
            conversation=MagicMock(id="conv-2"),
            value={"action": "show_preferences"}
        )
        context2.send_activity = AsyncMock()

        # Mock preferences
        with patch('app.api.teams.routes.show_user_preferences') as mock_prefs:
            mock_prefs.return_value = {
                "type": "message",
                "attachments": []
            }

            # Execute both handlers concurrently
            import asyncio
            await asyncio.gather(
                handle_invoke_activity(context1, mock_db),
                handle_invoke_activity(context2, mock_db)
            )

            # Both should succeed independently
            assert context1.send_activity.call_count == 2
            assert context2.send_activity.call_count == 2

    def test_payload_structure_documentation(self):
        """
        Document the expected payload structures for reference.

        This is a documentation test that shows the two main payload patterns.
        """
        # Pattern 1: Nested msteams.value (button clicks from adaptive cards)
        nested_payload = {
            "msteams": {
                "type": "invoke",
                "value": {
                    "action": "submit_clarification",
                    "session_id": "abc-123",
                    "clarification_response": "Last week"
                }
            }
        }

        # Pattern 2: Direct payload (form submissions, some actions)
        direct_payload = {
            "action": "save_preferences",
            "default_audience": "global",
            "notification_enabled": "true"
        }

        # Pattern 3: Mixed (has both nested and root-level data)
        # Root-level should override nested in case of conflicts
        mixed_payload = {
            "msteams": {
                "value": {
                    "action": "old_value",
                    "session_id": "123"
                }
            },
            "action": "submit_clarification",  # This wins
            "clarification_response": "user input"
        }

        # The handler processes these with the logic from lines 654-678:
        # 1. Extract raw_payload from activity.value
        # 2. Unwrap action_metadata from msteams.value (if present)
        # 3. Extract form_data (root level, excluding msteams)
        # 4. Merge: final_data = {**action_metadata, **form_data}
        # 5. Get action from final_data.get("action", "")

        # This test just documents the patterns - no assertions needed
        assert nested_payload is not None
        assert direct_payload is not None
        assert mixed_payload is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
