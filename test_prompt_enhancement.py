#!/usr/bin/env python3
"""
Test script for prompt enhancement integration
Tests the prompt enhancement functionality in the LangGraph workflow
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_prompt_enhancement_status():
    """Test the prompt enhancement status functionality"""
    logger.info("=== Testing Prompt Enhancement Status ===")
    
    try:
        from app.langgraph_manager import EmailProcessingWorkflow
        
        # Test with different email domains
        test_domains = [
            "example.com",
            "gmail.com", 
            "thewell.com",
            "microsoft.com"
        ]
        
        workflow = EmailProcessingWorkflow()
        
        for domain in test_domains:
            logger.info(f"\n--- Testing domain: {domain} ---")
            
            status = await workflow.get_prompt_enhancement_status(domain)
            
            logger.info(f"Enhancement ready: {status['enhancement_ready']}")
            logger.info(f"Correction service: {status['correction_service_available']}")
            logger.info(f"Azure AI Search: {status['azure_search_available']}")
            logger.info(f"Domain patterns: {status['domain_patterns_count']}")
            logger.info(f"Company template: {status['company_template_available']}")
            logger.info(f"Analytics available: {status['learning_analytics_available']}")
            
    except Exception as e:
        logger.error(f"Error testing prompt enhancement status: {e}")
        return False
    
    return True

async def test_prompt_enhancement_workflow():
    """Test the actual prompt enhancement in the workflow"""
    logger.info("\n=== Testing Prompt Enhancement Workflow ===")
    
    try:
        from app.langgraph_manager import EmailProcessingWorkflow
        
        # Sample email for testing
        test_email = """
        Subject: Software Engineer Candidate - John Doe
        
        Hi Steve,
        
        I wanted to introduce you to John Doe, a talented software engineer I met recently. 
        He has 5 years of experience at Google and is currently looking for new opportunities.
        
        Here's his contact info:
        - Email: john.doe@gmail.com
        - Phone: (555) 123-4567
        - LinkedIn: https://linkedin.com/in/johndoe
        
        He's interested in remote positions and has experience with Python, React, and AWS.
        
        Would you be interested in having a chat with him?
        
        Best regards,
        Alice Smith
        alice@microsoft.com
        """
        
        workflow = EmailProcessingWorkflow()
        sender_domain = "microsoft.com"
        
        logger.info(f"Processing test email from domain: {sender_domain}")
        logger.info(f"Email content preview: {test_email[:200]}...")
        
        # Process the email with learning hints
        learning_hints = "Test learning hints for better extraction"
        result = await workflow.process_email(
            email_body=test_email,
            sender_domain=sender_domain,
            learning_hints=learning_hints
        )
        
        logger.info(f"Extraction result: {result}")
        
        # Verify the result has expected fields
        if hasattr(result, 'candidate_name') and result.candidate_name:
            logger.info(f"✅ Successfully extracted candidate name: {result.candidate_name}")
        else:
            logger.warning("❌ Failed to extract candidate name")
        
        if hasattr(result, 'referrer_name') and result.referrer_name:
            logger.info(f"✅ Successfully extracted referrer name: {result.referrer_name}")
        else:
            logger.warning("❌ Failed to extract referrer name")
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing prompt enhancement workflow: {e}")
        return False

async def test_correction_service():
    """Test the correction learning service directly"""
    logger.info("\n=== Testing Correction Learning Service ===")
    
    try:
        from app.correction_learning import CorrectionLearningService
        
        # Initialize the service
        service = CorrectionLearningService(None, use_azure_search=True)
        
        logger.info(f"Correction service initialized: {service is not None}")
        logger.info(f"Azure Search available: {service.search_manager is not None}")
        
        # Test enhanced prompt generation
        base_prompt = "Extract information from the email."
        email_domain = "example.com"
        email_content = "Sample email content for testing"
        
        enhanced_prompt = await service.generate_enhanced_prompt(
            base_prompt=base_prompt,
            email_domain=email_domain,
            email_content=email_content
        )
        
        logger.info(f"Enhanced prompt length: {len(enhanced_prompt)} chars")
        logger.info(f"Enhancement applied: {enhanced_prompt != base_prompt}")
        
        if enhanced_prompt != base_prompt:
            logger.info("✅ Prompt enhancement working")
        else:
            logger.info("ℹ️  No enhancements available (no historical patterns)")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing correction service: {e}")
        return False

async def main():
    """Run all prompt enhancement tests"""
    logger.info("Starting Prompt Enhancement Integration Tests")
    logger.info("=" * 50)
    
    tests = [
        ("Prompt Enhancement Status", test_prompt_enhancement_status),
        ("Correction Learning Service", test_correction_service),
        ("Full Workflow Integration", test_prompt_enhancement_workflow),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning: {test_name}")
        try:
            success = await test_func()
            results[test_name] = "PASS" if success else "FAIL"
            logger.info(f"Result: {results[test_name]}")
        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
            results[test_name] = "ERROR"
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST RESULTS SUMMARY:")
    logger.info("=" * 50)
    
    for test_name, result in results.items():
        status_emoji = "✅" if result == "PASS" else "❌" if result == "FAIL" else "⚠️"
        logger.info(f"{status_emoji} {test_name}: {result}")
    
    # Overall result
    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Prompt enhancement integration is working correctly.")
        return 0
    else:
        logger.warning("⚠️  Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)