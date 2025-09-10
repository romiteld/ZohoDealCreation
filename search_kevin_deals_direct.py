#!/usr/bin/env python3
"""
Direct search for Kevin Sullivan deals using Zoho API v8 search endpoint
"""
import os
import aiohttp
import asyncio
import json
from dotenv import load_dotenv

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

async def search_kevin_sullivan_deals():
    """Search for Kevin Sullivan deals using search API"""
    token = await get_zoho_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("Searching for Kevin Sullivan deals using Zoho Search API...")
    print("=" * 60)
    
    base_url = "https://www.zohoapis.com/crm/v8"
    
    # Different search patterns
    search_patterns = [
        "Kevin Sullivan",
        "Kevin",
        "Sullivan",
        "kevin sullivan",
        "KEVIN SULLIVAN"
    ]
    
    all_deals = []
    
    async with aiohttp.ClientSession() as session:
        for pattern in search_patterns:
            print(f"\nSearching for pattern: '{pattern}'")
            
            # Try search endpoint
            url = f"{base_url}/Deals/search"
            params = {
                'criteria': f'(Candidate_Name:contains:{pattern})',
                'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time,Owner',
                'per_page': 200
            }
            
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data'):
                            print(f"  Found {len(data['data'])} deals")
                            for deal in data['data']:
                                # Avoid duplicates
                                if not any(d['id'] == deal['id'] for d in all_deals):
                                    all_deals.append(deal)
                                    print(f"    - {deal.get('Deal_Name')} | Candidate: {deal.get('Candidate_Name')} | ID: {deal.get('id')}")
                        else:
                            print(f"  No deals found")
                    elif response.status == 204:
                        print(f"  No deals found (204)")
                    else:
                        print(f"  Error: {response.status}")
                        text = await response.text()
                        print(f"  Response: {text[:200]}")
            except Exception as e:
                print(f"  Error searching: {e}")
        
        # Also try a direct query without search API
        print("\n\nTrying direct Deal listing with pagination...")
        url = f"{base_url}/Deals"
        page = 1
        has_more = True
        
        while has_more and page <= 5:  # Limit to 5 pages for now
            params = {
                'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time',
                'per_page': 200,
                'page': page,
                'sort_by': 'Created_Time',
                'sort_order': 'desc'
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data'):
                        print(f"\nPage {page}: Checking {len(data['data'])} deals...")
                        for deal in data['data']:
                            candidate = (deal.get('Candidate_Name') or '').lower()
                            deal_name = (deal.get('Deal_Name') or '').lower()
                            
                            if 'kevin' in candidate or 'sullivan' in candidate or 'kevin' in deal_name or 'sullivan' in deal_name:
                                # Avoid duplicates
                                if not any(d['id'] == deal['id'] for d in all_deals):
                                    all_deals.append(deal)
                                    print(f"  FOUND: {deal.get('Deal_Name')} | Candidate: {deal.get('Candidate_Name')} | ID: {deal.get('id')}")
                        
                        # Check if there are more pages
                        info = data.get('info', {})
                        has_more = info.get('more_records', False)
                        page += 1
                    else:
                        has_more = False
                elif response.status == 204:
                    print(f"No more deals")
                    has_more = False
                else:
                    print(f"Error fetching page {page}: {response.status}")
                    has_more = False
    
    print("\n" + "=" * 60)
    print(f"Total Kevin Sullivan deals found: {len(all_deals)}")
    
    if all_deals:
        print("\nDeals to review/delete:")
        for deal in all_deals:
            print(f"  - {deal.get('Deal_Name')} | Candidate: {deal.get('Candidate_Name')}")
            print(f"    ID: {deal.get('id')}")
    
    return all_deals

async def main():
    load_dotenv('.env.local')
    deals = await search_kevin_sullivan_deals()
    
    if deals:
        print(f"\n\nWould you like to delete these {len(deals)} deals?")
        print("Run with --delete flag to remove them")

if __name__ == "__main__":
    asyncio.run(main())