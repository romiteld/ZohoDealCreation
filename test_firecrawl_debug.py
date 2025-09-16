#!/usr/bin/env python3
"""Debug Firecrawl integration issues"""
import requests
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv('.env.local')

# Test 1: Check if Firecrawl API key exists
print("="*70)
print("FIRECRAWL INTEGRATION DEBUG")
print("="*70)

firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
print(f"\n1. Firecrawl API Key: {'✅ FOUND' if firecrawl_key else '❌ MISSING'}")
if firecrawl_key:
    print(f"   Key prefix: {firecrawl_key[:8]}...")

# Test 2: Test Firecrawl API directly
print("\n2. Testing Firecrawl API directly...")
if firecrawl_key:
    try:
        # Test Firecrawl v2 Extract endpoint
        headers = {
            "Authorization": f"Bearer {firecrawl_key}",
            "Content-Type": "application/json"
        }
        
        # Simple test extraction
        test_payload = {
            "urls": ["https://www.example.com"],
            "prompt": "Extract the main heading and description"
        }
        
        response = requests.post(
            "https://api.firecrawl.dev/v2/extract",
            json=test_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Firecrawl API is accessible")
        else:
            print(f"   ❌ Firecrawl API error: {response.text[:200]}")
            
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
else:
    print("   ⚠️ Cannot test - no API key")

# Test 3: Check if Firecrawl is enabled in the API
print("\n3. Testing if Firecrawl is integrated in production API...")
api_key = os.getenv("API_KEY", "test-api-key-2024")

# Test with a real company email
test_payload = {
    "sender_name": "John Smith",
    "sender_email": "john@microsoft.com",
    "subject": "Partnership Opportunity",
    "body": """
    Hi,
    
    I'm John Smith, Director of Business Development at Microsoft.
    
    I'd like to discuss partnership opportunities with The Well.
    
    You can reach me at john@microsoft.com or connect on LinkedIn.
    
    Best regards,
    John Smith
    Microsoft Corporation
    """,
    "attachments": [],
    "dry_run": True
}

response = requests.post(
    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email",
    json=test_payload,
    headers={"X-API-Key": api_key, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    extracted = result.get("extracted", {})
    
    print("\n   Checking for Firecrawl enrichment indicators:")
    
    # Check if we got LinkedIn URL (would come from Firecrawl)
    has_linkedin = bool(extracted.get("linkedin_url"))
    print(f"   LinkedIn URL: {'✅ FOUND' if has_linkedin else '❌ NOT FOUND'}")
    if has_linkedin:
        print(f"      URL: {extracted['linkedin_url']}")
    
    # Check if we got company website (from Firecrawl research)
    has_website = bool(extracted.get("website")) and "microsoft.com" in extracted.get("website", "")
    print(f"   Company Website: {'✅ FOUND' if has_website else '❌ NOT FOUND'}")
    if has_website:
        print(f"      URL: {extracted['website']}")
    
    # Check if company name was enriched
    has_full_company = extracted.get("company_name") == "Microsoft Corporation"
    print(f"   Full Company Name: {'✅ FOUND' if has_full_company else '❌ NOT FOUND'}")
    if extracted.get("company_name"):
        print(f"      Name: {extracted['company_name']}")
    
    # Check enrichment metadata
    if extracted.get("firecrawl_confidence"):
        print(f"   Firecrawl Confidence: {extracted['firecrawl_confidence']}")
    
    if extracted.get("extraction_method"):
        print(f"   Extraction Method: {extracted['extraction_method']}")
    
    # Conclusion
    print("\n   🎯 FIRECRAWL INTEGRATION STATUS:")
    if has_linkedin or has_website or has_full_company:
        print("   ✅ Firecrawl appears to be working (found enriched data)")
    else:
        print("   ❌ Firecrawl enrichment NOT detected")
        print("      Possible issues:")
        print("      - Firecrawl API key not configured in production")
        print("      - Firecrawl integration disabled")
        print("      - API timeout preventing Firecrawl calls")
        print("      - Firecrawl v2 changes not deployed")

# Test 4: Check logs for Firecrawl mentions
print("\n4. Checking for Firecrawl in API response...")
if response.status_code == 200:
    response_text = json.dumps(result, indent=2)
    firecrawl_mentions = [
        "firecrawl" in response_text.lower(),
        "fire-1" in response_text.lower(),
        "enrichment" in response_text.lower()
    ]
    
    if any(firecrawl_mentions):
        print("   ✅ Found Firecrawl-related fields in response")
    else:
        print("   ❌ No Firecrawl indicators in response")

print("\n" + "="*70)
print("DEBUG COMPLETE")
print("="*70)

# Summary
print("\n📊 SUMMARY:")
if not firecrawl_key:
    print("❌ CRITICAL: Firecrawl API key not found in local environment")
    print("   Add FIRECRAWL_API_KEY to .env.local")
elif not (has_linkedin or has_website):
    print("⚠️ WARNING: Firecrawl enrichment not working in production")
    print("   Check if FIRECRAWL_API_KEY is set in Azure Container Apps")
else:
    print("✅ Firecrawl integration appears functional")

