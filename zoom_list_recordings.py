#!/usr/bin/env python3
"""
List all Zoom cloud recordings from the last N days.
Uses the working app/zoom_client.py module.

Usage:
    python3 zoom_list_recordings.py [days]
    python3 zoom_list_recordings.py 30  # List recordings from last 30 days
"""

import asyncio
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, 'app')
from zoom_client import ZoomClient

load_dotenv('.env.local')

async def main():
    """List all recordings from last N days."""

    # Get number of days from command line or default to 7
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    print(f"🔍 Fetching Zoom recordings from last {days} days...")
    print()

    try:
        client = ZoomClient()

        # Calculate date range
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')

        # Get recordings
        recordings = await client.list_recordings(from_date=from_date, to_date=to_date)

        if not recordings:
            print(f"❌ No recordings found in last {days} days")
            return

        print(f"✅ Found {len(recordings)} recordings")
        print()

        # Display recordings
        for i, recording in enumerate(recordings, 1):
            topic = recording.get('topic', 'No Topic')
            start_time = recording.get('start_time', 'Unknown')
            duration = recording.get('duration', 0)
            recording_count = recording.get('recording_count', 0)
            meeting_id = recording.get('id', 'Unknown')
            uuid = recording.get('uuid', 'Unknown')

            # Parse start time
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %I:%M %p')
            except:
                formatted_time = start_time

            print(f"{i}. {topic}")
            print(f"   Meeting ID: {meeting_id}")
            print(f"   UUID: {uuid}")
            print(f"   Date: {formatted_time}")
            print(f"   Duration: {duration} minutes")
            print(f"   Files: {recording_count} recording(s)")

            # Show recording files
            recording_files = recording.get('recording_files', [])
            for rf in recording_files:
                file_type = rf.get('recording_type', 'Unknown')
                file_size = rf.get('file_size', 0) / (1024 * 1024)  # Convert to MB
                download_url = rf.get('download_url', 'N/A')

                print(f"      - {file_type}: {file_size:.2f} MB")
                if file_type in ['chat_file', 'transcript']:
                    print(f"        URL: {download_url}")

            print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
