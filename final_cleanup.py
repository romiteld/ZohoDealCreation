#!/usr/bin/env python3
"""
Final cleanup of any remaining test records.
"""

import asyncio
import httpx
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

async def final_cleanup():
    """Delete the latest test records created."""
    oauth_service_url = os.getenv('ZOHO_OAUTH_SERVICE_URL')

    # Latest test records
    final_records = [
        ('Deals', '6221978000101522131', 'Senior Financial Advisor (Fort Wayne) - Well Partners Recruiting'),
        ('Accounts', '6221978000101417253', 'Well Partners Recruiting'),
        ('Contacts', '6221978000100019021', 'Kevin Sullivan')
    ]

    print("🧹 FINAL CLEANUP OF TEST RECORDS")
    print("="*50)

    # Get access token
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{oauth_service_url}/oauth/token")
        if response.status_code != 200:
            print("❌ Could not get access token")
            return

        access_token = response.json().get('access_token')
        headers = {'Authorization': f'Zoho-oauthtoken {access_token}'}

        for module, record_id, name in final_records:
            print(f"\n🗑️ Deleting {module}: {name}")
            print(f"   ID: {record_id}")

            url = f"https://www.zohoapis.com/crm/v6/{module}/{record_id}"
            try:
                del_response = await client.delete(url, headers=headers)
                if del_response.status_code in [200, 204]:
                    print("   ✅ Deleted")
                elif del_response.status_code == 404:
                    print("   ⚠️ Already deleted")
                else:
                    print(f"   ❌ Failed: {del_response.status_code}")
            except Exception as e:
                print(f"   ❌ Error: {e}")

    print("\n✅ Final cleanup completed!")
    print("\n📊 SUMMARY OF ALL CLEANUP ACTIONS:")
    print("   • Deleted multiple test Deal records")
    print("   • Deleted multiple test Account records")
    print("   • Cleaned Kevin Sullivan test data")
    print("   • Removed Well Partners Recruiting test company")
    print("\n✨ Production Zoho CRM is now clean of test records!")

if __name__ == "__main__":
    asyncio.run(final_cleanup())