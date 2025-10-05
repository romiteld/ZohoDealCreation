#!/usr/bin/env python3
"""
Direct test of Zoom authentication to verify scope updates.
"""

import asyncio
import base64
import os
from dotenv import load_dotenv
import aiohttp

# Load environment variables
load_dotenv('.env.local')

async def test_zoom_auth():
    """Test Zoom Server-to-Server OAuth authentication."""
    
    # Get credentials
    account_id = os.getenv("ZOOM_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    
    print(f"Account ID: {account_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret[:8]}...")
    
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
        async with session.post(auth_url, headers=headers, data=data) as response:
            if response.status == 200:
                token_data = await response.json()
                access_token = token_data.get("access_token")
                print(f"\n✓ Authentication successful!")
                print(f"Token: {access_token[:50]}...")
                print(f"Scope: {token_data.get('scope', 'No scopes returned')}")
                
                # Test fetching a recording
                meeting_id = "85725475967"
                recording_url = f"https://api.zoom.us/v2/meetings/{meeting_id}/recordings"
                
                headers = {
                    "Authorization": f"Bearer {access_token}"
                }
                
                print(f"\nTesting recording access for meeting {meeting_id}...")
                async with session.get(recording_url, headers=headers) as rec_response:
                    if rec_response.status == 200:
                        print("✓ Recording access granted! Scopes are working.")
                        data = await rec_response.json()
                        print(f"Recording files found: {len(data.get('recording_files', []))}")
                    else:
                        error_data = await rec_response.text()
                        print(f"✗ Recording access denied: {rec_response.status}")
                        print(f"Error: {error_data}")
                        
                        if "does not contain scopes" in error_data:
                            print("\n⚠️  Scopes not yet active. Please:")
                            print("1. Go to https://marketplace.zoom.us/develop/apps")
                            print("2. Click on your Server-to-Server OAuth app")
                            print("3. Go to the 'Scopes' section")
                            print("4. Add these scopes:")
                            print("   - recording:read:admin")
                            print("   - cloud_recording:read:list_recording_files")
                            print("   - cloud_recording:read:list_recording_files:admin")
                            print("5. Click 'Save'")
                            print("6. If prompted, click 'Reauthorize' or 'Activate'")
            else:
                print(f"✗ Authentication failed: {response.status}")
                error = await response.text()
                print(f"Error: {error}")

if __name__ == "__main__":
    asyncio.run(test_zoom_auth())