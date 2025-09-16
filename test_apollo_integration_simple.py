#!/usr/bin/env python3
"""
Simple test for Apollo enrichment integration in main.py
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def test_apollo_import():
    """Test that Apollo enrichment can be imported"""
    try:
        from app.apollo_enricher import enrich_contact_with_apollo
        print("✅ Apollo enricher import successful")
        return True
    except Exception as e:
        print(f"❌ Apollo enricher import failed: {e}")
        return False

def test_main_import():
    """Test that main.py has the Apollo import"""
    try:
        # Read the main.py file to check for the import
        with open('/home/romiteld/outlook/app/main.py', 'r') as f:
            content = f.read()

        if 'from app.apollo_enricher import enrich_contact_with_apollo' in content:
            print("✅ Apollo import found in main.py")
            return True
        else:
            print("❌ Apollo import not found in main.py")
            return False
    except Exception as e:
        print(f"❌ Error checking main.py: {e}")
        return False

def test_apollo_integration_points():
    """Test that Apollo integration points exist in main.py"""
    try:
        with open('/home/romiteld/outlook/app/main.py', 'r') as f:
            content = f.read()

        integration_checks = [
            ('Apollo enrichment after success', 'apollo_data = await enrich_contact_with_apollo(request.sender_email)'),
            ('Apollo field mapping', "apollo_mapped['candidate_name'] = apollo_data['client_name']"),
            ('Apollo user corrections', 'request.user_corrections = apollo_mapped'),
            ('Apollo fallback case', 'APOLLO ENRICHMENT: Also apply Apollo enrichment for fallback extraction'),
            ('Apollo error handling', 'Apollo enrichment failed for'),
        ]

        all_found = True
        for check_name, check_pattern in integration_checks:
            if check_pattern in content:
                print(f"✅ {check_name}: Found")
            else:
                print(f"❌ {check_name}: Not found")
                all_found = False

        return all_found
    except Exception as e:
        print(f"❌ Error checking integration points: {e}")
        return False

def test_environment_config():
    """Test environment configuration"""
    apollo_key = os.getenv('APOLLO_API_KEY')
    if apollo_key:
        print(f"✅ Apollo API key configured: {apollo_key[:10]}...")
        return True
    else:
        print("❌ Apollo API key not configured")
        return False

if __name__ == "__main__":
    print("🚀 Testing Apollo enrichment integration (simple)...\n")

    tests = [
        ("Apollo Import", test_apollo_import),
        ("Main.py Import", test_main_import),
        ("Integration Points", test_apollo_integration_points),
        ("Environment Config", test_environment_config)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} test:")
        result = test_func()
        results.append((test_name, result))

    print("\n📊 Test Results Summary:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Overall: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 All tests passed! Apollo enrichment integration is ready.")
    else:
        print("⚠️  Some tests failed. Review the integration.")