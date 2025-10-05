#!/usr/bin/env python3
"""Test Calendly event extraction to understand missing fields"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')
api_key = os.getenv("API_KEY", "test-api-key-2024")

# This is the actual Calendly event content from the browser logs
test_payload = {
    "sender_name": "Steve Perry",
    "sender_email": "steve@thewellrecruiting.com", 
    "subject": "New Event Request: Kevin Sullivan", 
    "body": """
Hi Daniel,

A new Calendly event has been scheduled.

Event Type:
Introductory Meeting - RIA & Wirehouse Clients Only

Invitee:
Kevin Sullivan

Invitee Email:
donna@infinitewealthadvisors.com

Event Date/Time:
Thursday, December 19, 2024
10:00am - 10:30am (America/New_York)

Invitee Time Zone:
America/New_York

Guest Emails (Optional):
scott@emailthewell.com

Location:
This is a Zoom meeting.
The meeting details will be sent in a confirmation email.

Invitee Questions:
Phone Number:
+1 (336) 882-8800

How did you hear about us?:
Scott Leak

Additional Information:
Questions? Contact support@thewellrecruiting.com or call +1 704-905-8002

---
Powered by Calendly.com
""",
    "attachments": [],
    "dry_run": True
}

print("Testing Calendly Event Extraction...")
print("=" * 70)

response = requests.post(
    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email",
    json=test_payload,
    headers={"X-API-Key": api_key, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    extracted = result.get("extracted", {})
    
    print("\nRaw API Response:")
    print(json.dumps(result, indent=2))
    
    print("\n\n🔍 FIELD ANALYSIS:")
    print("-" * 70)
    
    # Check key fields
    fields_to_check = {
        "candidate_name": extracted.get("candidate_name"),
        "job_title": extracted.get("job_title"),
        "email": extracted.get("email"),
        "phone": extracted.get("phone"),
        "linkedin_url": extracted.get("linkedin_url"),
        "company_name": extracted.get("company_name"),
        "referrer_email": extracted.get("referrer_email"),
        "website": extracted.get("website")
    }
    
    print("\nDirect Fields:")
    for field, value in fields_to_check.items():
        status = "✅" if value else "❌"
        print(f"  {status} {field:20s}: {value or 'NOT EXTRACTED'}")
    
    # Check contact record
    if extracted.get("contact_record"):
        contact = extracted["contact_record"]
        print("\nContact Record:")
        print(f"  Email:     {contact.get('email') or 'NOT FOUND'}")
        print(f"  Phone:     {contact.get('phone') or 'NOT FOUND'}")
        print(f"  Company:   {contact.get('company_name') or 'NOT FOUND'}")
        
    # Check company record
    if extracted.get("company_record"):
        company = extracted["company_record"]
        print("\nCompany Record:")
        print(f"  Name:      {company.get('company_name') or 'NOT FOUND'}")
        print(f"  Phone:     {company.get('phone') or 'NOT FOUND'}")
        print(f"  Website:   {company.get('website') or 'NOT FOUND'}")
        
    print("\n\n🎯 KEY FINDINGS:")
    print("-" * 70)
    
    # The email donna@infinitewealthadvisors.com should have been extracted
    if "donna@infinitewealthadvisors.com" in test_payload["body"]:
        print("✅ Email 'donna@infinitewealthadvisors.com' is in the body text")
        if not extracted.get("email") and not (extracted.get("contact_record", {}).get("email")):
            print("❌ BUT it was NOT extracted into any email field!")
            print("   This is the issue - the extraction logic is missing this email")
    
    # LinkedIn is not in Calendly events typically
    print("\n📝 Note: LinkedIn URLs are not typically in Calendly events")
    print("   This is expected behavior, not a bug")
    
else:
    print(f"❌ API request failed: {response.status_code}")
    print(response.text)

