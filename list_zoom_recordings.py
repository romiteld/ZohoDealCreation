#!/usr/bin/env python3
"""
List all Zoom recordings in your account to find valid meeting IDs.
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import aiohttp

load_dotenv('.env.local')

async def list_all_recordings():
    """List all cloud recordings from the last 30 days."""
    
    # Get credentials
    account_id = os.getenv("ZOOM_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    
    # Get access token
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
                print("Failed to authenticate")
                return
                
            token_data = await response.json()
            access_token = token_data.get("access_token")
        
        # List recordings from last 30 days
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Get all users first
        users_url = "https://api.zoom.us/v2/users"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with session.get(users_url, headers=headers) as response:
            if response.status != 200:
                print("Failed to get users")
                return
                
            users_data = await response.json()
            users = users_data.get("users", [])
        
        print(f"Found {len(users)} users in account\n")
        print("Searching for recordings...\n")
        
        all_recordings = []
        
        # Check each user's recordings
        for user in users:
            user_id = user.get("id")
            email = user.get("email")
            
            recordings_url = f"https://api.zoom.us/v2/users/{user_id}/recordings"
            params = {
                "from": from_date,
                "to": to_date,
                "page_size": 30
            }
            
            async with session.get(recordings_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    meetings = data.get("meetings", [])
                    
                    for meeting in meetings:
                        meeting_id = meeting.get("id")
                        topic = meeting.get("topic", "No topic")
                        start_time = meeting.get("start_time", "")
                        recording_count = meeting.get("recording_count", 0)
                        
                        # Check if VTT transcript exists
                        recording_files = meeting.get("recording_files", [])
                        has_transcript = any(
                            f.get("file_type") == "TRANSCRIPT" 
                            for f in recording_files
                        )
                        
                        all_recordings.append({
                            "meeting_id": meeting_id,
                            "topic": topic,
                            "host": email,
                            "date": start_time[:10] if start_time else "Unknown",
                            "files": recording_count,
                            "has_transcript": has_transcript
                        })
        
        # Display results
        if all_recordings:
            print("=" * 80)
            print("AVAILABLE ZOOM RECORDINGS")
            print("=" * 80)
            
            for rec in all_recordings:
                transcript_status = "✓ Has VTT" if rec["has_transcript"] else "✗ No VTT"
                print(f"\nMeeting ID: {rec['meeting_id']}")
                print(f"  Topic: {rec['topic']}")
                print(f"  Host: {rec['host']}")
                print(f"  Date: {rec['date']}")
                print(f"  Files: {rec['files']}")
                print(f"  Transcript: {transcript_status}")
            
            # Show best candidates for testing
            with_transcripts = [r for r in all_recordings if r["has_transcript"]]
            if with_transcripts:
                print("\n" + "=" * 80)
                print("BEST TEST CANDIDATES (Have VTT Transcripts):")
                print("=" * 80)
                for rec in with_transcripts[:5]:  # Show top 5
                    print(f"\nMeeting ID: {rec['meeting_id']}")
                    print(f"  Topic: {rec['topic']}")
                    print(f"  Use this ID for testing!")
        else:
            print("No recordings found in the last 30 days")
            print("\nTry:")
            print("1. Recording a test meeting")
            print("2. Checking if cloud recording is enabled")
            print("3. Extending the date range")

if __name__ == "__main__":
    asyncio.run(list_all_recordings())