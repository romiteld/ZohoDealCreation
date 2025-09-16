#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

api_key = os.getenv("API_KEY", "test-api-key-2024")

# Test with a clearer example that should trigger Steve's format
test_payload = {
    "sender_name": "John Doe",
    "sender_email": "john.doe@namcoa.com",
    "subject": "Investment Advisor Representative opportunity",
    "body": """
Hello,

My name is John Doe and I am an Investment Advisor Representative 
currently working at NAMCOA in Naples, FL.

I have 10 years of experience in financial services.

Phone: (239) 555-1234
Email: john.doe@namcoa.com

I would like to explore opportunities with The Well.

Best regards,
John Doe
NAMCOA LLC
    """,
    "attachments": [],
    "dry_run": True
}

print("Testing Deal Name Format with clear job/location/company...")
response = requests.post(
    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email",
    json=test_payload,
    headers={"X-API-Key": api_key, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    print("Full response structure:")
    print(json.dumps(result, indent=2))
else:
    print(f"❌ Request failed: {response.status_code}")
    print("Response:", response.text)
