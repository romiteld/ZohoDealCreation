#!/usr/bin/env python3
"""
Clean up specific test deals identified from recent activity
"""
import os
import aiohttp
import asyncio
import json
from dotenv import load_dotenv
from datetime import datetime

async def get_zoho_token():
    """Get Zoho access token"""
    refresh_token = os.getenv('ZOHO_REFRESH_TOKEN')
    client_id = os.getenv('ZOHO_CLIENT_ID')
    client_secret = os.getenv('ZOHO_CLIENT_SECRET')
    
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
                return result.get('access_token')
            else:
                text = await response.text()
                raise Exception(f"Failed to get access token: {text}")

async def find_test_deals():
    """Find specific test deals to clean up"""
    token = await get_zoho_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("Finding specific test deals to clean up...")
    print("=" * 80)
    
    base_url = "https://www.zohoapis.com/crm/v8"
    test_deals = []
    
    async with aiohttp.ClientSession() as session:
        # Get recent deals
        url = f"{base_url}/Deals"
        params = {
            'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time,Source_Detail',
            'per_page': 200,
            'sort_by': 'Created_Time',
            'sort_order': 'desc'
        }
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('data'):
                    for deal in data['data']:
                        deal_name = deal.get('Deal_Name') or ''
                        source_detail = deal.get('Source_Detail') or ''
                        created = deal.get('Created_Time', '')[:10]
                        
                        # Check for specific test patterns
                        is_test = False
                        reason = ""
                        
                        # Brandon Murphy duplicates on 2025-08-31
                        if 'Brandon Murphy' in source_detail and '2025-08-31' in created:
                            is_test = True
                            reason = "Brandon Murphy duplicate test"
                        
                        # Senior Developer - Example tests
                        elif 'Senior Developer (New York) - Example' in deal_name:
                            is_test = True
                            reason = "Example company test"
                        
                        # Software Engineer - Tech Corp tests
                        elif 'Software Engineer' in deal_name and 'Tech Corp' in deal_name:
                            is_test = True
                            reason = "Tech Corp test"
                        
                        # Fort Wayne area tests (but be careful with legitimate ones)
                        elif 'Fort Wayne area' in deal_name and 'Well Partners Recruiting' in deal_name:
                            # Check if it's from test patterns
                            if 'John Referrer' in source_detail:
                                is_test = True
                                reason = "Fort Wayne test pattern"
                        
                        if is_test:
                            test_deals.append({
                                'id': deal.get('id'),
                                'name': deal_name,
                                'created': created,
                                'source_detail': source_detail,
                                'reason': reason
                            })
    
    return test_deals

async def delete_deals(deals_to_delete):
    """Delete the identified test deals"""
    if not deals_to_delete:
        print("No deals to delete")
        return
    
    token = await get_zoho_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    base_url = "https://www.zohoapis.com/crm/v8"
    deleted_count = 0
    failed_count = 0
    
    async with aiohttp.ClientSession() as session:
        for deal in deals_to_delete:
            url = f"{base_url}/Deals"
            params = {'ids': deal['id']}
            
            try:
                async with session.delete(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        deleted_count += 1
                        print(f"✓ Deleted: {deal['name']} (ID: {deal['id']})")
                    else:
                        failed_count += 1
                        print(f"✗ Failed to delete: {deal['name']} (ID: {deal['id']})")
                        text = await response.text()
                        print(f"  Error: {text[:100]}")
            except Exception as e:
                failed_count += 1
                print(f"✗ Error deleting {deal['name']}: {e}")
    
    return deleted_count, failed_count

async def main():
    load_dotenv('.env.local')
    
    # Find test deals
    test_deals = await find_test_deals()
    
    if not test_deals:
        print("\nNo test deals found matching the specified patterns.")
        return
    
    print(f"\nFound {len(test_deals)} test deals to clean up:")
    print("-" * 80)
    
    # Group by reason
    reasons = {}
    for deal in test_deals:
        reason = deal['reason']
        if reason not in reasons:
            reasons[reason] = []
        reasons[reason].append(deal)
    
    # Display grouped results
    for reason, deals in reasons.items():
        print(f"\n{reason} ({len(deals)} deals):")
        for deal in deals[:5]:  # Show first 5 of each type
            print(f"  - {deal['name']}")
            print(f"    Created: {deal['created']} | ID: {deal['id']}")
        if len(deals) > 5:
            print(f"  ... and {len(deals) - 5} more")
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {len(test_deals)} test deals identified for deletion")
    print("=" * 80)
    
    # Proceed with deletion as approved by user
    print("\n⚠️  Proceeding with deletion as approved...")
    
    if True:  # User has already approved cleanup
        print("\nDeleting test deals...")
        deleted, failed = await delete_deals(test_deals)
        
        print("\n" + "=" * 80)
        print("DELETION SUMMARY")
        print("=" * 80)
        print(f"✓ Successfully deleted: {deleted} deals")
        if failed > 0:
            print(f"✗ Failed to delete: {failed} deals")
        print(f"Total processed: {len(test_deals)} deals")
    else:
        print("\nDeletion cancelled. No changes made.")

if __name__ == "__main__":
    asyncio.run(main())