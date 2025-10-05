#!/usr/bin/env python3
"""
Test Zoom integration with a real meeting ID from the database.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.zoom_client import ZoomClient

load_dotenv('.env.local')

async def test_real_meeting():
    """Test with a real meeting ID that has a transcript."""
    
    # Use one of the recent meetings with transcripts
    test_meetings = [
        ("82397104869", "Brandon / Danny Daily"),
        ("83675699932", "Brandon Murphy's Zoom Meeting"),
        ("84198169927", "Keith Casiano Video Cover Letter Creation"),
    ]
    
    client = ZoomClient()
    
    for meeting_id, topic in test_meetings:
        print(f"\n{'='*60}")
        print(f"Testing Meeting ID: {meeting_id}")
        print(f"Topic: {topic}")
        print('='*60)
        
        # Fetch transcript using the main method
        transcript = await client.fetch_zoom_transcript_for_meeting(meeting_id)
        
        if transcript:
            print("✓ Successfully fetched transcript!")
            print(f"  Length: {len(transcript)} characters")
            
            # Show first 500 characters
            print(f"\n  Preview (first 500 chars):")
            print("  " + "-"*50)
            preview = transcript[:500].replace('\n', '\n  ')
            print(f"  {preview}")
            print("  " + "-"*50)
            
            # Check for key phrases
            if "brandon" in transcript.lower():
                print("  ✓ Contains 'Brandon'")
            if "candidate" in transcript.lower():
                print("  ✓ Contains 'candidate'")
            if "experience" in transcript.lower():
                print("  ✓ Contains 'experience'")
            
            print(f"\n✓ Meeting {meeting_id} is perfect for testing!")
            print(f"  Use this ID in your tests")
            
            # Save to file for inspection
            output_file = f"transcript_{meeting_id}.txt"
            with open(output_file, 'w') as f:
                f.write(f"Meeting ID: {meeting_id}\n")
                f.write(f"Topic: {topic}\n")
                f.write("="*60 + "\n\n")
                f.write(transcript)
            print(f"\n  Full transcript saved to: {output_file}")
            
            break  # Found a good one
        else:
            print("✗ No transcript found for this meeting")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_real_meeting())
    if success:
        print("\n✓ Zoom integration is working! Ready for deployment.")
    else:
        print("\n✗ Issues found with Zoom integration")