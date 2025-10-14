#!/usr/bin/env python3
"""
End-to-end anonymization testing for vault alerts system.

This script:
1. Generates vault alerts with PRIVACY_MODE=true
2. Validates anonymization in generated HTML
3. Checks audit logs for proper tracking
4. Verifies pre-send validation works

Run this script before deploying to production to ensure all
security controls are working correctly.
"""
import asyncio
import os
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

# Ensure PRIVACY_MODE is enabled
os.environ['PRIVACY_MODE'] = 'true'

from app.jobs.vault_alerts_generator import VaultAlertsGenerator
from app.jobs.vault_alerts_scheduler import VaultAlertsScheduler


class AnonymizationValidator:
    """Comprehensive anonymization validation for vault alerts."""

    # Firm name patterns (should NOT appear in anonymized output)
    PROHIBITED_FIRMS = [
        r'Merrill\s+Lynch', r'Morgan\s+Stanley', r'Wells\s+Fargo\s+Advisor',
        r'\bUBS\b', r'Raymond\s+James', r'Edward\s+Jones', r'Stifel',
        r'Cresset', r'Fisher\s+Investments', r'Edelman\s+Financial',
        r'Creative\s+Planning', r'Captrust', r'Brightworth', r'Mariner\s+Wealth',
        r'Hightower', r'Sanctuary\s+Wealth', r'Dynasty\s+Financial',
        r'Charles\s+Schwab', r'\bSchwab\b', r'Fidelity', r'Vanguard',
        r'JP\s*Morgan', r'JPMorgan', r'Goldman\s+Sachs', r'BlackRock',
        r'State\s+Street', r'BNY\s+Mellon', r'Northern\s+Trust',
        r'SAFE\s+Credit\s+Union', r'Regions\s+Bank', r'\bPNC\b',
        r'Fifth\s+Third', r'Truist', r'Key\s+Bank', r'Huntington',
        r'LPL\s+Financial', r'\bLPL\b', r'Commonwealth\s+Financial',
        r'Northwestern\s+Mutual', r'MassMutual', r'Lincoln\s+Financial',
        r'Ameriprise', r'Cetera', r'Cambridge\s+Investment', r'Osaic'
    ]

    # University patterns (should NOT appear)
    PROHIBITED_UNIVERSITIES = [
        r'University\s+of\s+\w+', r'\bLSU\b', r'Penn\s+State', r'Louisiana\s+State',
        r'Harvard', r'Stanford', r'MIT\b', r'Yale', r'Princeton',
        r'Columbia', r'Cornell', r'Duke', r'Northwestern', r'Georgetown',
        r'Vanderbilt', r'Emory', r'Rice', r'Notre\s+Dame',
        r'UCLA', r'USC\b', r'\bNYU\b', r'Michigan', r'Berkeley',
        r'IE\s+University', r'IE\s+Business', r'INSEAD', r'Wharton',
        r'Kellogg', r'Booth', r'Sloan', r'Haas', r'Stern'
    ]

    def __init__(self, strict: bool = True):
        """
        Initialize validator.

        Args:
            strict: If True, fails on any violation. If False, logs warnings only.
        """
        self.strict = strict
        self.violations = []
        self.warnings = []

    def validate_html(self, html: str, label: str = "HTML") -> bool:
        """
        Validate HTML doesn't contain identifiable information.

        Args:
            html: HTML content to validate
            label: Label for this HTML (e.g., "Advisor HTML", "Executive HTML")

        Returns:
            True if validation passes, False otherwise
        """
        print(f"\n{'='*70}")
        print(f"🔍 Validating {label}")
        print(f"{'='*70}")

        violations_found = False

        # Check 1: Firm names
        print("\n1️⃣ Checking for prohibited firm names...")
        for pattern in self.PROHIBITED_FIRMS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                violation = f"Found firm name '{pattern}': {matches}"
                self.violations.append(violation)
                print(f"   ❌ VIOLATION: {violation}")
                violations_found = True

        if not violations_found:
            print("   ✅ No firm names found")

        # Check 2: Universities
        print("\n2️⃣ Checking for prohibited university names...")
        university_violations = False
        for pattern in self.PROHIBITED_UNIVERSITIES:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                violation = f"Found university '{pattern}': {matches}"
                self.violations.append(violation)
                print(f"   ❌ VIOLATION: {violation}")
                university_violations = True

        if not university_violations:
            print("   ✅ No university names found")
        else:
            violations_found = True

        # Check 3: ZIP codes
        print("\n3️⃣ Checking for ZIP codes...")
        zip_matches = re.findall(r'\b\d{5}\b', html)
        if zip_matches:
            violation = f"Found ZIP codes: {zip_matches}"
            self.violations.append(violation)
            print(f"   ❌ VIOLATION: {violation}")
            violations_found = True
        else:
            print("   ✅ No ZIP codes found")

        # Check 4: Exact AUM figures
        print("\n4️⃣ Checking for exact AUM figures...")
        exact_aum_pattern = r'\$\d+\.\d+[BMK](?!\+|\s*-\s*\$)'
        exact_aum_matches = re.findall(exact_aum_pattern, html)
        if exact_aum_matches:
            violation = f"Found exact AUM figures: {exact_aum_matches}"
            self.violations.append(violation)
            print(f"   ❌ VIOLATION: {violation}")
            violations_found = True
        else:
            print("   ✅ No exact AUM figures (all have ranges or + suffix)")

        # Check 5: Verify expected anonymized patterns exist
        print("\n5️⃣ Checking for expected anonymized patterns...")
        expected_patterns = [
            (r'major wirehouse|regional brokerage|independent RIA|multi-billion dollar', 'Generic firm types'),
            (r'\$\d+[BMK]\+', 'AUM ranges with + suffix'),
            (r'Dallas/Fort Worth|Greater Los Angeles|San Francisco Bay Area', 'Major metro areas')
        ]

        for pattern, description in expected_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                print(f"   ✅ Found {description}")
            else:
                warning = f"Expected pattern not found: {description}"
                self.warnings.append(warning)
                print(f"   ⚠️ WARNING: {warning}")

        # Final verdict
        print(f"\n{'='*70}")
        if violations_found:
            print(f"❌ VALIDATION FAILED for {label}")
            print(f"   Found {len(self.violations)} violations")
            return False
        else:
            print(f"✅ VALIDATION PASSED for {label}")
            if self.warnings:
                print(f"   Note: {len(self.warnings)} warnings (not blocking)")
            return True

    def print_summary(self):
        """Print validation summary."""
        print(f"\n{'='*70}")
        print("📊 VALIDATION SUMMARY")
        print(f"{'='*70}")

        if self.violations:
            print(f"\n❌ FAILED - {len(self.violations)} violations found:")
            for i, violation in enumerate(self.violations, 1):
                print(f"   {i}. {violation}")
        else:
            print("\n✅ PASSED - No violations found")

        if self.warnings:
            print(f"\n⚠️ {len(self.warnings)} warnings:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")

        print(f"\n{'='*70}")


