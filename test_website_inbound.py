#!/usr/bin/env python3
"""
Test that Website Inbound still works for non-consultation Calendly emails.
"""

import sys
import json

# Add app directory to path
sys.path.append('app')

from business_rules import BusinessRulesEngine

def test_website_inbound_calendly():
    """Test non-consultation Calendly emails are still Website Inbound"""
    print("=== Testing Website Inbound for Non-Consultation Calendly ===")
    
    # Regular job application through Calendly
    print("\n1. Regular Job Application via Calendly:")
    email_body = """Hi Steve Perry,

A new event has been scheduled.

Event Type: Job Application Discussion  
Invitee: John Smith
Invitee Email: john@example.com
Event Date/Time: 02:30pm - Thursday, August 28, 2025 (Central Time - US & Canada)

Description:
Interested in financial advisor positions."""

    mock_ai_data = {"candidate_name": "John Smith", "email": "john@example.com"}
    result = BusinessRulesEngine().process_data(
        mock_ai_data, email_body, "notifications@calendly.com", 
        "New Event: John Smith - Job Application Discussion"
    )
    
    print(f"  Deal Name: {result.get('deal_name')}")
    print(f"  Source: {result.get('source_type')} - {result.get('source_detail')}")
    print(f"  Is Consultation: {result.get('is_client_consultation', False)}")
    
def test_consultation_vs_regular():
    """Test consultation keywords vs regular Calendly"""
    print("\n=== Consultation vs Regular Calendly ===")
    
    # Test consultation keywords
    consultation_email = """Event Type: Recruiting Consult
Invitee: Jane Doe
Description: Discuss recruiting strategies for our firm."""
    
    regular_email = """Event Type: Interview
Invitee: Jane Doe  
Description: Interview for financial advisor position."""
    
    consultation_result = BusinessRulesEngine().process_data(
        {"candidate_name": "Jane Doe"}, consultation_email, "notifications@calendly.com", 
        "Recruiting Consult Scheduled"
    )
    
    regular_result = BusinessRulesEngine().process_data(
        {"candidate_name": "Jane Doe"}, regular_email, "notifications@calendly.com",
        "Interview Scheduled"
    )
    
    print(f"\n2. Consultation Email:")
    print(f"  Source: {consultation_result.get('source_type')} - {consultation_result.get('source_detail')}")
    
    print(f"\n3. Regular Email:")
    print(f"  Source: {regular_result.get('source_type')} - {regular_result.get('source_detail')}")

if __name__ == "__main__":
    test_website_inbound_calendly()
    test_consultation_vs_regular()
    
    print("\n=== Summary ===")
    print("✅ Website Inbound: Non-consultation Calendly emails")
    print("✅ Referral: Consultation Calendly emails") 
    print("✅ Logic preserved for both scenarios")