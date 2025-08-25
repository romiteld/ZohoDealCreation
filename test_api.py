#!/usr/bin/env python3
"""
Test script for the Well Intake API
Tests the /intake/email endpoint with a Calendly event email
"""

import requests
import json
from datetime import datetime

# Read the test email content
with open("test.txt", "r") as f:
    email_body = f.read()

# Prepare the test payload
payload = {
    "sender_email": "calendly@nicholaswealth.com",
    "sender_name": "Nicholas Wealth Calendly",
    "subject": "New Recruiting Consult with David Nicholas",
    "body": email_body,
    "received_date": datetime.now().isoformat() + "Z",
    "message_id": "test-msg-" + datetime.now().strftime("%Y%m%d%H%M%S"),
    "attachments": []
    # Note: API key goes in header, not body
}

# API endpoint
url = "http://127.0.0.1:8000/intake/email"

# API key from .env.local
api_key = "your-secure-api-key-here"

print("Sending test email to API...")
print(f"Sender: {payload['sender_email']}")
print(f"Subject: {payload['subject']}")
print(f"API Key: {api_key[:10]}...")
print("-" * 50)

try:
    # Send POST request with API key in header
    response = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
    )
    
    # Print response
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print("-" * 50)
    
    if response.status_code == 200:
        data = response.json()
        print("Success! Response data:")
        print(json.dumps(data, indent=2))
        
        # Extract important IDs for cleanup
        if "zoho_response" in data and data["zoho_response"]:
            zoho_data = data["zoho_response"]
            print("\n" + "=" * 50)
            print("IMPORTANT - Save these IDs for cleanup:")
            print(f"Account ID: {zoho_data.get('account_id')}")
            print(f"Contact ID: {zoho_data.get('contact_id')}")
            print(f"Deal ID: {zoho_data.get('deal_id')}")
            print("=" * 50)
    else:
        print("Error Response:")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print(response.text)
            
except requests.exceptions.ConnectionError:
    print("ERROR: Could not connect to API. Is the server running on port 8000?")
except Exception as e:
    print(f"ERROR: {str(e)}")