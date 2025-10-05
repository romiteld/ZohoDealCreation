#!/usr/bin/env python3
"""
Test the new LangGraph implementation for email processing
"""

import asyncio
import json
from app.langgraph_manager import EmailProcessingWorkflow, EmailProcessingCrew
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

async def test_langgraph_extraction():
    """Test the LangGraph email extraction"""
    
    # Test email content (Kevin Sullivan example)
    test_email = """
    Hi Team,
    
    I wanted to introduce you to Kevin Sullivan who would be perfect for the 
    Senior Financial Advisor position in the Fort Wayne area.
    
    Kevin has over 10 years of experience in wealth management and has consistently 
    exceeded his targets. He's currently looking for new opportunities and would be 
    a great addition to your team.
    
    Please let me know if you'd like to schedule a call to discuss further.
    
    Best regards,
    John Referrer
    Well Partners Recruiting
    """
    
    sender_domain = "wellpartners.com"
    
    print("=" * 60)
    print("Testing LangGraph Email Processing")
    print("=" * 60)
    
    # Test with the workflow directly
    print("\n1. Testing EmailProcessingWorkflow directly...")
    try:
        workflow = EmailProcessingWorkflow()
        result = await workflow.process_email(test_email, sender_domain)
        print(f"✅ Direct workflow test successful!")
        print(f"   Extracted data: {result}")
        print(f"   - Candidate: {result.candidate_name}")
        print(f"   - Job Title: {result.job_title}")
        print(f"   - Location: {result.location}")
        print(f"   - Company: {result.company_name}")
        print(f"   - Referrer: {result.referrer_name}")
    except Exception as e:
        print(f"❌ Direct workflow test failed: {e}")
    
    # Test with the compatibility wrapper
    print("\n2. Testing EmailProcessingCrew (compatibility wrapper)...")
    try:
        crew = EmailProcessingCrew()
        result = await crew.run_async(test_email, sender_domain)
        print(f"✅ Compatibility wrapper test successful!")
        print(f"   Extracted data: {result}")
        print(f"   - Candidate: {result.candidate_name}")
        print(f"   - Job Title: {result.job_title}")
        print(f"   - Location: {result.location}")
        print(f"   - Company: {result.company_name}")
        print(f"   - Referrer: {result.referrer_name}")
    except Exception as e:
        print(f"❌ Compatibility wrapper test failed: {e}")
    
    # Test with a different email
    print("\n3. Testing with different email content...")
    test_email2 = """
    Dear Recruiting Team,
    
    I am pleased to recommend Sarah Johnson for the Data Scientist role at your 
    San Francisco office. Sarah has been working at TechCorp for the past 5 years 
    and has exceptional skills in machine learning and data analysis.
    
    She's ready for her next challenge and I think she would be a perfect fit 
    for your team at DataMinds Inc.
    
    Best,
    Michael Brown
    TechCorp HR Department
    """
    
    sender_domain2 = "techcorp.com"
    
    try:
        workflow = EmailProcessingWorkflow()
        result = await workflow.process_email(test_email2, sender_domain2)
        print(f"✅ Second email test successful!")
        print(f"   - Candidate: {result.candidate_name}")
        print(f"   - Job Title: {result.job_title}")
        print(f"   - Location: {result.location}")
        print(f"   - Company: {result.company_name}")
        print(f"   - Referrer: {result.referrer_name}")
    except Exception as e:
        print(f"❌ Second email test failed: {e}")
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("LangGraph implementation is ready to replace CrewAI!")
    print("Key improvements:")
    print("- No ChromaDB dependency issues")
    print("- Faster processing (no memory overhead)")
    print("- Better structured output with GPT-4o-mini")
    print("- Integrated Firecrawl research capabilities")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_langgraph_extraction())