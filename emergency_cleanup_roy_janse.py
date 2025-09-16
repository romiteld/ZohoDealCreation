#!/usr/bin/env python3
"""EMERGENCY: Clean up Roy Janse's 19 test deals from production Zoho"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv('.env.local')

# OAuth endpoint
oauth_url = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')
token_url = f"{oauth_url}/oauth/token"

print("=" * 70)
print("EMERGENCY CLEANUP: Roy Janse's 19 Test Deals")  
print("=" * 70)

# Get access token
print("\n1. Getting Zoho access token...")
try:
    token_response = requests.post(token_url)
    if token_response.status_code == 200:
        access_token = token_response.json()['access_token']
        print("   ✅ Access token obtained")
    else:
        print(f"   ❌ Failed to get token: {token_response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Error getting token: {e}")
    sys.exit(1)

headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}",
    "Content-Type": "application/json"
}

# Search for Roy Janse contact
print("\n2. Finding Roy Janse contact...")
search_url = "https://www.zohoapis.com/crm/v6/Contacts/search"
search_params = {
    "criteria": "(Email:equals:steve@emailthewell.com)",
    "fields": "id,Email,First_Name,Last_Name,Company"
}

search_response = requests.get(search_url, headers=headers, params=search_params)
if search_response.status_code == 200:
    contacts = search_response.json().get('data', [])
    if contacts:
        roy_contact = contacts[0]
        contact_id = roy_contact['id']
        print(f"   ✅ Found contact: {roy_contact.get('First_Name')} {roy_contact.get('Last_Name')} ({contact_id})")
        
        # Get all deals for this contact
        print(f"\n3. Finding all deals associated with Roy Janse...")
        deals_url = "https://www.zohoapis.com/crm/v6/Deals/search"
        deals_params = {
            "criteria": f"(Contact_Name:equals:{contact_id})",
            "fields": "id,Deal_Name,Account_Name,Contact_Name,Stage",
            "per_page": 200
        }
        
        deals_response = requests.get(deals_url, headers=headers, params=deals_params)
        if deals_response.status_code == 200:
            deals = deals_response.json().get('data', [])
            print(f"   ✅ Found {len(deals)} deals to delete")
            
            if deals:
                print("\n4. Deleting deals...")
                for i, deal in enumerate(deals, 1):
                    deal_id = deal['id']
                    deal_name = deal.get('Deal_Name', 'Unknown')
                    
                    delete_url = f"https://www.zohoapis.com/crm/v6/Deals/{deal_id}"
                    delete_response = requests.delete(delete_url, headers=headers)
                    
                    if delete_response.status_code in [200, 204]:
                        print(f"   [{i:2d}/19] ✅ Deleted: {deal_name[:60]}...")
                    else:
                        print(f"   [{i:2d}/19] ❌ Failed: {deal_name[:60]}...")
        else:
            print(f"   ⚠️ No deals found or error: {deals_response.status_code}")
    else:
        print("   ⚠️ Roy Janse contact not found by email, searching by name...")
        
        # Try searching by name
        search_params = {
            "criteria": "((First_Name:equals:Roy)and(Last_Name:equals:Janse))",
            "fields": "id,Email,First_Name,Last_Name,Company"
        }
        search_response = requests.get(search_url, headers=headers, params=search_params)
        if search_response.status_code == 200:
            contacts = search_response.json().get('data', [])
            if contacts:
                for contact in contacts:
                    contact_id = contact['id']
                    print(f"   ✅ Found: {contact.get('First_Name')} {contact.get('Last_Name')} ({contact_id})")
                    
                    # Get deals for this contact
                    deals_url = "https://www.zohoapis.com/crm/v6/Deals/search"
                    deals_params = {
                        "criteria": f"(Contact_Name:equals:{contact_id})",
                        "fields": "id,Deal_Name",
                        "per_page": 200
                    }
                    
                    deals_response = requests.get(deals_url, headers=headers, params=deals_params)
                    if deals_response.status_code == 200:
                        deals = deals_response.json().get('data', [])
                        print(f"   Found {len(deals)} deals to delete")
                        
                        for i, deal in enumerate(deals, 1):
                            deal_id = deal['id']
                            deal_name = deal.get('Deal_Name', 'Unknown')
                            
                            delete_url = f"https://www.zohoapis.com/crm/v6/Deals/{deal_id}"
                            delete_response = requests.delete(delete_url, headers=headers)
                            
                            if delete_response.status_code in [200, 204]:
                                print(f"   [{i:2d}] ✅ Deleted: {deal_name[:60]}...")
                            else:
                                print(f"   [{i:2d}] ❌ Failed: {deal_name[:60]}...")

# Also search for any deals with "Emailthewell" in the name
print("\n5. Searching for any remaining Emailthewell test deals...")
deals_params = {
    "criteria": "(Deal_Name:contains:Emailthewell)",
    "fields": "id,Deal_Name,Contact_Name",
    "per_page": 200
}

deals_response = requests.get(deals_url, headers=headers, params=deals_params)
if deals_response.status_code == 200:
    deals = deals_response.json().get('data', [])
    if deals:
        print(f"   Found {len(deals)} additional Emailthewell deals")
        for deal in deals:
            deal_id = deal['id']
            deal_name = deal.get('Deal_Name', 'Unknown')
            
            delete_url = f"https://www.zohoapis.com/crm/v6/Deals/{deal_id}"
            delete_response = requests.delete(delete_url, headers=headers)
            
            if delete_response.status_code in [200, 204]:
                print(f"   ✅ Deleted: {deal_name[:60]}...")
            else:
                print(f"   ❌ Failed: {deal_name[:60]}...")
else:
    print("   ✅ No additional Emailthewell deals found")

print("\n" + "=" * 70)
print("✅ CLEANUP COMPLETE - All Roy Janse test deals removed")
print("=" * 70)
