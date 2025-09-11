#!/usr/bin/env python3
"""
Test business rules with Jerry Fetta consultation email.
"""

import sys
import json

# Add app directory to path
sys.path.append('app')

from business_rules import BusinessRulesEngine

def test_jerry_fetta():
    print("Testing Jerry Fetta consultation email parsing...")
    
    # Jerry Fetta email content
    email_body = """Hi Steve Perry,

A new event has been scheduled.

Event Type: Recruiting Consult
Invitee: Jerry Fetta
Invitee Email: jerry@jerryfetta.com
Event Date/Time: 02:30pm - Thursday, August 28, 2025 (Central Time - US & Canada)

Description:
Who We Are: The Well Recruiting Solutions—your partner in finding and hiring top-tier talent.

What We'll Do: Discuss your specific recruiting goals, share proven strategies, and map out a plan to build your ideal team.

Our Approach: A refreshing, personalized experience focused on understanding your unique needs and setting you up for long-term hiring success.

Next Steps: Book a time that works for you, and we'll tackle your recruiting challenges together.

Location: This is a Zoom web conference."""

    subject = "New Event: Jerry Fetta - 02:30pm Thu, Aug 28, 2025 - Recruiting Consult"
    sender_email = "notifications@calendly.com"
    
    # Mock AI extracted data (what AI would extract from this email)
    mock_ai_data = {
        "candidate_name": "Jerry Fetta",  # In consultation emails, this is the client name
        "email": "jerry@jerryfetta.com",
        "company_name": None,  # Not explicitly mentioned
        "job_title": None,
        "location": None,
        "referrer": None
    }
    
    # Test business rules
    rules_engine = BusinessRulesEngine()
    result = rules_engine.process_data(mock_ai_data, email_body, sender_email, subject)
    
    print("Business Rules Result:")
    print(json.dumps(result, indent=2))
    
    print("\nKey Results:")
    print(f"- Is Client Consultation: {result.get('is_client_consultation', False)}")
    print(f"- Deal Name: {result.get('deal_name')}")
    print(f"- Source Type: {result.get('source_type')}")
    print(f"- Source Detail: {result.get('source_detail')}")
    print(f"- Contact Name: {result.get('candidate_name')}")
    print(f"- Email: {result.get('email')}")
    print(f"- Company: {result.get('company_name')}")

if __name__ == "__main__":
    test_jerry_fetta()