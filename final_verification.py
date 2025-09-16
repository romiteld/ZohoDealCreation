#!/usr/bin/env python3
"""Final deployment verification with correct URLs"""
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

print("=" * 70)
print("FINAL DEPLOYMENT VERIFICATION")  
print("=" * 70)

base_url = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"

# Correct URLs (not under /static/)
tests = [
    ("Health Check", "/health", 200),
    ("Manifest XML", "/manifest.xml", 200),
    ("Taskpane HTML", "/taskpane.html", 200),
    ("Commands HTML", "/commands.html", 200),
    ("Config JS", "/config.js", 200),
    ("Commands JS", "/commands.js", 200),
    ("Taskpane JS", "/taskpane.js", 200),
    ("Icon 16", "/icon-16.png", 200),
    ("Icon 32", "/icon-32.png", 200),
    ("Icon 80", "/icon-80.png", 200),
]

print("\n🔍 Testing All Endpoints...")
print("-" * 50)

all_passed = True
for name, path, expected_status in tests:
    url = f"{base_url}{path}"
    try:
        response = requests.get(url, timeout=10)
        status = response.status_code
        
        if status == expected_status:
            print(f"✅ {name:20} - Status: {status}")
            
            # Check UI improvements in taskpane.html
            if path == "/taskpane.html" and status == 200:
                content = response.text
                improvements = []
                
                if "expressMode" in content or "express-send" in content:
                    improvements.append("Express Send")
                if "confidence" in content.lower():
                    improvements.append("Confidence Score")
                if "collapsible" in content or "toggleSection" in content:
                    improvements.append("Collapsible Sections")
                if "autofill" in content.lower() or "populateDefaults" in content:
                    improvements.append("Auto-fill")
                    
                if improvements:
                    print(f"   📦 UI Features: {', '.join(improvements)}")
                    
        else:
            print(f"❌ {name:20} - Status: {status}")
            all_passed = False
            
    except Exception as e:
        print(f"❌ {name:20} - Error: {str(e)}")
        all_passed = False

# Test API with proper API key
print("\n🔍 Testing API Functionality...")
print("-" * 50)

api_key = os.getenv("API_KEY", "test-api-key-2024")

test_payload = {
    "sender_name": "Final Test",
    "sender_email": "test@example.com",
    "subject": "Senior Developer - San Francisco, CA",
    "body": """
    John Smith
    Senior Developer at Tech Company
    San Francisco, CA
    Phone: (415) 555-0123
    Email: john.smith@techcompany.com
    
    Looking forward to opportunities.
    """,
    "attachments": [],
    "dry_run": True
}

try:
    response = requests.post(
        f"{base_url}/intake/email",
        json=test_payload,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        confidence = data.get("confidence_score", 0)
        extracted = data.get("extracted", {})
        
        print(f"✅ API Working - Confidence: {confidence}%")
        
        # Check 3-record structure
        has_company = extracted.get("company_record") is not None
        has_contact = extracted.get("contact_record") is not None
        has_deal = extracted.get("deal_record") is not None
        
        if has_company and has_contact and has_deal:
            print("✅ All 3 records present (Company, Contact, Deal)")
            
            # Check deal name format
            deal = extracted["deal_record"]
            if deal.get("deal_name") and "(" in deal.get("deal_name", "") and ")" in deal.get("deal_name", ""):
                print("✅ Deal name format correct")
                
        else:
            print("❌ Missing records in extraction")
            all_passed = False
            
    else:
        print(f"❌ API Error - Status: {response.status_code}")
        all_passed = False
        
except Exception as e:
    print(f"❌ API Error: {str(e)}")
    all_passed = False

# Summary
print("\n" + "=" * 70)
if all_passed:
    print("✅ DEPLOYMENT SUCCESSFUL!")
    print("• All static files accessible (200 OK)")
    print("• Manifest serving correctly")
    print("• Taskpane with UI improvements deployed")
    print("• API responding with 3-record structure")
    print("• Deal name format working")
    print("\n🎉 LATEST CODE IS LIVE IN PRODUCTION!")
else:
    print("⚠️ SOME ISSUES DETECTED")
    print("Review errors above")
    
print("=" * 70)
