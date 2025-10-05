#!/usr/bin/env python3
"""
Test Apollo.io Deep Enrichment Integration
Tests the comprehensive Apollo data extraction in the main email processing pipeline
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_apollo_deep_enrichment():
    """Test the apollo_deep_enrichment function directly"""
    from app.apollo_enricher import apollo_deep_enrichment

    test_cases = [
        {
            "email": "john.doe@techcompany.com",
            "name": "John Doe",
            "company": "TechCompany",
            "description": "Testing full enrichment capabilities"
        },
        {
            "email": "jane.smith@startup.io",
            "name": "Jane Smith",
            "company": None,  # Test without company hint
            "description": "Testing person-only enrichment"
        },
        {
            "email": None,
            "name": None,
            "company": "Microsoft",  # Test company-only enrichment
            "description": "Testing company-only enrichment"
        }
    ]

    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"Test Case: {test['description']}")
        print(f"Input: email={test['email']}, name={test['name']}, company={test['company']}")
        print(f"{'='*60}")

        try:
            result = await apollo_deep_enrichment(
                email=test['email'],
                name=test['name'],
                company=test['company'],
                extract_all=True
            )

            if result:
                print(f"✅ Enrichment Successful!")
                print(f"Data Completeness: {result.get('data_completeness', 0):.1f}%")

                # Person data
                if result.get('person'):
                    person = result['person']
                    print("\n📧 Person Data:")
                    print(f"  - Name: {person.get('client_name', 'N/A')}")
                    print(f"  - Email: {person.get('email', 'N/A')}")
                    print(f"  - Title: {person.get('job_title', 'N/A')}")
                    print(f"  - Location: {person.get('location', 'N/A')}")
                    print(f"  - LinkedIn: {person.get('linkedin_url', 'N/A')}")
                    print(f"  - Mobile: {person.get('mobile_phone', 'N/A')}")
                    print(f"  - Work Phone: {person.get('work_phone', 'N/A')}")
                    print(f"  - Company: {person.get('firm_company', 'N/A')}")

                    if person.get('alternative_matches'):
                        print(f"\n  Alternative Matches: {len(person['alternative_matches'])}")
                        for alt in person['alternative_matches'][:2]:
                            print(f"    • {alt.get('name')} at {alt.get('company')}")

                # Company data
                if result.get('company'):
                    company = result['company']
                    print("\n🏢 Company Data:")
                    print(f"  - Name: {company.get('company_name', 'N/A')}")
                    print(f"  - Website: {company.get('website', 'N/A')}")
                    print(f"  - LinkedIn: {company.get('linkedin_url', 'N/A')}")
                    print(f"  - Industry: {company.get('industry', 'N/A')}")
                    print(f"  - Employees: {company.get('employee_count', 'N/A')}")
                    print(f"  - Location: {company.get('city', 'N/A')}, {company.get('state', 'N/A')}")

                    if company.get('key_employees'):
                        print(f"\n  Key Employees: {len(company['key_employees'])}")
                        for emp in company['key_employees'][:3]:
                            print(f"    • {emp.get('name')} - {emp.get('title')}")
                            if emp.get('linkedin'):
                                print(f"      LinkedIn: {emp['linkedin']}")

                    if company.get('decision_makers'):
                        print(f"\n  Decision Makers: {len(company['decision_makers'])}")
                        for dm in company['decision_makers'][:3]:
                            print(f"    • {dm.get('name')} - {dm.get('title')}")

                    if company.get('recruiters'):
                        print(f"\n  Recruiters: {len(company['recruiters'])}")
                        for rec in company['recruiters'][:2]:
                            print(f"    • {rec.get('name')} - {rec.get('title')}")
                            if rec.get('phone'):
                                print(f"      Phone: {rec['phone']}")

                # Network data
                if result.get('network'):
                    print(f"\n👥 Network Connections: {len(result['network'])}")
                    for conn in result['network'][:2]:
                        print(f"  • {conn.get('name')} - {conn.get('title')}")

            else:
                print("❌ No enrichment data returned")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            logger.error(f"Test failed for {test['email']}: {str(e)}", exc_info=True)


async def test_email_pipeline_integration():
    """Test the full email processing pipeline with Apollo deep enrichment"""
    from app.main import app
    from fastapi.testclient import TestClient
    import httpx

    # Create test client
    client = TestClient(app)

    # Test email request
    test_email = {
        "subject": "Senior Software Engineer Opportunity at TechCorp",
        "body": """Hi Daniel,

        I came across your profile and wanted to reach out about an exciting opportunity.

        We have a Senior Software Engineer position at TechCorp in San Francisco.
        The role involves working with modern cloud technologies and leading a team of developers.

        The candidate we're looking for:
        - John Smith (john.smith@email.com)
        - Currently at StartupXYZ
        - 10 years of experience
        - Looking for $180k-200k

        Would you be interested in discussing this further?

        Best regards,
        Sarah Johnson
        Talent Acquisition Manager
        TechCorp
        """,
        "sender_email": "sarah.johnson@techcorp.com",
        "sender_name": "Sarah Johnson",
        "cc_emails": [],
        "attachments": []
    }

    print("\n" + "="*60)
    print("Testing Email Pipeline with Apollo Deep Enrichment")
    print("="*60)

    try:
        # Send request to the intake endpoint
        response = client.post(
            "/intake/email",
            json=test_email,
            headers={"X-API-Key": "test-api-key"}  # You may need the actual API key
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Email processed successfully!")
            print(f"\nExtracted Data:")
            print(json.dumps(result, indent=2, default=str))

            # Check if Apollo enrichment was applied
            if 'notes' in result and 'APOLLO.IO ENRICHMENT' in result.get('notes', ''):
                print("\n✅ Apollo enrichment detected in notes!")

            # Check for enriched fields
            enriched_fields = ['linkedin_url', 'mobile_phone', 'company_website', 'key_employees']
            found_fields = [f for f in enriched_fields if f in result]
            if found_fields:
                print(f"\n✅ Enriched fields found: {found_fields}")

        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"❌ Pipeline test error: {str(e)}")
        logger.error(f"Pipeline test failed: {str(e)}", exc_info=True)


async def test_enrichment_metrics():
    """Test and display enrichment metrics"""
    from app.apollo_enricher import apollo_deep_enrichment

    print("\n" + "="*60)
    print("Testing Enrichment Metrics Collection")
    print("="*60)

    # Test with a known email/company
    test_data = {
        "email": "test@microsoft.com",
        "name": "Test User",
        "company": "Microsoft"
    }

    try:
        result = await apollo_deep_enrichment(**test_data, extract_all=True)

        if result:
            # Calculate metrics
            metrics = {
                'total_data_points': 0,
                'person_fields': 0,
                'company_fields': 0,
                'social_profiles': 0,
                'phone_numbers': 0,
                'employees_found': 0,
                'completeness': result.get('data_completeness', 0)
            }

            # Count person fields
            if result.get('person'):
                person = result['person']
                metrics['person_fields'] = len([k for k, v in person.items() if v])
                metrics['total_data_points'] += metrics['person_fields']

                # Count social profiles
                social_fields = ['linkedin_url', 'twitter_url', 'facebook_url', 'github_url']
                metrics['social_profiles'] = sum(1 for f in social_fields if person.get(f))

                # Count phone numbers
                phone_fields = ['phone', 'mobile_phone', 'work_phone']
                metrics['phone_numbers'] = sum(1 for f in phone_fields if person.get(f))

            # Count company fields
            if result.get('company'):
                company = result['company']
                metrics['company_fields'] = len([k for k, v in company.items() if v])
                metrics['total_data_points'] += metrics['company_fields']

                # Count employees
                if company.get('key_employees'):
                    metrics['employees_found'] = len(company['key_employees'])

            # Display metrics
            print("\n📊 Enrichment Metrics:")
            print(f"  Total Data Points: {metrics['total_data_points']}")
            print(f"  Person Fields: {metrics['person_fields']}")
            print(f"  Company Fields: {metrics['company_fields']}")
            print(f"  Social Profiles: {metrics['social_profiles']}")
            print(f"  Phone Numbers: {metrics['phone_numbers']}")
            print(f"  Employees Found: {metrics['employees_found']}")
            print(f"  Data Completeness: {metrics['completeness']:.1f}%")

            # Performance rating
            if metrics['completeness'] >= 80:
                rating = "🌟 Excellent"
            elif metrics['completeness'] >= 60:
                rating = "✅ Good"
            elif metrics['completeness'] >= 40:
                rating = "⚠️ Fair"
            else:
                rating = "❌ Poor"

            print(f"\n  Overall Rating: {rating}")

        else:
            print("❌ No enrichment data returned")

    except Exception as e:
        print(f"❌ Metrics test error: {str(e)}")
        logger.error(f"Metrics test failed: {str(e)}", exc_info=True)


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("APOLLO.IO DEEP ENRICHMENT INTEGRATION TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run tests
    await test_apollo_deep_enrichment()
    await test_enrichment_metrics()

    # Note: Pipeline integration test needs actual API running
    # await test_email_pipeline_integration()

    print("\n" + "="*80)
    print("TEST SUITE COMPLETED")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())