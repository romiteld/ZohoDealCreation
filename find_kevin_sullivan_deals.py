#!/usr/bin/env python3
"""
Find all deals with Kevin Sullivan as candidate, sorted by date
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

async def find_all_kevin_sullivan_deals():
    """Find ALL deals and check for Kevin Sullivan"""
    token = await get_zoho_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("Searching ALL deals for Kevin Sullivan as candidate...")
    print("=" * 80)
    
    base_url = "https://www.zohoapis.com/crm/v8"
    
    kevin_sullivan_deals = []
    
    async with aiohttp.ClientSession() as session:
        # Get ALL deals - paginate through everything
        page = 1
        has_more = True
        total_checked = 0
        
        while has_more:
            url = f"{base_url}/Deals"
            params = {
                'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time,Modified_Time,Owner,Source,Source_Detail,Stage',
                'per_page': 200,
                'page': page,
                'sort_by': 'Created_Time',
                'sort_order': 'asc'  # Oldest first to find the original
            }
            
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data'):
                            deals = data['data']
                            total_checked += len(deals)
                            
                            for deal in deals:
                                # Check multiple fields for Kevin Sullivan
                                candidate = (deal.get('Candidate_Name') or '').lower()
                                deal_name = (deal.get('Deal_Name') or '').lower()
                                source_detail = (deal.get('Source_Detail') or '').lower()
                                
                                # Look for Kevin Sullivan in any relevant field
                                if ('kevin' in candidate and 'sullivan' in candidate) or \
                                   ('kevin' in deal_name and 'sullivan' in deal_name) or \
                                   ('kevin sullivan' in candidate) or \
                                   ('kevin sullivan' in deal_name) or \
                                   ('kevin sullivan' in source_detail):
                                    kevin_sullivan_deals.append(deal)
                                    created = deal.get('Created_Time', 'Unknown')[:10]
                                    print(f"\nFound Kevin Sullivan Deal:")
                                    print(f"  Created: {created}")
                                    print(f"  Deal Name: {deal.get('Deal_Name')}")
                                    print(f"  Candidate: {deal.get('Candidate_Name')}")
                                    print(f"  Firm: {deal.get('Firm_Name')}")
                                    print(f"  Stage: {deal.get('Stage')}")
                                    print(f"  Source: {deal.get('Source')}")
                                    print(f"  Source Detail: {deal.get('Source_Detail')}")
                                    print(f"  ID: {deal.get('id')}")
                            
                            # Check for more pages
                            info = data.get('info', {})
                            has_more = info.get('more_records', False)
                            
                            if page % 5 == 0:  # Progress update every 5 pages
                                print(f"  Checked {total_checked} deals so far...")
                            
                            page += 1
                        else:
                            has_more = False
                    elif response.status == 204:
                        print(f"No more deals found after checking {total_checked} deals")
                        has_more = False
                    else:
                        print(f"Error fetching page {page}: {response.status}")
                        text = await response.text()
                        print(f"Response: {text[:200]}")
                        has_more = False
            except Exception as e:
                print(f"Error: {e}")
                has_more = False
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: Checked {total_checked} total deals")
    print(f"Found {len(kevin_sullivan_deals)} Kevin Sullivan deals")
    
    if kevin_sullivan_deals:
        # Sort by date
        kevin_sullivan_deals.sort(key=lambda x: x.get('Created_Time', ''))
        
        print("\nKevin Sullivan Deals (sorted by creation date):")
        print("-" * 80)
        
        for i, deal in enumerate(kevin_sullivan_deals, 1):
            created = deal.get('Created_Time', 'Unknown')
            modified = deal.get('Modified_Time', 'Unknown')
            print(f"\n{i}. Deal: {deal.get('Deal_Name')}")
            print(f"   Candidate: {deal.get('Candidate_Name')}")
            print(f"   Firm: {deal.get('Firm_Name')}")
            print(f"   Created: {created}")
            print(f"   Modified: {modified}")
            print(f"   Stage: {deal.get('Stage')}")
            print(f"   ID: {deal.get('id')}")
            
            # Mark likely test vs real
            created_date = created[:10] if created != 'Unknown' else ''
            if i == 1:
                print(f"   => LIKELY THE ORIGINAL/REAL DEAL (oldest)")
            else:
                print(f"   => LIKELY A TEST (created after the first one)")
    
    return kevin_sullivan_deals

async def main():
    load_dotenv('.env.local')
    deals = await find_all_kevin_sullivan_deals()
    
    if len(deals) > 1:
        print(f"\n\n⚠️  Found {len(deals)} Kevin Sullivan deals.")
        print("The FIRST one (oldest) is likely the real deal.")
        print("The others are likely test deals that can be deleted.")
        print("\nNO DELETION WILL OCCUR WITHOUT YOUR APPROVAL.")
        
        # Save to file
        with open('kevin_sullivan_deals.json', 'w') as f:
            json.dump(deals, f, indent=2)
        print("\nFull details saved to kevin_sullivan_deals.json")

if __name__ == "__main__":
    asyncio.run(main())