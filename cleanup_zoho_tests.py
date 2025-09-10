#!/usr/bin/env python3
"""
Script to clean up test deals from Zoho CRM
Identifies and deletes test records based on patterns
"""
import os
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

class ZohoTestCleanup:
    """Clean up test records from Zoho CRM"""
    
    def __init__(self):
        self.headers = None
        self.base_url = "https://www.zohoapis.com/crm/v8"
        self.access_token = None
        
    async def get_access_token(self):
        """Get Zoho access token using refresh token"""
        refresh_token = os.getenv('ZOHO_REFRESH_TOKEN')
        client_id = os.getenv('ZOHO_CLIENT_ID')
        client_secret = os.getenv('ZOHO_CLIENT_SECRET')
        
        if not all([refresh_token, client_id, client_secret]):
            raise ValueError("Missing Zoho credentials in environment")
        
        url = "https://accounts.zoho.com/oauth/v2/token"
        data = {
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result.get('access_token')
                    self.headers = {
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    }
                    return self.access_token
                else:
                    text = await response.text()
                    raise Exception(f"Failed to get access token: {text}")
    
    async def ensure_auth(self):
        """Ensure we have valid authentication"""
        if not self.headers:
            await self.get_access_token()
        self.test_patterns = [
            "test",
            "testing",
            "unknown",
            "techcorp",
            "kevin sullivan",
            "kevin",
            "sullivan",
            "john smith",
            "sarah johnson",
            "mike chen",
            "financial advisor"
        ]
        self.deleted_count = {
            'deals': 0,
            'contacts': 0,
            'accounts': 0
        }
        
    async def search_test_deals(self, dry_run=True) -> List[Dict[str, Any]]:
        """Search for test deals based on patterns"""
        await self.ensure_auth()
        test_deals = []
        
        # Search by different criteria
        search_criteria = [
            "(Deal_Name:contains:test)",
            "(Deal_Name:contains:unknown)",
            "(Deal_Name:contains:techcorp)",
            "(Deal_Name:contains:Kevin Sullivan)",
            "(Deal_Name:contains:kevin)",
            "(Deal_Name:contains:sullivan)",
            "(Firm_Name:equals:Techcorp)",
            "(Candidate_Name:equals:Kevin Sullivan)",
            "(Candidate_Name:contains:Kevin)",
            "(Candidate_Name:contains:Sullivan)",
            "(Source_Detail:contains:test)",
            "(Created_Time:greater_than:2025-09-01T00:00:00-05:00)"  # Recent tests
        ]
        
        async with aiohttp.ClientSession() as session:
            for criteria in search_criteria:
                url = f"{self.base_url}/Deals/search"
                params = {
                    'criteria': criteria,
                    'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Source,Created_Time,Owner',
                    'per_page': 200
                }
                
                try:
                    async with session.get(url, headers=self.headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('data'):
                                for deal in data['data']:
                                    # Check if it's really a test deal
                                    if self._is_test_deal(deal):
                                        test_deals.append(deal)
                                        print(f"Found test deal: {deal.get('Deal_Name')} (ID: {deal.get('id')})")
                        elif response.status == 204:
                            print(f"No deals found for criteria: {criteria}")
                        else:
                            print(f"Error searching with criteria {criteria}: {response.status}")
                except Exception as e:
                    print(f"Error searching deals: {e}")
        
        # Remove duplicates
        unique_deals = {deal['id']: deal for deal in test_deals}
        return list(unique_deals.values())
    
    def _is_test_deal(self, deal: Dict[str, Any]) -> bool:
        """Check if a deal is likely a test based on patterns"""
        deal_name = (deal.get('Deal_Name') or '').lower()
        candidate = (deal.get('Candidate_Name') or '').lower()
        firm = (deal.get('Firm_Name') or '').lower()
        source_detail = (deal.get('Source_Detail') or '').lower()
        
        # Check for test patterns
        for pattern in self.test_patterns:
            if pattern in deal_name or pattern in candidate or pattern in firm or pattern in source_detail:
                return True
        
        # Check for deals created by test@example.com
        if 'test@example.com' in (deal.get('Source_Detail') or ''):
            return True
            
        return False
    
    async def get_related_records(self, deal_id: str) -> Dict[str, List[str]]:
        """Get related contacts and accounts for a deal"""
        await self.ensure_auth()
        related = {
            'contacts': [],
            'accounts': []
        }
        
        async with aiohttp.ClientSession() as session:
            # Get deal details with related records
            url = f"{self.base_url}/Deals/{deal_id}"
            params = {'fields': 'Contact_Name,Account_Name'}
            
            try:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data'):
                            deal_data = data['data'][0]
                            
                            # Get contact ID
                            if deal_data.get('Contact_Name') and isinstance(deal_data['Contact_Name'], dict):
                                related['contacts'].append(deal_data['Contact_Name'].get('id'))
                            
                            # Get account ID
                            if deal_data.get('Account_Name') and isinstance(deal_data['Account_Name'], dict):
                                related['accounts'].append(deal_data['Account_Name'].get('id'))
            except Exception as e:
                print(f"Error getting related records for deal {deal_id}: {e}")
        
        return related
    
    async def delete_records(self, record_type: str, record_ids: List[str], dry_run=True):
        """Delete records from Zoho"""
        if not record_ids:
            return
        
        if dry_run:
            print(f"[DRY RUN] Would delete {len(record_ids)} {record_type}")
            return
        
        await self.ensure_auth()
        async with aiohttp.ClientSession() as session:
            # Zoho allows bulk delete up to 100 records at a time
            for i in range(0, len(record_ids), 100):
                batch = record_ids[i:i+100]
                ids_param = ','.join(batch)
                url = f"{self.base_url}/{record_type}"
                params = {'ids': ids_param}
                
                try:
                    async with session.delete(url, headers=self.headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('data'):
                                for result in data['data']:
                                    if result.get('status') == 'success':
                                        self.deleted_count[record_type.lower()] += 1
                                print(f"Deleted {len(batch)} {record_type}")
                        else:
                            print(f"Error deleting {record_type}: {response.status}")
                            text = await response.text()
                            print(f"Response: {text}")
                except Exception as e:
                    print(f"Error deleting {record_type}: {e}")
    
    async def cleanup(self, dry_run=True, delete_contacts=False, delete_accounts=False):
        """Main cleanup process"""
        print("=" * 60)
        print(f"Zoho CRM Test Data Cleanup - {'DRY RUN' if dry_run else 'LIVE'}")
        print("=" * 60)
        
        # Step 1: Find test deals
        print("\n1. Searching for test deals...")
        test_deals = await self.search_test_deals(dry_run)
        print(f"Found {len(test_deals)} test deals")
        
        if not test_deals:
            print("No test deals found. Exiting.")
            return
        
        # Step 2: Collect related records
        all_contacts = set()
        all_accounts = set()
        
        if delete_contacts or delete_accounts:
            print("\n2. Finding related records...")
            for deal in test_deals:
                related = await self.get_related_records(deal['id'])
                all_contacts.update(related['contacts'])
                all_accounts.update(related['accounts'])
            
            print(f"Found {len(all_contacts)} related contacts")
            print(f"Found {len(all_accounts)} related accounts")
        
        # Step 3: Delete deals first (they depend on contacts/accounts)
        print("\n3. Deleting deals...")
        deal_ids = [deal['id'] for deal in test_deals]
        await self.delete_records('Deals', deal_ids, dry_run)
        
        # Step 4: Delete contacts (optional)
        if delete_contacts and all_contacts:
            print("\n4. Deleting contacts...")
            await self.delete_records('Contacts', list(all_contacts), dry_run)
        
        # Step 5: Delete accounts (optional)
        if delete_accounts and all_accounts:
            print("\n5. Deleting accounts...")
            await self.delete_records('Accounts', list(all_accounts), dry_run)
        
        # Summary
        print("\n" + "=" * 60)
        print("Cleanup Summary")
        print("=" * 60)
        if dry_run:
            print("DRY RUN - No actual deletions performed")
            print(f"Would delete:")
        else:
            print(f"Deleted:")
        
        print(f"  - Deals: {len(deal_ids)}")
        if delete_contacts:
            print(f"  - Contacts: {len(all_contacts)}")
        if delete_accounts:
            print(f"  - Accounts: {len(all_accounts)}")
        
        # List deals that would be/were deleted
        print("\nDeals processed:")
        for deal in test_deals[:10]:  # Show first 10
            print(f"  - {deal.get('Deal_Name')} (ID: {deal.get('id')})")
        if len(test_deals) > 10:
            print(f"  ... and {len(test_deals) - 10} more")
    
    async def list_recent_deals(self, days=7):
        """List recent deals for review"""
        await self.ensure_auth()
        print(f"\nRecent deals (last {days} days):")
        print("-" * 60)
        
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/Deals/search"
            params = {
                'criteria': f"(Created_Time:greater_than:{start_date})",
                'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time',
                'per_page': 50,
                'sort_by': 'Created_Time',
                'sort_order': 'desc'
            }
            
            try:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data'):
                            for deal in data['data']:
                                created = deal.get('Created_Time', '')[:10]
                                print(f"{created} | {deal.get('Deal_Name')} | ID: {deal.get('id')}")
                    elif response.status == 204:
                        print("No recent deals found")
            except Exception as e:
                print(f"Error listing recent deals: {e}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up test data from Zoho CRM')
    parser.add_argument('--live', action='store_true', help='Perform actual deletion (default is dry run)')
    parser.add_argument('--delete-contacts', action='store_true', help='Also delete related contacts')
    parser.add_argument('--delete-accounts', action='store_true', help='Also delete related accounts')
    parser.add_argument('--list-recent', type=int, metavar='DAYS', help='List deals from last N days')
    
    args = parser.parse_args()
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    
    cleanup = ZohoTestCleanup()
    
    if args.list_recent:
        await cleanup.list_recent_deals(args.list_recent)
    else:
        await cleanup.cleanup(
            dry_run=not args.live,
            delete_contacts=args.delete_contacts,
            delete_accounts=args.delete_accounts
        )
        
        if not args.live:
            print("\n⚠️  This was a DRY RUN. To actually delete records, run with --live flag")
            print("Example: python cleanup_zoho_tests.py --live")


if __name__ == "__main__":
    asyncio.run(main())