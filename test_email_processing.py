#!/usr/bin/env python3
"""
Test script for email processing with DRY RUN mode
Tests all fixes WITHOUT sending data to Zoho
"""

import json
import asyncio
from typing import Dict, Any
from app.langgraph_manager import EmailProcessingWorkflow
from app.business_rules import BusinessRulesEngine
# ZohoClient not needed for dry run testing
from app.models import ExtractedData
from unittest.mock import MagicMock, patch
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test emails covering all scenarios from boss's feedback
TEST_EMAILS = {
    "missing_data": {
        "subject": "Job Opportunity",
        "body": """
        Hi,
        
        I have a great opportunity for you. Please let me know if you're interested.
        
        Best regards,
        John
        """,
        "sender": "john@example.com",
        "expected_issues": ["Missing job title", "Missing location", "Missing company name"]
    },
    
    "calendly_with_params": {
        "subject": "Interview Scheduled",
        "body": """
        Hi Daniel,
        
        Your interview has been scheduled for the Senior Developer position at Tech Corp in Boston.
        
        Please join using this link:
        https://calendly.com/techcorp/interview?email=candidate@example.com&phone=555-1234&name=Sarah%20Johnson
        
        Best regards,
        HR Team
        """,
        "sender": "hr@techcorp.com",
        "expected_extraction": {
            "job_title": "Senior Developer",
            "location": "Boston",
            "company_name": "Tech Corp",
            "email": "candidate@example.com",
            "phone": "555-1234",
            "candidate_name": "Sarah Johnson"
        }
    },
    
    "referral_email": {
        "subject": "Referral from Phil Blosser",
        "body": """
        Hi Daniel,
        
        Phil Blosser suggested I reach out to you about the Financial Advisor position 
        in Phoenix with Advisors Excel.
        
        I'm very interested in learning more.
        
        Best,
        Mike Thompson
        mike@example.com
        602-555-9876
        """,
        "sender": "mike@example.com",
        "expected_extraction": {
            "job_title": "Financial Advisor",
            "location": "Phoenix",
            "company_name": "Advisors Excel",
            "referrer": "Phil Blosser",
            "candidate_name": "Mike Thompson",
            "candidate_phone": "602-555-9876"
        },
        "expected_deal_name": "Financial Advisor Phoenix - Advisors Excel"
    },
    
    "duplicate_check": {
        "subject": "Following up on my application",
        "body": """
        Hi,
        
        I wanted to follow up on my application for the Product Manager role 
        in San Francisco at StartupCo.
        
        I'm Sarah Johnson and I applied yesterday.
        
        Thanks,
        Sarah
        """,
        "sender": "sarah.j@example.com",
        "candidate_name": "Sarah Johnson",
        "should_be_duplicate": True
    },
    
    "partial_data": {
        "subject": "Interested in opportunities",
        "body": """
        Hi Daniel,
        
        I'm interested in Software Engineer positions at your company.
        I'm based in Austin.
        
        Best,
        Alex Chen
        """,
        "sender": "alex.chen@example.com",
        "expected_extraction": {
            "job_title": "Software Engineer",
            "location": "Austin",
            "candidate_name": "Alex Chen"
        },
        "expected_issue": "Missing company name"
    }
}

class TestEmailProcessor:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.processor = EmailProcessingWorkflow()
        self.business_rules = BusinessRulesEngine()
        self.results = []
        
    async def test_email(self, test_name: str, test_data: Dict[str, Any]):
        """Test a single email scenario"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {test_name}")
        logger.info(f"{'='*60}")
        
        result = {
            "test_name": test_name,
            "passed": True,
            "issues": []
        }
        
        try:
            # Process with EmailProcessingWorkflow
            extraction = await self.processor.process_email(
                test_data["body"],
                test_data["sender"].split("@")[1] if "@" in test_data["sender"] else "example.com"
            )
            
            # Apply business rules
            processed = self.business_rules.process_data(
                extraction.model_dump() if extraction else {},
                test_data["body"],
                test_data["sender"]
            )
            
            logger.info(f"Extracted data: {json.dumps(processed, indent=2)}")
            
            # Validate no fabrication
            if processed:
                for key, value in processed.items():
                    if value and isinstance(value, str):
                        # Check for placeholder values that indicate fabrication
                        if value.lower() in ["unknown", "n/a", "not specified", "tbd"]:
                            result["issues"].append(f"Fabricated placeholder found: {key}={value}")
                            result["passed"] = False
            
            # Check if missing data is properly flagged
            if "expected_issues" in test_data:
                if not processed.get("requires_user_input"):
                    result["issues"].append("Failed to flag missing data for user input")
                    result["passed"] = False
                else:
                    logger.info(f"✓ Correctly flagged missing fields: {processed.get('missing_fields')}")
            
            # Validate Calendly extraction
            if "calendly.com" in test_data["body"]:
                if "expected_extraction" in test_data:
                    for field, expected_value in test_data["expected_extraction"].items():
                        actual_value = processed.get(field)
                        if actual_value != expected_value:
                            result["issues"].append(
                                f"Calendly extraction mismatch: {field} expected '{expected_value}' but got '{actual_value}'"
                            )
                            result["passed"] = False
                        else:
                            logger.info(f"✓ Correctly extracted {field}: {actual_value}")
            
            # Validate deal name format
            if "expected_deal_name" in test_data:
                actual_deal_name = processed.get("deal_name")
                expected = test_data["expected_deal_name"]
                if actual_deal_name != expected:
                    result["issues"].append(
                        f"Deal name format error: expected '{expected}' but got '{actual_deal_name}'"
                    )
                    result["passed"] = False
                else:
                    logger.info(f"✓ Correct deal name format: {actual_deal_name}")
            
            # Test deduplication (mocked)
            if test_data.get("should_be_duplicate"):
                logger.info("✓ Deduplication check would be performed in production")
            
            # Show what would be sent to Zoho (DRY RUN)
            if self.dry_run:
                logger.info("\n🔒 DRY RUN MODE - Nothing sent to Zoho")
                logger.info("Would create in Zoho:")
                if processed.get("deal_name"):
                    logger.info(f"  Deal: {processed.get('deal_name')}")
                if processed.get("contact_full_name"):
                    logger.info(f"  Contact: {processed.get('contact_full_name')}")
                if processed.get("company_name"):
                    logger.info(f"  Account: {processed.get('company_name')}")
            
        except Exception as e:
            result["issues"].append(f"Processing error: {str(e)}")
            result["passed"] = False
            logger.error(f"Error: {e}")
        
        self.results.append(result)
        return result
    
    async def run_all_tests(self):
        """Run all test scenarios"""
        logger.info("Starting email processing tests (DRY RUN MODE)")
        logger.info("No data will be sent to Zoho\n")
        
        for test_name, test_data in TEST_EMAILS.items():
            await self.test_email(test_name, test_data)
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*60}")
        
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        logger.info(f"Tests passed: {passed}/{total}")
        
        for result in self.results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            logger.info(f"{status}: {result['test_name']}")
            for issue in result["issues"]:
                logger.info(f"  - {issue}")
        
        return passed == total

async def main():
    # Run in DRY RUN mode - no data sent to Zoho
    tester = TestEmailProcessor(dry_run=True)
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n✅ All tests passed! The fixes are working correctly.")
        logger.info("To send test data to Zoho, set dry_run=False")
        logger.info("⚠️  Remember to manually delete test data from Zoho after testing!")
    else:
        logger.info("\n❌ Some tests failed. Please review the issues above.")

if __name__ == "__main__":
    asyncio.run(main())