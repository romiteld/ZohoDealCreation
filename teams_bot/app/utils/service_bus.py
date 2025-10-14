"""
Azure Service Bus utility functions.

Provides helpers for working with Service Bus messages across SDK versions.
"""


def normalize_message_body(message) -> bytes:
    """
    Normalize Service Bus message body to bytes across SDK versions.

    Azure Service Bus SDK supports multiple message body types that vary
    across versions:
    - VALUE bodies: str from ServiceBusMessage(body=model_dump_json())
    - SEQUENCE bodies: bytes/bytearray/memoryview from binary payloads
    - SequenceBody: Iterable of bytes chunks

    This function normalizes all body types to bytes for consistent JSON parsing.

    Args:
        message: ServiceBusReceivedMessage with body attribute

    Returns:
        bytes: UTF-8 encoded message body ready for JSON decoding

    Raises:
        TypeError: If body type is unexpected

    Examples:
        >>> # VALUE body (string)
        >>> message.body = '{"key": "value"}'
        >>> normalize_message_body(message)
        b'{"key": "value"}'

        >>> # SEQUENCE body (bytes)
        >>> message.body = b'{"key": "value"}'
        >>> normalize_message_body(message)
        b'{"key": "value"}'

        >>> # SequenceBody (iterable)
        >>> message.body = [b'{"key":', b' "value"}']
        >>> normalize_message_body(message)
        b'{"key": "value"}'
    """
    body_obj = message.body

    if isinstance(body_obj, (bytes, bytearray, memoryview)):
        # SEQUENCE body - binary payload
        return bytes(body_obj)
    elif isinstance(body_obj, str):
        # VALUE body - string payload (common from model_dump_json())
        return body_obj.encode("utf-8")
    elif hasattr(body_obj, '__iter__'):
        # SequenceBody - iterable of bytes chunks
        return b"".join(body_obj)
    else:
        raise TypeError(
            f"Unexpected Service Bus message body type: {type(body_obj)}. "
            f"Expected str, bytes, bytearray, memoryview, or iterable."
        )
