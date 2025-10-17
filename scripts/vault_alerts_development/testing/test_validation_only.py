#!/usr/bin/env python3
"""
Quick validation-only test for vault alerts pre-send security.

Tests pre-send validation without running full generation.
Run this for fast security verification.
"""
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

from app.jobs.vault_alerts_scheduler import VaultAlertsScheduler


def test_pre_send_validation():
    """Test pre-send validation blocks non-anonymized content."""
    print("="*70)
    print("🛡️ PRE-SEND VALIDATION SECURITY TEST")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    scheduler = VaultAlertsScheduler()
    all_passed = True

    # Test 1: Valid anonymized HTML (should pass)
    print("1️⃣ Testing VALID anonymized HTML...")
    valid_html = """
    <html><body>
        <h1>Vault Alerts</h1>
        <p>Major wirehouse advisor with $1B+ AUM seeking opportunities in Dallas/Fort Worth metro.</p>
        <p>MBA degree, 15+ years experience in wealth management.</p>
        <p>Top performance in client acquisition and retention.</p>
    </body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(valid_html)
        if is_valid:
            print("   ✅ PASSED: Valid HTML accepted\n")
        else:
            print("   ❌ FAILED: Valid HTML rejected (false positive)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Test 2: HTML with firm name (should fail)
    print("2️⃣ Testing HTML with FIRM NAME (should be blocked)...")
    invalid_firm = """
    <html><body><p>Merrill Lynch advisor seeking opportunities.</p></body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(invalid_firm)
        if not is_valid:
            print("   ✅ PASSED: Firm name BLOCKED correctly\n")
        else:
            print("   ❌ FAILED: Firm name NOT detected (security hole!)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Test 3: HTML with university (should fail)
    print("3️⃣ Testing HTML with UNIVERSITY NAME (should be blocked)...")
    invalid_university = """
    <html><body><p>MBA from Harvard, CFA charterholder.</p></body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(invalid_university)
        if not is_valid:
            print("   ✅ PASSED: University name BLOCKED correctly\n")
        else:
            print("   ❌ FAILED: University name NOT detected (security hole!)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Test 4: HTML with ZIP code (should fail)
    print("4️⃣ Testing HTML with ZIP CODE (should be blocked)...")
    invalid_zip = """
    <html><body><p>Located in Dallas, TX 75034</p></body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(invalid_zip)
        if not is_valid:
            print("   ✅ PASSED: ZIP code BLOCKED correctly\n")
        else:
            print("   ❌ FAILED: ZIP code NOT detected (security hole!)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Test 5: HTML with exact AUM (should fail)
    print("5️⃣ Testing HTML with EXACT AUM (should be blocked)...")
    invalid_aum = """
    <html><body><p>Manages $1.68B in client assets.</p></body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(invalid_aum)
        if not is_valid:
            print("   ✅ PASSED: Exact AUM BLOCKED correctly\n")
        else:
            print("   ❌ FAILED: Exact AUM NOT detected (security hole!)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Test 6: HTML with multiple violations (should fail)
    print("6️⃣ Testing HTML with MULTIPLE VIOLATIONS (should be blocked)...")
    multiple_violations = """
    <html><body>
        <p>Former UBS advisor with MBA from Penn State.</p>
        <p>Located in Frisco, TX 75034</p>
        <p>Manages $2.3B in assets.</p>
    </body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(multiple_violations)
        if not is_valid:
            print("   ✅ PASSED: Multiple violations BLOCKED correctly\n")
        else:
            print("   ❌ FAILED: Multiple violations NOT detected (security hole!)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Test 7: Valid HTML with ranges (should pass)
    print("7️⃣ Testing VALID HTML with AUM RANGES (should pass)...")
    valid_ranges = """
    <html><body>
        <p>Senior advisor with $1B+ AUM seeking opportunities.</p>
        <p>Compensation: $150K-$200K OTE</p>
        <p>Located in Dallas/Fort Worth metro area.</p>
    </body></html>
    """

    try:
        is_valid = scheduler._validate_anonymization(valid_ranges)
        if is_valid:
            print("   ✅ PASSED: Valid ranges accepted\n")
        else:
            print("   ❌ FAILED: Valid ranges rejected (false positive)\n")
            all_passed = False
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")
        all_passed = False

    # Final summary
    print("="*70)
    print("📊 FINAL RESULTS")
    print("="*70)

    if all_passed:
        print("✅ ALL VALIDATION TESTS PASSED")
        print("\nPre-send validation is working correctly!")
        print("Safe to proceed with end-to-end testing.\n")
        return 0
    else:
        print("❌ SOME VALIDATION TESTS FAILED")
        print("\nFix security issues before deploying!")
        print("DO NOT send emails until all tests pass.\n")
        return 1


if __name__ == '__main__':
    exit_code = test_pre_send_validation()
    sys.exit(exit_code)
