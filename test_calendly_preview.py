#!/usr/bin/env python3
"""
SAFE TEST: Preview Calendly email processing WITHOUT creating Zoho records
This script shows what WOULD be created without actually creating anything
"""

import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# API Configuration
API_BASE_URL = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
API_KEY = os.getenv('API_KEY', 'your-api-key')

# Calendly email content from your message
CALENDLY_EMAIL = """Hi Steve Perry,

A new event has been scheduled.

Event Type:
Recruiting Consult

Invitee:
Tim Koski

Invitee Email:
tim.koski@everpar.com

Text Reminder Number:
+1 918-237-1276

Event Date/Time:
12:45pm - Wednesday, September 24, 2025 (Central Time - US & Canada)

Description:

Who We Are: The Well Recruiting Solutions—your partner in finding and hiring top-tier talent.

What We'll Do: Discuss your specific recruiting goals, share proven strategies, and map out a plan to build your ideal team.

Our Approach: A refreshing, personalized experience focused on understanding your unique needs and setting you up for long-term hiring success.

Next Steps: Book a time that works for you, and we'll tackle your recruiting challenges together.

Location:
This is a Zoom web conference.

Questions:

Phone

+1 918-237-1276

What recruiting goals or ideas would you like to discuss?

Plan to hire 2 new lead advisors as soon as possible. I have a preliminary offer out to one at this time. Not sure if it will be accepted. Then hire a third CSA in 2026 . Then hire two associate advisors in 2027. Then Hire another lead advisor, probably in 2028. We are in Tulsa, prefer to hire locally (within 2-hour drive) but open to discussing other markets."""

def preview_calendly_extraction():
    """Preview extraction WITHOUT creating Zoho records"""
    
    print("=" * 80)
    print("🔍 PREVIEW MODE - No Zoho Records Will Be Created")
    print("=" * 80)
    print()
    
    # Create the payload with dry_run=True
    payload = {
        "sender_email": "notifications@calendly.com",
        "sender_name": "Calendly",
        "reply_to": "tim.koski@everpar.com",
        "subject": "New Event: Tim Koski - 12:45pm Wed, Sep 24, 2025 - Recruiting Consult",
        "body": CALENDLY_EMAIL,
        "attachments": [],
        "dry_run": True  # THIS PREVENTS ZOHO RECORD CREATION
    }
    
    print("📧 Processing Email (DRY RUN):")
    print(f"  From: {payload['sender_name']} <{payload['sender_email']}>")
    print(f"  Reply-To: {payload['reply_to']}")
    print(f"  Subject: {payload['subject']}")
    print(f"  Dry Run: {payload['dry_run']} ✅ (No Zoho records will be created)")
    print()
    
    # Make the API call
    print("🚀 Calling extraction API...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/intake/email",
            json=payload,
            headers={
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Extraction successful! Here's what WOULD be created:\n")
            
            # Pretty print the extraction results
            if 'extraction' in result:
                extraction = result['extraction']
                
                print("🏢 COMPANY RECORD (Account):")
                if 'company_record' in extraction and extraction['company_record']:
                    company = extraction['company_record']
                    print(f"  - Company Name: {company.get('company_name', 'N/A')}")
                    print(f"  - Phone: {company.get('phone', 'N/A')}")
                    print(f"  - Website: {company.get('website', 'N/A')}")
                    print(f"  - Detail (owner): {company.get('detail', 'N/A')}")
                    print(f"  - Source: {company.get('source', 'N/A')}")
                    print(f"  - Source Detail: {company.get('source_detail', 'N/A')}")
                else:
                    print("  No company record extracted")
                
                print("\n👤 CONTACT RECORD:")
                if 'contact_record' in extraction and extraction['contact_record']:
                    contact = extraction['contact_record']
                    print(f"  - First Name: {contact.get('first_name', 'N/A')}")
                    print(f"  - Last Name: {contact.get('last_name', 'N/A')}")
                    print(f"  - Email: {contact.get('email', 'N/A')}")
                    print(f"  - Phone: {contact.get('phone', 'N/A')}")
                    print(f"  - City: {contact.get('city', 'N/A')}")
                    print(f"  - State: {contact.get('state', 'N/A')}")
                else:
                    print("  No contact record extracted")
                
                print("\n💼 DEAL RECORD:")
                if 'deal_record' in extraction and extraction['deal_record']:
                    deal = extraction['deal_record']
                    print(f"  - Deal Name: {deal.get('deal_name', 'N/A')}")
                    print(f"  - Source: {deal.get('source', 'N/A')}")
                    print(f"  - Source Detail: {deal.get('source_detail', 'N/A')}")
                    print(f"  - Pipeline: {deal.get('pipeline', 'N/A')}")
                    print(f"  - Closing Date: {deal.get('closing_date', 'N/A')}")
                    print(f"  - Description of Requirements: {deal.get('description_of_reqs', 'N/A')[:100]}...")
                else:
                    print("  No deal record extracted")
            
            print("\n" + "-" * 80)
            print("📄 Full extraction response:")
            print(json.dumps(result, indent=2))
            
            print("\n✅ This is what would be created in Zoho CRM (but nothing was actually created)")
            
        else:
            print(f"\n❌ ERROR: API returned status code {response.status_code}")
            print("Response:", response.text)
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 80)

def test_kevin_sullivan():
    """Test the Kevin Sullivan endpoint as an alternative"""
    print("\n📝 Alternative: Testing Kevin Sullivan endpoint...")
    print("This endpoint also previews extraction without creating records\n")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/test/kevin-sullivan",
            headers={'X-API-Key': API_KEY},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Kevin Sullivan test successful")
            result = response.json()
            print(json.dumps(result, indent=2)[:500] + "...")
        else:
            print(f"❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🛡️  SAFE TEST MODE - No production Zoho records will be created\n")
    
    # Run the preview
    preview_calendly_extraction()
    
    # Optionally test Kevin Sullivan endpoint
    # print("\n" + "="*80)
    # test_kevin_sullivan()