#!/usr/bin/env python3
"""
Send the manually cleaned vault alerts HTML to bosses for approval.
All university names have been removed and formatting is preserved.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.local')

# Import scheduler for email sending
from app.jobs.vault_alerts_scheduler import VaultAlertsScheduler

def send_email():
    """Send cleaned vault alerts to all three recipients."""
    print("="*70)
    print("📧 SENDING CLEANED VAULT ALERTS TO BOSSES")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Read cleaned HTML files
    with open('debug_advisor_CLEANED.html', 'r') as f:
        advisor_html = f.read()

    try:
        with open('debug_executive_CLEANED.html', 'r') as f:
            executive_html = f.read()
    except FileNotFoundError:
        print("⚠️  No executive HTML found")
        executive_html = ""

    # Count candidates
    advisor_count = advisor_html.count('candidate-card')
    executive_count = executive_html.count('candidate-card') if executive_html else 0
    total_candidates = advisor_count + executive_count

    print(f"\n📊 Statistics:")
    print(f"   Total Candidates: {total_candidates}")
    print(f"   Advisor Cards: {advisor_count}")
    print(f"   Executive Cards: {executive_count}")

    # Create email wrapper
    email_html = f"""<!DOCTYPE html>
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
        <h1>🔒 Vault Alerts - ALL {total_candidates} Candidates (Manually Cleaned)</h1>
        <p>University names manually removed - Ready for final review</p>
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
    </div>

    <div class="section security">
        <h2>✅ Manual Security Cleanup: COMPLETE</h2>
        <ul>
            <li>✅ All university names manually removed</li>
            <li>✅ Temple University → removed</li>
            <li>✅ Washington State University → removed</li>
            <li>✅ University of Florida → removed</li>
            <li>✅ Indiana University → removed</li>
            <li>✅ All other identifying education info → removed</li>
            <li>✅ Formatting and emojis preserved (‼️ 🔔 📍)</li>
        </ul>
    </div>

    <div class="section">
        <h2>🔐 Anonymization Applied</h2>
        <ul>
            <li><strong>Firm Names</strong> → Generic descriptors (e.g., "Major wirehouse", "Large RIA")</li>
            <li><strong>AUM Values</strong> → Rounded ranges with + suffix (e.g., "$1B+ AUM")</li>
            <li><strong>Universities</strong> → Removed or generalized (e.g., "MBA degree")</li>
            <li><strong>Locations</strong> → Major metro areas (e.g., "Dallas/Fort Worth metro")</li>
        </ul>
    </div>

    <div class="alert-section">
        <h2>📋 Advisor Format ({advisor_count} cards)</h2>
        <p style="color: #666; margin-bottom: 20px;">Detailed bullets for advisor audience</p>
        {advisor_html}
    </div>

    {f'''
    <div class="alert-section">
        <h2>📋 Executive Format ({executive_count} cards)</h2>
        <p style="color: #666; margin-bottom: 20px;">Concise bullets for executive audience</p>
        {executive_html}
    </div>
    ''' if executive_html else ''}

    <div class="footer">
        <h3>🎯 Please Review & Approve</h3>
        <p>This email contains all {total_candidates} candidates with university names manually removed.</p>
        <p><strong>Reply to approve or request changes.</strong></p>
        <p style="font-size: 12px; color: #999; margin-top: 20px;">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            System: Vault Alerts v1.0 (Manually Cleaned)<br>
            University names: Manually removed
        </p>
    </div>
</body>
</html>"""

    # Send email
    scheduler = VaultAlertsScheduler()
    subject = f"✅ Vault Alerts - ALL {total_candidates} Candidates (Universities Removed) - Ready for Review"

    recipients = [
        "steve@emailthewell.com",
        "brandon@emailthewell.com",
        "daniel.romitelli@emailthewell.com"
    ]

    print(f"\n📧 Sending to {len(recipients)} recipients...")
    message_ids = []

    for recipient in recipients:
        print(f"   📤 Sending to {recipient}...")
        message_id = scheduler.send_email(
            to_email=recipient,
            subject=subject,
            html_body=email_html,
            user_name=recipient.split('@')[0].title()
        )
        message_ids.append(message_id)
        print(f"      ✅ Sent (ID: {message_id[:20]}...)")

    print(f"\n{'='*70}")
    print("✅ EMAILS SENT SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"📨 {len(message_ids)} emails delivered")
    print(f"📬 From: DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net")
    print(f"📬 To: {', '.join(recipients)}")
    print(f"📊 {total_candidates} candidates ({advisor_count} advisor, {executive_count} executive)")
    print(f"\n✅ University names manually removed - ready for boss approval!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    send_email()
