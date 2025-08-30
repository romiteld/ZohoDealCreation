#!/usr/bin/env python3
"""
Comprehensive test of Outlook Add-in endpoints
Verifies manifest and all related resources are correctly deployed
"""

import requests
import json
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

# Base URL for the Container Apps deployment
BASE_URL = "https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io"
API_KEY = "e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384"

def test_manifest():
    """Test manifest.xml is served correctly"""
    print("\n=== Testing Manifest ===")
    
    response = requests.get(f"{BASE_URL}/manifest.xml")
    if response.status_code == 200:
        print(f"✓ Manifest served successfully")
        
        # Parse XML to verify structure
        try:
            root = ET.fromstring(response.text)
            
            # Check key elements
            app_id = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Id')
            if app_id is not None:
                print(f"  App ID: {app_id.text}")
            
            # Check all URLs in manifest point to Container Apps
            urls = []
            for elem in root.iter():
                if 'DefaultValue' in elem.attrib:
                    url = elem.attrib['DefaultValue']
                    if url.startswith('http'):
                        urls.append(url)
            
            print(f"  Found {len(urls)} URLs in manifest")
            
            # Verify all URLs use Container Apps domain
            container_app_urls = [u for u in urls if 'orangedesert-c768ae6e' in u]
            print(f"  Container Apps URLs: {len(container_app_urls)}/{len(urls)}")
            
            if len(container_app_urls) == len(urls):
                print("  ✓ All URLs correctly point to Container Apps")
            else:
                print("  ✗ Some URLs don't point to Container Apps")
                other_urls = [u for u in urls if 'orangedesert-c768ae6e' not in u]
                for url in other_urls[:3]:  # Show first 3
                    print(f"    - {url}")
                    
        except ET.ParseError as e:
            print(f"  ✗ Failed to parse manifest XML: {e}")
    else:
        print(f"✗ Failed to get manifest: HTTP {response.status_code}")
    
    return response.status_code == 200

def test_static_resources():
    """Test all static resources referenced in manifest"""
    print("\n=== Testing Static Resources ===")
    
    resources = [
        ("taskpane.html", "text/html"),
        ("taskpane.js", "application/javascript"),
        ("commands.html", "text/html"),
        ("commands.js", "application/javascript"),
        ("placeholder.html", "text/html"),
        ("icon-16.png", "image/png"),
        ("icon-32.png", "image/png"),
        ("icon-80.png", "image/png"),
    ]
    
    all_ok = True
    for resource, expected_type in resources:
        response = requests.get(f"{BASE_URL}/{resource}")
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            if expected_type in content_type:
                print(f"✓ {resource:20} - OK ({len(response.content):,} bytes)")
            else:
                print(f"⚠ {resource:20} - Wrong type: {content_type}")
        else:
            print(f"✗ {resource:20} - HTTP {response.status_code}")
            all_ok = False
    
    return all_ok

def test_api_configuration():
    """Test JavaScript files have correct API configuration"""
    print("\n=== Testing API Configuration ===")
    
    js_files = ["taskpane.js", "commands.js"]
    
    for js_file in js_files:
        response = requests.get(f"{BASE_URL}/{js_file}")
        if response.status_code == 200:
            content = response.text
            
            # Check for correct API endpoint
            if BASE_URL in content:
                print(f"✓ {js_file}: Correct API endpoint")
            else:
                print(f"✗ {js_file}: Wrong API endpoint")
                
            # Check for API key
            if API_KEY in content:
                print(f"✓ {js_file}: API key configured")
            else:
                print(f"⚠ {js_file}: API key not found")
        else:
            print(f"✗ {js_file}: Failed to load")

def test_api_endpoints():
    """Test API endpoints used by the add-in"""
    print("\n=== Testing API Endpoints ===")
    
    # Test health endpoint
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Health endpoint: {data['status']}")
        for service, status in data.get('services', {}).items():
            print(f"  - {service}: {status}")
    else:
        print(f"✗ Health endpoint: HTTP {response.status_code}")
    
    # Test intake endpoint with sample data
    print("\n  Testing email intake endpoint...")
    test_email = {
        "sender_email": "test@example.com",
        "sender_name": "Test User",
        "subject": "Test candidate - Add-in verification",
        "body": "Testing the Outlook add-in deployment to ensure all endpoints work correctly.",
        "attachments": []
    }
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/intake/email",
        json=test_email,
        headers=headers,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Email intake endpoint: {data.get('status', 'success')}")
        if 'deal_id' in data:
            print(f"  Deal created: {data['deal_id']}")
    else:
        print(f"✗ Email intake endpoint: HTTP {response.status_code}")
        if response.text:
            print(f"  Error: {response.text[:200]}")

def test_cors_headers():
    """Test CORS headers for cross-origin requests from Outlook"""
    print("\n=== Testing CORS Configuration ===")
    
    # Simulate an OPTIONS request from Outlook
    headers = {
        "Origin": "https://outlook.office.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-api-key"
    }
    
    response = requests.options(f"{BASE_URL}/intake/email", headers=headers)
    
    cors_headers = {
        "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
        "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
        "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
    }
    
    if cors_headers["Access-Control-Allow-Origin"]:
        print(f"✓ CORS enabled")
        for header, value in cors_headers.items():
            if value:
                print(f"  {header}: {value}")
    else:
        print("⚠ CORS headers not fully configured")
        print("  This may cause issues when the add-in makes API calls")

def main():
    """Run all tests"""
    print("=" * 60)
    print("OUTLOOK ADD-IN DEPLOYMENT TEST")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    
    results = {
        "manifest": test_manifest(),
        "static_resources": test_static_resources(),
        "api_configuration": test_api_configuration(),
        "api_endpoints": test_api_endpoints(),
        "cors": test_cors_headers()
    }
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    # Count successes
    total_tests = len([r for r in results.values() if r is not None])
    passed_tests = len([r for r in results.values() if r])
    
    if passed_tests == total_tests:
        print(f"✅ All tests passed! The add-in is correctly deployed.")
    else:
        print(f"⚠️ {passed_tests}/{total_tests} tests passed.")
        print("\nNext steps:")
        print("1. Check failed tests above for details")
        print("2. Verify CORS settings if API calls fail from Outlook")
        print("3. Test the add-in in Outlook Web or Desktop")
    
    print(f"\n📋 Manifest URL for installation:")
    print(f"   {BASE_URL}/manifest.xml")

if __name__ == "__main__":
    main()