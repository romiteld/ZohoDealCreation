#!/usr/bin/env python3
"""
Delete additional test records that were recreated.
"""

import asyncio
import httpx
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

class ZohoAdditionalDeleter:
    def __init__(self):
        self.oauth_service_url = os.getenv('ZOHO_OAUTH_SERVICE_URL')
        self.access_token = None

        # Additional test records found
        self.records_to_delete = [
            {
                'module': 'Deals',
                'id': '6221978000101461171',
                'name': 'Introduction - Kevin Sullivan for Senior Financial Advisor Role'
            },
            {
                'module': 'Contacts',
                'id': '6221978000100019021',  # Same contact ID still exists
                'name': 'Kevin Sullivan'
            },
            {
                'module': 'Accounts',
                'id': '6221978000099933039',
                'name': 'Well Partners Recruiting (duplicate)'
            }
        ]

    async def get_access_token(self) -> str:
        """Get fresh access token from OAuth service."""
        print("🔐 Getting Zoho access token...")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.oauth_service_url}/oauth/token")
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get('access_token')
                    print("   ✅ Access token obtained")
                    return self.access_token
                else:
                    print(f"   ❌ Failed to get token: {response.status_code}")
                    return None
            except Exception as e:
                print(f"   ❌ Error getting token: {e}")
                return None

    async def delete_record(self, module: str, record_id: str, record_name: str) -> bool:
        """Delete a single record from Zoho CRM."""
        if not self.access_token:
            print("   ❌ No access token available")
            return False

        url = f"https://www.zohoapis.com/crm/v6/{module}/{record_id}"
        headers = {
            'Authorization': f'Zoho-oauthtoken {self.access_token}'
        }

        print(f"\n🗑️  Deleting {module} record: {record_name}")
        print(f"   ID: {record_id}")

        async with httpx.AsyncClient() as client:
            try:
                # Delete the record
                response = await client.delete(url, headers=headers)

                if response.status_code in [200, 204]:
                    print(f"   ✅ Successfully deleted")
                    return True
                elif response.status_code == 404:
                    print(f"   ⚠️  Record not found (may already be deleted)")
                    return True
                else:
                    print(f"   ❌ Failed to delete: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ Error deleting record: {e}")
                return False

    async def cleanup_all_records(self) -> None:
        """Delete all identified test records."""
        print("\n" + "="*50)
        print("🧹 ADDITIONAL ZOHO TEST RECORD CLEANUP")
        print("="*50)
        print(f"📅 {datetime.now().isoformat()}")

        # Get access token first
        token = await self.get_access_token()
        if not token:
            print("\n❌ Failed to get access token. Cannot proceed with deletion.")
            return

        # Delete each record
        for record in self.records_to_delete:
            await self.delete_record(
                record['module'],
                record['id'],
                record['name']
            )

        print("\n✅ Additional cleanup completed!")

async def main():
    """Main execution."""
    deleter = ZohoAdditionalDeleter()
    await deleter.cleanup_all_records()

if __name__ == "__main__":
    asyncio.run(main())