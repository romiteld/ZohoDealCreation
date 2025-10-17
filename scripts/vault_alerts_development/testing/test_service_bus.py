#!/usr/bin/env python3
"""Test Azure Service Bus connectivity and queue operations."""

import os
import json
import asyncio
from datetime import datetime
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

CONNECTION_STRING = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
DIGEST_QUEUE = os.getenv("AZURE_SERVICE_BUS_DIGEST_QUEUE", "teams-digest-requests")
NLP_QUEUE = os.getenv("AZURE_SERVICE_BUS_NLP_QUEUE", "teams-nlp-queries")


async def test_send_message(queue_name: str, message_body: dict):
    """Send a test message to a queue."""
    print(f"\n📤 Sending message to queue: {queue_name}")
    print(f"Message body: {json.dumps(message_body, indent=2)}")

    async with ServiceBusClient.from_connection_string(
        CONNECTION_STRING
    ) as servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        async with sender:
            message = ServiceBusMessage(
                body=json.dumps(message_body),
                content_type="application/json",
                application_properties={
                    "source": "test_script",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            await sender.send_messages(message)
            print(f"✅ Message sent successfully to {queue_name}")


async def test_receive_message(queue_name: str, max_wait_time: int = 5):
    """Receive messages from a queue."""
    print(f"\n📥 Receiving messages from queue: {queue_name}")

    async with ServiceBusClient.from_connection_string(
        CONNECTION_STRING
    ) as servicebus_client:
        receiver = servicebus_client.get_queue_receiver(
            queue_name=queue_name,
            max_wait_time=max_wait_time
        )
        async with receiver:
            messages = await receiver.receive_messages(
                max_message_count=10,
                max_wait_time=max_wait_time
            )

            if not messages:
                print(f"⚠️  No messages in {queue_name}")
                return

            for message in messages:
                print(f"\n📨 Received message:")
                print(f"  Body: {str(message)}")
                print(f"  Message ID: {message.message_id}")
                print(f"  Sequence Number: {message.sequence_number}")
                print(f"  Application Properties: {message.application_properties}")

                # Complete the message (acknowledge receipt)
                await receiver.complete_message(message)
                print(f"  ✅ Message completed (removed from queue)")


async def test_peek_messages(queue_name: str, count: int = 5):
    """Peek at messages without removing them from the queue."""
    print(f"\n👀 Peeking at messages in queue: {queue_name}")

    async with ServiceBusClient.from_connection_string(
        CONNECTION_STRING
    ) as servicebus_client:
        receiver = servicebus_client.get_queue_receiver(queue_name=queue_name)
        async with receiver:
            messages = await receiver.peek_messages(max_message_count=count)

            if not messages:
                print(f"⚠️  No messages to peek in {queue_name}")
                return

            print(f"Found {len(messages)} message(s):")
            for i, message in enumerate(messages, 1):
                print(f"\n  Message {i}:")
                print(f"    Body: {str(message)}")
                print(f"    Sequence Number: {message.sequence_number}")


async def main():
    """Run Service Bus tests."""
    print("=" * 60)
    print("Azure Service Bus Connection Test")
    print("=" * 60)
    print(f"Namespace: wellintakebus-standard")
    print(f"Digest Queue: {DIGEST_QUEUE}")
    print(f"NLP Queue: {NLP_QUEUE}")

    # Test digest queue
    print("\n" + "=" * 60)
    print("Testing DIGEST QUEUE")
    print("=" * 60)

    digest_message = {
        "request_id": "test-digest-001",
        "user_email": "test@emailthewell.com",
        "audience": "advisors",
        "date_range": {
            "from": "2025-01-01",
            "to": "2025-01-14"
        }
    }

    await test_send_message(DIGEST_QUEUE, digest_message)
    await asyncio.sleep(1)  # Brief pause
    await test_peek_messages(DIGEST_QUEUE)
    await test_receive_message(DIGEST_QUEUE)

    # Test NLP queue
    print("\n" + "=" * 60)
    print("Testing NLP QUEUE")
    print("=" * 60)

    nlp_message = {
        "request_id": "test-nlp-001",
        "user_email": "test@emailthewell.com",
        "query": "Show me all candidates from New York",
        "timestamp": datetime.utcnow().isoformat()
    }

    await test_send_message(NLP_QUEUE, nlp_message)
    await asyncio.sleep(1)  # Brief pause
    await test_peek_messages(NLP_QUEUE)
    await test_receive_message(NLP_QUEUE)

    print("\n" + "=" * 60)
    print("✅ Service Bus connection test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    if not CONNECTION_STRING:
        print("❌ ERROR: AZURE_SERVICE_BUS_CONNECTION_STRING not found in environment")
        print("Please ensure .env.local contains the connection string")
        exit(1)

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        exit(1)