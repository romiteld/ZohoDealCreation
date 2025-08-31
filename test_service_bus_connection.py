#!/usr/bin/env python3
"""
Quick test script to verify Azure Service Bus connection
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

async def test_connection():
    """Test Service Bus connection and basic operations"""
    
    # Import after loading env vars
    from app.service_bus_manager import ServiceBusManager
    
    print("Testing Azure Service Bus connection...")
    print(f"Connection String: {os.getenv('AZURE_SERVICE_BUS_CONNECTION_STRING')[:50]}...")
    print(f"Queue Name: {os.getenv('AZURE_SERVICE_BUS_QUEUE_NAME')}")
    
    try:
        # Create Service Bus manager
        service_bus = ServiceBusManager()
        
        # Connect to Service Bus
        await service_bus.connect()
        print("✅ Successfully connected to Azure Service Bus")
        
        # Get queue status
        status = await service_bus.get_queue_status()
        print(f"\n📊 Queue Status:")
        print(f"  - Queue Name: {status.get('queue_name')}")
        print(f"  - Message Count: {status.get('message_count', 0)}")
        print(f"  - Total Emails: {status.get('total_emails', 0)}")
        print(f"  - Max Batch Size: {status.get('max_batch_size')}")
        print(f"  - Connected: {status.get('connected')}")
        
        # Peek at messages without removing them
        messages = await service_bus.peek_messages(max_messages=5)
        if messages:
            print(f"\n📨 Found {len(messages)} messages in queue:")
            for msg in messages:
                print(f"  - Batch ID: {msg.get('batch_id')}")
                print(f"    Email Count: {msg.get('email_count')}")
                print(f"    Created: {msg.get('created_at')}")
        else:
            print("\n📨 No messages currently in queue")
        
        # Close connection
        await service_bus.close()
        print("\n✅ Service Bus connection test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Service Bus connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_connection())
    exit(0 if success else 1)