#!/usr/bin/env python3
"""
Test all email patterns with updated business rules.
"""

import sys
import json

# Add app directory to path
sys.path.append('app')

from business_rules import BusinessRulesEngine

def test_pattern_1_consultation():
    """Test Calendly consultation emails (potential clients)"""
    print("=== Testing Pattern 1: Calendly Consultation Emails ===")
    
    # Jerry Fetta example
    print("\n1. Jerry Fetta:")
    email_body = """Hi Steve Perry,

A new event has been scheduled.

Event Type: Recruiting Consult
Invitee: Jerry Fetta
Invitee Email: jerry@jerryfetta.com
Event Date/Time: 02:30pm - Thursday, August 28, 2025 (Central Time - US & Canada)

Description:
Who We Are: The Well Recruiting Solutions—your partner in finding and hiring top-tier talent."""

    mock_ai_data = {"candidate_name": "Jerry Fetta", "email": "jerry@jerryfetta.com"}
    result = BusinessRulesEngine().process_data(
        mock_ai_data, email_body, "notifications@calendly.com", 
        "New Event: Jerry Fetta - 02:30pm Thu, Aug 28, 2025 - Recruiting Consult"
    )
    
    print(f"  Deal Name: {result.get('deal_name')}")
    print(f"  Source: {result.get('source_type')} - {result.get('source_detail')}")
    print(f"  Is Consultation: {result.get('is_client_consultation', False)}")
    print(f"  Referrer: {result.get('referrer')}")

def test_pattern_2_manual_internal():
    """Test manual internal referrals (candidates)"""
    print("\n=== Testing Pattern 2: Manual Internal Referrals ===")
    
    # Brad Lineberger example
    print("\n2. Brad Lineberger:")
    email_body = """Brad lineberger seaside wealth management
Reverse recruiting referral from advisors excel
Cell phone Is 760-470-2429"""

    mock_ai_data = {
        "candidate_name": "Brad Lineberger", 
        "company_name": "Seaside Wealth Management",
        "job_title": "Financial Advisor",
        "location": "Unknown Location"
    }
    result = BusinessRulesEngine().process_data(
        mock_ai_data, email_body, "steve@emailthewell.com", ""
    )
    
    print(f"  Deal Name: {result.get('deal_name')}")
    print(f"  Source: {result.get('source_type')} - {result.get('source_detail')}")
    print(f"  Is Consultation: {result.get('is_client_consultation', False)}")
    print(f"  Referrer: {result.get('referrer')}")

def test_pattern_3_external_referral():
    """Test external referral emails (candidates)"""
    print("\n=== Testing Pattern 3: External Referral Emails ===")
    
    # Reid Abedeen example
    print("\n3. Reid Abedeen:")
    email_body = """New deal
Reid abedeen
Owns safeguard investment advisory group
949-278-8316
Referral from josh whitehead
See notes below"""

    mock_ai_data = {
        "candidate_name": "Reid Abedeen",
        "company_name": "Safeguard Investment Advisory Group", 
        "job_title": "Financial Advisor",
        "location": "Unknown Location"
    }
    result = BusinessRulesEngine().process_data(
        mock_ai_data, email_body, "josh.whitehead@advisorsexcel.com", 
        "FW: AZ candidates - \"The Well\""
    )
    
    print(f"  Deal Name: {result.get('deal_name')}")
    print(f"  Source: {result.get('source_type')} - {result.get('source_detail')}")
    print(f"  Is Consultation: {result.get('is_client_consultation', False)}")
    print(f"  Referrer: {result.get('referrer')}")

if __name__ == "__main__":
    test_pattern_1_consultation()
    test_pattern_2_manual_internal() 
    test_pattern_3_external_referral()
    
    print("\n=== Summary ===")
    print("Pattern 1 (Consultations): Potential CLIENTS for recruiting services")
    print("Pattern 2 & 3 (Referrals): CANDIDATES for job placement")
    print("\nShould consultation emails be classified as 'Referral' instead of 'Website Inbound'?")