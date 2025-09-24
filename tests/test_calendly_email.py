#!/usr/bin/env python3
"""
Test script for processing Calendly emails through the Well Intake API.
This demonstrates how to structure and send a Calendly email payload.
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Configuration
API_URL = os.getenv('CONTAINER_URL', 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io')
API_KEY = os.getenv('API_KEY')

def test_calendly_email():
    """Test the /intake/email endpoint with a Calendly email"""
    
    # Calendly email payload
    calendly_payload = {
        "sender_email": "notifications@calendly.com",
        "sender_name": "Calendly",
        "subject": "New Event: Tim Koski - Recruiting Consult",
        "body": """A new event has been scheduled.

Event Type:
Recruiting Consult

Invitee:
Tim Koski
tim.koski@everpar.com

Invitee Phone Number:
+1 918-237-1276

Event Date/Time:
11:00am - 11:30am (America/Chicago) on Wednesday, September 24, 2025

Location:
This is a phone call. The Well will call the invitee at the phone number provided.

Invitee Time Zone:
America/Chicago

Questions:

Please share more about the opportunity you have available:
Looking to hire 2 lead advisors in the Tulsa market ASAP. Planning to add a third CSA in 2026, two associate advisors in 2027, and another lead advisor in 2028.

View event in Calendly: https://calendly.com/scheduled_events/evt_abc123

Need to make changes to this event?
Cancel: https://calendly.com/cancellations/evt_abc123
Reschedule: https://calendly.com/reschedulings/evt_abc123

Powered by Calendly.com""",
        "attachments": [],
        "reply_to": "tim.koski@everpar.com",
        "internet_message_id": "evt_abc123@calendly.com"
    }
    
    # Headers
    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Make request
    print(f"Sending Calendly email to {API_URL}/intake/email")
    print("-" * 80)
    
    try:
        response = requests.post(
            f"{API_URL}/intake/email",
            json=calendly_payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Success!")
            result = response.json()
            print(json.dumps(result, indent=2))
            
            # Expected extracted data:
            # - Contact: Tim Koski (tim.koski@everpar.com, +1 918-237-1276)
            # - Company: Everpar (from email domain)
            # - Location: Tulsa
            # - Deal Name: "Lead Advisor (Tulsa) - Everpar"
            # - Source: "Website Inbound" (because it's from Calendly)
            # - Requirements: Hiring timeline and positions detailed
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_dry_run():
    """Test with dry_run=true to preview extraction without creating records"""
    
    calendly_payload = {
        "sender_email": "notifications@calendly.com",
        "sender_name": "Calendly",
        "subject": "New Event: Tim Koski - Recruiting Consult",
        "body": """A new event has been scheduled.

Event Type:
Recruiting Consult

Invitee:
Tim Koski
tim.koski@everpar.com

Invitee Phone Number:
+1 918-237-1276

Event Date/Time:
11:00am - 11:30am (America/Chicago) on Wednesday, September 24, 2025

Location:
This is a phone call. The Well will call the invitee at the phone number provided.

Questions:

Please share more about the opportunity you have available:
Looking to hire 2 lead advisors in the Tulsa market ASAP. Planning to add a third CSA in 2026, two associate advisors in 2027, and another lead advisor in 2028.""",
        "attachments": [],
        "reply_to": "tim.koski@everpar.com",
        "dry_run": True  # Only extract, don't create records
    }
    
    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    
    print("\nTesting dry run mode...")
    print("-" * 80)
    
    try:
        response = requests.post(
            f"{API_URL}/intake/email",
            json=calendly_payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Dry run success!")
            result = response.json()
            
            # Show extracted data
            if 'extracted' in result:
                extracted = result['extracted']
                print("\nExtracted Data:")
                print("-" * 40)
                
                # Show structured records (new format)
                if 'contact_record' in extracted:
                    print("\nContact Record:")
                    print(json.dumps(extracted['contact_record'], indent=2))
                
                if 'company_record' in extracted:
                    print("\nCompany Record:")
                    print(json.dumps(extracted['company_record'], indent=2))
                
                if 'deal_record' in extracted:
                    print("\nDeal Record:")
                    print(json.dumps(extracted['deal_record'], indent=2))
                
                # Show legacy fields for backward compatibility
                print("\nLegacy Fields:")
                legacy_fields = {k: v for k, v in extracted.items() 
                               if k not in ['contact_record', 'company_record', 'deal_record']}
                print(json.dumps(legacy_fields, indent=2))
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    # Check API key
    if not API_KEY:
        print("❌ Error: API_KEY not found in environment")
        print("Please set API_KEY in .env.local file")
        exit(1)
    
    # Run tests
    print("🧪 Testing Calendly Email Processing")
    print("=" * 80)
    
    # Test dry run first to see what will be extracted
    test_dry_run()
    
    # Uncomment to actually create records
    # print("\n" + "=" * 80)
    # test_calendly_email()