#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

api_key = os.getenv("API_KEY", "test-api-key-2024")

test_payload = {
    "sender_name": "Test Deal Format",
    "sender_email": "test@example.com",
    "subject": "Investment Advisor - Naples, FL",
    "body": "Hi, I am John Doe from NAMCOA LLC. Phone: (555) 123-4567",
    "attachments": [],
    "dry_run": True
}

print("Testing Deal Name Format Fix...")
response = requests.post(
    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email",
    json=test_payload,
    headers={"X-API-Key": api_key, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    extracted = result.get("extracted", {})
    
    if extracted.get("deal_record"):
        deal_name = extracted["deal_record"]["deal_name"]
        print(f"Deal Name: '{deal_name}'")
        
        # Check if dash is present between location and company
        if " - " in deal_name:
            print("✅ DASH IS PRESENT - Steve's format is CORRECT!")
        else:
            print("❌ DASH IS MISSING - Format needs fixing")
    else:
        print("❌ No deal record found")
        print("Full response:", json.dumps(result, indent=2))
else:
    print(f"❌ Request failed: {response.status_code}")
    print("Response:", response.text)
