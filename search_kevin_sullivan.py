#!/usr/bin/env python3
"""
Search for Kevin Sullivan records in Zoho CRM
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

async def search_kevin_sullivan():
    """Search for Kevin Sullivan deals"""
    token = await get_zoho_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("Searching for Kevin Sullivan records...")
    print("=" * 60)
    
    # Try different search approaches
    base_url = "https://www.zohoapis.com/crm/v8"
    
    # Search 1: Get all deals and filter locally
    url = f"{base_url}/Deals"
    params = {
        'fields': 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time,Owner',
        'per_page': 200,
        'sort_by': 'Created_Time',
        'sort_order': 'desc'
    }
    
    kevin_deals = []
    
    async with aiohttp.ClientSession() as session:
        # Get first page
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('data'):
                    for deal in data['data']:
                        deal_name = (deal.get('Deal_Name') or '').lower()
                        candidate = (deal.get('Candidate_Name') or '').lower()
                        
                        if 'kevin' in deal_name or 'sullivan' in deal_name:
                            kevin_deals.append(deal)
                            print(f"Found: {deal.get('Deal_Name')} | Candidate: {deal.get('Candidate_Name')} | ID: {deal.get('id')}")
                        elif 'kevin' in candidate or 'sullivan' in candidate:
                            kevin_deals.append(deal)
                            print(f"Found: {deal.get('Deal_Name')} | Candidate: {deal.get('Candidate_Name')} | ID: {deal.get('id')}")
                        
                    # Check if there are more pages
                    info = data.get('info', {})
                    if info.get('more_records'):
                        print(f"\nNote: There are more records. Showing first {len(data['data'])} deals.")
            elif response.status == 204:
                print("No deals found")
            else:
                print(f"Error: {response.status}")
                text = await response.text()
                print(text)
        
        # Also search in Contacts
        print("\nSearching in Contacts...")
        url = f"{base_url}/Contacts"
        params = {
            'fields': 'id,Full_Name,First_Name,Last_Name,Email',
            'per_page': 200
        }
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('data'):
                    for contact in data['data']:
                        full_name = (contact.get('Full_Name') or '').lower()
                        first_name = (contact.get('First_Name') or '').lower()
                        last_name = (contact.get('Last_Name') or '').lower()
                        
                        if 'kevin' in full_name or 'sullivan' in full_name or 'kevin' in first_name or 'sullivan' in last_name:
                            print(f"Found Contact: {contact.get('Full_Name')} | Email: {contact.get('Email')} | ID: {contact.get('id')}")
    
    print("\n" + "=" * 60)
    print(f"Total Kevin Sullivan deals found: {len(kevin_deals)}")
    
    if kevin_deals:
        print("\nDeal IDs to delete:")
        for deal in kevin_deals:
            print(f"  {deal.get('id')}")
    
    return kevin_deals

async def main():
    load_dotenv('.env.local')
    await search_kevin_sullivan()

if __name__ == "__main__":
    asyncio.run(main())