#!/usr/bin/env python3
"""
Simple Test for Firecrawl v2 Supercharged Integration
Uses basic workflow without C³ cache complexity
"""

import os
import asyncio
import json
from dotenv import load_dotenv

load_dotenv('.env.local')

# Import the enhanced LangGraph manager
from app.langgraph_manager import EmailProcessingWorkflow

async def test_firecrawl_v2_integration():
    """Test Firecrawl v2 supercharged integration with simplified workflow"""

    print("=" * 80)
    print("🚀 TESTING FIRECRAWL V2 SUPERCHARGED INTEGRATION (SIMPLIFIED)")
    print("=" * 80)
    print("Testing with Kevin Sullivan email...")
    print("-" * 80)

    # Kevin Sullivan test email (same as before)
    test_email = {
        "sender_name": "Kevin Sullivan",
        "sender_email": "ksullivan@wealthconsultinggroup.com",
        "subject": "Experienced Financial Advisor - Boston Market",
        "body": """
        Hi,

        I'm Kevin Sullivan, a Senior Financial Advisor with Wealth Consulting Group.

        With over 10 years of experience in wealth management and financial planning,
        I've helped numerous high-net-worth clients achieve their financial goals.

        Currently based in Boston, MA, I'm interested in exploring opportunities
        with The Well.

        You can reach me at:
        Phone: (617) 555-1234
        Email: ksullivan@wealthconsultinggroup.com
        Website: www.wealthconsultinggroup.com

        Looking forward to discussing how my expertise can contribute to your team.

        Best regards,
        Kevin Sullivan
        Wealth Consulting Group
        """,
        "attachments": []
    }

    # Initialize processor
    processor = EmailProcessingWorkflow()

    # Process the email using BASIC method (no C³ cache complexity)
    print("\n📧 Processing email with basic workflow...")
    try:
        # Get domain from sender email
        sender_domain = test_email["sender_email"].split('@')[1]

        # Use the simpler process_email method
        result = await processor.process_email(
            email_body=test_email["body"],
            sender_domain=sender_domain,
            learning_hints=f"Sender: {test_email['sender_name']} <{test_email['sender_email']}>"
        )

        print("\n✅ EXTRACTION RESULTS:")
        print("-" * 60)

        # Check if we got extracted data (result is ExtractedData object)
        if result:
            print("\n📊 Company Record:")
            if hasattr(result, 'company_record') and result.company_record:
                company = result.company_record
                print(f"  Name: {getattr(company, 'company_name', 'N/A')}")
                print(f"  Domain: {getattr(company, 'company_domain', 'N/A')}")
                print(f"  💰 Revenue: {getattr(company, 'revenue', 'Not enriched')}")
                print(f"  👥 Employees: {getattr(company, 'employee_count', 'Not enriched')}")
                print(f"  💵 Funding: {getattr(company, 'funding', 'Not enriched')}")
                print(f"  🔧 Tech Stack: {getattr(company, 'tech_stack', 'Not enriched')}")
                print(f"  🏭 Industry: {getattr(company, 'industry', 'Not enriched')}")

                # Check if we have enrichment data
                enrichment_data = getattr(company, 'enrichment_data', None)
                if enrichment_data:
                    try:
                        if isinstance(enrichment_data, str):
                            enrichment = json.loads(enrichment_data)
                        else:
                            enrichment = enrichment_data

                        print(f"\n  📈 ENRICHMENT DATA FOUND:")
                        print(f"    - Revenue: {enrichment.get('revenue', 'N/A')}")
                        print(f"    - Employees: {enrichment.get('employee_count', 'N/A')}")
                        print(f"    - Funding: {enrichment.get('funding_total', 'N/A')}")
                        print(f"    - Tech Stack: {', '.join(enrichment.get('tech_stack', []))}")
                        print(f"    - Industry: {enrichment.get('industry', 'N/A')}")
                    except Exception as e:
                        print(f"    - Raw enrichment data: {enrichment_data}")
            else:
                print("  No company record found")

            print("\n👤 Contact Record:")
            if hasattr(result, 'contact_record') and result.contact_record:
                contact = result.contact_record
                first_name = getattr(contact, 'first_name', '')
                last_name = getattr(contact, 'last_name', '')
                print(f"  Name: {first_name} {last_name}")
                print(f"  Email: {getattr(contact, 'email', 'N/A')}")
                print(f"  Phone: {getattr(contact, 'phone', 'N/A')}")
                city = getattr(contact, 'city', '')
                state = getattr(contact, 'state', '')
                print(f"  Location: {city}, {state}")
            else:
                print("  No contact record found")

            print("\n💼 Deal Record:")
            if hasattr(result, 'deal_record') and result.deal_record:
                deal = result.deal_record
                print(f"  Deal Name: {getattr(deal, 'deal_name', 'N/A')}")
                print(f"  Stage: {getattr(deal, 'stage', 'N/A')}")
                print(f"  Source: {getattr(deal, 'source', 'N/A')}")
            else:
                print("  No deal record found")

        print("\n" + "=" * 80)
        print("🎯 INTEGRATION TEST RESULT:")
        print("=" * 80)

        # Check for Firecrawl v2 enrichment
        has_enrichment = False
        if (hasattr(result, 'company_record') and result.company_record and
            getattr(result.company_record, 'enrichment_data', None)):
            has_enrichment = True
            print("✅ FIRECRAWL V2 SUPERCHARGED IS WORKING!")
            print("   - Enhanced enrichment data successfully extracted")
            print("   - Revenue, employee, and funding data available")
        elif (hasattr(result, 'company_record') and result.company_record and
              (getattr(result.company_record, 'revenue', None) or getattr(result.company_record, 'employee_count', None))):
            has_enrichment = True
            print("✅ ENRICHMENT DATA FOUND!")
            print("   - Some enrichment data was extracted")

        if not has_enrichment:
            print("⚠️ Standard extraction only (enrichment may not be available)")
            print("   - This could be normal if the website doesn't have the data")
            print("   - Or if Firecrawl v2 module is not loaded")

        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run the simple integration test"""
    print("\n🚀 FIRECRAWL V2 SUPERCHARGED - SIMPLE INTEGRATION TEST\n")

    await test_firecrawl_v2_integration()

    print("\n✅ Simple integration testing complete!")
    print("\n💡 Note: This test uses the basic workflow without C³ cache")
    print("   If enrichment data is not showing:")
    print("   1. Check that app/firecrawl_v2_supercharged.py exists")
    print("   2. Verify FIRECRAWL_API_KEY is set in .env.local")
    print("   3. Some companies may not have public data available")


if __name__ == "__main__":
    asyncio.run(main())