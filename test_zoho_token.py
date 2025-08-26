#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

print(f"Client ID: {CLIENT_ID[:20]}...")
print(f"Client Secret: {CLIENT_SECRET[:10]}...")
print(f"Refresh Token: {REFRESH_TOKEN[:30]}...")

# Try to get access token
token_url = "https://accounts.zoho.com/oauth/v2/token"
payload = {
    "refresh_token": REFRESH_TOKEN,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "grant_type": "refresh_token"
}

print("\nRequesting access token...")
response = requests.post(token_url, data=payload)
print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success! Access Token: {data.get('access_token', '')[:50]}...")
    print(f"Expires in: {data.get('expires_in')} seconds")
    print(f"API Domain: {data.get('api_domain')}")
else:
    print(f"❌ Failed: {response.text}")