#!/bin/bash
# Test Zoho search API

# Get access token
TOKEN=$(curl -s "https://well-zoho-oauth-v2.azurewebsites.net/oauth/token" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Testing Zoho search API with token: ${TOKEN:0:20}..."

# Test search
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://www.zohoapis.com/crm/v8/Candidates/search?criteria=%28Candidate_Type%3Aequals%3AVault%29&per_page=5&page=1" \
  | python3 -m json.tool | head -50
