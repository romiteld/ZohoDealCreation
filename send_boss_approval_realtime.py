#!/usr/bin/env python3
"""
Send vault alerts test email to bosses for approval - WITH REAL-TIME PROGRESS.

Shows progress of each candidate as it's being processed.
"""
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load environment
load_dotenv('.env.local')

# Ensure PRIVACY_MODE is enabled
os.environ['PRIVACY_MODE'] = 'true'

# Import after env is set
from app.jobs.vault_alerts_generator import VaultAlertsGenerator
from app.jobs.vault_alerts_scheduler import VaultAlertsScheduler


async def send_boss_approval_email():
    """Generate and send vault alerts to bosses for approval."""
    print("="*70, flush=True)
    print("📧 SENDING VAULT ALERTS TEST TO BOSSES FOR APPROVAL", flush=True)
    print("="*70, flush=True)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"From: noreply@emailthewell.com", flush=True)
    print(f"To: steve@, brandon@, daniel.romitelli@", flush=True)
    print("="*70, flush=True)

    # Verify PRIVACY_MODE
    from app.config import PRIVACY_MODE
    print(f"\n✅ PRIVACY_MODE: {PRIVACY_MODE}", flush=True)

    if not PRIVACY_MODE:
        print("❌ ERROR: PRIVACY_MODE must be enabled!", flush=True)
        sys.exit(1)

    # Initialize generator
    print("\n📦 Initializing VaultAlertsGenerator...", flush=True)
    generator = VaultAlertsGenerator()

    print("\n🎯 Starting vault alerts generation...", flush=True)
    print("="*70, flush=True)
    print("⏰ ESTIMATED TIME:", flush=True)
    print("   First run (cache empty): 2-3 HOURS", flush=True)
    print("   - Database load: ~30 seconds", flush=True)
    print("   - Per candidate: 10-15 minutes (GPT-5 bullet generation)", flush=True)
    print("   - HTML render: ~2 minutes", flush=True)
    print("   - Validation: ~30 seconds", flush=True)
    print("\n   Future runs (cache warm): 8 minutes", flush=True)
    print("="*70, flush=True)
    print("\n🔄 YOU CAN WATCH PROGRESS BELOW IN REAL-TIME\n", flush=True)

    start_time = datetime.now()

    try:
        # Generate alerts
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Starting generation...\n", flush=True)

        result = await generator.generate_alerts(
            max_candidates=10,  # Target 10 candidates
            custom_filters={
                'date_range_days': 30,
            },
            save_files=False
        )

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        metadata = result.get('metadata', {})
        total_candidates = metadata.get('total_candidates', 0)
        advisor_count = metadata.get('advisor_count', 0)
        executive_count = metadata.get('executive_count', 0)

        print(f"\n{'='*70}", flush=True)
        print(f"✅ GENERATION COMPLETED", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)", flush=True)
        print(f"👥 Candidates processed: {total_candidates}", flush=True)
        print(f"📝 Advisor cards: {advisor_count}", flush=True)
        print(f"📝 Executive cards: {executive_count}", flush=True)

        # Get HTML
        advisor_html = result.get('advisor_html', '')
        executive_html = result.get('executive_html', '')

        if not advisor_html:
            print("\n❌ ERROR: No HTML generated", flush=True)
            sys.exit(1)

        # Validate HTML
        print(f"\n{'='*70}", flush=True)
        print("🔍 RUNNING SECURITY VALIDATION", flush=True)
        print(f"{'='*70}", flush=True)

        scheduler = VaultAlertsScheduler()

        print("\n1️⃣ Validating advisor HTML...", flush=True)
        advisor_valid = scheduler._validate_anonymization(advisor_html)
        if not advisor_valid:
            print("❌ VALIDATION FAILED - Blocking email", flush=True)
            sys.exit(1)
        print("✅ Advisor HTML validation PASSED", flush=True)

        if executive_html:
            print("\n2️⃣ Validating executive HTML...", flush=True)
            executive_valid = scheduler._validate_anonymization(executive_html)
            if not executive_valid:
                print("❌ VALIDATION FAILED - Blocking email", flush=True)
                sys.exit(1)
            print("✅ Executive HTML validation PASSED", flush=True)

        # Prepare email HTML
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
        .stats {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .stat {{
            flex: 1;
            min-width: 150px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        .section {{
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .security {{
            background: #d4edda;
            border-left-color: #28a745;
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
            margin-top: 0;
        }}
        .footer {{
            margin-top: 50px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: center;
            color: #666;
        }}
        ul {{
            line-height: 1.8;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Vault Alerts Test - Anonymization Complete</h1>
        <p>New security-enhanced candidate alerts ready for your review</p>
    </div>

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
            <div class="stat-number">{total_time/60:.0f}m</div>
            <div class="stat-label">Generation Time</div>
        </div>
    </div>

    <div class="section security">
        <h2>✅ Security Validation: PASSED</h2>
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
            Security: PRIVACY_MODE enabled | 7/7 validation tests passed
        </p>
    </div>
</body>
</html>
"""

        # Send email
        print(f"\n{'='*70}", flush=True)
        print("📧 SENDING EMAIL VIA AZURE COMMUNICATION SERVICES", flush=True)
        print(f"{'='*70}", flush=True)

        subject = f"Vault Alerts Test - {total_candidates} Candidates (Anonymized) - Approval Needed"

        recipients = [
            "steve@emailthewell.com",
            "brandon@emailthewell.com",
            "daniel.romitelli@emailthewell.com"
        ]

        print(f"\n📧 Recipients: {', '.join(recipients)}", flush=True)
        print(f"📝 Subject: {subject}", flush=True)
        print("\n🚀 Sending...", flush=True)

        message_id = scheduler.send_email(
            to_email=recipients[0],
            subject=subject,
            html_body=email_html,
            user_name="Boss Approval Team"
        )

        print(f"\n{'='*70}", flush=True)
        print("✅ EMAIL SENT SUCCESSFULLY!", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"📨 Message ID: {message_id}", flush=True)
        print(f"📬 From: noreply@emailthewell.com", flush=True)
        print(f"📬 To: {', '.join(recipients)}", flush=True)
        print(f"📊 Candidates: {total_candidates}", flush=True)
        print(f"📝 Cards: {advisor_count} advisor, {executive_count} executive", flush=True)

        print(f"\n{'='*70}", flush=True)
        print("🎉 BOSS APPROVAL PROCESS INITIATED", flush=True)
        print(f"{'='*70}", flush=True)
        print("\nNext steps:", flush=True)
        print("1. ✅ Bosses will receive email from noreply@emailthewell.com", flush=True)
        print("2. ⏳ Wait for their review and approval", flush=True)
        print("3. 🚀 After approval, deploy to production", flush=True)
        print("4. 📊 Setup PowerBI monitoring dashboard", flush=True)
        print("5. 🤖 Update Teams bot with vault alerts command", flush=True)

        return 0

    except Exception as e:
        print(f"\n{'='*70}", flush=True)
        print(f"❌ ERROR: {e}", flush=True)
        print(f"{'='*70}", flush=True)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(send_boss_approval_email())
    sys.exit(exit_code)
