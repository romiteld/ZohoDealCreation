#!/usr/bin/env python3
"""
DLQ cleanup script - Clear dead-letter queue for digest requests.

This script provides safe options for clearing the dead-letter queue:
1. Purge all DLQ messages (destructive)
2. Move DLQ messages back to active queue (reprocessing)
3. List DLQ messages for inspection

Usage:
    python scripts/clear_digest_queue.py --action purge
    python scripts/clear_digest_queue.py --action requeue
    python scripts/clear_digest_queue.py --action list
"""
import asyncio
import argparse
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusSubQueue, ServiceBusMessage
from azure.servicebus.exceptions import MessageSizeExceededError
from azure.identity.aio import DefaultAzureCredential

# Import normalize_message_body for proper payload extraction
try:
    from teams_bot.app.utils.service_bus import normalize_message_body
except ImportError:
    # Fallback implementation if running standalone
    def normalize_message_body(message) -> bytes:
        """Extract message body as bytes (fallback implementation)."""
        body_obj = message.body
        if isinstance(body_obj, (bytes, bytearray, memoryview)):
            return bytes(body_obj)
        elif isinstance(body_obj, str):
            return body_obj.encode("utf-8")
        elif hasattr(body_obj, '__iter__'):
            return b"".join(body_obj)
        else:
            raise TypeError(f"Unexpected body type: {type(body_obj)}")


def _create_client(namespace: str, connection_string: str = None):
    """Create Service Bus client with managed identity or connection string."""
    if connection_string:
        return ServiceBusClient.from_connection_string(connection_string)
    else:
        # DefaultAzureCredential chain (in order):
        # 1. EnvironmentCredential (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
        # 2. ManagedIdentityCredential (Azure Container Apps, VMs)
        # 3. AzureCliCredential (local development with `az login`)
        credential = DefaultAzureCredential()
        return ServiceBusClient(
            fully_qualified_namespace=f"{namespace}.servicebus.windows.net",
            credential=credential
        ), credential


async def list_dlq_messages(namespace: str, queue_name: str, connection_string: str = None):
    """
    List messages in dead-letter queue without removing them.

    Uses peek_messages() to avoid locking messages or incrementing delivery count.
    """
    print(f"📋 Listing messages in DLQ: {queue_name}")

    client_result = _create_client(namespace, connection_string)
    if isinstance(client_result, tuple):
        client, credential = client_result
    else:
        client = client_result
        credential = None

    try:
        receiver = client.get_queue_receiver(
            queue_name=queue_name,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
            max_wait_time=5
        )

        async with receiver:
            messages = []

            # Use peek_messages() for non-destructive inspection
            # This doesn't lock messages or increment delivery count
            peeked_messages = await receiver.peek_messages(max_message_count=100)

            for message in peeked_messages:
                messages.append({
                    'message_id': message.message_id,
                    'enqueued_time': message.enqueued_time_utc,
                    'delivery_count': message.delivery_count,
                    'dead_letter_reason': message.dead_letter_reason,
                    'dead_letter_description': message.dead_letter_error_description,
                    'content_type': message.content_type,
                    'correlation_id': message.correlation_id
                })

            print(f"\n📊 Found {len(messages)} messages in DLQ:\n")
            for i, msg in enumerate(messages, 1):
                print(f"{i}. Message ID: {msg['message_id']}")
                print(f"   Enqueued: {msg['enqueued_time']}")
                print(f"   Delivery Count: {msg['delivery_count']}")
                print(f"   Reason: {msg['dead_letter_reason']}")
                print(f"   Description: {msg['dead_letter_description'][:100] if msg['dead_letter_description'] else 'N/A'}...")
                if msg['correlation_id']:
                    print(f"   Correlation ID: {msg['correlation_id']}")
                print()

            return len(messages)

    finally:
        await client.close()
        if credential:
            await credential.close()


