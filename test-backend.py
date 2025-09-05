#!/usr/bin/env python3
"""Test backend integration with .msg files"""

import requests
import base64
import json

API_URL = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
API_KEY = "dev-key-only-for-testing"  # Replace with actual key

def test_email_processing():
    """Test email processing with sample data"""
    
    # Sample email data matching your examples
    test_payload = {
        "sender_email": "kevin.sullivan@namcoa.com",
        "subject": "Recruiting Consult - Kevin Sullivan",
        "body": """From: Kevin Sullivan <ksullivan@namcoa.com>
Phone: 704-905-8002
Company: NAMCOA - Naples Asset Management Company

I'm interested in discussing advisor opportunities with The Well.
        
Referred by: Scott Leak""",
        "dry_run": True  # Preview only
    }
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    print("Testing email extraction...")
    response = requests.post(
        f"{API_URL}/intake/email",
        headers=headers,
        json=test_payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS! Extracted data:")
        print(json.dumps(data, indent=2))
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False

if __name__ == "__main__":
    success = test_email_processing()
    if success:
        print("\n🎉 Backend integration verified!")
        print("\n📱 Access your UI at:")
        print("https://proud-ocean-087af290f.2.azurestaticapps.net")
    else:
        print("\n⚠️  Backend test failed - check API key")