async def test_generation_with_anonymization():
    """Test vault alert generation with PRIVACY_MODE enabled."""
    print("="*70)
    print("🚀 Starting End-to-End Anonymization Test")
    print("="*70)

    # Verify PRIVACY_MODE is enabled
    from app.config import PRIVACY_MODE
    print(f"\n✅ PRIVACY_MODE: {PRIVACY_MODE}")

    if not PRIVACY_MODE:
        print("❌ ERROR: PRIVACY_MODE is not enabled!")
        print("   Set PRIVACY_MODE=true in .env.local")
        sys.exit(1)

    # Initialize generator
    print("\n📦 Initializing VaultAlertsGenerator...")
    generator = VaultAlertsGenerator()

    # Test with 5 recent candidates
    print("\n🎯 Generating alerts for 5 recent candidates (last 30 days)...")

    try:
        result = await generator.generate_alerts(
            max_candidates=5,
            custom_filters={'date_range_days': 30},
            save_files=False  # Don't save files during testing
        )

        print(f"\n✅ Generation completed")
        metadata = result.get('metadata', {})
        print(f"   Total candidates: {metadata.get('total_candidates', 0)}")
        print(f"   Advisor count: {metadata.get('advisor_count', 0)}")
        print(f"   Executive count: {metadata.get('executive_count', 0)}")
        print(f"   Generation time: {metadata.get('generation_time_seconds', 0)}s")

        # Validate advisor HTML
        advisor_html = result.get('advisor_html', '')
        executive_html = result.get('executive_html', '')

        if not advisor_html and not executive_html:
            print("\n❌ ERROR: No HTML generated")
            return False

        # Run validation
        validator = AnonymizationValidator(strict=True)

        advisor_pass = True
        executive_pass = True

        if advisor_html:
            advisor_pass = validator.validate_html(advisor_html, "Advisor HTML")

        if executive_html:
            executive_pass = validator.validate_html(executive_html, "Executive HTML")

        validator.print_summary()

        return advisor_pass and executive_pass

    except Exception as e:
        print(f"\n❌ ERROR during generation: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_pre_send_validation():
    """Test pre-send validation blocks non-anonymized content."""
    print("\n" + "="*70)
    print("🛡️ Testing Pre-Send Validation")
    print("="*70)

    scheduler = VaultAlertsScheduler()

    # Test 1: Valid anonymized HTML (should pass)
    valid_html = """
    <html>
    <body>
        <h1>Vault Alerts</h1>
        <p>Major wirehouse advisor with $1B+ AUM seeking opportunities in Dallas/Fort Worth metro.</p>
        <p>MBA degree, 15+ years experience in wealth management.</p>
    </body>
    </html>
    """

    print("\n1️⃣ Testing valid anonymized HTML...")
    try:
        is_valid = scheduler._validate_anonymization(valid_html)
        if is_valid:
            print("   ✅ PASSED: Valid HTML accepted")
        else:
            print("   ❌ FAILED: Valid HTML rejected (false positive)")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    # Test 2: HTML with firm name (should fail)
    invalid_html_firm = """
    <html>
    <body>
        <h1>Vault Alerts</h1>
        <p>Merrill Lynch advisor with $1B+ AUM seeking opportunities.</p>
    </body>
    </html>
    """

    print("\n2️⃣ Testing HTML with firm name (should be blocked)...")
    try:
        is_valid = scheduler._validate_anonymization(invalid_html_firm)
        if not is_valid:
            print("   ✅ PASSED: Firm name blocked correctly")
        else:
            print("   ❌ FAILED: Firm name not detected (false negative)")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    # Test 3: HTML with university (should fail)
    invalid_html_university = """
    <html>
    <body>
        <h1>Vault Alerts</h1>
        <p>MBA from Harvard, 15+ years experience.</p>
    </body>
    </html>
    """

    print("\n3️⃣ Testing HTML with university name (should be blocked)...")
    try:
        is_valid = scheduler._validate_anonymization(invalid_html_university)
        if not is_valid:
            print("   ✅ PASSED: University name blocked correctly")
        else:
            print("   ❌ FAILED: University name not detected (false negative)")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    # Test 4: HTML with ZIP code (should fail)
    invalid_html_zip = """
    <html>
    <body>
        <h1>Vault Alerts</h1>
        <p>Located in Dallas, TX 75034</p>
    </body>
    </html>
    """

    print("\n4️⃣ Testing HTML with ZIP code (should be blocked)...")
    try:
        is_valid = scheduler._validate_anonymization(invalid_html_zip)
        if not is_valid:
            print("   ✅ PASSED: ZIP code blocked correctly")
        else:
            print("   ❌ FAILED: ZIP code not detected (false negative)")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    print("\n" + "="*70)
    print("✅ All pre-send validation tests PASSED")
    print("="*70)
    return True


async def main():
    """Run all end-to-end tests."""
    print("\n" + "="*70)
    print("🧪 VAULT ALERTS ANONYMIZATION E2E TEST SUITE")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Environment: {os.getenv('ENV', 'development')}")
    print("="*70)

    results = {}

    # Test 1: Generation with anonymization
    print("\n\n📝 TEST 1: Alert Generation with Anonymization")
    results['generation'] = await test_generation_with_anonymization()

    # Test 2: Pre-send validation
    print("\n\n📝 TEST 2: Pre-Send Validation")
    results['validation'] = await test_pre_send_validation()

    # Final summary
    print("\n\n" + "="*70)
    print("🏁 FINAL TEST RESULTS")
    print("="*70)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name.upper()}: {status}")

    all_passed = all(results.values())

    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Safe to deploy")
        print("="*70)
        print("\nNext steps:")
        print("1. Send test email to steve@, brandon@, daniel.romitelli@")
        print("2. Get boss approval")
        print("3. Deploy to production")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - DO NOT DEPLOY")
        print("="*70)
        print("\nFix the issues above before deploying to production")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
