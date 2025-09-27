#!/usr/bin/env python3
"""
Test script for financial advisor data extraction
Tests the enhanced LangGraph workflow with financial advisor specific fields
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
except ImportError:
    print("Note: dotenv not available, using environment variables")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test email samples with financial advisor data
FINANCIAL_ADVISOR_EMAILS = [
    {
        "name": "Senior Wealth Manager - High AUM",
        "sender_email": "recruiter@talentfirm.com",
        "sender_domain": "talentfirm.com",
        "body": """
Dear Hiring Manager,

I am pleased to present Michael Thompson, an exceptional Senior Financial Advisor
with substantial assets under management.

Candidate Profile:
Name: Michael Thompson
Current Position: VP Wealth Management at Morgan Stanley
Email: michael.thompson@morganstanley.com
Phone: (312) 555-9876
Experience: 15 years in financial services
AUM: $350M under management
Annual Production: $1.2M
Client Base: 180 high-net-worth clients
Location: Chicago, IL
Education: MBA Finance, Northwestern Kellogg

Professional Credentials:
• Series 7, 66, and Life Insurance licenses
• CFA Charterholder
• CFP designation

Michael has consistently exceeded his targets with a 97% client retention rate.
He's seeking a new opportunity with a growing independent firm offering more
entrepreneurial freedom.

Key Accomplishments:
• Top 5% producer nationally for 3 consecutive years
• Specialized in high-net-worth estate planning
• Strong alternative investment expertise
• 85% of book transferable

Availability: 30 days notice
Compensation Expectations: $650K-$750K total compensation

Best regards,
Jennifer Recruiter
Senior Executive Recruiter
"""
    },
    {
        "name": "Portfolio Manager - Mid-Level",
        "sender_email": "lisa@executivesearch.com",
        "sender_domain": "executivesearch.com",
        "body": """
Good morning,

I have an excellent Portfolio Manager candidate for your investment advisory team.

CANDIDATE PROFILE: Emily Chen
• Current: JPMorgan Private Bank
• Experience: 14 years in wealth management
• AUM: $220M managed
• Production: $850K annually
• Clients: 125 households
• Location: Chicago
• Compensation: $425K base + bonus
• Education: CFA, University of Chicago Booth

Licenses & Designations:
- Series 7, 66, 65
- CFA Charter
- CAIA (Alternative Investment Analyst)

Specializations:
• High-net-worth portfolio management
• Alternative investments (private equity, hedge funds)
• Estate and trust planning
• Tax-efficient investing

Emily is available immediately and looking for $500K-$600K total compensation.
90% of her book is expected to transfer.

Please let me know if you'd like to schedule an interview.

Best regards,
Lisa Chen
Executive Search Consultant
"""
    },
    {
        "name": "Direct Application - Entry Level Advisor",
        "sender_email": "david.rodriguez@gmail.com",
        "sender_domain": "gmail.com",
        "body": """
Dear The Well Partners Hiring Team,

I am writing to express my strong interest in the Financial Advisor position.
With 8 years of experience at Edward Jones, I have built a solid foundation
in wealth management.

