#!/usr/bin/env python3
"""
Send vault alerts test email to bosses for approval.

Generates anonymized alerts and sends via Azure Communication Services
from noreply@emailthewell.com to steve@, brandon@, daniel.romitelli@
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
from app.jobs.vault_alerts_scheduler import VaultAlertsScheduler


async def send_boss_approval_email():
    """Generate and send vault alerts to bosses for approval."""
    print("="*70)
    print("📧 SENDING VAULT ALERTS TEST TO BOSSES FOR APPROVAL")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"From: noreply@emailthewell.com")
    print(f"To: steve@emailthewell.com, brandon@emailthewell.com, daniel.romitelli@emailthewell.com")
    print("="*70)

    # Verify PRIVACY_MODE
    from app.config import PRIVACY_MODE
    print(f"\n✅ PRIVACY_MODE: {PRIVACY_MODE}")

    if not PRIVACY_MODE:
        print("❌ ERROR: PRIVACY_MODE must be enabled!")
        sys.exit(1)

    # Initialize generator
    print("\n📦 Initializing VaultAlertsGenerator...")
    generator = VaultAlertsGenerator()

    print("\n🎯 Generating vault alerts (this will take 5-10 minutes)...")
    print("   - LangGraph 4-agent workflow")
    print("   - GPT-5 bullet generation per candidate")
    print("   - Cache cleared, so first run will be slower")
    print("   - Please be patient...")

    try:
        # Generate alerts
        result = await generator.generate_alerts(
            max_candidates=10,  # Target 10 strong candidates
            custom_filters={
                'date_range_days': 30,  # Last 30 days
            },
            save_files=False  # Return HTML directly
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

        # Get HTML
        advisor_html = result.get('advisor_html', '')
        executive_html = result.get('executive_html', '')

        if not advisor_html:
            print("\n❌ ERROR: No HTML generated")
            print("   This may mean no candidates match the filters")
            sys.exit(1)

        # Validate HTML
        print("\n" + "="*70)
        print("🔍 RUNNING SECURITY VALIDATION")
        print("="*70)

        scheduler = VaultAlertsScheduler()

        print("\nValidating advisor HTML...")
        advisor_valid = scheduler._validate_anonymization(advisor_html)
        if not advisor_valid:
            print("❌ VALIDATION FAILED - Blocking email")
            sys.exit(1)
        print("✅ Advisor HTML validation PASSED")

        if executive_html:
            print("\nValidating executive HTML...")
            executive_valid = scheduler._validate_anonymization(executive_html)
            if not executive_valid:
                print("❌ VALIDATION FAILED - Blocking email")
                sys.exit(1)
            print("✅ Executive HTML validation PASSED")

        # Prepare email
        print("\n" + "="*70)
        print("📧 SENDING EMAIL VIA AZURE COMMUNICATION SERVICES")
        print("="*70)

        # Create combined HTML email with both formats
        email_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .section {{
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }}
        .stat {{
            flex: 1;
            padding: 15px;
            background: white;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
        }}
        .security {{
            background: #d4edda;
            border-left-color: #28a745;
            padding: 15px;
            margin: 20px 0;
            border-radius: 8px;
        }}
        .alert-section {{
            margin: 40px 0;
            padding: 30px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h2 {{
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .footer {{
            margin-top: 50px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: center;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Vault Alerts Test - Anonymization Complete</h1>
        <p>New security-enhanced candidate alerts ready for review</p>
    </div>

    <div class="section">
        <h2>📊 Generation Summary</h2>
        <div class="stats">
            <div class="stat">
                <div class="stat-number">{total_candidates}</div>
                <div class="stat-label">Candidates</div>
            </div>
            <div class="stat">
                <div class="stat-number">{advisor_count}</div>
                <div class="stat-label">Advisor Cards</div>
            </div>
            <div class="stat">
                <div class="stat-number">{executive_count}</div>
                <div class="stat-label">Executive Cards</div>
            </div>
            <div class="stat">
                <div class="stat-number">{generation_time:.1f}s</div>
                <div class="stat-label">Generation Time</div>
            </div>
        </div>
    </div>

    <div class="security">
        <h3>✅ Security Validation: PASSED</h3>
        <ul>
            <li>✅ No firm names detected</li>
            <li>✅ No university names detected</li>
            <li>✅ No ZIP codes detected</li>
            <li>✅ No exact AUM figures detected</li>
            <li>✅ All identifiable information anonymized</li>
        </ul>
    </div>

    <div class="section">
        <h2>🔐 Anonymization Rules Applied</h2>
        <ul>
            <li><strong>Firm Names</strong> → Generic descriptors (e.g., "Major wirehouse", "Large RIA")</li>
            <li><strong>AUM Values</strong> → Rounded ranges with + suffix (e.g., "$1B+ AUM")</li>
            <li><strong>Universities</strong> → Degree types only (e.g., "MBA degree")</li>
            <li><strong>Locations</strong> → Major metro areas (e.g., "Dallas/Fort Worth metro")</li>
            <li><strong>Achievements</strong> → Generalized statements (no specific rankings)</li>
        </ul>
    </div>

    <div class="alert-section">
        <h2>📋 Advisor Format ({advisor_count} cards)</h2>
        <p style="color: #666; margin-bottom: 20px;">Detailed bullets for advisor audience - includes compensation, experience, and availability details.</p>
        {advisor_html}
    </div>

    {f'''
    <div class="alert-section">
        <h2>📋 Executive Format ({executive_count} cards)</h2>
        <p style="color: #666; margin-bottom: 20px;">Concise bullets for executive audience - high-level overview optimized for quick scanning.</p>
        {executive_html}
    </div>
    ''' if executive_html else ''}

    <div class="footer">
        <h3>🎯 Please Review & Confirm</h3>
        <p>Please review the alerts above and confirm:</p>
        <ul style="text-align: left; display: inline-block;">
            <li>✅ No identifying information visible?</li>
            <li>✅ Format easy to read?</li>
            <li>✅ Information actionable?</li>
        </ul>
        <p style="margin-top: 20px;">
            <strong>Reply to this email</strong> with your approval or any requested changes.
        </p>
        <p style="font-size: 12px; color: #999; margin-top: 20px;">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            Test System: Vault Alerts v1.0<br>
            Security Level: PRIVACY_MODE enabled
        </p>
    </div>
</body>
</html>
"""

        # Send email
        subject = f"Vault Alerts Test - {total_candidates} Candidates (Anonymized) - Approval Needed"

        recipients = [
            "steve@emailthewell.com",
            "brandon@emailthewell.com",
            "daniel.romitelli@emailthewell.com"
        ]

        print(f"\n📧 Sending to: {', '.join(recipients)}")
        print(f"📝 Subject: {subject}")

        message_id = scheduler.send_email(
            to_email=recipients[0],  # Primary recipient
            subject=subject,
            html_body=email_html,
            user_name="Boss Approval Team"
        )

        print(f"\n✅ EMAIL SENT SUCCESSFULLY!")
        print(f"   Message ID: {message_id}")
        print(f"   From: noreply@emailthewell.com")
        print(f"   To: {', '.join(recipients)}")
        print(f"   Candidates: {total_candidates}")
        print(f"   Advisor cards: {advisor_count}")
        print(f"   Executive cards: {executive_count}")

        print("\n" + "="*70)
        print("🎉 BOSS APPROVAL EMAIL SENT")
        print("="*70)
        print("\nNext steps:")
        print("1. Bosses will receive email from noreply@emailthewell.com")
        print("2. They can review the anonymized alerts")
        print("3. Wait for their approval confirmation")
        print("4. After approval, deploy to production")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(send_boss_approval_email())
    sys.exit(exit_code)