async def purge_dlq_messages(namespace: str, queue_name: str, confirm: bool = False, connection_string: str = None):
    """Purge all messages from dead-letter queue (destructive)."""
    if not confirm:
        print("⚠️  This will PERMANENTLY DELETE all messages in the DLQ.")
        response = input("Type 'PURGE' to confirm: ")
        if response != "PURGE":
            print("❌ Operation cancelled")
            return 0

    print(f"🗑️  Purging DLQ: {queue_name}")

    client_result = _create_client(namespace, connection_string)
    if isinstance(client_result, tuple):
        client, credential = client_result
    else:
        client = client_result
        credential = None

    try:
        receiver = client.get_queue_receiver(
            queue_name=queue_name,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
            max_wait_time=5
        )

        async with receiver:
            purged_count = 0
            batch_size = 10

            while True:
                messages = []
                async for message in receiver:
                    messages.append(message)
                    if len(messages) >= batch_size:
                        break

                if not messages:
                    break

                # Complete all messages in batch (removes from DLQ)
                for message in messages:
                    await receiver.complete_message(message)
                    purged_count += 1

                print(f"✅ Purged batch of {len(messages)} messages (total: {purged_count})")

            print(f"\n🎉 Purged {purged_count} messages from DLQ")
            return purged_count

    finally:
        await client.close()
        if credential:
            await credential.close()


async def requeue_dlq_messages(namespace: str, queue_name: str, confirm: bool = False, connection_string: str = None, regenerate_ids: bool = False):
    """
    Move messages from DLQ back to active queue for reprocessing.

    Creates fresh ServiceBusMessage instances to preserve all properties:
    - Application properties (custom key-value pairs)
    - System properties (correlation_id, content_type, session_id, etc.)
    - Message body (cloned to avoid reference issues)

    Args:
        regenerate_ids: If True, generates new message_id for each message.
                       Use when queue has duplicate detection enabled to avoid rejection.
                       Default False preserves original message_id for idempotency.
    """
    if not confirm:
        print("⚠️  This will move all DLQ messages back to the active queue for reprocessing.")
        response = input("Type 'REQUEUE' to confirm: ")
        if response != "REQUEUE":
            print("❌ Operation cancelled")
            return 0

    print(f"♻️  Requeuing DLQ messages: {queue_name}")

    client_result = _create_client(namespace, connection_string)
    if isinstance(client_result, tuple):
        client, credential = client_result
    else:
        client = client_result
        credential = None

    try:
        receiver = client.get_queue_receiver(
            queue_name=queue_name,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
            max_wait_time=5
        )

        sender = client.get_queue_sender(queue_name=queue_name)

        async with receiver, sender:
            requeued_count = 0
            batch_size = 10

            while True:
                messages = []
                async for message in receiver:
                    messages.append(message)
                    if len(messages) >= batch_size:
                        break

                if not messages:
                    break

                # Build batch of fresh messages for requeue
                new_messages = []
                for dlq_message in messages:
                    # Extract actual payload using normalize_message_body
                    # This handles VALUE (str), SEQUENCE (bytes), and SequenceBody (iterable) types
                    body_bytes = normalize_message_body(dlq_message)

                    # Create fresh ServiceBusMessage with cloned body and properties
                    # This ensures Azure SDK accepts the message and preserves metadata
                    #
                    # NOTE: message_id handling:
                    # - Default (regenerate_ids=False): Preserves original message_id for idempotency
                    # - regenerate_ids=True: Generates new UUID to avoid duplicate detection rejection
                    #   Use --regenerate-message-ids flag if queue has duplicate detection enabled
                    new_message = ServiceBusMessage(
                        body=body_bytes,  # Use extracted payload, not str(dlq_message)
                        content_type=dlq_message.content_type,
                        correlation_id=dlq_message.correlation_id,
                        subject=dlq_message.subject,
                        message_id=str(uuid.uuid4()) if regenerate_ids else dlq_message.message_id,
                        partition_key=dlq_message.partition_key,
                        session_id=dlq_message.session_id,
                        reply_to=dlq_message.reply_to,
                        reply_to_session_id=dlq_message.reply_to_session_id,
                        time_to_live=dlq_message.time_to_live
                    )

                    # Copy application properties (custom key-value pairs)
                    if dlq_message.application_properties:
                        # Initialize dict if None (Azure SDK default)
                        if new_message.application_properties is None:
                            new_message.application_properties = {}
                        for key, value in dlq_message.application_properties.items():
                            new_message.application_properties[key] = value

                    new_messages.append(new_message)

                # Send entire batch in one API call (reduces round-trips)
                # Fall back to single-message sends if batch exceeds size limit
                try:
                    await sender.send_messages(new_messages)
                except MessageSizeExceededError:
                    print(f"⚠️  Batch too large, falling back to single-message sends...")
                    for new_message in new_messages:
                        await sender.send_messages(new_message)

                # Complete all DLQ messages (removes from DLQ)
                for dlq_message in messages:
                    await receiver.complete_message(dlq_message)
                    requeued_count += 1

                print(f"♻️  Requeued batch of {len(messages)} messages (total: {requeued_count})")

            print(f"\n🎉 Requeued {requeued_count} messages from DLQ to active queue")
            print(f"⚠️  KEDA will now scale up workers to process these messages")
            return requeued_count

    finally:
        await client.close()
        if credential:
            await credential.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Manage dead-letter queue for teams-digest-requests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List DLQ messages (non-destructive peek)
  python scripts/clear_digest_queue.py --action list

  # Purge DLQ (with confirmation)
  python scripts/clear_digest_queue.py --action purge

  # Purge DLQ (skip confirmation for automation)
  python scripts/clear_digest_queue.py --action purge --yes

  # Move DLQ messages back to active queue (clones properties)
  python scripts/clear_digest_queue.py --action requeue

  # Use connection string (local development without Azure CLI)
  python scripts/clear_digest_queue.py --action list --connection-string "Endpoint=sb://..."

