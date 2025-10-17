#!/usr/bin/env python3
"""Find existing contact in Zoho CRM by ID."""

import asyncio
import os
from dotenv import load_dotenv
import aiohttp
import json

# Load environment variables
load_dotenv('.env.local')

CONTACT_ID = "6221978000101789065"

async def get_zoho_token():
    """Get Zoho OAuth token from the service."""
    oauth_service_url = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{oauth_service_url}/api/token") as response:
            if response.status == 200:
                data = await response.json()
                return data.get('access_token')
            else:
                print(f"Failed to get token: {response.status}")
                return None

async def find_contact_by_id(contact_id):
    """Find a contact in Zoho CRM by ID."""
    token = await get_zoho_token()
    if not token:
        print("Failed to get Zoho token")
        return None

    # Zoho API v8 endpoint for getting a specific contact
    url = f"https://www.zohoapis.com/crm/v8/Contacts/{contact_id}"

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', [{}])[0] if data.get('data') else None
            else:
                error_text = await response.text()
                print(f"Error fetching contact {contact_id}: {response.status}")
                print(f"Response: {error_text}")
                return None

async def search_contact_by_name(name):
    """Search for contacts by name."""
    token = await get_zoho_token()
    if not token:
        print("Failed to get Zoho token")
        return None

    # Zoho API v8 search endpoint
    url = "https://www.zohoapis.com/crm/v8/Contacts/search"

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json"
    }

    # Search criteria - looking for Tim Koski
    params = {
        "criteria": f"(Full_Name:equals:Tim Koski)",
        "fields": "First_Name,Last_Name,Email,Account_Name,Phone,id,Created_Time,Modified_Time"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', [])
            else:
                error_text = await response.text()
                print(f"Error searching contacts: {response.status}")
                print(f"Response: {error_text}")
                return None

async def get_related_deals(contact_id):
    """Get deals related to a contact."""
    token = await get_zoho_token()
    if not token:
        return None

    # Get related deals for this contact
    url = f"https://www.zohoapis.com/crm/v8/Contacts/{contact_id}/Deals"

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', [])
            else:
                return []

async def main():
    print(f"=== Finding Zoho Contact ID: {CONTACT_ID} ===\n")

    # Try to get contact by ID
    print("1. Fetching contact by ID...")
    contact = await find_contact_by_id(CONTACT_ID)

    if contact:
        print(f"✅ Contact found!")
        print(f"   Name: {contact.get('First_Name', '')} {contact.get('Last_Name', '')}")
        print(f"   Email: {contact.get('Email', 'N/A')}")
        print(f"   Company: {contact.get('Account_Name', {}).get('name', 'N/A') if isinstance(contact.get('Account_Name'), dict) else contact.get('Account_Name', 'N/A')}")
        print(f"   Phone: {contact.get('Phone', 'N/A')}")
        print(f"   Created: {contact.get('Created_Time', 'N/A')}")
        print(f"   Modified: {contact.get('Modified_Time', 'N/A')}")
        print(f"   Owner: {contact.get('Owner', {}).get('name', 'N/A') if isinstance(contact.get('Owner'), dict) else 'N/A'}")

        # Get related deals
        print("\n2. Fetching related deals...")
        deals = await get_related_deals(CONTACT_ID)
        if deals:
            print(f"   Found {len(deals)} related deal(s):")
            for deal in deals[:5]:  # Show first 5 deals
                print(f"   - {deal.get('Deal_Name', 'N/A')} (Stage: {deal.get('Stage', 'N/A')})")
        else:
            print("   No related deals found")
    else:
        print(f"❌ Contact ID {CONTACT_ID} not found")

        # Try searching by name
        print("\n3. Searching for 'Tim Koski' by name...")
        contacts = await search_contact_by_name("Tim Koski")

        if contacts:
            print(f"   Found {len(contacts)} contact(s) named Tim Koski:")
            for c in contacts:
                print(f"   - ID: {c.get('id')}")
                print(f"     Name: {c.get('First_Name', '')} {c.get('Last_Name', '')}")
                print(f"     Email: {c.get('Email', 'N/A')}")
                print(f"     Company: {c.get('Account_Name', {}).get('name', 'N/A') if isinstance(c.get('Account_Name'), dict) else c.get('Account_Name', 'N/A')}")
                print()
        else:
            print("   No contacts found with name 'Tim Koski'")

    # Direct Zoho CRM link
    print(f"\n=== Direct Zoho CRM Link ===")
    print(f"https://crm.zoho.com/crm/org749563832/tab/Contacts/{CONTACT_ID}")
    print("\nNote: You can copy and paste this URL into your browser to view the contact directly in Zoho CRM")

if __name__ == "__main__":
    asyncio.run(main())