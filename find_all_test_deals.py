#!/usr/bin/env python3
"""Find ALL test deals in production Zoho"""
import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv('.env.local')

oauth_url = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')
token_url = f"{oauth_url}/oauth/token"

print("=" * 70)
print("SCANNING FOR ALL TEST DEALS IN PRODUCTION")
print("=" * 70)

# Get access token
token_response = requests.post(token_url)
if token_response.status_code == 200:
    access_token = token_response.json()['access_token']
    print("✅ Access token obtained\n")
else:
    print(f"❌ Failed to get token: {token_response.status_code}")
    sys.exit(1)

headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}",
    "Content-Type": "application/json"
}

# Get all recent deals (last 2 days)
print("Searching for recent deals that might be test data...")
deals_url = "https://www.zohoapis.com/crm/v6/Deals"
today = datetime.now()
two_days_ago = (today - timedelta(days=2)).strftime("%Y-%m-%d")

params = {
    "fields": "id,Deal_Name,Account_Name,Contact_Name,Stage,Created_Time,Owner",
    "per_page": 200,
    "sort_by": "Created_Time",
    "sort_order": "desc"
}

response = requests.get(deals_url, headers=headers, params=params)
if response.status_code == 200:
    all_deals = response.json().get('data', [])
    
    # Filter for potential test deals
    test_patterns = [
        "Emailthewell", "emailthewell", 
        "Test", "test",
        "Roy Janse", "Steve Perry",
        "Recruiting Services",
        "Unknown Location",
        "Wealth DynamX", "Wealth Dynamx",
        "Well Recruiting Solutions",
        "Mariner Wealth"
    ]
    
    test_deals = []
    for deal in all_deals:
        deal_name = deal.get('Deal_Name', '')
        created = deal.get('Created_Time', '')
        
        # Check if it's recent (last 2 days) or matches test patterns
        is_test = False
        for pattern in test_patterns:
            if pattern in deal_name:
                is_test = True
                break
        
        if created and created >= two_days_ago:
            is_test = True
            
        if is_test:
            test_deals.append(deal)
    
    print(f"\n📊 Found {len(test_deals)} potential test deals:\n")
    
    if test_deals:
        print("Deal ID                    | Deal Name")
        print("-" * 70)
        for deal in test_deals:
            deal_id = deal['id']
            deal_name = deal.get('Deal_Name', 'Unknown')[:60]
            print(f"{deal_id} | {deal_name}")
        
        print(f"\n⚠️ Total test deals found: {len(test_deals)}")
        
        # Delete them
        print("\n🗑️ Deleting all test deals...")
        for i, deal in enumerate(test_deals, 1):
            deal_id = deal['id']
            deal_name = deal.get('Deal_Name', 'Unknown')
            
            delete_url = f"https://www.zohoapis.com/crm/v6/Deals/{deal_id}"
            delete_response = requests.delete(delete_url, headers=headers)
            
            if delete_response.status_code in [200, 204]:
                print(f"   [{i:2d}/{len(test_deals)}] ✅ Deleted: {deal_name[:50]}...")
            else:
                print(f"   [{i:2d}/{len(test_deals)}] ❌ Failed: {deal_name[:50]}...")
    else:
        print("✅ No test deals found")
else:
    print(f"❌ Error fetching deals: {response.status_code}")

print("\n" + "=" * 70)
print("✅ CLEANUP COMPLETE")
print("=" * 70)
