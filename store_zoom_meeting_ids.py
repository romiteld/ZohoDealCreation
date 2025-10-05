#!/usr/bin/env python3
"""
Fetch all Zoom meeting IDs with recordings and store them in PostgreSQL database.
Only stores meeting IDs and metadata, not the actual recordings.
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import aiohttp
import asyncpg
import json

load_dotenv('.env.local')

async def create_zoom_meetings_table(conn):
    """Create table to store Zoom meeting IDs if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS zoom_meetings (
            id SERIAL PRIMARY KEY,
            meeting_id BIGINT UNIQUE NOT NULL,
            topic TEXT,
            host_email TEXT,
            start_time TIMESTAMP,
            duration INTEGER,
            has_transcript BOOLEAN DEFAULT FALSE,
            has_recording BOOLEAN DEFAULT FALSE,
            recording_count INTEGER DEFAULT 0,
            participant_count INTEGER,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index for faster lookups
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_meetings_meeting_id 
        ON zoom_meetings(meeting_id)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_meetings_has_transcript 
        ON zoom_meetings(has_transcript)
    """)
    
    print("✓ Database table 'zoom_meetings' ready")

async def fetch_and_store_recordings():
    """Fetch all Zoom recordings and store meeting IDs in database."""
    
    # Get credentials
    account_id = os.getenv("ZOOM_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    database_url = os.getenv("DATABASE_URL")
    
    # Connect to PostgreSQL
    conn = await asyncpg.connect(database_url)
    
    try:
        # Create table if needed
        await create_zoom_meetings_table(conn)
        
        # Get Zoom access token
        auth_url = "https://zoom.us/oauth/token"
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "account_credentials",
            "account_id": account_id
        }
        
        async with aiohttp.ClientSession() as session:
            # Get token
            async with session.post(auth_url, headers=headers, data=data) as response:
                if response.status != 200:
                    print("Failed to authenticate with Zoom")
                    return
                    
                token_data = await response.json()
                access_token = token_data.get("access_token")
                print("✓ Zoom authentication successful")
            
            # Prepare date range (last 90 days - max allowed by Zoom)
            to_date = datetime.now()
            from_date = to_date - timedelta(days=90)
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Method 1: Try account-level recordings endpoint
            print("\nFetching account-wide recordings...")
            recordings_url = "https://api.zoom.us/v2/accounts/me/recordings"
            
            page_count = 0
            total_meetings = 0
            next_page_token = ""
            
            while True:
                params = {
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                    "page_size": 300,  # Max allowed
                }
                
                if next_page_token:
                    params["next_page_token"] = next_page_token
                
                async with session.get(recordings_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        meetings = data.get("meetings", [])
                        
                        page_count += 1
                        print(f"  Page {page_count}: Found {len(meetings)} meetings")
                        
                        for meeting in meetings:
                            meeting_id = int(meeting.get("id", 0))
                            if not meeting_id:
                                continue
                            
                            topic = meeting.get("topic", "")
                            host_email = meeting.get("user_email", "")
                            start_time = meeting.get("start_time")
                            duration = meeting.get("duration", 0)
                            participant_count = meeting.get("participant_count", 0)
                            
                            # Parse start time (make timezone-naive for PostgreSQL)
                            if start_time:
                                try:
                                    # Remove timezone info for PostgreSQL compatibility
                                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                                except:
                                    start_dt = None
                            else:
                                start_dt = None
                            
                            # Check for transcript
                            recording_files = meeting.get("recording_files", [])
                            has_transcript = any(
                                f.get("file_type") == "TRANSCRIPT" or 
                                f.get("file_extension") == "VTT"
                                for f in recording_files
                            )
                            has_recording = len(recording_files) > 0
                            
                            # Store metadata
                            metadata = {
                                "uuid": meeting.get("uuid"),
                                "host_id": meeting.get("user_id"),
                                "recording_files": [
                                    {
                                        "type": f.get("file_type"),
                                        "extension": f.get("file_extension"),
                                        "size": f.get("file_size", 0)
                                    }
                                    for f in recording_files
                                ],
                                "share_url": meeting.get("share_url")
                            }
                            
                            # Insert or update in database
                            await conn.execute("""
                                INSERT INTO zoom_meetings (
                                    meeting_id, topic, host_email, start_time, 
                                    duration, has_transcript, has_recording,
                                    recording_count, participant_count, metadata
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                                ON CONFLICT (meeting_id) 
                                DO UPDATE SET 
                                    topic = EXCLUDED.topic,
                                    has_transcript = EXCLUDED.has_transcript,
                                    has_recording = EXCLUDED.has_recording,
                                    recording_count = EXCLUDED.recording_count,
                                    metadata = EXCLUDED.metadata,
                                    updated_at = CURRENT_TIMESTAMP
                            """, 
                                meeting_id, topic, host_email, start_dt,
                                duration, has_transcript, has_recording,
                                len(recording_files), participant_count,
                                json.dumps(metadata)
                            )
                            
                            total_meetings += 1
                        
                        # Check for more pages
                        next_page_token = data.get("next_page_token", "")
                        if not next_page_token:
                            break
                            
                    elif response.status == 404:
                        print("  Account-level endpoint not available, trying user-level...")
                        break
                    else:
                        error = await response.text()
                        print(f"  Error: {response.status} - {error}")
                        break
            
            # Method 2: If account-level fails, try user-level
            if total_meetings == 0:
                print("\nTrying user-level recordings...")
                
                # Get current user
                me_url = "https://api.zoom.us/v2/users/me"
                async with session.get(me_url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        user_id = user_data.get("id")
                        user_email = user_data.get("email")
                        print(f"  Checking recordings for: {user_email}")
                        
                        # Get user's recordings
                        user_recordings_url = f"https://api.zoom.us/v2/users/{user_id}/recordings"
                        params = {
                            "from": from_date.strftime("%Y-%m-%d"),
                            "to": to_date.strftime("%Y-%m-%d"),
                            "page_size": 300
                        }
                        
                        async with session.get(user_recordings_url, headers=headers, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                meetings = data.get("meetings", [])
                                
                                for meeting in meetings:
                                    meeting_id = int(meeting.get("id", 0))
                                    if not meeting_id:
                                        continue
                                    
                                    # Process and store as above
                                    topic = meeting.get("topic", "")
                                    start_time = meeting.get("start_time")
                                    duration = meeting.get("duration", 0)
                                    
                                    if start_time:
                                        try:
                                            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                                        except:
                                            start_dt = None
                                    else:
                                        start_dt = None
                                    
                                    recording_files = meeting.get("recording_files", [])
                                    has_transcript = any(
                                        f.get("file_type") == "TRANSCRIPT"
                                        for f in recording_files
                                    )
                                    
                                    metadata = {
                                        "uuid": meeting.get("uuid"),
                                        "share_url": meeting.get("share_url")
                                    }
                                    
                                    await conn.execute("""
                                        INSERT INTO zoom_meetings (
                                            meeting_id, topic, host_email, start_time,
                                            duration, has_transcript, has_recording,
                                            recording_count, metadata
                                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                                        ON CONFLICT (meeting_id) DO UPDATE SET
                                            updated_at = CURRENT_TIMESTAMP
                                    """,
                                        meeting_id, topic, user_email, start_dt,
                                        duration, has_transcript, True,
                                        len(recording_files), json.dumps(metadata)
                                    )
                                    
                                    total_meetings += 1
        
        # Display results
        print(f"\n✓ Stored {total_meetings} meeting IDs in database")
        
        # Query and show summary
        transcript_count = await conn.fetchval(
            "SELECT COUNT(*) FROM zoom_meetings WHERE has_transcript = true"
        )
        
        recent_with_transcript = await conn.fetch("""
            SELECT meeting_id, topic, host_email, start_time
            FROM zoom_meetings
            WHERE has_transcript = true
            ORDER BY start_time DESC
            LIMIT 5
        """)
        
        print(f"\nDatabase Summary:")
        print(f"  Total meetings: {total_meetings}")
        print(f"  With transcripts: {transcript_count}")
        
        if recent_with_transcript:
            print(f"\nRecent meetings with transcripts (for testing):")
            for row in recent_with_transcript:
                print(f"  Meeting ID: {row['meeting_id']}")
                print(f"    Topic: {row['topic']}")
                print(f"    Host: {row['host_email']}")
                print(f"    Date: {row['start_time']}")
                print()
        
    finally:
        await conn.close()

async def query_stored_meetings():
    """Query stored meeting IDs from database."""
    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    
    try:
        # Get counts
        total = await conn.fetchval("SELECT COUNT(*) FROM zoom_meetings")
        with_transcript = await conn.fetchval(
            "SELECT COUNT(*) FROM zoom_meetings WHERE has_transcript = true"
        )
        
        print(f"Stored Meeting IDs:")
        print(f"  Total: {total}")
        print(f"  With transcripts: {with_transcript}")
        
        # Get sample meetings for testing
        samples = await conn.fetch("""
            SELECT meeting_id, topic, has_transcript
            FROM zoom_meetings
            WHERE has_transcript = true
            ORDER BY start_time DESC
            LIMIT 10
        """)
        
        if samples:
            print("\nSample meeting IDs with transcripts:")
            for row in samples:
                print(f"  {row['meeting_id']}: {row['topic'][:50]}")
                
    finally:
        await conn.close()

if __name__ == "__main__":
    print("Fetching and storing Zoom meeting IDs...")
    asyncio.run(fetch_and_store_recordings())
    
    print("\n" + "="*60)
    print("Querying stored meetings...")
    asyncio.run(query_stored_meetings())