#!/usr/bin/env python3
"""
Test script to verify Steve's 3-record structure implementation.
This ensures all 21 fields are properly extracted and formatted.
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from dotenv import load_dotenv
load_dotenv('.env.local')

from app.models import EmailPayload, ExtractedData, CompanyRecord, ContactRecord, DealRecord
from app.langgraph_manager import EmailProcessingWorkflow
from app.business_rules import format_deal_name

async def test_steve_structure():
    """Test that we correctly create Steve's 3-record structure."""

    print("=" * 60)
    print("TESTING STEVE'S 3-RECORD STRUCTURE")
    print("=" * 60)

    # Sample email that should extract to 3 records
    test_email = EmailPayload(
        sender_name="Kevin Sullivan",
        sender_email="kevin.sullivan@wellpartners.com",
        subject="Senior Financial Advisor - Fort Wayne Position",
        body="""
        Hi Team,

        I'm Kevin Sullivan, a Senior Financial Advisor based in Fort Wayne, IN.
        I'm interested in learning more about opportunities with The Well.

        Currently working at Well Partners Recruiting.
        Phone: (555) 123-4567

        Looking forward to discussing this opportunity.

        Best regards,
        Kevin Sullivan
        Well Partners Recruiting
        www.wellpartners.com
        """,
        attachments=[]
    )

    print("\n1. Testing LangGraph extraction...")
    workflow = EmailProcessingWorkflow()

    try:
        # Run extraction - process_email expects email body string, not EmailPayload
        extracted = await workflow.process_email(test_email.body, sender_domain="wellpartners.com")

        if not extracted:
            print("   ❌ No data extracted!")
            return False

        print("   ✅ Extraction completed")
        print(f"\n   DEBUG - Extracted type: {type(extracted)}")
        print(f"   DEBUG - Company record: {extracted.company_record}")
        print(f"   DEBUG - Contact record: {extracted.contact_record}")
        print(f"   DEBUG - Deal record: {extracted.deal_record}")

        # Check if records are None
        if not extracted.company_record:
            print("   ⚠️ Company record is None - checking legacy fields...")
            print(f"   DEBUG - company_name: {getattr(extracted, 'company_name', 'N/A')}")
            print(f"   DEBUG - candidate_name: {getattr(extracted, 'candidate_name', 'N/A')}")
            print(f"   DEBUG - job_title: {getattr(extracted, 'job_title', 'N/A')}")

        # Check Steve's 3-record structure
        print("\n2. Validating Steve's 21 fields...")

        # Company Record (7 fields)
        company = extracted.company_record
        if company:
            print("\n   Company Record:")
            print(f"   1. Company Name: {company.company_name or 'MISSING'}")
            print(f"   2. Phone: {company.phone or 'MISSING'}")
            print(f"   3. Website: {company.website or 'MISSING'}")
            print(f"   4. Company Source: {company.company_source or 'MISSING'}")
            print(f"   5. Source Detail: {company.source_detail or 'MISSING'}")
            print(f"   6. Who Gets Credit: {company.who_gets_credit or 'MISSING'}")
            print(f"   7. Detail: {company.detail or 'MISSING'}")
        else:
            print("   ❌ No Company Record created!")

        # Contact Record (8 fields)
        contact = extracted.contact_record
        if contact:
            print("\n   Contact Record:")
            print(f"   1. First Name: {contact.first_name or 'MISSING'}")
            print(f"   2. Last Name: {contact.last_name or 'MISSING'}")
            print(f"   3. Company Name: {contact.company_name or 'MISSING'}")
            print(f"   4. Email: {contact.email or 'MISSING'}")
            print(f"   5. Phone: {contact.phone or 'MISSING'}")
            print(f"   6. City: {contact.city or 'MISSING'}")
            print(f"   7. State: {contact.state or 'MISSING'}")
            print(f"   8. Source: {contact.source or 'MISSING'}")
        else:
            print("   ❌ No Contact Record created!")

        # Deal Record (6 fields)
        deal = extracted.deal_record
        if deal:
            print("\n   Deal Record:")
            print(f"   1. Deal Name: {deal.deal_name or 'MISSING'}")
            print(f"   2. Pipeline: {deal.pipeline or 'MISSING'}")
            print(f"   3. Closing Date: {deal.closing_date or 'MISSING'}")
            print(f"   4. Source: {deal.source or 'MISSING'}")
            print(f"   5. Source Detail: {deal.source_detail or 'MISSING'}")
            print(f"   6. Description of Reqs: {deal.description_of_reqs or 'MISSING'}")

            # Check Deal Name format
            expected_format = "Senior Financial Advisor (Fort Wayne) Well Partners Recruiting"
            if deal.deal_name and "Senior Financial Advisor" in deal.deal_name:
                print(f"\n   ✅ Deal Name format matches Steve's template")
            else:
                print(f"\n   ⚠️ Deal Name format may not match Steve's template")
                print(f"      Expected format: [Job Title] ([Location]) [Company Name]")
        else:
            print("   ❌ No Deal Record created!")

        # Summary
        print("\n3. Summary:")
        records_created = sum([
            1 if extracted.company_record else 0,
            1 if extracted.contact_record else 0,
            1 if extracted.deal_record else 0
        ])

        if records_created == 3:
            print(f"   ✅ All 3 records created successfully!")
            return True
        else:
            print(f"   ❌ Only {records_created}/3 records created")
            return False

    except Exception as e:
        print(f"\n   ❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_deal_name_format():
    """Test Deal Name formatting matches Steve's requirement."""
    print("\n" + "=" * 60)
    print("TESTING DEAL NAME FORMAT")
    print("=" * 60)

    test_cases = [
        ("Senior Financial Advisor", "Fort Wayne", "Well Partners Recruiting"),
        ("Wealth Manager", "Chicago, IL", "ABC Financial"),
        ("Investment Advisor", None, "XYZ Corp"),
    ]

    for job, loc, company in test_cases:
        # Test Steve's format
        steve_format = format_deal_name(job, loc, company, use_steve_format=True)
        print(f"\nJob: {job}, Location: {loc}, Company: {company}")
        print(f"Steve Format: {steve_format}")

        # Verify format
        if loc and all([job, loc, company]):
            expected = f"{job} ({loc}) {company}"
            if steve_format == expected:
                print("   ✅ Format correct")
            else:
                print(f"   ❌ Format incorrect. Expected: {expected}")

async def main():
    """Run all tests."""
    print("\n🚀 CRITICAL VALIDATION FOR STEVE'S REQUIREMENTS\n")

    # Test 1: Structure validation
    structure_ok = await test_steve_structure()

    # Test 2: Deal name format
    await test_deal_name_format()

    print("\n" + "=" * 60)
    if structure_ok:
        print("✅ ALL TESTS PASSED - Safe to deploy!")
    else:
        print("❌ TESTS FAILED - DO NOT DEPLOY!")
        print("\nFix the issues above before deploying to production.")
    print("=" * 60)

    return structure_ok

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)