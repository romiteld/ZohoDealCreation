#!/usr/bin/env python3
"""
Comprehensive search for Kevin Sullivan across all Zoho CRM modules
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

async def search_module(session, headers, module, search_terms):
    """Search a specific module for Kevin Sullivan records"""
    base_url = "https://www.zohoapis.com/crm/v8"
    found_records = []
    
    print(f"\n{'='*60}")
    print(f"Searching {module}...")
    print(f"{'='*60}")
    
    # Get records from module
    url = f"{base_url}/{module}"
    
    # Define fields based on module
    if module == 'Deals':
        fields = 'id,Deal_Name,Candidate_Name,Firm_Name,Created_Time,Owner,Source,Source_Detail'
    elif module == 'Contacts':
        fields = 'id,Full_Name,First_Name,Last_Name,Email,Created_Time,Owner'
    elif module == 'Leads':
        fields = 'id,Full_Name,First_Name,Last_Name,Company,Email,Created_Time,Owner'
    elif module == 'Accounts':
        fields = 'id,Account_Name,Created_Time,Owner'
    else:
        fields = 'id,Name,Created_Time'
    
    params = {
        'fields': fields,
        'per_page': 200,
        'sort_by': 'Created_Time',
        'sort_order': 'desc'
    }
    
    try:
        page = 1
        has_more = True
        total_checked = 0
        
        while has_more and page <= 10:  # Check up to 10 pages (2000 records)
            params['page'] = page
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data'):
                        records = data['data']
                        total_checked += len(records)
                        
                        for record in records:
                            # Convert record to string for searching
                            record_str = json.dumps(record).lower()
                            
                            # Check if any search term appears in the record
                            for term in search_terms:
                                if term.lower() in record_str:
                                    found_records.append(record)
                                    
                                    # Display key fields based on module
                                    if module == 'Deals':
                                        print(f"  FOUND: Deal: {record.get('Deal_Name')}")
                                        print(f"         Candidate: {record.get('Candidate_Name')}")
                                        print(f"         Firm: {record.get('Firm_Name')}")
                                    elif module == 'Contacts':
                                        print(f"  FOUND: Contact: {record.get('Full_Name', record.get('Last_Name'))}")
                                        print(f"         Email: {record.get('Email')}")
                                    elif module == 'Leads':
                                        print(f"  FOUND: Lead: {record.get('Full_Name', record.get('Last_Name'))}")
                                        print(f"         Company: {record.get('Company')}")
                                        print(f"         Email: {record.get('Email')}")
                                    elif module == 'Accounts':
                                        print(f"  FOUND: Account: {record.get('Account_Name')}")
                                    
                                    print(f"         ID: {record.get('id')}")
                                    print(f"         Created: {record.get('Created_Time', 'Unknown')[:10]}")
                                    print()
                                    break
                        
                        # Check for more pages
                        info = data.get('info', {})
                        has_more = info.get('more_records', False)
                        
                        if page == 1:
                            total_records = info.get('count', 0)
                            print(f"  Total {module} in CRM: {total_records}")
                        
                        print(f"  Checked page {page} ({total_checked} records so far)...")
                        page += 1
                    else:
                        has_more = False
                elif response.status == 204:
                    print(f"  No {module} found")
                    has_more = False
                else:
                    print(f"  Error fetching {module}: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text[:200]}")
                    has_more = False
                    
    except Exception as e:
        print(f"  Error searching {module}: {e}")
    
    if found_records:
        print(f"\n  Summary: Found {len(found_records)} {module} with Kevin/Sullivan")
    else:
        print(f"\n  Summary: No Kevin/Sullivan found in {total_checked} {module} checked")
    
    return found_records

async def comprehensive_search():
    """Search all modules for Kevin Sullivan records"""
    token = await get_zoho_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("\nCOMPREHENSIVE SEARCH FOR KEVIN SULLIVAN RECORDS")
    print("=" * 60)
    print(f"Search started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Search terms
    search_terms = ['kevin', 'sullivan', 'Kevin', 'Sullivan', 'KEVIN', 'SULLIVAN']
    
    # Modules to search
    modules = ['Deals', 'Contacts', 'Leads', 'Accounts']
    
    all_results = {}
    
    async with aiohttp.ClientSession() as session:
        for module in modules:
            results = await search_module(session, headers, module, search_terms)
            if results:
                all_results[module] = results
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    
    if all_results:
        total_count = sum(len(records) for records in all_results.values())
        print(f"\nTotal Kevin/Sullivan records found: {total_count}")
        
        for module, records in all_results.items():
            print(f"\n{module}: {len(records)} records")
            for i, record in enumerate(records[:5], 1):  # Show first 5 of each
                if module == 'Deals':
                    print(f"  {i}. {record.get('Deal_Name')} (ID: {record.get('id')})")
                elif module == 'Contacts':
                    print(f"  {i}. {record.get('Full_Name', record.get('Last_Name'))} (ID: {record.get('id')})")
                elif module == 'Leads':
                    print(f"  {i}. {record.get('Full_Name', record.get('Last_Name'))} (ID: {record.get('id')})")
                elif module == 'Accounts':
                    print(f"  {i}. {record.get('Account_Name')} (ID: {record.get('id')})")
            
            if len(records) > 5:
                print(f"  ... and {len(records) - 5} more")
        
        print("\n⚠️  NO DELETION WILL OCCUR WITHOUT YOUR EXPLICIT APPROVAL")
        print("Review the records above and let me know which ones to delete.")
    else:
        print("\nNo Kevin Sullivan records found in any module.")
    
    return all_results

async def main():
    load_dotenv('.env.local')
    results = await comprehensive_search()
    
    # Save results to file for review
    if results:
        with open('kevin_sullivan_records.json', 'w') as f:
            # Convert to serializable format
            output = {}
            for module, records in results.items():
                output[module] = []
                for record in records:
                    output[module].append({
                        'id': record.get('id'),
                        'name': record.get('Deal_Name') or record.get('Full_Name') or record.get('Account_Name') or record.get('Last_Name'),
                        'created': record.get('Created_Time', 'Unknown')
                    })
            json.dump(output, f, indent=2)
        print("\nResults saved to kevin_sullivan_records.json for review")

if __name__ == "__main__":
    asyncio.run(main())