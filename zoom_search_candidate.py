#!/usr/bin/env python3
"""
Search Zoom recordings by participant name or meeting topic.
Uses the working app/zoom_client.py module.

Usage:
    python3 zoom_search_candidate.py <search_term> [days]
    python3 zoom_search_candidate.py "John Smith" 30
    python3 zoom_search_candidate.py "financial advisor" 14
"""

import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, 'app')
from zoom_client import ZoomClient

load_dotenv('.env.local')

async def main():
    """Search recordings by participant or topic."""

    if len(sys.argv) < 2:
        print("Usage: python3 zoom_search_candidate.py <search_term> [days]")
        print()
        print("Examples:")
        print("  python3 zoom_search_candidate.py \"John Smith\" 30")
        print("  python3 zoom_search_candidate.py \"financial advisor\" 14")
        sys.exit(1)

    search_term = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    print(f"🔍 Searching Zoom recordings for: '{search_term}' (last {days} days)")
    print()

    try:
        client = ZoomClient()

        # Search by participant
        print("📌 Searching by participant name...")
        participant_results = await client.search_recordings_by_participant(
            participant_name=search_term,
            days=days
        )

        # Search by topic
        print("📌 Searching by meeting topic...")
        topic_results = await client.search_recordings_by_topic(
            topic=search_term,
            days=days
        )

        # Combine and deduplicate results
        all_results = {}
        for recording in participant_results + topic_results:
            meeting_id = recording.get('id')
            if meeting_id:
                all_results[meeting_id] = recording

        results = list(all_results.values())

        if not results:
            print(f"❌ No recordings found matching '{search_term}'")
            return

        print()
        print(f"✅ Found {len(results)} matching recording(s)")
        print()

        # Display results
        for i, recording in enumerate(results, 1):
            topic = recording.get('topic', 'No Topic')
            start_time = recording.get('start_time', 'Unknown')
            duration = recording.get('duration', 0)
            meeting_id = recording.get('id', 'Unknown')
            uuid = recording.get('uuid', 'Unknown')
            share_url = recording.get('share_url', 'N/A')

            # Parse start time
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %I:%M %p')
            except:
                formatted_time = start_time

            print(f"{i}. {topic}")
            print(f"   Meeting ID: {meeting_id}")
            print(f"   Date: {formatted_time}")
            print(f"   Duration: {duration} minutes")
            print(f"   Share URL: {share_url}")

            # Check for transcript
            recording_files = recording.get('recording_files', [])
            has_transcript = any(rf.get('recording_type') == 'transcript' for rf in recording_files)

            if has_transcript:
                print(f"   ✅ Transcript available")
            else:
                print(f"   ⚠️  No transcript")

            print()

        # Show command to fetch transcript
        if results:
            first_meeting_id = results[0].get('id')
            print(f"💡 To fetch transcript:")
            print(f"   python3 zoom_get_transcript.py {first_meeting_id}")
            print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