My Background:
• 8 years at Edward Jones as Financial Advisor
• $125M in assets under management
• 95 client households
• Annual production: $380K
• Consistent top performer (President's Club 4 years)
• Series 7, 66, and Life & Health insurance licenses
• Bachelor's in Finance from DePaul University

My client retention rate is 96% and I specialize in:
- Retirement planning for professionals
- 401(k) rollovers and IRA management
- Insurance and risk management
- College funding strategies

I am available with 45 days notice and seeking $300K-$400K total compensation.
Approximately 80% of my book would be transferable.

Thank you for your consideration.

Sincerely,
David Rodriguez
(312) 555-9876
david.rodriguez@gmail.com
"""
    }
]

async def test_financial_advisor_extraction():
    """Test the enhanced LangGraph extraction for financial advisor data"""

    try:
        from app.langgraph_manager import EmailProcessingWorkflow

        # Initialize the workflow
        workflow = EmailProcessingWorkflow()
        logger.info("LangGraph workflow initialized successfully")

        results = []

        for i, test_email in enumerate(FINANCIAL_ADVISOR_EMAILS):
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing Email {i+1}: {test_email['name']}")
            logger.info(f"{'='*60}")

            try:
                # Process the email
                extracted_data = await workflow.process_email(
                    email_body=test_email['body'],
                    sender_domain=test_email['sender_domain']
                )

                # Print results
                print(f"\n--- EXTRACTION RESULTS for {test_email['name']} ---")

                # Financial advisor specific fields
                fa_fields = [
                    'aum_managed', 'production_annual', 'client_count',
                    'licenses_held', 'designations', 'years_experience',
                    'availability_timeframe', 'compensation_range',
                    'book_transferable', 'specializations'
                ]

                print("\nFINANCIAL ADVISOR FIELDS:")
                for field in fa_fields:
                    value = getattr(extracted_data, field, None)
                    if value:
                        print(f"  {field}: {value}")

                # Core contact info
                print("\nCORE CONTACT INFO:")
                if extracted_data.contact_record:
                    print(f"  Name: {extracted_data.contact_record.first_name} {extracted_data.contact_record.last_name}")
                    print(f"  Email: {extracted_data.contact_record.email}")
                    print(f"  Phone: {extracted_data.contact_record.phone}")
                    print(f"  Location: {extracted_data.contact_record.city}, {extracted_data.contact_record.state}")

                # Company info
                print("\nCOMPANY INFO:")
                if extracted_data.company_record:
                    print(f"  Company: {extracted_data.company_record.company_name}")
                    print(f"  Website: {extracted_data.company_record.website}")

                # Deal info
                print("\nDEAL INFO:")
                if extracted_data.deal_record:
                    print(f"  Deal Name: {extracted_data.deal_record.deal_name}")
                    print(f"  Source: {extracted_data.deal_record.source}")
                    print(f"  Description: {extracted_data.deal_record.description_of_reqs}")

                results.append({
                    'test_name': test_email['name'],
                    'success': True,
                    'extracted_data': extracted_data
                })

            except Exception as e:
                logger.error(f"Failed to process email {i+1}: {e}")
                results.append({
                    'test_name': test_email['name'],
                    'success': False,
                    'error': str(e)
                })

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        successful = sum(1 for r in results if r['success'])
        total = len(results)

        print(f"Successful extractions: {successful}/{total}")

        for result in results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  {status} {result['test_name']}")
            if not result['success']:
                print(f"    Error: {result['error']}")

        return results

    except Exception as e:
        logger.error(f"Test setup failed: {e}")
        return []

async def test_bullet_generation():
    """Test the enhanced bullet point generation for financial advisors"""

    try:
        from app.jobs.talentwell_curator import TalentWellCurator

        curator = TalentWellCurator()
        logger.info("TalentWell curator initialized successfully")

        # Mock deal data with financial advisor information
        mock_deal = {
            'job_title': 'Senior Financial Advisor',
            'company_name': 'Morgan Stanley',
            'book_size_aum': '$350M',
            'production_12mo': '$1.2M',
            'professional_designations': 'Series 7, 66, CFA',
            'when_available': '30 days notice',
            'desired_comp': '$650K-$750K'
        }

        # Mock enhanced data from extraction
        enhanced_data = {
            'aum_managed': '$350M',
            'production_annual': '$1.2M',
            'client_count': '180 clients',
            'licenses_held': ['Series 7', 'Series 66', 'Life Insurance'],
            'designations': ['CFA', 'CFP'],
            'years_experience': '15 years',
            'availability_timeframe': '30 days notice',
            'compensation_range': '$650K-$750K',
            'specializations': ['High-net-worth', 'Estate planning', 'Alternative investments']
        }

        print(f"\n{'='*60}")
        print("TESTING BULLET POINT GENERATION")
        print(f"{'='*60}")

        # Generate bullets
        bullets = await curator._generate_hard_skill_bullets(
            deal=mock_deal,
            enhanced_data=enhanced_data,
            transcript=None
        )

        print(f"\nGenerated {len(bullets)} bullet points:")
        for i, bullet in enumerate(bullets, 1):
            print(f"  {i}. {bullet.text} (confidence: {bullet.confidence}, source: {bullet.source})")

        # Test minimum bullets
        min_bullets = await curator._ensure_minimum_bullets(mock_deal, bullets)

        if len(min_bullets) > len(bullets):
            print(f"\nAdded {len(min_bullets) - len(bullets)} minimum bullets:")
            for bullet in min_bullets[len(bullets):]:
                print(f"  • {bullet.text} (confidence: {bullet.confidence}, source: {bullet.source})")

        return bullets

    except Exception as e:
        logger.error(f"Bullet generation test failed: {e}")
        return []

async def main():
    """Main test runner"""
    print("Starting Financial Advisor Extraction Tests...")

    # Test 1: Email extraction
    extraction_results = await test_financial_advisor_extraction()

    # Test 2: Bullet generation
    bullet_results = await test_bullet_generation()

    print(f"\n{'='*60}")
    print("ALL TESTS COMPLETED")
    print(f"{'='*60}")

    if extraction_results:
        successful_extractions = sum(1 for r in extraction_results if r['success'])
        print(f"Email Extraction: {successful_extractions}/{len(extraction_results)} passed")

    if bullet_results:
        print(f"Bullet Generation: {len(bullet_results)} bullets generated")

    return extraction_results, bullet_results

if __name__ == "__main__":
    asyncio.run(main())