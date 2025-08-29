#!/usr/bin/env python3
"""
Test script for WebSocket streaming functionality
Tests real-time email processing with progressive updates
"""

import asyncio
import json
import time
import websockets
import aiohttp
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"
API_KEY = "your-secure-api-key-here"

# Test email data
TEST_EMAIL = {
    "sender_email": "john.referrer@wellpartners.com",
    "sender_name": "John Referrer",
    "subject": "Introduction - Kevin Sullivan for Senior Financial Advisor Role",
    "body": """
    Hi Team,
    
    I wanted to introduce you to Kevin Sullivan who would be perfect for the 
    Senior Financial Advisor position in the Fort Wayne area.
    
    Kevin has over 10 years of experience in wealth management and has consistently 
    exceeded his targets. He's currently looking for new opportunities and would be 
    a great addition to your team.
    
    His phone number is (555) 123-4567 and email is kevin.sullivan@email.com.
    You can also find his LinkedIn profile at linkedin.com/in/kevinsullivan
    
    Please let me know if you'd like to schedule a call to discuss further.
    
    Best regards,
    John Referrer
    Well Partners Recruiting
    """,
    "attachments": []
}


async def test_negotiate():
    """Test the negotiate endpoint"""
    print("\n=== Testing Negotiate Endpoint ===")
    
    async with aiohttp.ClientSession() as session:
        headers = {"X-API-Key": API_KEY}
        
        async with session.get(f"{BASE_URL}/stream/negotiate", headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✓ Negotiate successful:")
                print(f"  Mode: {data.get('mode')}")
                print(f"  URL: {data.get('url')}")
                print(f"  User ID: {data.get('userId')}")
                print(f"  Features: {json.dumps(data.get('features', {}), indent=2)}")
                return data
            else:
                print(f"✗ Negotiate failed: {response.status}")
                return None


async def test_websocket_streaming():
    """Test WebSocket streaming endpoint"""
    print("\n=== Testing WebSocket Streaming ===")
    
    # First negotiate
    negotiate_data = await test_negotiate()
    if not negotiate_data:
        print("Cannot test WebSocket without negotiate data")
        return
    
    ws_url = f"{WS_BASE_URL}/stream/ws/email-processing"
    print(f"Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✓ WebSocket connected")
            
            # Track metrics
            start_time = time.time()
            first_token_time = None
            events_received = []
            extracted_fields = {}
            
            # Send email for processing
            await websocket.send(json.dumps({
                "type": "process_email",
                "data": TEST_EMAIL
            }))
            print("✓ Email data sent")
            
            # Receive streaming updates
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    # Track first token time
                    if first_token_time is None and data.get("type") == "extraction_token":
                        first_token_time = elapsed
                        print(f"\n⚡ First token received in {first_token_time*1000:.0f}ms")
                    
                    # Process event
                    event_type = data.get("type")
                    events_received.append(event_type)
                    
                    if event_type == "extraction_field":
                        field = data["data"]["field"]
                        value = data["data"]["value"]
                        extracted_fields[field] = value
                        print(f"  [{elapsed:.2f}s] Found {field}: {value}")
                    
                    elif event_type == "extraction_token":
                        # Don't print every token, just track
                        pass
                    
                    elif event_type == "research_result":
                        if data["data"].get("status") == "complete":
                            company = data["data"].get("result", {}).get("company_name", "Unknown")
                            print(f"  [{elapsed:.2f}s] Company research: {company}")
                    
                    elif event_type == "complete":
                        total_time = time.time() - start_time
                        print(f"\n✓ Processing complete in {total_time:.2f}s")
                        print(f"  First token: {first_token_time*1000:.0f}ms" if first_token_time else "  No tokens streamed")
                        print(f"  Total events: {len(events_received)}")
                        print(f"  Extracted fields: {len(extracted_fields)}")
                        break
                    
                    elif event_type == "error":
                        print(f"\n✗ Error: {data['data'].get('error')}")
                        break
                    
                    else:
                        print(f"  [{elapsed:.2f}s] {event_type}: {data.get('data', {}).get('message', '')}")
                
                except asyncio.TimeoutError:
                    print("\n✗ Timeout waiting for response")
                    break
            
            # Print summary
            print("\n=== Extraction Summary ===")
            for field, value in extracted_fields.items():
                print(f"  {field}: {value}")
            
    except Exception as e:
        print(f"✗ WebSocket error: {e}")


async def test_sse_streaming():
    """Test Server-Sent Events streaming"""
    print("\n=== Testing SSE Streaming ===")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        
        start_time = time.time()
        first_event_time = None
        events_received = []
        
        async with session.post(
            f"{BASE_URL}/stream/sse/process-email",
            headers=headers,
            json=TEST_EMAIL
        ) as response:
            print(f"✓ SSE connection established: {response.status}")
            
            async for line in response.content:
                if line:
                    decoded = line.decode('utf-8').strip()
                    
                    if decoded.startswith('event:'):
                        event_type = decoded.split(':', 1)[1].strip()
                        events_received.append(event_type)
                        
                        elapsed = time.time() - start_time
                        if first_event_time is None:
                            first_event_time = elapsed
                            print(f"⚡ First event in {first_event_time*1000:.0f}ms")
                        
                        print(f"  [{elapsed:.2f}s] Event: {event_type}")
                    
                    elif decoded.startswith('data:'):
                        try:
                            data = json.loads(decoded.split(':', 1)[1].strip())
                            if 'message' in data.get('data', {}):
                                print(f"    → {data['data']['message']}")
                        except:
                            pass
        
        print(f"\n✓ SSE streaming complete")
        print(f"  Total events: {len(events_received)}")


async def test_batch_streaming():
    """Test batch endpoint with chunked streaming"""
    print("\n=== Testing Batch Streaming ===")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        
        params = {"stream_chunks": "true"}
        
        async with session.post(
            f"{BASE_URL}/stream/batch/process-email",
            headers=headers,
            json=TEST_EMAIL,
            params=params
        ) as response:
            print(f"✓ Batch streaming started: {response.status}")
            
            chunk_count = 0
            async for chunk in response.content.iter_any():
                if chunk:
                    chunk_count += 1
                    try:
                        # Each chunk is NDJSON
                        for line in chunk.decode('utf-8').strip().split('\n'):
                            if line:
                                data = json.loads(line)
                                print(f"  Chunk {chunk_count}: {data.get('type')} - {data.get('sequence', 0)}")
                    except:
                        pass
            
            print(f"✓ Received {chunk_count} chunks")


async def test_streaming_health():
    """Test streaming service health endpoint"""
    print("\n=== Testing Streaming Health ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/stream/health") as response:
            if response.status == 200:
                data = await response.json()
                print("✓ Streaming services healthy")
                print(f"  Active connections: {data.get('active_connections', 0)}")
                print(f"  SignalR configured: {data.get('signalr_configured', False)}")
                print(f"  Features: {json.dumps(data.get('features', {}), indent=4)}")
            else:
                print(f"✗ Health check failed: {response.status}")


async def main():
    """Run all streaming tests"""
    print("=" * 60)
    print("WELL INTAKE API - STREAMING TESTS")
    print("=" * 60)
    print(f"Testing against: {BASE_URL}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Test health first
    await test_streaming_health()
    
    # Test WebSocket streaming (primary)
    await test_websocket_streaming()
    
    # Test SSE streaming (fallback)
    await test_sse_streaming()
    
    # Test batch streaming
    await test_batch_streaming()
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())