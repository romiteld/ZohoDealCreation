#!/usr/bin/env python3
"""
Test script for OAuth Service Reverse Proxy
Tests all proxy endpoints and OAuth functionality
"""
import requests
import json
import time
from datetime import datetime

# Configuration
OAUTH_SERVICE_URL = "https://well-zoho-oauth.azurewebsites.net"  # Production
# OAUTH_SERVICE_URL = "http://localhost:8000"  # Local testing
API_KEY = "your-api-key"  # Replace with actual API key

def test_health_check():
    """Test the health check endpoint"""
    print("\n" + "="*50)
    print("Testing Health Check Endpoint")
    print("="*50)
    
    try:
        response = requests.get(f"{OAUTH_SERVICE_URL}/health")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Service Status: {data.get('status')}")
            print(f"OAuth Configured: {data.get('oauth_configured')}")
            print(f"Proxy Configured: {data.get('proxy_configured')}")
            print(f"Proxy Status: {data.get('proxy_status')}")
            print(f"Proxy Target: {data.get('proxy_target')}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_oauth_token():
    """Test OAuth token refresh"""
    print("\n" + "="*50)
    print("Testing OAuth Token Refresh")
    print("="*50)
    
    try:
        response = requests.get(f"{OAUTH_SERVICE_URL}/oauth/token")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Access Token: {data.get('access_token')[:20]}...")
            print(f"Expires At: {data.get('expires_at')}")
            print(f"Cached: {data.get('cached')}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_proxy_health():
    """Test proxy health check"""
    print("\n" + "="*50)
    print("Testing Proxy Health Check")
    print("="*50)
    
    try:
        response = requests.get(f"{OAUTH_SERVICE_URL}/proxy/health")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Proxy Status: {data.get('proxy_status')}")
            print(f"Backend Status: {data.get('backend_status')}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_kevin_sullivan():
    """Test Kevin Sullivan endpoint through proxy"""
    print("\n" + "="*50)
    print("Testing Kevin Sullivan Endpoint (via Proxy)")
    print("="*50)
    
    try:
        headers = {"X-API-Key": API_KEY}
        response = requests.get(
            f"{OAUTH_SERVICE_URL}/api/test/kevin-sullivan",
            headers=headers
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Extracted Data:")
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_email_intake():
    """Test email intake endpoint through proxy"""
    print("\n" + "="*50)
    print("Testing Email Intake Endpoint (via Proxy)")
    print("="*50)
    
    sample_email = {
        "subject": "Test Email via Proxy",
        "body": "This is a test email sent through the OAuth proxy service.",
        "from": {
            "emailAddress": {
                "address": "test@example.com"
            }
        },
        "toRecipients": [{
            "emailAddress": {
                "address": "recruit@thewell.com"
            }
        }]
    }
    
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        response = requests.post(
            f"{OAUTH_SERVICE_URL}/api/intake/email",
            headers=headers,
            json=sample_email
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_manifest():
    """Test manifest.xml proxy"""
    print("\n" + "="*50)
    print("Testing Manifest.xml Proxy")
    print("="*50)
    
    try:
        response = requests.get(f"{OAUTH_SERVICE_URL}/manifest.xml")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"Content Type: {response.headers.get('content-type')}")
            print(f"Content Length: {len(response.content)} bytes")
            print("First 200 chars:")
            print(response.text[:200])
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "#"*50)
    print("# OAuth Service Reverse Proxy Test Suite")
    print("#"*50)
    print(f"Target: {OAUTH_SERVICE_URL}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    
    tests = [
        ("Health Check", test_health_check),
        ("OAuth Token", test_oauth_token),
        ("Proxy Health", test_proxy_health),
        ("Kevin Sullivan Test", test_kevin_sullivan),
        ("Email Intake", test_email_intake),
        ("Manifest XML", test_manifest)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Test failed with exception: {str(e)}")
            results.append((test_name, False))
        
        # Small delay between tests
        time.sleep(1)
    
    # Summary
    print("\n" + "#"*50)
    print("# Test Results Summary")
    print("#"*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)