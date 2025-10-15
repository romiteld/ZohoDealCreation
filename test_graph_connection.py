#!/usr/bin/env python3
"""
Test Microsoft Graph Email Integration
Verifies authentication and email query functionality
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.microsoft_graph_client import MicrosoftGraphClient


async def test_graph_integration():
    """Test Microsoft Graph connection and email queries"""

    print("=" * 70)
    print("Microsoft Graph Email Integration Test")
    print("=" * 70)

    # Check environment variables
    print("\n1. Checking environment variables...")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        print("❌ FAILED: Missing environment variables")
        print("   Required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET")
        return False

    print(f"✅ TENANT_ID: {tenant_id[:8]}...")
    print(f"✅ CLIENT_ID: {client_id[:8]}...")
    print(f"✅ CLIENT_SECRET: {'*' * 20}")

    # Initialize client
    print("\n2. Initializing Microsoft Graph client...")
    try:
        client = MicrosoftGraphClient()
        print("✅ Client initialized")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

    # Test connection
    print("\n3. Testing connection...")
    try:
        is_connected = await client.test_connection()
        if is_connected:
            print("✅ Successfully connected to Microsoft Graph")
        else:
            print("❌ Connection test failed")
            return False
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

    # Test email query
    print("\n4. Testing email query...")
    test_email = "daniel.romitelli@emailthewell.com"

    try:
        emails = await client.get_user_emails(
            user_email=test_email,
            filter_recruitment=False,  # Get all emails for test
            hours_back=168,  # Last week
            max_emails=5
        )

        print(f"✅ Retrieved {len(emails)} email(s) for {test_email}")

        if emails:
            print("\n   Sample emails:")
            for i, email in enumerate(emails[:3], 1):
                print(f"   {i}. From: {email.from_name} <{email.from_address}>")
                print(f"      Subject: {email.subject[:60]}...")
                print(f"      Received: {email.received_time}")
                if email.has_attachments:
                    print(f"      📎 {len(email.attachments)} attachment(s)")
                print()
        else:
            print("   ⚠️  No emails found (may be empty inbox or timeframe)")

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - Microsoft Graph integration working")
    print("=" * 70)
    return True


if __name__ == "__main__":
    result = asyncio.run(test_graph_integration())
    sys.exit(0 if result else 1)
