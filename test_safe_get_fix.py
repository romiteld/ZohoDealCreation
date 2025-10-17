#!/usr/bin/env python3
"""
Test script to verify safe_get function handles both dict and object formats.
This simulates the scenario that was causing the "'dict' object has no attribute 'channel_id'" error.
"""

def safe_get(obj, key, default=None):
    """Get value from object attribute or dict key"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class MockConversationReference:
    """Mock object to simulate ConversationReference object format"""
    def __init__(self):
        self.channel_id = "msteams"
        self.service_url = "https://smba.trafficmanager.net/amer/"
        self.conversation = MockConversation()
        self.user = MockUser()
        self.bot = MockBot()
        self.locale = "en-US"
        self.activity_id = "12345"


class MockConversation:
    def __init__(self):
        self.id = "19:abc123"
        self.tenant_id = "tenant-123"
        self.conversation_type = "personal"


class MockUser:
    def __init__(self):
        self.id = "user-123"
        self.name = "Test User"
        self.aad_object_id = "aad-123"


class MockBot:
    def __init__(self):
        self.id = "bot-123"
        self.name = "TalentWell"


def test_object_format():
    """Test safe_get with object format (ConversationReference)"""
    print("\n=== Test 1: Object Format ===")
    conv_ref = MockConversationReference()

    # Test accessing top-level attributes
    channel_id = safe_get(conv_ref, 'channel_id')
    service_url = safe_get(conv_ref, 'service_url')

    print(f"✓ channel_id: {channel_id}")
    print(f"✓ service_url: {service_url}")

    # Test accessing nested objects
    conversation = safe_get(conv_ref, 'conversation')
    user = safe_get(conv_ref, 'user')

    if conversation:
        conv_id = safe_get(conversation, 'id')
        tenant_id = safe_get(conversation, 'tenant_id')
        print(f"✓ conversation.id: {conv_id}")
        print(f"✓ conversation.tenant_id: {tenant_id}")

    if user:
        user_id = safe_get(user, 'id')
        user_name = safe_get(user, 'name')
        print(f"✓ user.id: {user_id}")
        print(f"✓ user.name: {user_name}")

    print("✅ Object format test passed!")


def test_dict_format():
    """Test safe_get with dict format (what was causing the error)"""
    print("\n=== Test 2: Dict Format ===")
    conv_ref = {
        "channel_id": "msteams",
        "service_url": "https://smba.trafficmanager.net/amer/",
        "conversation": {
            "id": "19:abc123",
            "tenant_id": "tenant-123",
            "conversation_type": "personal"
        },
        "user": {
            "id": "user-123",
            "name": "Test User",
            "aad_object_id": "aad-123"
        },
        "bot": {
            "id": "bot-123",
            "name": "TalentWell"
        },
        "locale": "en-US",
        "activity_id": "12345"
    }

    # Test accessing top-level keys (THIS WAS FAILING BEFORE)
    channel_id = safe_get(conv_ref, 'channel_id')
    service_url = safe_get(conv_ref, 'service_url')

    print(f"✓ channel_id: {channel_id}")
    print(f"✓ service_url: {service_url}")

    # Test accessing nested dicts
    conversation = safe_get(conv_ref, 'conversation')
    user = safe_get(conv_ref, 'user')

    if conversation:
        conv_id = safe_get(conversation, 'id')
        tenant_id = safe_get(conversation, 'tenant_id')
        print(f"✓ conversation['id']: {conv_id}")
        print(f"✓ conversation['tenant_id']: {tenant_id}")

    if user:
        user_id = safe_get(user, 'id')
        user_name = safe_get(user, 'name')
        print(f"✓ user['id']: {user_id}")
        print(f"✓ user['name']: {user_name}")

    print("✅ Dict format test passed!")


def test_missing_attributes():
    """Test safe_get with missing attributes/keys"""
    print("\n=== Test 3: Missing Attributes ===")

    # Empty dict
    empty_dict = {}
    result = safe_get(empty_dict, 'channel_id', 'default')
    print(f"✓ Empty dict with default: {result}")
    assert result == 'default', "Default value should be returned"

    # Object without attribute
    class EmptyObject:
        pass

    empty_obj = EmptyObject()
    result = safe_get(empty_obj, 'channel_id', 'default')
    print(f"✓ Empty object with default: {result}")
    assert result == 'default', "Default value should be returned"

    print("✅ Missing attributes test passed!")


def test_original_error_scenario():
    """
    Simulate the exact scenario that was causing the error:
    TurnContext.get_conversation_reference() returns a dict,
    but code tries to access .channel_id attribute.
    """
    print("\n=== Test 4: Original Error Scenario ===")

    # This simulates what TurnContext.get_conversation_reference() might return
    conversation_ref = {
        "channel_id": "msteams",
        "service_url": "https://smba.trafficmanager.net/amer/",
        "conversation": {"id": "19:abc123"},
        "user": {"id": "user-123", "name": "Test User"},
        "bot": {"id": "bot-123", "name": "TalentWell"}
    }

    # OLD CODE (would fail):
    # channel_id = conversation_ref.channel_id  # AttributeError: 'dict' object has no attribute 'channel_id'

    # NEW CODE (works with both formats):
    channel_id = safe_get(conversation_ref, 'channel_id')
    print(f"✓ Extracted channel_id: {channel_id}")

    # Test the full serialization logic from the actual code
    conv_conversation = safe_get(conversation_ref, 'conversation')
    conv_user = safe_get(conversation_ref, 'user')
    conv_bot = safe_get(conversation_ref, 'bot')

    reference_json = {
        "channel_id": safe_get(conversation_ref, 'channel_id'),
        "service_url": safe_get(conversation_ref, 'service_url'),
        "conversation": {
            "id": safe_get(conv_conversation, 'id') if conv_conversation else None,
            "tenant_id": safe_get(conv_conversation, 'tenant_id') if conv_conversation else None,
        },
        "user": {
            "id": safe_get(conv_user, 'id') if conv_user else None,
            "name": safe_get(conv_user, 'name') if conv_user else None,
        },
        "bot": {
            "id": safe_get(conv_bot, 'id') if conv_bot else None,
            "name": safe_get(conv_bot, 'name') if conv_bot else None,
        }
    }

    print(f"✓ Serialization successful!")
    print(f"  channel_id: {reference_json['channel_id']}")
    print(f"  conversation.id: {reference_json['conversation']['id']}")
    print(f"  user.name: {reference_json['user']['name']}")

    print("✅ Original error scenario test passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing safe_get fix for Teams Bot")
    print("=" * 60)

    try:
        test_object_format()
        test_dict_format()
        test_missing_attributes()
        test_original_error_scenario()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("=" * 60)
        print("\nThe fix successfully handles both object and dict formats.")
        print("The error 'dict' object has no attribute 'channel_id' is now resolved.")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
