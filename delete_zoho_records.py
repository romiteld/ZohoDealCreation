#!/usr/bin/env python3
"""
Direct Zoho CRM record deletion script.
Deletes test records from production Zoho CRM using Zoho API v6.
"""

import asyncio
import httpx
import os
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

class ZohoDirectDeleter:
    def __init__(self):
        self.oauth_service_url = os.getenv('ZOHO_OAUTH_SERVICE_URL')
        self.access_token = None

        # Test records to delete
        self.records_to_delete = [
            {
                'module': 'Deals',
                'id': '6221978000101417224',
                'name': 'Senior Financial Advisor (Fort Wayne) - Well Partners Recruiting'
            },
            {
                'module': 'Contacts',
                'id': '6221978000100019021',
                'name': 'Kevin Sullivan'
            },
            {
                'module': 'Accounts',
                'id': '6221978000100700056',
                'name': 'Well Partners Recruiting'
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
                # First check if record exists
                check_response = await client.get(url, headers=headers)
                if check_response.status_code == 404:
                    print(f"   ⚠️  Record not found (may already be deleted)")
                    return True
                elif check_response.status_code != 200:
                    print(f"   ❌ Error checking record: {check_response.status_code}")
                    print(f"   Response: {check_response.text}")
                    return False

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

    async def cleanup_all_records(self) -> Dict[str, Any]:
        """Delete all identified test records."""
        print("\n" + "="*50)
        print("🧹 ZOHO CRM TEST RECORD CLEANUP")
        print("="*50)
        print(f"📅 {datetime.now().isoformat()}")

        # Get access token first
        token = await self.get_access_token()
        if not token:
            print("\n❌ Failed to get access token. Cannot proceed with deletion.")
            return {'success': False, 'error': 'No access token'}

        results = {
            'total': len(self.records_to_delete),
            'deleted': 0,
            'failed': 0,
            'details': []
        }

        # Delete in reverse order (Deals -> Contacts -> Accounts)
        # This ensures we don't have orphaned records
        for record in self.records_to_delete:
            success = await self.delete_record(
                record['module'],
                record['id'],
                record['name']
            )

            if success:
                results['deleted'] += 1
                results['details'].append({
                    'module': record['module'],
                    'id': record['id'],
                    'name': record['name'],
                    'status': 'deleted'
                })
            else:
                results['failed'] += 1
                results['details'].append({
                    'module': record['module'],
                    'id': record['id'],
                    'name': record['name'],
                    'status': 'failed'
                })

        # Print summary
        print("\n" + "="*50)
        print("📊 CLEANUP SUMMARY")
        print("="*50)
        print(f"Total records: {results['total']}")
        print(f"✅ Deleted: {results['deleted']}")
        print(f"❌ Failed: {results['failed']}")

        if results['deleted'] == results['total']:
            print("\n🎉 All test records successfully deleted from production!")
        elif results['deleted'] > 0:
            print(f"\n⚠️  Partial success: {results['deleted']}/{results['total']} records deleted")
        else:
            print("\n❌ No records were deleted. Please check manually.")

        return results

async def main():
    """Main execution."""
    deleter = ZohoDirectDeleter()

    print("🚨 WARNING: This will DELETE records from PRODUCTION Zoho CRM")
    print("Records to be deleted:")
    for record in deleter.records_to_delete:
        print(f"  • {record['module']}: {record['name']} (ID: {record['id']})")

    print("\nProceeding with deletion...")

    results = await deleter.cleanup_all_records()

    # Verify deletion by testing the endpoint
    print("\n🔍 Verifying cleanup...")
    async with httpx.AsyncClient() as client:
        test_url = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/test/kevin-sullivan"
        headers = {'X-API-Key': os.getenv('API_KEY')}

        try:
            response = await client.get(test_url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'duplicate':
                    print("   ⚠️  Test endpoint still shows duplicate - records may not be fully deleted")
                else:
                    print("   ✅ Test endpoint confirmed - no duplicates found")
        except Exception as e:
            print(f"   ❌ Could not verify: {e}")

    print("\n✅ Cleanup script completed!")
    return results

if __name__ == "__main__":
    asyncio.run(main())