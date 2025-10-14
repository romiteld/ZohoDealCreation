#!/usr/bin/env python3
"""
Load test script - Publish 25 digest requests to validate KEDA horizontal scaling.

Expected behavior:
- KEDA should scale from 0 → 5 replicas (25 messages / 5 per replica)
- Scale-up should complete within 90 seconds
- All messages should process without DLQ growth
- Scale-down should occur 300 seconds after queue empty

Usage:
    python scripts/load_test_digest.py
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from teams_bot.app.services.message_bus import MessageBusService

async def main():
    """Publish 25 digest requests for load testing."""
    print("🔥 Starting load test - Publishing 25 digest requests...")
    print(f"⏱️  Start time: {datetime.now().isoformat()}")
    print()

    # Initialize message bus
    message_bus = MessageBusService()

    try:
        message_ids = []

        # Publish 25 messages
        for i in range(1, 26):
            message_id = await message_bus.publish_digest_request(
                conversation_id=f"load-test-conversation-{i:03d}",
                service_url="https://smba.trafficmanager.net/amer/",
                audience="advisors",
                user_email=f"load-test-{i:03d}@example.com",
                date_range_days=7
            )
            message_ids.append(message_id)
            print(f"✅ [{i:2d}/25] Published message: {message_id}")

        print()
        print(f"📬 All 25 messages sent to queue: teams-digest-requests")
        print(f"⏱️  Publish complete: {datetime.now().isoformat()}")
        print()
        print("🔍 Expected KEDA behavior:")
        print("   - 0-60s:   KEDA detects 25 messages, spawns first replica")
        print("   - 60-90s:  5 replicas running (25 messages / 5 per replica)")
        print("   - 5-10min: All messages processed, queue empty")
        print("   - 15min:   Cooldown complete (300s), replicas scale to 0")
        print()
        print("📊 Monitor with:")
        print("   # Watch replicas scale up")
        print("   watch -n 2 'az containerapp replica list --name teams-digest-worker --resource-group TheWell-Infra-East --query \"[].{name:name,state:properties.runningState,created:properties.createdTime}\" -o table'")
        print()
        print("   # Watch queue depth")
        print("   watch -n 5 'az servicebus queue show --name teams-digest-requests --namespace-name wellintakebus-standard --resource-group TheWell-Infra-East --query \"countDetails.{active:activeMessageCount,deadLetter:deadLetterMessageCount}\" -o table'")
        print()
        print("   # View worker logs")
        print("   az containerapp logs show --name teams-digest-worker --resource-group TheWell-Infra-East --follow")
        print()
        print("📝 Message IDs for tracking:")
        for i, msg_id in enumerate(message_ids, 1):
            print(f"   [{i:2d}] {msg_id}")

    except Exception as e:
        print(f"❌ Failed to publish load test messages: {e}")
        raise
    finally:
        await message_bus.close()

if __name__ == "__main__":
    asyncio.run(main())
