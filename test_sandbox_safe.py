#!/usr/bin/env python3
"""
SAFE Sandbox Test - Does NOT modify any production code
Tests Zoho Sandbox API directly without going through the main application
"""

import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

class ZohoSandboxTester:
    """Direct Zoho Sandbox API tester - completely isolated from production"""
    
    def __init__(self):
        # Get credentials from environment
        self.client_id = os.getenv('ZOHO_CLIENT_ID')
        self.client_secret = os.getenv('ZOHO_CLIENT_SECRET')
        self.refresh_token = os.getenv('ZOHO_REFRESH_TOKEN')
        self.dc = os.getenv('ZOHO_DC', 'com')
        
        # SANDBOX URLs - not production!
        self.token_url = f"https://accounts.zoho.{self.dc}/oauth/v2/token"
        self.api_base = f"https://sandbox.zohoapis.{self.dc}/crm/v8"
        
        self.access_token = None
        
    def get_sandbox_token(self):
        """Get access token for SANDBOX environment"""
        print("🔐 Getting SANDBOX access token...")
        
        # IMPORTANT: This token request needs to be for SANDBOX organization
        # The refresh token must be generated specifically for sandbox
        
        data = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(self.token_url, data=data)
        
        if response.status_code == 200:
            self.access_token = response.json()['access_token']
            print("✅ Got sandbox access token")
            return True
        else:
            print(f"❌ Failed to get token: {response.text}")
            return False
    
    def search_existing_records(self):
        """Search for any existing test records in sandbox"""
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        print("\n🔍 Checking for existing records in SANDBOX...")
        
        # Search for Everpar company
        company_search = requests.get(
            f"{self.api_base}/Accounts/search?criteria=Account_Name:equals:Everpar",
            headers=headers
        )
        
        if company_search.status_code == 200 and company_search.json().get('data'):
            print("⚠️  Found existing Everpar company in sandbox")
            return True
        
        # Search for Tim Koski
        contact_search = requests.get(
            f"{self.api_base}/Contacts/search?criteria=Email:equals:tim.koski@everpar.com",
            headers=headers
        )
        
        if contact_search.status_code == 200 and contact_search.json().get('data'):
            print("⚠️  Found existing Tim Koski contact in sandbox")
            return True
            
        print("✅ No existing test records found - safe to proceed")
        return False
    
    def create_test_records(self):
        """Create the three test records in SANDBOX"""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        print("\n📝 Creating test records in SANDBOX...")
        
        # 1. Create Company (Account)
        company_data = {
            "data": [{
                "Account_Name": "Everpar",
                "Website": "https://everpar.com",
                "Phone": "(918) 555-0100",  # Test phone
                "Account_Source": "Website Inbound",
                "Source_Detail": "Calendly scheduling",
                "Who_Gets_Credit": "BD Rep",
                "Credit_Detail": "Steve Perry",
                "Description": "Test company from Calendly integration"
            }]
        }
        
        print("\n1️⃣ Creating Company Record...")
        company_response = requests.post(
            f"{self.api_base}/Accounts",
            headers=headers,
            json=company_data
        )
        
        if company_response.status_code == 201:
            company_id = company_response.json()['data'][0]['details']['id']
            print(f"✅ Company created: {company_id}")
        else:
            print(f"❌ Failed to create company: {company_response.text}")
            return False
        
        # 2. Create Contact
        contact_data = {
            "data": [{
                "First_Name": "Tim",
                "Last_Name": "Koski",
                "Email": "tim.koski@everpar.com",
                "Phone": "+1 918-237-1276",
                "Account_Name": {"id": company_id},
                "Mailing_City": "Tulsa",
                "Mailing_State": "OK",
                "Lead_Source": "Website Inbound"
            }]
        }
        
        print("\n2️⃣ Creating Contact Record...")
        contact_response = requests.post(
            f"{self.api_base}/Contacts",
            headers=headers,
            json=contact_data
        )
        
        if contact_response.status_code == 201:
            contact_id = contact_response.json()['data'][0]['details']['id']
            print(f"✅ Contact created: {contact_id}")
        else:
            print(f"❌ Failed to create contact: {contact_response.text}")
            return False
        
        # 3. Create Deal
        closing_date = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
        
        deal_data = {
            "data": [{
                "Deal_Name": "Lead Advisor (Tulsa) - Everpar",
                "Account_Name": {"id": company_id},
                "Contact_Name": {"id": contact_id},
                "Stage": "Lead",
                "Pipeline": "Recruitment",
                "Source": "Website Inbound",
                "Source_Detail": "Calendly scheduling",
                "Closing_Date": closing_date,
                "Description": "Plan to hire 2 new lead advisors as soon as possible. "
                             "I have a preliminary offer out to one at this time. "
                             "Then hire a third CSA in 2026. "
                             "Then hire two associate advisors in 2027. "
                             "Then hire another lead advisor, probably in 2028.",
                "Who_Gets_Credit": "BD Rep",
                "Credit_Detail": "Steve Perry"
            }]
        }
        
        print("\n3️⃣ Creating Deal Record...")
        deal_response = requests.post(
            f"{self.api_base}/Deals",
            headers=headers,
            json=deal_data
        )
        
        if deal_response.status_code == 201:
            deal_id = deal_response.json()['data'][0]['details']['id']
            print(f"✅ Deal created: {deal_id}")
        else:
            print(f"❌ Failed to create deal: {deal_response.text}")
            return False
        
        print("\n🎉 All three records created successfully in SANDBOX!")
        print("\n📋 Created Records:")
        print(f"  Company ID: {company_id}")
        print(f"  Contact ID: {contact_id}")
        print(f"  Deal ID: {deal_id}")
        
        return True

def main():
    print("=" * 80)
    print("🧪 Zoho CRM SANDBOX Test - Completely Safe!")
    print("This test creates records ONLY in sandbox, not production")
    print("=" * 80)
    
    # Confirm with user
    print("\n⚠️  IMPORTANT: This test requires:")
    print("1. Zoho Sandbox to be set up")
    print("2. OAuth tokens generated specifically for SANDBOX")
    print("3. The refresh token in .env.local must be for SANDBOX organization")
    
    response = input("\nHave you set up sandbox-specific OAuth tokens? (y/n): ")
    if response.lower() != 'y':
        print("\n❌ Test cancelled. Please set up sandbox OAuth tokens first.")
        print("\nTo generate sandbox tokens:")
        print("1. Use the same OAuth flow but select SANDBOX organization")
        print("2. Update ZOHO_REFRESH_TOKEN in .env.local with sandbox token")
        return
    
    # Run test
    tester = ZohoSandboxTester()
    
    # Get token
    if not tester.get_sandbox_token():
        print("❌ Could not authenticate with sandbox")
        return
    
    # Check for existing records
    if tester.search_existing_records():
        response = input("\n⚠️  Found existing test records. Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Test cancelled.")
            return
    
    # Create test records
    tester.create_test_records()
    
    print("\n✅ Test complete! Check your Zoho SANDBOX to verify:")
    print("1. Login to sandbox.zoho.com")
    print("2. Check Accounts module for 'Everpar'")
    print("3. Check Contacts module for 'Tim Koski'")
    print("4. Check Deals module for 'Lead Advisor (Tulsa) - Everpar'")

if __name__ == "__main__":
    main()