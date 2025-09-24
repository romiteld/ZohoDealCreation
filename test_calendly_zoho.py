#!/usr/bin/env python3
"""
Test script to process Calendly email and verify Zoho CRM record creation
Tests all three record types: Company, Contact, and Deal
"""

import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# API Configuration
API_BASE_URL = "http://localhost:8000"  # Change to production URL if needed
API_KEY = os.getenv('API_KEY', 'dev-key-only-for-testing')

# Calendly email content
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

Attendees can join this meeting from a computer, tablet or smartphone.
https://us02web.zoom.us/j/84757092166

One tap mobile:
+1 309 205 3325,,84757092166#
+1 312 626 6799,,84757092166#

They can also dial in using a phone.
US: +1 309 205 3325, +1 312 626 6799, +1 646 558 8656, +1 646 931 3860, +1 301 715 8592, +1 305 224 1968, +1 253 215 8782, +1 346 248 7799, +1 360 209 5623, +1 386 347 5053, +1 507 473 4847, +1 564 217 2000, +1 669 444 9171, +1 669 900 9128, +16892781000, +1 719 359 4580, +1 253 205 0468
Meeting ID: 847-570-92166

Invitee Time Zone:
Central Time - US & Canada

Questions:

Phone

+1 918-237-1276

What recruiting goals or ideas would you like to discuss?

Plan to hire 2 new lead advisors as soon as possible. I have a preliminary offer out to one at this time. Not sure if it will be accepted. Then hire a third CSA in 2026 . Then hire two associate advisors in 2027. Then Hire another lead advisor, probably in 2028. We are in Tulsa, prefer to hire locally (within 2-hour drive) but open to discussing other markets.

Your confirmation email might land in spam/junk.

Got it- I'll check my spam/junk

View event in Calendly"""

def test_calendly_processing():
    """Test processing of Calendly email through the API"""
    
    print("=" * 80)
    print("Testing Calendly Email Processing for Zoho CRM")
    print("=" * 80)
    print()
    
    # Create the payload
    payload = {
        "sender_email": "notifications@calendly.com",
        "sender_name": "Calendly",
        "reply_to": "tim.koski@everpar.com",  # Important: Reply-to takes precedence
        "subject": "New Event: Tim Koski - 12:45pm Wed, Sep 24, 2025 - Recruiting Consult",
        "body": CALENDLY_EMAIL,
        "attachments": [],
        "internet_message_id": f"cal_{datetime.now().strftime('%Y%m%d%H%M%S')}@calendly.com",
        "dry_run": False  # Set to True to preview without creating records
    }
    
    print("📧 Email Details:")
    print(f"  From: {payload['sender_name']} <{payload['sender_email']}>")
    print(f"  Reply-To: {payload['reply_to']}")
    print(f"  Subject: {payload['subject']}")
    print()
    
    # Expected extraction results
    print("🎯 Expected Extraction Results:")
    print("\nCompany Record:")
    print("  - Company Name: Everpar (from tim.koski@everpar.com)")
    print("  - Phone: (Will be enriched by Firecrawl/Apollo)")
    print("  - Website: https://everpar.com (will be enriched)")
    print("  - Detail: Steve Perry (who gets credit)")
    print("  - Source: Website Inbound (Calendly)")
    print()
    print("Contact Record:")
    print("  - First Name: Tim")
    print("  - Last Name: Koski")
    print("  - Email: tim.koski@everpar.com")
    print("  - Phone: +1 918-237-1276")
    print("  - City: Tulsa")
    print("  - State: OK (or empty if not inferred)")
    print()
    print("Deal Record:")
    print("  - Deal Name: Lead Advisor (Tulsa) - Everpar")
    print("  - Source: Website Inbound")
    print("  - Source Detail: Calendly scheduling")
    print("  - Closing Date: (60 days from today)")
    print("  - Description of Requirements: Plan to hire 2 new lead advisors...")
    print("  - Pipeline: Recruitment")
    print()
    
    # Make the API call
    print("🚀 Sending to API...")
    print(f"  URL: {API_BASE_URL}/intake/email")
    print(f"  API Key: {'***' + API_KEY[-4:] if len(API_KEY) > 4 else '***'}")
    print()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/intake/email",
            json=payload,
            headers={
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            },
            timeout=60  # Longer timeout for LangGraph processing
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS! Email processed successfully")
            print()
            print("📋 Created Records:")
            print(json.dumps(result, indent=2))
            
            # Extract and display the IDs
            if 'company_id' in result:
                print(f"\n🏢 Company ID: {result['company_id']}")
            if 'contact_id' in result:
                print(f"👤 Contact ID: {result['contact_id']}")
            if 'deal_id' in result:
                print(f"💼 Deal ID: {result['deal_id']}")
            
            # Display extraction details if available
            if 'extraction' in result:
                print("\n🔍 Extraction Details:")
                extraction = result['extraction']
                if 'company_record' in extraction:
                    print("  Company:", json.dumps(extraction['company_record'], indent=4))
                if 'contact_record' in extraction:
                    print("  Contact:", json.dumps(extraction['contact_record'], indent=4))
                if 'deal_record' in extraction:
                    print("  Deal:", json.dumps(extraction['deal_record'], indent=4))
            
            print("\n✅ All three records (Company, Contact, Deal) should now be created in Zoho CRM!")
            
        else:
            print(f"❌ ERROR: API returned status code {response.status_code}")
            print("Response:", response.text)
            
    except requests.exceptions.Timeout:
        print("❌ ERROR: Request timed out. The server might be processing slowly.")
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to the API. Make sure the server is running.")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 80)

def verify_in_zoho(company_name="Everpar", contact_email="tim.koski@everpar.com"):
    """
    Verify the records were created in Zoho CRM
    Note: This requires direct Zoho API access
    """
    print("\n🔍 To verify in Zoho CRM:")
    print("1. Log into Zoho CRM")
    print("2. Check Accounts module for:", company_name)
    print("3. Check Contacts module for:", contact_email)
    print("4. Check Deals module for: Lead Advisor (Tulsa) - Everpar")
    print("\nOr use Zoho API to verify programmatically.")

if __name__ == "__main__":
    # Test with dry_run first to preview
    print("💡 TIP: Set dry_run=True in the script to preview without creating records\n")
    
    # Run the test
    test_calendly_processing()
    
    # Show verification steps
    verify_in_zoho()