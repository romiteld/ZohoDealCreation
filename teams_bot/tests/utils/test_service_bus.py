"""
Unit tests for Service Bus utility functions.

Tests normalize_message_body() across different SDK body types.
"""
import pytest
from unittest.mock import Mock
from teams_bot.app.utils.service_bus import normalize_message_body


class TestNormalizeMessageBody:
    """Test normalize_message_body() handles all SDK body types."""

    def test_string_value_body(self):
        """Test VALUE body (str from model_dump_json())."""
        message = Mock()
        message.body = '{"key": "value"}'

        result = normalize_message_body(message)

        assert result == b'{"key": "value"}'
        assert isinstance(result, bytes)

    def test_bytes_sequence_body(self):
        """Test SEQUENCE body (bytes from binary payload)."""
        message = Mock()
        message.body = b'{"key": "value"}'

        result = normalize_message_body(message)

        assert result == b'{"key": "value"}'
        assert isinstance(result, bytes)

    def test_bytearray_body(self):
        """Test bytearray SEQUENCE body."""
        message = Mock()
        message.body = bytearray(b'{"key": "value"}')

        result = normalize_message_body(message)

        assert result == b'{"key": "value"}'
        assert isinstance(result, bytes)

    def test_memoryview_body(self):
        """Test memoryview SEQUENCE body."""
        message = Mock()
        message.body = memoryview(b'{"key": "value"}')

        result = normalize_message_body(message)

        assert result == b'{"key": "value"}'
        assert isinstance(result, bytes)

    def test_iterable_sequence_body(self):
        """Test SequenceBody (iterable of bytes chunks)."""
        message = Mock()
        message.body = [b'{"key":', b' "value"}']

        result = normalize_message_body(message)

        assert result == b'{"key": "value"}'
        assert isinstance(result, bytes)

    def test_unicode_string_body(self):
        """Test VALUE body with unicode characters."""
        message = Mock()
        message.body = '{"emoji": "🚀", "text": "Hello 世界"}'

        result = normalize_message_body(message)

        assert b'{"emoji": "\xf0\x9f\x9a\x80"' in result
        assert isinstance(result, bytes)

    def test_empty_string_body(self):
        """Test empty VALUE body."""
        message = Mock()
        message.body = ''

        result = normalize_message_body(message)

        assert result == b''
        assert isinstance(result, bytes)

    def test_empty_bytes_body(self):
        """Test empty SEQUENCE body."""
        message = Mock()
        message.body = b''

        result = normalize_message_body(message)

        assert result == b''
        assert isinstance(result, bytes)

    def test_unexpected_body_type_raises_typeerror(self):
        """Test TypeError raised for unexpected body types."""
        message = Mock()
        message.body = 12345  # int is not a valid body type

        with pytest.raises(TypeError) as exc_info:
            normalize_message_body(message)

        assert "Unexpected Service Bus message body type" in str(exc_info.value)
        assert "int" in str(exc_info.value)

    def test_none_body_raises_typeerror(self):
        """Test TypeError raised for None body."""
        message = Mock()
        message.body = None

        with pytest.raises(TypeError) as exc_info:
            normalize_message_body(message)

        assert "Unexpected Service Bus message body type" in str(exc_info.value)
