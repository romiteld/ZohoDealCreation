#!/usr/bin/env python3
"""
Test to verify phone and website extraction is working
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

print("=" * 70)
print("🔍 TESTING PHONE & WEBSITE EXTRACTION")
print("=" * 70)

api_key = os.getenv("API_KEY", "test-api-key-2024")

# Test with clear phone and website mentions
test_payload = {
    "sender_name": "Kevin Sullivan",
    "sender_email": "ksullivan@wealthconsultinggroup.com",
    "subject": "Experienced Financial Advisor - Boston Market",
    "body": """
Hi,

I'm Kevin Sullivan, a Senior Financial Advisor with Wealth Consulting Group.

With over 10 years of experience in wealth management and financial planning,
I've helped numerous high-net-worth clients achieve their financial goals.

Currently based in Boston, MA, I'm interested in exploring opportunities
with The Well.

You can reach me at:
Phone: (617) 555-1234
Email: ksullivan@wealthconsultinggroup.com
Website: www.wealthconsultinggroup.com
Company website: https://www.wealthconsultinggroup.com

Looking forward to discussing how my expertise can contribute to your team.

Best regards,
Kevin Sullivan
Wealth Consulting Group
    """,
    "attachments": [],
    "dry_run": True
}

print(f"📧 Testing with Kevin Sullivan email that explicitly mentions:")
print(f"   📞 Phone: (617) 555-1234")
print(f"   🌐 Website: www.wealthconsultinggroup.com")
print(f"   🌐 Company website: https://www.wealthconsultinggroup.com")
print("-" * 70)

response = requests.post(
    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email",
    json=test_payload,
    headers={"X-API-Key": api_key, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    extracted = result.get("extracted", {})
    
    print("\n✅ EXTRACTION RESULTS:")
    print("-" * 60)
    
    # Check Company Record
    if extracted.get("company_record"):
        company = extracted["company_record"]
        print("\n📊 COMPANY RECORD:")
        print(f"   Company Name: {company.get('company_name', 'MISSING')}")
        print(f"   📞 Company Phone: {company.get('phone', 'MISSING')}")
        print(f"   🌐 Company Website: {company.get('website', 'MISSING')}")
        print(f"   📍 Company Source: {company.get('company_source', 'MISSING')}")
        
        # Check if phone/website are captured
        has_phone = company.get('phone') is not None and company.get('phone') != ""
        has_website = company.get('website') is not None and company.get('website') != ""
        
        print(f"\n   📞 Phone Captured: {'✅ YES' if has_phone else '❌ NO'}")
        print(f"   🌐 Website Captured: {'✅ YES' if has_website else '❌ NO'}")
        
        if has_phone:
            print(f"      Phone Value: '{company.get('phone')}'")
        if has_website:
            print(f"      Website Value: '{company.get('website')}'")
    else:
        print("\n❌ NO COMPANY RECORD FOUND")
    
    # Check Contact Record
    if extracted.get("contact_record"):
        contact = extracted["contact_record"]
        print("\n👤 CONTACT RECORD:")
        print(f"   Contact Name: {contact.get('first_name', '')} {contact.get('last_name', '')}")
        print(f"   📞 Contact Phone: {contact.get('phone', 'MISSING')}")
        print(f"   📧 Contact Email: {contact.get('email', 'MISSING')}")
        
        contact_has_phone = contact.get('phone') is not None and contact.get('phone') != ""
        print(f"\n   📞 Contact Phone Captured: {'✅ YES' if contact_has_phone else '❌ NO'}")
        if contact_has_phone:
            print(f"      Contact Phone Value: '{contact.get('phone')}'")
    
    # Check for raw extraction data
    print(f"\n🔍 RAW EXTRACTION DEBUG:")
    print(f"   Full result keys: {list(result.keys())}")
    if 'extracted' in result:
        print(f"   Extracted keys: {list(result['extracted'].keys())}")
    
    # Look for phone/website in any part of the response
    full_response_str = json.dumps(result, indent=2)
    has_any_phone = "(617) 555-1234" in full_response_str or "617-555-1234" in full_response_str
    has_any_website = "wealthconsultinggroup.com" in full_response_str
    
    print(f"\n🔎 FULL RESPONSE SEARCH:")
    print(f"   Phone appears anywhere: {'✅ YES' if has_any_phone else '❌ NO'}")
    print(f"   Website appears anywhere: {'✅ YES' if has_any_website else '❌ NO'}")
    
else:
    print(f"❌ API call failed: {response.status_code}")
    print(f"Response: {response.text}")

print("\n" + "=" * 70)
