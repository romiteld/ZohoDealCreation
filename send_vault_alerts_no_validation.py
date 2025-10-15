#!/usr/bin/env python3
"""
Send vault alerts bypassing security validation - MANUAL OVERRIDE
Use only when violations have been manually verified and fixed.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from azure.communication.email import EmailClient

# Load environment
from dotenv import load_dotenv
load_dotenv(".env.local")

def send_email_direct():
    """Send email directly via Azure Communication Services - NO VALIDATION"""

    # Read cleaned HTML files
    advisor_html = Path("debug_advisor_CLEANED.html").read_text()
    exec_html = Path("debug_executive_CLEANED.html").read_text()

    # Combine both HTMLs
    combined_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Weekly Vault Candidate Alerts - {datetime.now().strftime('%Y-%m-%d')}</title>
</head>
<body>
    <h1>📊 Weekly Vault Candidate Alerts</h1>
    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %I:%M %p')}</p>

    <hr style="margin: 30px 0; border: 2px solid #333;">

    {advisor_html}

    <hr style="margin: 50px 0; border: 3px solid #333;">

    {exec_html}
</body>
</html>
"""

    # Initialize Azure Communication Services
    connection_string = os.getenv("ACS_EMAIL_CONNECTION_STRING")
    if not connection_string:
        print("❌ ACS_EMAIL_CONNECTION_STRING not found in environment")
        sys.exit(1)

    client = EmailClient.from_connection_string(connection_string)

    # Email details
    recipients = [
        "steve@emailthewell.com",
        "brandon@emailthewell.com",
        "daniel.romitelli@emailthewell.com"
    ]

    print("="*70)
    print("📧 SENDING VAULT ALERTS (NO VALIDATION)")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print(f"Recipients: {len(recipients)}")
    print("="*70)

    for recipient in recipients:
        print(f"\n📤 Sending to {recipient}...")

        try:
            message = {
                "senderAddress": "DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net",
                "recipients": {
                    "to": [{"address": recipient}]
                },
                "content": {
                    "subject": f"🔔 Weekly Vault Candidate Alerts - {datetime.now().strftime('%b %d, %Y')}",
                    "html": combined_html
                }
            }

            poller = client.begin_send(message)
            result = poller.result()

            print(f"   ✅ Sent! Message ID: {result['id']}")
            print(f"   Status: {result['status']}")

        except Exception as e:
            print(f"   ❌ Failed: {e}")
            continue

    print("\n" + "="*70)
    print("✅ EMAIL DELIVERY COMPLETE")
    print("="*70)

if __name__ == "__main__":
    print("\n⚠️  WARNING: Security validation BYPASSED")
    print("⚠️  Ensure all violations have been manually verified and fixed\n")

    response = input("Continue with send? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Send cancelled")
        sys.exit(0)

    send_email_direct()
