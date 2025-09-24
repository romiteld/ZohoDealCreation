#!/usr/bin/env python3
"""
API Diagnostic Test - Tests the /intake/email endpoint with detailed error reporting
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def test_intake_email():
    """Test the intake/email endpoint with the Calendly email data"""
    
    api_url = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
    api_key = os.getenv('API_KEY')
    
    # Test email data based on the Calendly screenshot
    test_payload = {
        "sender_name": "calendly.com",
        "sender_email": "notifications@calendly.com",
        "subject": "Event Scheduled: Tim Koski and Steve Perry - Wed Sep 25, 2025 3:00pm - 3:45pm (CDT) (daniel.romitelli@emailthewell.com)",
        "body": """Hi Daniel Romitelli,

A new event has been scheduled.

Event Type: Meet n Greet

Invitee: Tim Koski
Invitee Email: tim.koski@everpar.com

Event Date/Time: 3:00pm - 3:45pm (America/Chicago) on Wednesday, September 25, 2025

Event Location: Phone call
Steve will call the number provided after reviewing the questionnaire.

Invitee Phone Number: +1 918-237-1276

Additional notes:

Looking to learn about the TheWell. Not sure if I need your services but I do have an idea of what I'm looking for in the future.

Plan to hire 2 new lead advisors as soon as possible. I have a preliminary offer out to one at this time. Then hire a third CSA in 2026. Then hire two associate advisors in 2027. Then hire another lead advisor, probably in 2028.

Currently in Tulsa, planning to open up a 2nd office OKC, and potentially a 3rd office in Bentonville area.

Best of luck on your search!

Questions and Answers:
Firm Name: Everpar
Website: Everpar.com
How long have you been in business? N/A
Positions interested in recruiting for: Lead Advisor
Office location: Tulsa""",
        "received_date": datetime.utcnow().isoformat(),
        "attachments": [],
        # Include the structured user_corrections as the frontend would send
        "user_corrections": {
            "company_record": {
                "company_name": "Everpar",
                "phone": "",  # To be enriched
                "website": "https://everpar.com",
                "detail": "Steve Perry",
                "source": "Website Inbound",
                "source_detail": "Calendly scheduling",
                "who_gets_credit": "BD Rep"
            },
            "contact_record": {
                "first_name": "Tim",
                "last_name": "Koski",
                "email": "tim.koski@everpar.com",
                "phone": "+1 918-237-1276",
                "city": "Tulsa",
                "state": "OK"
            },
            "deal_record": {
                "source": "Website Inbound",
                "deal_name": "Lead Advisor (Tulsa) - Everpar",
                "pipeline": "Recruitment",
                "closing_date": "2026-01-01",  # Estimated
                "description_of_reqs": "Plan to hire 2 new lead advisors as soon as possible. I have a preliminary offer out to one at this time. Then hire a third CSA in 2026. Then hire two associate advisors in 2027. Then hire another lead advisor, probably in 2028."
            }
        },
        # Add dry_run flag to prevent actual Zoho record creation
        "dry_run": True
    }
    
    print("=" * 80)
    print("🧪 API Diagnostic Test - Testing /intake/email endpoint")
    print("=" * 80)
    print(f"\n📍 API URL: {api_url}/intake/email")
    print(f"🔑 API Key: {'Present' if api_key else 'MISSING!'}")
    print("\n📧 Test Email: Calendly event from Tim Koski")
    print("\n🔄 Making API request with dry_run=True...")
    
    try:
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{api_url}/intake/email",
            headers=headers,
            json=test_payload,
            timeout=30
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers:")
        for key, value in response.headers.items():
            if key.lower() not in ['date', 'server']:
                print(f"   {key}: {value}")
        
        # Try to parse response
        try:
            response_data = response.json()
            print(f"\n📄 Response Body:")
            print(json.dumps(response_data, indent=2))
            
            if response.status_code == 200:
                print("\n✅ SUCCESS: API processed the request")
                if 'zoho_ids' in response_data:
                    print("\n🎯 Zoho IDs that would be created:")
                    for key, value in response_data['zoho_ids'].items():
                        print(f"   {key}: {value}")
                        
            elif response.status_code == 500:
                print("\n❌ ERROR 500: Internal Server Error")
                if 'error' in response_data:
                    print(f"   Error: {response_data['error']}")
                if 'message' in response_data:
                    print(f"   Message: {response_data['message']}")
                if 'details' in response_data:
                    print(f"   Details: {response_data['details']}")
                    
        except json.JSONDecodeError:
            print(f"\n❌ Could not parse JSON response")
            print(f"Raw Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("\n❌ ERROR: Request timed out after 30 seconds")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API")
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        
    print("\n" + "=" * 80)
    print("🔍 Diagnostic Summary:")
    print("1. Check if API_KEY is set in .env.local")
    print("2. Verify Container App is running latest revision")
    print("3. Check Application Insights for detailed errors")
    print("4. Review /app/main.py error handling for 'Transaction failed' message")
    print("=" * 80)

if __name__ == "__main__":
    test_intake_email()