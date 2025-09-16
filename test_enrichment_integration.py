#!/usr/bin/env python3
"""
Test Firecrawl v2 Supercharged Integration with Kevin Sullivan Example
"""

import os
import asyncio
import json
from dotenv import load_dotenv

load_dotenv('.env.local')

# Import the enhanced LangGraph manager
from app.langgraph_manager import EmailProcessingWorkflow

async def test_kevin_sullivan():
    """Test with Kevin Sullivan email that mentions Wealth Consulting Group"""

    print("=" * 80)
    print("🚀 TESTING FIRECRAWL V2 SUPERCHARGED INTEGRATION")
    print("=" * 80)
    print("Testing with Kevin Sullivan email...")
    print("-" * 80)

    # Kevin Sullivan test email
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

    # Process the email
    print("\n📧 Processing email...")
    try:
        # Get domain from sender email
        sender_domain = test_email["sender_email"].split('@')[1]

        # Process with the workflow
        result = await processor.process_email_with_learning(
            email_body=test_email["body"],
            sender_domain=sender_domain,
            learning_hints=f"Sender: {test_email['sender_name']} <{test_email['sender_email']}>"
        )

        print("\n✅ EXTRACTION RESULTS:")
        print("-" * 60)

        # Check if we got enriched data
        if result and result.get("extraction_result"):
            extracted = result["extraction_result"]

            # Company record
            if extracted.get("company_record"):
                company = extracted["company_record"]
                print("\n📊 Company Record:")
                print(f"  Name: {company.get('company_name')}")
                print(f"  Domain: {company.get('company_domain')}")
                print(f"  💰 Revenue: {company.get('revenue', 'Not enriched')}")
                print(f"  👥 Employees: {company.get('employee_count', 'Not enriched')}")
                print(f"  💵 Funding: {company.get('funding', 'Not enriched')}")
                print(f"  🔧 Tech Stack: {company.get('tech_stack', 'Not enriched')}")

                # Check for enrichment data
                if company.get('enrichment_data'):
                    try:
                        enrichment = json.loads(company['enrichment_data'])
                        print(f"\n  📈 ENRICHMENT DATA FOUND:")
                        print(f"    - Revenue: {enrichment.get('revenue')}")
                        print(f"    - Employees: {enrichment.get('employees')}")
                        print(f"    - Funding: {enrichment.get('funding')}")
                        print(f"    - Valuation: {enrichment.get('valuation')}")
                        print(f"    - Industry: {enrichment.get('industry')}")
                        print(f"    - Products: {', '.join(enrichment.get('products', []))}")
                    except:
                        pass

            # Contact record
            if extracted.get("contact_record"):
                contact = extracted["contact_record"]
                print("\n👤 Contact Record:")
                print(f"  Name: {contact.get('first_name')} {contact.get('last_name')}")
                print(f"  Email: {contact.get('email')}")
                print(f"  Phone: {contact.get('phone')}")
                print(f"  Location: {contact.get('city')}, {contact.get('state')}")

            # Deal record
            if extracted.get("deal_record"):
                deal = extracted["deal_record"]
                print("\n💼 Deal Record:")
                print(f"  Deal Name: {deal.get('deal_name')}")
                print(f"  Stage: {deal.get('stage')}")
                print(f"  Source: {deal.get('source')}")

        # Check company research
        if result.get("company_research"):
            research = result["company_research"]
            print("\n🔍 Company Research:")
            print(f"  Enrichment Source: {research.get('enrichment_source', 'standard')}")
            if research.get('revenue'):
                print(f"  ✅ Revenue Data: {research.get('revenue')}")
            if research.get('employee_count'):
                print(f"  ✅ Employee Count: {research.get('employee_count')}")
            if research.get('funding_total'):
                print(f"  ✅ Total Funding: {research.get('funding_total')}")
            if research.get('valuation'):
                print(f"  ✅ Valuation: {research.get('valuation')}")
            if research.get('tech_stack'):
                print(f"  ✅ Tech Stack: {', '.join(research.get('tech_stack', []))}")
            if research.get('industry'):
                print(f"  ✅ Industry: {research.get('industry')}")

        print("\n" + "=" * 80)
        print("🎯 INTEGRATION TEST RESULT:")
        print("=" * 80)

        # Determine if enrichment worked
        has_enrichment = False
        if result.get("company_research"):
            research = result["company_research"]
            if research.get('enrichment_source') == 'firecrawl_v2_supercharged':
                has_enrichment = True
                print("✅ FIRECRAWL V2 SUPERCHARGED IS WORKING!")
                print("   - Enhanced enrichment data successfully extracted")
                print("   - Revenue, employee, and funding data available")
            elif research.get('revenue') or research.get('employee_count'):
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


