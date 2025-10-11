#!/usr/bin/env python3
"""
Fetch transcript for a specific Zoom meeting.
Uses the working app/zoom_client.py module.

Usage:
    python3 zoom_get_transcript.py <meeting_id_or_url>
    python3 zoom_get_transcript.py 1234567890
    python3 zoom_get_transcript.py https://zoom.us/rec/share/abcd1234
"""

import asyncio
import sys
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, 'app')
from zoom_client import ZoomClient

load_dotenv('.env.local')

async def main():
    """Fetch transcript for a meeting."""

    if len(sys.argv) < 2:
        print("Usage: python3 zoom_get_transcript.py <meeting_id_or_url>")
        print()
        print("Examples:")
        print("  python3 zoom_get_transcript.py 1234567890")
        print("  python3 zoom_get_transcript.py https://zoom.us/rec/share/abcd1234")
        sys.exit(1)

    meeting_input = sys.argv[1]

    print(f"🔍 Fetching transcript for: {meeting_input}")
    print()

    try:
        client = ZoomClient()

        # Fetch transcript
        transcript = await client.fetch_zoom_transcript_for_meeting(meeting_input)

        if not transcript:
            print("❌ No transcript found for this meeting")
            print()
            print("Possible reasons:")
            print("  - Meeting does not have a transcript")
            print("  - Transcript not yet processed by Zoom")
            print("  - Invalid meeting ID or URL")
            print("  - Recording not found")
            return

        print("✅ Transcript found!")
        print()
        print("=" * 80)
        print(transcript)
        print("=" * 80)
        print()
        print(f"📊 Transcript length: {len(transcript)} characters")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
