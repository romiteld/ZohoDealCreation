#!/usr/bin/env python3
"""Test the deployed API with sample emails"""

import requests
import json

API_URL = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{API_URL}/health")
    if response.status_code == 200:
        print("✅ Health check passed")
        return True
    else:
        print("❌ Health check failed")
        return False

def test_manifest():
    """Test manifest.xml endpoint"""
    response = requests.get(f"{API_URL}/manifest.xml")
    if response.status_code == 200 and "OfficeApp" in response.text:
        print("✅ Manifest endpoint working")
        return True
    else:
        print("❌ Manifest endpoint failed")
        return False

def test_kevin_sullivan():
    """Test the Kevin Sullivan endpoint"""
    response = requests.get(f"{API_URL}/test/kevin-sullivan")
    if response.status_code == 200:
        data = response.json()
        print("✅ Kevin Sullivan test endpoint working")
        
        # Check for key improvements
        if data.get("extracted"):
            extracted = data["extracted"]
            
            # Check deal name format (should be "Position Location - Company")
            deal_name = extracted.get("deal_name", "")
            if deal_name and "(" not in deal_name and "-" in deal_name:
                print("  ✅ Deal name format correct (no parentheses)")
            else:
                print(f"  ⚠️  Deal name format: {deal_name}")
            
            # Check if phone/email extracted
            if extracted.get("phone"):
                print(f"  ✅ Phone extracted: {extracted['phone']}")
            if extracted.get("email"):
                print(f"  ✅ Email extracted: {extracted['email']}")
                
        return True
    else:
        print(f"❌ Kevin Sullivan test failed: {response.status_code}")
        return False

def main():
    print("Testing deployed API at:", API_URL)
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    if test_health():
        tests_passed += 1
    
    if test_manifest():
        tests_passed += 1
    
    if test_kevin_sullivan():
        tests_passed += 1
    
    print("=" * 60)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! Deployment successful.")
    else:
        print("⚠️  Some tests failed. Check the logs above.")

if __name__ == "__main__":
    main()
