#!/usr/bin/env python3
"""
Generate test vault alerts email for boss approval.

Generates anonymized vault alerts for 5-10 candidates and prepares
for manual review before sending to steve@, brandon@, daniel.romitelli@
"""
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

# Ensure PRIVACY_MODE is enabled
os.environ['PRIVACY_MODE'] = 'true'

from app.jobs.vault_alerts_generator import VaultAlertsGenerator


async def generate_test_email():
    """Generate test email with anonymized vault alerts."""
    print("="*70)
    print("📧 GENERATING TEST EMAIL FOR BOSS APPROVAL")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Recipients: steve@, brandon@, daniel.romitelli@")
    print("="*70)

    # Verify PRIVACY_MODE
    from app.config import PRIVACY_MODE
    print(f"\n✅ PRIVACY_MODE: {PRIVACY_MODE}")

    if not PRIVACY_MODE:
        print("❌ ERROR: PRIVACY_MODE must be enabled!")
        sys.exit(1)

    print("\n📦 Initializing VaultAlertsGenerator...")
    generator = VaultAlertsGenerator()

    print("\n🎯 Generating alerts for recent candidates (last 30 days)...")
    print("   Target: 5-10 candidates with strong profiles")

    try:
        # Generate alerts with filters for high-quality candidates
        result = await generator.generate_alerts(
            max_candidates=10,  # Target 10, but may return fewer
            custom_filters={
                'date_range_days': 30,  # Last 30 days
                # Optional: Add filters for strong candidates
                # 'compensation_min': 150000,  # $150K+ compensation
                # 'designations': ['CFP', 'CFA', 'CIMA']  # Strong designations
            },
            save_files=False  # Don't save files, just return HTML
        )

        metadata = result.get('metadata', {})
        total_candidates = metadata.get('total_candidates', 0)
        advisor_count = metadata.get('advisor_count', 0)
        executive_count = metadata.get('executive_count', 0)
        generation_time = metadata.get('generation_time_seconds', 0)

        print(f"\n✅ Generation completed in {generation_time:.1f}s")
        print(f"   Total candidates: {total_candidates}")
        print(f"   Advisor format: {advisor_count} cards")
        print(f"   Executive format: {executive_count} cards")

        # Get HTML outputs
        advisor_html = result.get('advisor_html', '')
        executive_html = result.get('executive_html', '')

        if not advisor_html and not executive_html:
            print("\n❌ ERROR: No HTML generated")
            print("   This may mean no candidates match the filters")
            print("   Try adjusting custom_filters or date_range_days")
            sys.exit(1)

        # Save outputs to files for review
        output_dir = '/home/romiteld/Development/Desktop_Apps/outlook/test_outputs'
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if advisor_html:
            advisor_file = f"{output_dir}/advisor_format_{timestamp}.html"
            with open(advisor_file, 'w', encoding='utf-8') as f:
                f.write(advisor_html)
            print(f"\n📄 Advisor HTML saved: {advisor_file}")

        if executive_html:
            executive_file = f"{output_dir}/executive_format_{timestamp}.html"
            with open(executive_file, 'w', encoding='utf-8') as f:
                f.write(executive_html)
            print(f"📄 Executive HTML saved: {executive_file}")

        # Run validation on outputs
        print("\n" + "="*70)
        print("🔍 RUNNING SECURITY VALIDATION")
        print("="*70)

        from app.jobs.vault_alerts_scheduler import VaultAlertsScheduler
        scheduler = VaultAlertsScheduler()

        advisor_valid = True
        executive_valid = True

        if advisor_html:
            print("\n1️⃣ Validating Advisor HTML...")
            advisor_valid = scheduler._validate_anonymization(advisor_html)
            if advisor_valid:
                print("   ✅ PASSED: No violations found")
            else:
                print("   ❌ FAILED: Contains identifiable information")

        if executive_html:
            print("\n2️⃣ Validating Executive HTML...")
            executive_valid = scheduler._validate_anonymization(executive_html)
            if executive_valid:
                print("   ✅ PASSED: No violations found")
            else:
                print("   ❌ FAILED: Contains identifiable information")

        # Final summary
        print("\n" + "="*70)
        print("📊 TEST EMAIL GENERATION SUMMARY")
        print("="*70)

        if advisor_valid and executive_valid:
            print("\n✅ VALIDATION PASSED - Safe to send")
            print(f"\n📧 Email subject: Vault Alerts Test - {total_candidates} New Candidates")
            print(f"\n📨 Recipients (manual send):")
            print(f"   - steve@emailthewell.com")
            print(f"   - brandon@emailthewell.com")
            print(f"   - daniel.romitelli@emailthewell.com")
            print(f"\n📎 Attachments:")
            if advisor_html:
                print(f"   - Advisor Format ({advisor_count} cards)")
            if executive_html:
                print(f"   - Executive Format ({executive_count} cards)")

            print("\n" + "="*70)
            print("📋 NEXT STEPS FOR BOSS APPROVAL")
            print("="*70)
            print("\n1. Review the generated HTML files:")
            if advisor_html:
                print(f"   {advisor_file}")
            if executive_html:
                print(f"   {executive_file}")

            print("\n2. Open files in browser to preview formatting")

            print("\n3. Compose email to bosses:")
            print("   To: steve@emailthewell.com, brandon@emailthewell.com, daniel.romitelli@emailthewell.com")
            print(f"   Subject: Vault Alerts Test - {total_candidates} New Candidates (Anonymized)")
            print("   Body:")
            print("""
   Hi Steve, Brandon, and Daniel,

   I've completed the vault alerts anonymization system with the following security controls:

   ✅ Firm names → Generic descriptors (e.g., "Major wirehouse", "Large RIA")
   ✅ AUM → Rounded ranges with + suffix (e.g., "$1B+ AUM")
   ✅ Universities → Degree types only (e.g., "MBA degree")
   ✅ Locations → Major metro areas (e.g., "Dallas/Fort Worth metro")
   ✅ Pre-send validation blocks any violations
   ✅ Audit logging tracks all anonymization operations

   Attached are two formats:
   - Advisor Format: Detailed bullets for advisors
   - Executive Format: Concise bullets for executives

   Please review and confirm:
   1. No identifying information visible?
   2. Format easy to read?
   3. Information actionable?

   Looking forward to your feedback!

   Best,
   [Your name]
            """)

            print("\n4. Attach the HTML files to the email")

            print("\n5. Send and wait for approval")

            print("\n" + "="*70)
            return 0
        else:
            print("\n❌ VALIDATION FAILED - DO NOT SEND")
            print("\nFix violations before sending to bosses")
            print("Check application logs for specific violations")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR during generation: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(generate_test_email())
    sys.exit(exit_code)