async def test_jerry_fetta():
    """Test with Jerry Fetta email"""

    print("\n" + "=" * 80)
    print("Testing with Jerry Fetta email...")
    print("-" * 80)

    # Jerry Fetta test email
    test_email = {
        "sender_name": "Jerry Fetta",
        "sender_email": "info@jerryfetta.com",
        "subject": "Financial Education Expert Available",
        "body": """
        Hello,

        I'm Jerry Fetta, CEO and Founder of Wealth DynaM(X).

        I specialize in financial education and wealth management strategies
        that help individuals build lasting wealth.

        My company information:
        - Company: Wealth DynaM(X) / Fetta Financial Alliance
        - Website: https://wealthdynamx.com
        - Phone: 505-397-6020
        - Email: info@jerryfetta.com

        I'm interested in discussing partnership opportunities with The Well.

        Best regards,
        Jerry Fetta
        CEO & Founder
        Wealth DynaM(X)
        """,
        "attachments": []
    }

    # Initialize processor
    processor = EmailProcessingWorkflow()

    # Process the email
    print("\n📧 Processing email...")
    try:
        # Get domain from sender email
        sender_domain = test_email["sender_email"].split('@')[1]

        # Process with the workflow
        result = await processor.process_email_with_learning(
            email_body=test_email["body"],
            sender_domain=sender_domain,
            learning_hints=f"Sender: {test_email['sender_name']} <{test_email['sender_email']}>"
        )

        print("\n✅ EXTRACTION RESULTS:")
        print("-" * 60)

        # Check if we got enriched data
        if result and result.get("extraction_result"):
            extracted = result["extraction_result"]

            # Company record
            if extracted.get("company_record"):
                company = extracted["company_record"]
                print("\n📊 Company Record:")
                print(f"  Name: {company.get('company_name')}")
                print(f"  💰 Revenue: {company.get('revenue', 'Not enriched')}")
                print(f"  👥 Employees: {company.get('employee_count', 'Not enriched')}")
                print(f"  🏭 Industry: {company.get('industry', 'Not enriched')}")

        # Check company research
        if result.get("company_research"):
            research = result["company_research"]
            print("\n🔍 Company Research:")
            if research.get('enrichment_source') == 'firecrawl_v2_supercharged':
                print("  ✅ Using Firecrawl v2 Supercharged!")
            print(f"  Industry: {research.get('industry', 'Not found')}")
            print(f"  Products: {', '.join(research.get('products', []))[:100] if research.get('products') else 'Not found'}")

    except Exception as e:
        print(f"\n❌ Error during processing: {e}")


async def main():
    """Run all tests"""
    print("\n🚀 FIRECRAWL V2 SUPERCHARGED - INTEGRATION TESTING\n")

    # Test Kevin Sullivan
    await test_kevin_sullivan()

    # Test Jerry Fetta
    await test_jerry_fetta()

    print("\n✅ Integration testing complete!")
    print("\n💡 Note: If enrichment data is not showing:")
    print("   1. Check that app/firecrawl_v2_supercharged.py exists")
    print("   2. Verify FIRECRAWL_API_KEY is set in .env.local")
    print("   3. Some companies may not have public data available")


if __name__ == "__main__":
    asyncio.run(main())