Authentication Methods (in priority order):
  1. --connection-string: Direct connection string (highest priority)
  2. DefaultAzureCredential chain:
     a. Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
     b. Managed identity (Azure Container Apps, VMs, AKS)
     c. Azure CLI (local development with `az login`)

Production Features:
  - List uses peek_messages() to avoid locking or incrementing delivery count
  - Requeue creates fresh ServiceBusMessage with cloned body and all properties
  - Batch processing (10 messages/batch) prevents memory overflow
        """
    )

    parser.add_argument(
        '--action',
        choices=['list', 'purge', 'requeue'],
        required=True,
        help='Action to perform on DLQ'
    )

    parser.add_argument(
        '--namespace',
        default='wellintakebus-standard',
        help='Service Bus namespace (default: wellintakebus-standard)'
    )

    parser.add_argument(
        '--queue',
        default='teams-digest-requests',
        help='Queue name (default: teams-digest-requests)'
    )

    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompts (use with caution)'
    )

    parser.add_argument(
        '--connection-string',
        help='Service Bus connection string (alternative to managed identity)'
    )

    parser.add_argument(
        '--regenerate-message-ids',
        action='store_true',
        help='Generate new message_id for each requeued message (use if queue has duplicate detection enabled)'
    )

    args = parser.parse_args()

    print(f"🚀 DLQ Manager")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print(f"📮 Namespace: {args.namespace}")
    print(f"📬 Queue: {args.queue}")
    print(f"🎬 Action: {args.action}")

    if args.connection_string:
        print(f"🔑 Auth: Connection string")
    else:
        print(f"🔑 Auth: DefaultAzureCredential (managed identity/Azure CLI)")
    print()

    try:
        if args.action == 'list':
            count = await list_dlq_messages(args.namespace, args.queue, args.connection_string)
            if count == 0:
                print("✅ DLQ is empty")

        elif args.action == 'purge':
            count = await purge_dlq_messages(args.namespace, args.queue, confirm=args.yes, connection_string=args.connection_string)
            if count == 0:
                print("✅ DLQ was already empty")

        elif args.action == 'requeue':
            count = await requeue_dlq_messages(args.namespace, args.queue, confirm=args.yes, connection_string=args.connection_string, regenerate_ids=args.regenerate_message_ids)
            if count == 0:
                print("✅ DLQ was already empty")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
