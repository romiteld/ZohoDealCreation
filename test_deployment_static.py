#!/usr/bin/env python3
"""Test if static file serving is working in deployment"""

import requests
import json

BASE_URL = "https://well-intake-api.azurewebsites.net"

def test_endpoints():
    """Test various endpoints to understand what's working"""
    
    endpoints = [
        ("/health", "GET", None),
        ("/manifest.xml", "GET", None),
        ("/commands.js", "GET", None),
        ("/addin/manifest.xml", "GET", None),
        ("/addin/commands.js", "GET", None),
        ("/static/manifest.xml", "GET", None),
        ("/static/commands.js", "GET", None),
        ("/docs", "GET", None),
        ("/openapi.json", "GET", None),
    ]
    
    print("Testing endpoints on production deployment:\n")
    
    for endpoint, method, data in endpoints:
        url = BASE_URL + endpoint
        try:
            if method == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, json=data, timeout=5)
            
            status = "✅" if response.status_code < 400 else "❌"
            print(f"{status} {method} {endpoint}: {response.status_code}")
            
            if response.status_code < 400 and endpoint == "/health":
                print(f"   Health data: {json.dumps(response.json(), indent=2)}")
            elif response.status_code >= 400 and endpoint in ["/manifest.xml", "/commands.js"]:
                print(f"   Error response: {response.text[:100]}")
                
        except Exception as e:
            print(f"❌ {method} {endpoint}: ERROR - {str(e)}")
    
    print("\n" + "="*50)
    print("Summary:")
    print("- Health endpoint is working (API is running)")
    print("- Static files are NOT being served")
    print("- Need to fix static file routing in production")

if __name__ == "__main__":
    test_endpoints()