#!/usr/bin/env python3
"""
Smoke test script - Publish single digest request to Service Bus queue.

Usage:
    python scripts/smoke_test_digest.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from teams_bot.app.services.message_bus import MessageBusService


async def main():
    """Publish single smoke test digest request."""
    print("🧪 Starting smoke test - Publishing 1 digest request...")

    # Initialize message bus
    message_bus = MessageBusService()

    # Create test message
    try:
        message_id = await message_bus.publish_digest_request(
            conversation_id="smoke-test-conversation-001",
            service_url="https://smba.trafficmanager.net/amer/",
            audience="advisors",
            user_email="smoke-test@example.com",
            date_range_days=7  # Use date_range_days instead of from_date/to_date
        )

        print(f"✅ Published smoke test message: {message_id}")
        print(f"📬 Message sent to queue: teams-digest-requests")
        print(f"⏱️  Timestamp: {datetime.now().isoformat()}")
        print("\n👀 Monitor worker logs with:")
        print("   az containerapp logs show --name teams-digest-worker --resource-group TheWell-Infra-East --follow")

    except Exception as e:
        print(f"❌ Failed to publish smoke test message: {e}")
        raise
    finally:
        await message_bus.close()


if __name__ == "__main__":
    asyncio.run(main())
