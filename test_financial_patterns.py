#!/usr/bin/env python3
"""
Test Script for Financial Advisor Pattern Recognition

This script demonstrates the new financial advisor pattern recognition capabilities
including AUM extraction, license detection, and database integration.

Usage:
    python test_financial_patterns.py
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.financial_advisor_extractor import FinancialPatternExtractor, FinancialAdvisorProcessor
from app.models import ExtractedData, CompanyRecord, ContactRecord, DealRecord
from app.database_enhancements import EnhancedPostgreSQLClient


# Sample advisor emails for testing
SAMPLE_EMAILS = [
    {
        "name": "High-Net-Worth RIA Advisor",
        "content": """
        Subject: Senior Financial Advisor - $240M AUM

        Dear Hiring Manager,

        I am a seasoned financial advisor with 12 years of experience managing $240M in assets
        under management for high-net-worth clients. My book consists of 85 client relationships
        with an average account size of $2.8M.

        Key achievements:
        - Built and manage $240M AUM over 12 years
        - Annual production of $1.2M in trailing 12 months
        - Ranked #3 out of 180 advisors nationally
        - 98% client retention rate
        - President's Club member for 4 consecutive years

        I hold Series 7, Series 66, and am a CFA charterholder. I also have my MBA from
        Northwestern Kellogg. Currently seeking $425K-$500K base salary plus bonus structure.

        Available with 60 days notice. 85% of my book is transferable.

        Best regards,
        Michael Thompson
        Senior Financial Advisor
        Wells Fargo Private Bank
        """
    },
    {
        "name": "Wirehouse Advisor with Team",
        "content": """
        Re: Financial Advisor Opportunity

        Hi there,

        I'm currently a Vice President at Morgan Stanley with a strong track record.
        I manage $180M in client assets with my team of 3 associates. We generated
        $950K in revenue last year and are on track for $1.1M this year.

        Background:
        - 8 years in financial services
        - $180M AUM across 120 client relationships
        - Team of 3 (myself + 2 associates)
        - Series 7, Series 63, Series 66 licensed
        - CFP certification
        - Top 5% performer company-wide
        - 42% growth in AUM over last 3 years

        Looking for the right opportunity to grow our practice. Open to RIA or
        independent broker-dealer models. Compensation expectations around $350K-$400K.

        Thanks,
        Sarah Chen
        Vice President - Financial Advisor
        Morgan Stanley Wealth Management
        """
    },
    {
        "name": "Experienced Independent Advisor",
        "content": """
        Subject: Senior Wealth Manager - Seeking Partnership

        I am an experienced wealth manager currently running my own RIA firm with
        $85M under management. After 15 years in the business, I'm exploring
        opportunities to join a larger platform for enhanced capabilities.

        Professional Summary:
        - Founded and grew RIA from $0 to $85M over 8 years
        - Serve 45 high-net-worth families (average $1.9M)
        - Specialize in estate planning and tax optimization
        - CPA and CFP designated professional
        - Series 65 investment advisor license
        - Graduated summa cum laude with MBA in Finance

        Recent accomplishments:
        - Grew AUM by 28% in 2023 despite market volatility
        - Chairman's Club recognition for client acquisition
        - Named to Barron's Top Financial Advisors list (regional)
        - Maintained 100% client retention for past 5 years

        Revenue: $510K trailing 12 months

        I can be available within 90 days with proper transition planning.

        Best,
        James Rodriguez, CPA, CFP
        Managing Partner
        Rodriguez Wealth Advisors
        """
    }
]


async def test_pattern_extraction():
    """Test the financial pattern extraction functionality"""
    print("=" * 60)
    print("FINANCIAL ADVISOR PATTERN EXTRACTION TEST")
    print("=" * 60)

    extractor = FinancialPatternExtractor()

    for i, email_data in enumerate(SAMPLE_EMAILS, 1):
        print(f"\n{i}. Testing: {email_data['name']}")
        print("-" * 50)

        # Extract financial metrics
        metrics = extractor.extract_financial_metrics(email_data['content'])

        # Display results
        print(f"📊 FINANCIAL METRICS:")
        if metrics['aum_amount']:
            print(f"   💰 AUM: ${metrics['aum_amount']:,.0f}")
        if metrics['production_amount']:
            print(f"   📈 Production: ${metrics['production_amount']:,.0f}")
        if metrics['compensation_low']:
            comp_range = f"${metrics['compensation_low']:,.0f}"
            if metrics['compensation_high'] and metrics['compensation_high'] != metrics['compensation_low']:
                comp_range += f" - ${metrics['compensation_high']:,.0f}"
            print(f"   💵 Compensation: {comp_range}")
        if metrics['years_experience']:
            print(f"   ⏱️  Experience: {metrics['years_experience']} years")
        if metrics['client_count']:
            print(f"   👥 Clients: {metrics['client_count']:,}")

        print(f"\n🎓 CREDENTIALS:")
        licenses = [lic for lic, has in metrics.items() if lic.startswith('has_') and has and 'series' in lic]
        designations = [des for des, has in metrics.items() if lic.startswith('has_') and has and 'series' not in lic]

        if metrics['licenses']:
            print(f"   📋 Licenses: {', '.join(metrics['licenses'])}")
        if metrics['designations']:
            print(f"   🏆 Designations: {', '.join(metrics['designations'])}")

        print(f"\n🎯 ACHIEVEMENTS:")
        for achievement in metrics['achievements'][:3]:  # Show first 3
            print(f"   ⭐ {achievement}")

        print(f"\n📝 RAW PATTERNS EXTRACTED:")
        for pattern in metrics['raw_patterns'][:5]:  # Show first 5
            print(f"   • {pattern['type']}: {pattern['raw_text']}")

        print("\n" + "=" * 50)


async def test_extracted_data_enhancement():
    """Test enhancement of ExtractedData with financial fields"""
    print("\n" + "=" * 60)
    print("EXTRACTED DATA ENHANCEMENT TEST")
    print("=" * 60)

    extractor = FinancialPatternExtractor()

    # Create sample extracted data
    sample_data = ExtractedData(
        company_record=CompanyRecord(
            company_name="Wells Fargo Private Bank",
            website="www.wellsfargo.com"
        ),
        contact_record=ContactRecord(
            first_name="Michael",
            last_name="Thompson",
            email="michael.thompson@wf.com",
            city="Chicago",
            state="IL"
        ),
        deal_record=DealRecord(
            source="Email Inbound",
            deal_name="Senior Financial Advisor (Chicago) - Wells Fargo Private Bank"
        )
    )

    # Enhance with financial data
    enhanced_data = await extractor.enhance_extracted_data(
        sample_data,
        SAMPLE_EMAILS[0]['content']
    )

    print("📋 ENHANCED EXTRACTED DATA:")
    print(f"   💰 AUM Managed: {enhanced_data.aum_managed}")
    print(f"   📈 Annual Production: {enhanced_data.production_annual}")
    print(f"   👥 Client Count: {enhanced_data.client_count}")
    print(f"   📋 Licenses: {enhanced_data.licenses_held}")
    print(f"   🏆 Designations: {enhanced_data.designations}")
    print(f"   ⏱️  Experience: {enhanced_data.years_experience}")
    print(f"   💵 Compensation Range: {enhanced_data.compensation_range}")

    # Show enhanced description
    if enhanced_data.deal_record and enhanced_data.deal_record.description_of_reqs:
        print(f"\n📝 Enhanced Description:")
        print(f"   {enhanced_data.deal_record.description_of_reqs}")


async def test_database_integration():
    """Test database integration (requires PostgreSQL connection)"""
    print("\n" + "=" * 60)
    print("DATABASE INTEGRATION TEST")
    print("=" * 60)

    # Check for database connection string
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("⚠️  DATABASE_URL not found in environment variables")
        print("   Skipping database integration test")
        print("   To run this test, set DATABASE_URL environment variable")
        return

    try:
        # Initialize database client
        print("🔌 Connecting to PostgreSQL...")
        db_client = EnhancedPostgreSQLClient(db_url, enable_vectors=True)
        processor = FinancialAdvisorProcessor(db_client)

        # Test processing
        print("🧪 Testing financial advisor processing...")

        sample_data = ExtractedData(
            contact_record=ContactRecord(
                first_name="Test",
                last_name="Advisor",
                email="test@advisor.com"
            )
        )

        enhanced_data, metadata = await processor.process_advisor_email(
            SAMPLE_EMAILS[1]['content'],
            sample_data,
            email_id="test-email-123"
        )

        print(f"✅ Processing completed successfully")
        print(f"   📊 Patterns extracted: {metadata['patterns_extracted']}")
        print(f"   🗄️  Pattern IDs stored: {len(metadata['pattern_ids'])}")
        print(f"   ⏰ Processing timestamp: {metadata['processing_timestamp']}")

        # Test market analysis
        print("\n📈 Testing market analysis...")
        market_data = await processor.extractor.analyze_market_data()

        if market_data:
            print("✅ Market analysis completed")
            print(f"   📊 Market stats: {len(market_data.get('market_stats', {})) > 0}")
            print(f"   🎓 Top designations: {len(market_data.get('top_designations', []))}")
        else:
            print("ℹ️  No market data available (empty database)")

    except Exception as e:
        print(f"❌ Database integration test failed: {e}")
        print("   This is expected if PostgreSQL is not running or configured")


def test_regex_patterns():
    """Test individual regex patterns"""
    print("\n" + "=" * 60)
    print("REGEX PATTERN VALIDATION TEST")
    print("=" * 60)

    test_cases = [
        ("$240M AUM", "Should extract AUM amount"),
        ("manages $180M in assets", "Should extract AUM with context"),
        ("annual production of $1.2M", "Should extract production"),
        ("Series 7 and Series 66", "Should extract licenses"),
        ("CFA charterholder", "Should extract CFA designation"),
        ("ranked #3 out of 180 advisors", "Should extract ranking"),
        ("98% client retention", "Should extract percentage"),
        ("12 years of experience", "Should extract years"),
        ("$425K-$500K base salary", "Should extract salary range")
    ]

    extractor = FinancialPatternExtractor()

    for test_text, expected in test_cases:
        print(f"\n🧪 Testing: '{test_text}'")
        print(f"   Expected: {expected}")

        metrics = extractor.extract_financial_metrics(test_text)

        # Check what was extracted
        extracted = []
        if metrics['aum_amount']:
            extracted.append(f"AUM: ${metrics['aum_amount']:,.0f}")
        if metrics['production_amount']:
            extracted.append(f"Production: ${metrics['production_amount']:,.0f}")
        if metrics['licenses']:
            extracted.append(f"Licenses: {', '.join(metrics['licenses'])}")
        if metrics['designations']:
            extracted.append(f"Designations: {', '.join(metrics['designations'])}")
        if metrics['years_experience']:
            extracted.append(f"Experience: {metrics['years_experience']} years")
        if metrics['achievements']:
            extracted.append(f"Achievements: {len(metrics['achievements'])}")
        if metrics['performance_percentages']:
            extracted.append(f"Percentages: {metrics['performance_percentages']}")
        if metrics['compensation_low']:
            extracted.append(f"Compensation: ${metrics['compensation_low']:,.0f}")

        if extracted:
            print(f"   ✅ Extracted: {', '.join(extracted)}")
        else:
            print(f"   ❌ Nothing extracted")


async def main():
    """Run all tests"""
    print("🚀 Starting Financial Advisor Pattern Recognition Tests")
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Run tests
        await test_pattern_extraction()
        await test_extracted_data_enhancement()
        test_regex_patterns()
        await test_database_integration()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print("\n📋 NEXT STEPS:")
        print("1. Run the migration script: migrations/add_financial_advisor_patterns.sql")
        print("2. Update your email processing pipeline to use FinancialAdvisorProcessor")
        print("3. Review the database schema documentation")
        print("4. Configure environment variables for database connection")
        print("5. Test with real advisor emails to validate patterns")

    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())