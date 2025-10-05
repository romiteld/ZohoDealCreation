#!/usr/bin/env python3
"""
Test Zoom integration for TalentWell system.
Tests Server-to-Server OAuth and transcript fetching.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.zoom_client import ZoomClient

# Load environment variables
load_dotenv('.env.local')

async def test_zoom_authentication():
    """Test Zoom Server-to-Server OAuth authentication."""
    print("Testing Zoom authentication...")
    
    client = ZoomClient()
    
    # Test getting access token
    token = await client.get_access_token()
    if token:
        print(f"✓ Successfully obtained access token: {token[:20]}...")
        return True
    else:
        print("✗ Failed to obtain access token")
        return False

async def test_fetch_recording():
    """Test fetching recording for a known meeting."""
    print("\nTesting recording fetch...")
    
    client = ZoomClient()
    
    # Test with a sample meeting ID (replace with actual)
    test_meeting_id = "85725475967"  # Example from requirements
    
    recording = await client.fetch_meeting_recording(test_meeting_id)
    if recording:
        print(f"✓ Successfully fetched recording for meeting {test_meeting_id}")
        print(f"  Recording files: {len(recording.get('recording_files', []))}")
        return True
    else:
        print(f"✗ No recording found for meeting {test_meeting_id}")
        return False

async def test_transcript_download():
    """Test downloading and parsing transcript."""
    print("\nTesting transcript download...")
    
    client = ZoomClient()
    
    # Test with sample meeting
    test_meeting_id = "85725475967"
    
    transcript = await client.fetch_zoom_transcript_for_meeting(test_meeting_id)
    if transcript:
        print(f"✓ Successfully fetched transcript")
        print(f"  Transcript length: {len(transcript)} characters")
        print(f"  First 200 chars: {transcript[:200]}...")
        return True
    else:
        print(f"✗ No transcript available for meeting {test_meeting_id}")
        return False

async def test_url_parsing():
    """Test parsing Zoom meeting URLs."""
    print("\nTesting URL parsing...")
    
    client = ZoomClient()
    
    test_urls = [
        "https://us02web.zoom.us/rec/share/ABC123XYZ",
        "https://zoom.us/rec/play/85725475967",
        "85725475967",  # Direct meeting ID
    ]
    
    for url in test_urls:
        meeting_id = client._extract_meeting_id(url)
        print(f"  URL: {url}")
        print(f"  Extracted ID: {meeting_id}")
    
    return True

async def test_vtt_parsing():
    """Test VTT transcript parsing."""
    print("\nTesting VTT parsing...")
    
    sample_vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
Brandon: Welcome everyone to today's meeting.

00:00:05.000 --> 00:00:10.000
John: Thanks Brandon. I wanted to discuss the candidate.

00:00:10.000 --> 00:00:15.000
Brandon: Sure, let's talk about their qualifications.
They have 10 years of experience in wealth management.
"""
    
    client = ZoomClient()
    parsed = client.parse_vtt_to_text(sample_vtt)
    
    print(f"✓ Parsed transcript:")
    print(f"  Length: {len(parsed)} characters")
    print(f"  Contains Brandon: {'Brandon:' in parsed}")
    print(f"  Contains timestamp removal: {'00:00' not in parsed}")
    
    return True

async def test_error_handling():
    """Test error handling for invalid meetings."""
    print("\nTesting error handling...")
    
    client = ZoomClient()
    
    # Test with invalid meeting ID
    invalid_id = "99999999999"
    transcript = await client.fetch_zoom_transcript_for_meeting(invalid_id)
    
    if transcript is None:
        print(f"✓ Correctly handled invalid meeting ID")
        return True
    else:
        print(f"✗ Should have returned None for invalid meeting")
        return False

async def main():
    """Run all tests."""
    print("=" * 60)
    print("ZOOM INTEGRATION TEST SUITE")
    print("=" * 60)
    
    # Check environment variables
    print("\nEnvironment Check:")
    print(f"  ZOOM_ACCOUNT_ID: {'✓' if os.getenv('ZOOM_ACCOUNT_ID') else '✗'}")
    print(f"  ZOOM_CLIENT_ID: {'✓' if os.getenv('ZOOM_CLIENT_ID') else '✗'}")
    print(f"  ZOOM_CLIENT_SECRET: {'✓' if os.getenv('ZOOM_CLIENT_SECRET') else '✗'}")
    
    # Run tests
    tests = [
        test_zoom_authentication,
        test_url_parsing,
        test_vtt_parsing,
        test_fetch_recording,
        test_transcript_download,
        test_error_handling,
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
    else:
        print(f"✗ {total - passed} test(s) failed")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)