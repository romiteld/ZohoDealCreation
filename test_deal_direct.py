import requests
import json

# Zoho configuration
api_domain = "https://www.zohoapis.com"
access_token = "get_from_refresh"  # We'll need to refresh this

# Test deal data
deal_data = {
    "data": [{
        "Deal_Name": "TEST: Portfolio Manager - Kirsner Wealth",
        "Stage": "Qualification",
        "Pipeline": "Sales Pipeline",
        "Source": "Website Inbound",
        "Source_Detail": "Calendly scheduling",
        "Owner": "5835637000000153001"  # Steve's owner ID
    }]
}

# First, refresh the token
refresh_url = "https://well-zoho-oauth.azurewebsites.net/refresh"
refresh_response = requests.get(refresh_url)
if refresh_response.status_code == 200:
    access_token = refresh_response.json()["access_token"]
    print(f"Got access token: {access_token[:20]}...")
else:
    print("Failed to refresh token")
    exit(1)

# Try to create the deal
headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}",
    "Content-Type": "application/json"
}

create_url = f"{api_domain}/crm/v8/Deals"
response = requests.post(create_url, json=deal_data, headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
