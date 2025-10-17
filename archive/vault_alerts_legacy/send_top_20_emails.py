#!/usr/bin/env python3
"""
Send Top 20 Marketable Candidates - Vault Style

Sends vault-style cards (ready to forward to clients)
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from azure.communication.email import EmailClient

# Load environment
load_dotenv('.env.local')

# Get connection string
ACS_CONNECTION_STRING = os.getenv('ACS_EMAIL_CONNECTION_STRING')

if not ACS_CONNECTION_STRING:
    raise ValueError("ACS_EMAIL_CONNECTION_STRING not configured")


def send_email(subject: str, html_body: str, recipients: list) -> list:
    """Send email via Azure Communication Services."""
    email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)
    message_ids = []

    for recipient in recipients:
        message = {
            "senderAddress": "DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net",
            "recipients": {
                "to": [{"address": recipient}]
            },
            "content": {
                "subject": subject,
                "html": html_body
            }
        }

        poller = email_client.begin_send(message)
        result = poller.result()
        message_ids.append(result.get('id', 'N/A'))

    return message_ids


def main():
    """Send vault-style email."""
    print("="*70)
    print("📧 SENDING TOP 20 MARKETABLE CANDIDATES - VAULT STYLE")
    print("="*70)
    print()

    recipients = [
        "steve@emailthewell.com",
        "brandon@emailthewell.com",
        "daniel.romiteld@emailthewell.com"
    ]

    print(f"📬 Recipients: {len(recipients)}")
    for r in recipients:
        print(f"   • {r}")
    print()

    # Load vault-style HTML (20 candidates, ready to forward)
    print("📂 Loading vault-style cards email (20 candidates)...")
    vault_path = Path(__file__).parent / "top_20_vault_style.html"
    with open(vault_path, 'r', encoding='utf-8') as f:
        vault_html_original = f.read()
    print(f"   ✅ Loaded ({len(vault_html_original):,} characters)")

    # Add fun intro about the percussionist situation
    intro_note = """
    <div style="background: #fff9e6; border-left: 4px solid #ffa726; padding: 20px; margin: 20px 0; border-radius: 8px; font-family: Arial, sans-serif;">
        <h3 style="margin-top: 0; color: #e65100;">📝 Note from Daniel: Percussionist Fixed! 😄</h3>
        <p><strong>Steve, you weren't being messed with!</strong> 😂</p>
        <p>The candidate in question is a <strong>Financial Planning Professional</strong> (7 years, CFP® candidate, Series 65).
        The "Percussionist" title was an AI mishap — the system latched onto their background as a former music major
        and professional percussionist instead of their actual financial services role.</p>
        <p><strong>What I fixed:</strong></p>
        <ul>
            <li>✅ Changed title from "Percussionist Candidate Alert" to "Financial Planning Professional Candidate Alert"</li>
            <li>✅ Removed all scoring methodology and score displays (cleaner format for client forwarding)</li>
            <li>✅ Kept all 20 candidates with proper professional titles</li>
        </ul>
        <p style="margin-bottom: 0;"><em>This is the clean version ready to go. No more musical instruments in job titles! 🎵➡️💼</em></p>
    </div>
    """

    # Insert intro right after opening body tag
    if '<body>' in vault_html_original:
        parts = vault_html_original.split('<body>', 1)
        vault_html = parts[0] + '<body>' + intro_note + parts[1]
    else:
        vault_html = intro_note + vault_html_original

    print("\n" + "="*70)
    print("📧 Vault-Style Cards (Client-Ready) - WITH PERCUSSIONIST FIX NOTE")
    print("="*70)

    subject = f"🏆 Top 20 Most Marketable Vault Candidates (Fixed!) - {datetime.now().strftime('%B %d, %Y')}"
    print(f"\n📝 Subject: {subject}")
    print("📋 Content: 20 candidate cards in vault alert format")
    print("🎯 Purpose: Ready to forward to clients/partners")
    print()

    # Send vault-style email
    print("📤 Sending email...")
    try:
        message_ids = send_email(subject, vault_html, recipients)
        print(f"✅ Email sent successfully!")
        print(f"   Message IDs: {message_ids}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        sys.exit(1)

    print("\n" + "="*70)
    print("✅ EMAIL SENT SUCCESSFULLY")
    print("="*70)


if __name__ == "__main__":
    main()
