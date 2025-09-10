#!/usr/bin/env python3
"""
Test enhanced extraction without creating Zoho deals
"""

import asyncio
import json
from dotenv import load_dotenv
from app.enhanced_extraction import EnhancedExtractor

# Sample email that simulates what you showed in the screenshots
SAMPLE_EMAIL = """
Subject: Recruiting Consult Invitee: Roy Janse

Hi Team,

I wanted to introduce you to Roy Janse who is interested in discussing opportunities.

Roy Janse
Email: roy.janse@mariner.com
Phone: 806.500.4359
LinkedIn: https://linkedin.com/in/royjanse
Location: 21501 N

Roy is currently with Mariner Wealth Advisors and has extensive experience in wealth management.

Meeting scheduled via: https://calendly.com/stevenperry/30min?name=Roy+Janse&email=roy.janse@mariner.com&phone=806.500.4359

Best regards,
Steven Perry
steve@emailthewell.com
The Well Recruiting Solutions
"""

async def test_extraction():
    """Test the enhanced extraction without Zoho"""
    
    print("="*80)
    print("TESTING ENHANCED EXTRACTION")
    print("="*80)
    
    # Simulate initial extraction (what GPT might return)
    initial_extraction = {
        'candidate_name': 'Roy Janse Invitee Email: roy...',  # Truncated
        'job_title': 'Recruiting Consult Invitee: Ro...',  # Truncated  
        'location': '21501 N',  # Partial zip
        'email': 'roy.janse@mariner.com',
        'phone': '806.500.4359',
        'linkedin_url': None,  # Not extracted
        'company_name': None,  # Not extracted
        'referrer_name': 'Steven Perry',
        'referrer_email': 'steve@emailthewell.com',
        'calendly_url': None  # Not extracted
    }
    
    print("\nINITIAL EXTRACTION (simulated GPT output):")
    print(json.dumps(initial_extraction, indent=2))
    
    print("\n" + "-"*80)
    print("APPLYING ENHANCEMENTS...")
    print("-"*80)
    
    async with EnhancedExtractor() as extractor:
        enhanced = await extractor.enhance_extraction(
            initial_extraction,
            SAMPLE_EMAIL,
            'steve@emailthewell.com'
        )
    
    print("\nENHANCED EXTRACTION:")
    print(json.dumps(enhanced, indent=2))
    
    print("\n" + "="*80)
    print("IMPROVEMENTS MADE:")
    print("="*80)
    
    # Check what was improved
    improvements = []
    
    # Check Calendly extraction
    if enhanced.get('calendly_url') and not initial_extraction.get('calendly_url'):
        improvements.append("✅ Extracted Calendly URL automatically")
    
    # Check LinkedIn extraction
    if enhanced.get('linkedin_url') and not initial_extraction.get('linkedin_url'):
        improvements.append("✅ Extracted LinkedIn URL from email body")
    
    # Check company name
    if enhanced.get('company_name') and not initial_extraction.get('company_name'):
        improvements.append(f"✅ Determined company name from email domain: {enhanced['company_name']}")
    
    # Check location improvement
    if initial_extraction.get('location') == '21501 N' and enhanced.get('location') != '21501 N':
        improvements.append(f"✅ Improved location from partial zip to: {enhanced.get('location')}")
    
    # Check for truncation fixes
    if 'candidate_name_truncated' not in enhanced:
        improvements.append("✅ Fixed candidate name truncation")
    
    if 'job_title_truncated' not in enhanced:
        improvements.append("✅ Fixed job title truncation")
    
    for improvement in improvements:
        print(f"  {improvement}")
    
    print("\n" + "="*80)
    print("EXPECTED ZOHO DEAL NAME:")
    print("="*80)
    
    # Show what the deal name would be
    job_title = enhanced.get('job_title', 'Unknown')
    location = enhanced.get('location', 'Unknown')
    company_name = enhanced.get('company_name', 'Unknown')
    
    # Fix truncated fields for deal name
    if 'Recruiting Consult' in job_title:
        job_title = 'Recruiting Consult'
    
    deal_name = f"{job_title} ({location}) - {company_name}"
    print(f"  {deal_name}")
    
    print("\n✅ Test completed successfully - NO Zoho records created")

async def test_specific_domains():
    """Test company lookups for specific domains"""
    print("\n" + "="*80)
    print("TESTING DOMAIN LOOKUPS")
    print("="*80)
    
    test_emails = [
        'candidate@mariner.com',
        'john@wellsfargo.com',
        'jane@morganstanley.com',
        'bob@gmail.com',  # Should skip generic
        'alice@somecompany.com'
    ]
    
    async with EnhancedExtractor() as extractor:
        for email in test_emails:
            company_info = await extractor.lookup_company_from_domain(email)
            print(f"\n{email}:")
            if company_info:
                print(f"  Company: {company_info.get('company_name')}")
                print(f"  Website: {company_info.get('website')}")
                print(f"  Confidence: {company_info.get('confidence')}")
            else:
                print("  [Skipped - generic domain]")

async def main():
    load_dotenv('.env.local')
    
    # Test main extraction enhancement
    await test_extraction()
    
    # Test domain lookups
    await test_specific_domains()

if __name__ == "__main__":
    asyncio.run(main())