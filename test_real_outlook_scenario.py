#!/usr/bin/env python3
"""Test with a realistic Outlook scenario"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

print("=" * 70)
print("🔍 TESTING REAL OUTLOOK SCENARIO")
print("=" * 70)

api_key = os.getenv("API_KEY", "test-api-key-2024")

# Test with a more realistic email like what would come from Outlook
test_payload = {
    "sender_name": "John Smith",
    "sender_email": "jsmith@financialgroup.com",
    "subject": "Financial Advisor Position Inquiry",
    "body": """Hi there,

I hope this email finds you well. My name is John Smith and I'm a Senior Financial Advisor with over 8 years of experience in wealth management.

I'm currently working at Financial Advisory Group in Dallas, Texas, and I'm interested in exploring new opportunities with your firm.

You can reach me at:
Phone: (214) 555-9876
Email: jsmith@financialgroup.com
Company Website: www.financialgroup.com

I have extensive experience working with high-net-worth clients and have consistently exceeded my sales targets.

Looking forward to hearing from you.

Best regards,
John Smith
Senior Financial Advisor
Financial Advisory Group
Dallas, TX""",
    "attachments": [],
    "dry_run": False  # Use False to see full processing
}

print("📧 Testing with realistic Outlook email...")
print(f"   From: {test_payload['sender_name']} <{test_payload['sender_email']}>")
print(f"   Subject: {test_payload['subject']}")
print("-" * 70)

response = requests.post(
    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email",
    json=test_payload,
    headers={"X-API-Key": api_key, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    extracted = result.get("extracted", {})
    
    print("✅ EXTRACTION RESULTS:")
    print("-" * 60)
    
    # Company Record Analysis
    if extracted.get("company_record"):
        company = extracted["company_record"]
        print("\n📊 COMPANY RECORD:")
        print(f"   Company Name: {company.get('company_name', 'MISSING')}")
        print(f"   📞 Company Phone: {company.get('phone', 'MISSING')}")
        print(f"   🌐 Company Website: {company.get('website', 'MISSING')}")
        print(f"   📍 Company Source: {company.get('company_source', 'MISSING')}")
        
        # Check if phone/website captured
        has_phone = company.get('phone') is not None and company.get('phone') != ""
        has_website = company.get('website') is not None and company.get('website') != ""
        
        print(f"\n   📞 Phone Status: {'✅ CAPTURED' if has_phone else '❌ MISSING'}")
        print(f"   🌐 Website Status: {'✅ CAPTURED' if has_website else '❌ MISSING'}")
    else:
        print("\n❌ NO COMPANY RECORD FOUND")
    
    # Deal Record Analysis
    if extracted.get("deal_record"):
        deal = extracted["deal_record"]
        print("\n💼 DEAL RECORD:")
        print(f"   Deal Name: {deal.get('deal_name', 'MISSING')}")
        print(f"   Pipeline: {deal.get('pipeline', 'MISSING')}")
        print(f"   Source: {deal.get('source', 'MISSING')}")
        
        # Check deal name format
        deal_name = deal.get('deal_name', '')
        expected_pattern = "Senior Financial Advisor (Dallas, TX) - Financial Advisory Group"
        has_proper_format = "(" in deal_name and ")" in deal_name and "-" in deal_name
        
        print(f"\n   📝 Deal Name Format: {'✅ CORRECT' if has_proper_format else '❌ INCORRECT'}")
        if not has_proper_format:
            print(f"      Expected: Job Title (Location) - Company")
            print(f"      Got: {deal_name}")
    else:
        print("\n❌ NO DEAL RECORD FOUND")
    
    # Contact Record
    if extracted.get("contact_record"):
        contact = extracted["contact_record"]
        print("\n👤 CONTACT RECORD:")
        print(f"   Name: {contact.get('first_name', '')} {contact.get('last_name', '')}")
        print(f"   Phone: {contact.get('phone', 'MISSING')}")
        print(f"   Email: {contact.get('email', 'MISSING')}")
        print(f"   Location: {contact.get('city', '')}, {contact.get('state', '')}")
    
    # Debug raw data
    print(f"\n🔍 RAW DEBUG:")
    print(f"   All root fields: {list(extracted.keys())}")
    
    # Check for phone/website in raw data
    raw_phone = extracted.get('phone')
    raw_website = extracted.get('website')
    print(f"   Raw phone: {repr(raw_phone)}")
    print(f"   Raw website: {repr(raw_website)}")
    
else:
    print(f"❌ API call failed: {response.status_code}")
    print(f"Response: {response.text[:500]}...")

print("\n" + "=" * 70)
