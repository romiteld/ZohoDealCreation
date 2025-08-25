#!/usr/bin/env python
"""
Test script to verify Zoho Deal creation with correct field mappings
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('.env.local')

# Set up logging to see detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from app.integrations import ZohoClient
from app.business_rules import BusinessRulesEngine

async def test_deal_creation():
    """Test creating a deal with all the correct field mappings"""
    
    print("\n" + "="*80)
    print("TESTING ZOHO DEAL CREATION WITH CORRECT FIELD MAPPINGS")
    print("="*80)
    
    # Initialize clients
    zoho_client = ZohoClient()
    rules_engine = BusinessRulesEngine()
    
    # Test data simulating an email
    test_email_data = {
        'candidate_name': 'John Smith',
        'job_title': 'Senior Financial Advisor',
        'location': 'Fort Wayne, IN',
        'company_name': 'Test Financial Services',
        'referrer': None  # Will trigger "Email Inbound" source
    }
    
    email_body = "This is a test email for creating a deal in Zoho."
    sender_email = "john.smith@testfinancial.com"
    
    # Process through business rules
    print("\n1. Processing data through business rules...")
    processed_data = rules_engine.process_data(test_email_data, email_body, sender_email)
    
    print(f"   - Deal Name: {processed_data.get('deal_name')}")
    print(f"   - Source Type: {processed_data.get('source_type')}")
    print(f"   - Source Detail: {processed_data.get('source_detail')}")
    
    try:
        # Create or find Account
        print("\n2. Creating/finding Account...")
        account_id = await zoho_client.upsert_account(
            company_name=processed_data.get('company_name', 'Test Company'),
            website=f"https://testfinancial.com"
        )
        print(f"   - Account ID: {account_id}")
        
        # Create or find Contact
        print("\n3. Creating/finding Contact...")
        contact_id = await zoho_client.upsert_contact(
            full_name=processed_data.get('contact_full_name', 'John Smith'),
            email=sender_email,
            account_id=account_id
        )
        print(f"   - Contact ID: {contact_id}")
        
        # Prepare Deal data with all fields
        print("\n4. Preparing Deal data...")
        deal_data = {
            "deal_name": processed_data.get('deal_name'),
            "account_id": account_id,
            "contact_id": contact_id,
            "source": processed_data.get('source_type', 'Email Inbound'),
            "source_detail": processed_data.get('source_detail', 'Direct email contact'),
            "pipeline": "Sales Pipeline",
            "closing_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "next_activity_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "next_activity_description": "Follow up on initial contact",
            "description": f"Test deal created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nEmail: {sender_email}"
        }
        
        print("   Deal data prepared:")
        for key, value in deal_data.items():
            if key not in ['account_id', 'contact_id']:
                print(f"     - {key}: {value}")
        
        # Create Deal
        print("\n5. Creating Deal in Zoho...")
        deal_id = zoho_client.create_deal(deal_data)
        
        print(f"\n✅ SUCCESS! Deal created with ID: {deal_id}")
        print(f"   - Deal Name: {deal_data['deal_name']}")
        print(f"   - Source: {deal_data['source']}")
        print(f"   - Source Detail: {deal_data['source_detail']}")
        
        return {
            "success": True,
            "deal_id": deal_id,
            "account_id": account_id,
            "contact_id": contact_id,
            "deal_name": deal_data['deal_name']
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        logger.exception("Failed to create deal")
        return {
            "success": False,
            "error": str(e)
        }

async def test_referral_source():
    """Test creating a deal with Referral source"""
    
    print("\n" + "="*80)
    print("TESTING REFERRAL SOURCE DEAL")
    print("="*80)
    
    zoho_client = ZohoClient()
    rules_engine = BusinessRulesEngine()
    
    # Test data with referrer
    test_email_data = {
        'candidate_name': 'Jane Doe',
        'job_title': 'Financial Planner',
        'location': 'Chicago, IL',
        'company_name': 'Referral Test Corp',
        'referrer': 'Phil Blosser'  # Will trigger "Referral" source
    }
    
    email_body = "Referred by Phil Blosser"
    sender_email = "jane.doe@referraltest.com"
    
    # Process through business rules
    processed_data = rules_engine.process_data(test_email_data, email_body, sender_email)
    
    print(f"   - Deal Name: {processed_data.get('deal_name')}")
    print(f"   - Source Type: {processed_data.get('source_type')}")
    print(f"   - Source Detail: {processed_data.get('source_detail')}")
    
    # Quick validation
    assert processed_data.get('source_type') == 'Referral', "Source should be Referral"
    assert processed_data.get('source_detail') == 'Phil Blosser', "Source detail should be Phil Blosser"
    print("\n✅ Referral source test passed!")

if __name__ == "__main__":
    print("\nStarting Zoho Deal Creation Tests...")
    print("-" * 80)
    
    # Run the main test
    result = asyncio.run(test_deal_creation())
    
    # Run referral source test
    asyncio.run(test_referral_source())
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    if result['success']:
        print("✅ All tests completed successfully!")
        print(f"   - Deal ID: {result['deal_id']}")
        print(f"   - Deal Name: {result['deal_name']}")
    else:
        print("❌ Tests failed. Check the logs above for details.")
        print(f"   - Error: {result.get('error')}")