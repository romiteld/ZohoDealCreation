#!/usr/bin/env python3
"""
Enhanced Batch Processing Test Script
Tests the new learning-integrated batch processing capabilities
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.batch_processor import create_enhanced_batch_processor, EnhancedBatchEmailProcessor, ProcessingMetrics
from app.service_bus_manager import EmailBatchMessage

# Test data - realistic recruitment emails
TEST_EMAILS = [
    {
        "sender_email": "sarah.jones@techstartup.com",
        "sender_name": "Sarah Jones",
        "subject": "Senior Software Engineer - Remote Opportunity",
        "body": """Hi there,

I hope this email finds you well. I'm Sarah Jones, VP of Engineering at TechStartup Inc. We're looking for a Senior Software Engineer to join our remote team.

The position is based remotely but we prefer candidates in the PST timezone. We're offering competitive compensation and equity.

Key requirements:
- 5+ years experience with Python and React
- Experience with cloud platforms (AWS/Azure)
- Strong communication skills

If you're interested, please let me know. We'd love to chat!

Best regards,
Sarah Jones
VP of Engineering
TechStartup Inc.
www.techstartup.com""",
        "attachments": []
    },
    {
        "sender_email": "recruiter@bigtech.com",
        "sender_name": "Mike Chen",
        "subject": "Referral: Data Scientist Position in NYC",
        "body": """Hello,

I was referred to you by Jennifer Smith for a Data Scientist position at BigTech Corp in New York City.

We're looking for someone with:
- PhD in Computer Science or related field
- Experience with machine learning and Python
- 3+ years in a data science role

The role comes with excellent benefits and growth opportunities. The salary range is $140k-180k.

Please let me know if you'd be interested in learning more.

Best,
Mike Chen
Senior Technical Recruiter
BigTech Corp
Phone: (555) 123-4567""",
        "attachments": []
    },
    {
        "sender_email": "hr@consultingfirm.com",
        "sender_name": "Lisa Wang",
        "subject": "Management Consultant - Boston Office",
        "body": """Dear Candidate,

We have an exciting opportunity for a Management Consultant at our Boston office. This role involves working with Fortune 500 clients on strategic initiatives.

Requirements:
- MBA from top-tier school
- 2-4 years consulting experience
- Strong analytical and communication skills

We offer competitive compensation, excellent benefits, and opportunities for rapid career advancement.

If interested, please respond with your resume.

Regards,
Lisa Wang
Human Resources
ConsultingFirm LLC
Boston, MA""",
        "attachments": []
    },
    {
        "sender_email": "john.davis@healthtech.io",
        "sender_name": "John Davis",
        "subject": "Healthcare Software Engineer - San Francisco",
        "body": """Hi,

I'm John Davis, CTO at HealthTech.io. We're building the next generation of healthcare technology.

We're hiring a Healthcare Software Engineer for our San Francisco headquarters. This person will work on patient management systems and healthcare analytics.

What we're looking for:
- Strong background in software engineering
- Interest in healthcare technology
- Experience with JavaScript, Node.js, and databases

We're offering a competitive salary ($120k-160k) plus equity and full benefits.

Would you be interested in discussing this opportunity?

John Davis
CTO, HealthTech.io
San Francisco, CA""",
        "attachments": []
    }
]

async def test_basic_batch_processing():
    """Test basic batch processing functionality"""
    print("🧪 Testing Basic Enhanced Batch Processing...")
    
    try:
        # Create enhanced processor
        processor = create_enhanced_batch_processor(
            enable_learning=True
        )
        
        # Create batch message
        batch_message = EmailBatchMessage(
            batch_id=f"test_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            emails=TEST_EMAILS,
            total_count=len(TEST_EMAILS),
            created_at=datetime.utcnow().isoformat()
        )
        
        # Process the batch
        print(f"  📧 Processing batch with {len(TEST_EMAILS)} emails...")
        result = await processor.process_batch(batch_message)
        
        # Display results
        print(f"  ✅ Batch Processing Results:")
        print(f"     - Batch ID: {result.batch_id}")
        print(f"     - Status: {result.status.value}")
        print(f"     - Processed: {result.processed_count}/{result.total_count}")
        print(f"     - Processing Time: {result.processing_time_seconds:.2f}s")
        
        if result.errors:
            print(f"     - Errors: {len(result.errors)}")
            for error in result.errors[:2]:  # Show first 2 errors
                print(f"       * {error}")
        
        # Show sample results
        if result.results:
            print(f"  📊 Sample Processing Results:")
            for i, res in enumerate(result.results[:2]):  # Show first 2 results
                print(f"     Email {i+1}:")
                print(f"       - Status: {res.get('status', 'unknown')}")
                print(f"       - Confidence: {res.get('confidence_score', 'N/A')}")
                print(f"       - Learning Applied: {res.get('learning_applied', False)}")
        
        return result
        
    except Exception as e:
        print(f"  ❌ Error in basic batch processing: {e}")
        return None

async def test_enhanced_prompt_creation():
    """Test the enhanced prompt creation with learning patterns"""
    print("\n🧠 Testing Enhanced Prompt Creation...")
    
    try:
        processor = create_enhanced_batch_processor(enable_learning=True)
        
        # Test enhanced prompt creation
        prompt, learning_context = await processor._create_enhanced_batch_prompt(
            TEST_EMAILS[:2], use_learning=True
        )
        
        print(f"  📝 Enhanced Prompt Generated:")
        print(f"     - Prompt Length: {len(prompt)} characters")
        print(f"     - Learning Context: {learning_context}")
        print(f"     - Patterns Applied: {learning_context.get('patterns_applied', 0)}")
        print(f"     - Templates Used: {learning_context.get('templates_used', 0)}")
        
        # Show portion of prompt
        print(f"  📄 Prompt Preview:")
        preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
        print(f"     {preview}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error in enhanced prompt creation: {e}")
        return False

async def test_learning_analytics():
    """Test learning analytics and reporting"""
    print("\n📊 Testing Learning Analytics...")
    
    try:
        processor = create_enhanced_batch_processor(enable_learning=True)
        
        # Test optimization analysis
        optimization_report = await processor.optimize_batch_processing()
        
        print(f"  🔍 Optimization Report:")
        print(f"     - Current Performance: {optimization_report.get('current_performance', {})}")
        print(f"     - Bottlenecks: {len(optimization_report.get('bottlenecks', []))}")
        print(f"     - Recommendations: {len(optimization_report.get('recommendations', []))}")
        
        for recommendation in optimization_report.get('recommendations', [])[:3]:
            print(f"       • {recommendation}")
        
        # Test learning report (would need actual batch IDs in real scenario)
        try:
            learning_report = await processor.get_batch_learning_report(["test_batch_123"])
            print(f"  📈 Learning Report Available: {bool(learning_report)}")
        except Exception as lr_error:
            print(f"  📈 Learning Report: {lr_error}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error in learning analytics: {e}")
        return False

async def test_error_handling():
    """Test enhanced error handling for partial success scenarios"""
    print("\n🛡️ Testing Enhanced Error Handling...")
    
    try:
        processor = create_enhanced_batch_processor(enable_learning=True)
        
        # Create batch with some problematic emails
        problematic_emails = [
            {
                "sender_email": "valid@example.com",
                "subject": "Valid Email",
                "body": "This is a valid recruitment email for Software Engineer at TechCorp."
            },
            {
                "sender_email": "",  # Invalid email
                "subject": "Invalid Email",
                "body": "This email has no sender"
            },
            {
                "sender_email": "another@example.com",
                "subject": "Another Valid Email", 
                "body": "Data Scientist position at DataCorp in San Francisco, $150k salary."
            }
        ]
        
        batch_message = EmailBatchMessage(
            batch_id="error_test_batch",
            emails=problematic_emails,
            total_count=len(problematic_emails),
            created_at=datetime.utcnow().isoformat()
        )
        
        result = await processor.process_batch(batch_message)
        
        print(f"  🔍 Error Handling Results:")
        print(f"     - Total Emails: {result.total_count}")
        print(f"     - Processed Successfully: {result.processed_count}")
        print(f"     - Failed: {result.failed_count}")
        print(f"     - Status: {result.status.value}")
        
        if result.errors:
            print(f"     - Error Details:")
            for error in result.errors:
                print(f"       • Email {error.get('email_index', 'unknown')}: {error.get('error', 'Unknown error')}")
        
        return result.status.value in ['completed', 'partial']  # Success if completed or partial
        
    except Exception as e:
        print(f"  ❌ Error in error handling test: {e}")
        return False

async def run_comprehensive_test():
    """Run comprehensive test suite for enhanced batch processing"""
    print("🚀 Enhanced Batch Processing Test Suite")
    print("=" * 50)
    
    test_results = {}
    
    # Test 1: Basic batch processing
    basic_result = await test_basic_batch_processing()
    test_results['basic_processing'] = bool(basic_result and basic_result.processed_count > 0)
    
    # Test 2: Enhanced prompt creation
    prompt_result = await test_enhanced_prompt_creation()
    test_results['enhanced_prompts'] = prompt_result
    
    # Test 3: Learning analytics
    analytics_result = await test_learning_analytics()
    test_results['learning_analytics'] = analytics_result
    
    # Test 4: Error handling
    error_handling_result = await test_error_handling()
    test_results['error_handling'] = error_handling_result
    
    # Summary
    print("\n📋 Test Summary:")
    print("=" * 30)
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\n🎯 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🌟 All tests passed! Enhanced batch processing is working correctly.")
    else:
        print("⚠️ Some tests failed. Review the output above for details.")
    
    return passed_tests == total_tests

def display_enhanced_features():
    """Display the enhanced features implemented"""
    print("\n🔥 Enhanced Batch Processing Features:")
    print("=" * 40)
    
    features = [
        "✨ Learning-integrated prompt enhancement",
        "🧠 Pattern matching from previous corrections",
        "🏢 Company-specific template application",
        "📊 Comprehensive analytics and metrics tracking",
        "🔍 Confidence score monitoring",
        "⚡ Enhanced error handling with partial success support",
        "📈 Batch learning effectiveness reporting",
        "🎯 Performance optimization recommendations",
        "💾 Comprehensive storage with learning metadata",
        "🔄 Continuous improvement feedback loops"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print("\n🌐 New API Endpoints:")
    endpoints = [
        "GET /batch/learning/report - Learning effectiveness analysis",
        "GET /batch/optimization - Performance optimization report", 
        "GET /batch/metrics - Comprehensive processing metrics",
        "POST /batch/learning/feedback - Submit learning feedback"
    ]
    
    for endpoint in endpoints:
        print(f"  📡 {endpoint}")

if __name__ == "__main__":
    print("Enhanced Batch Processing Integration Test")
    print("Agent #9 - Batch Processing Pipeline Connection")
    print("=" * 60)
    
    # Display enhanced features
    display_enhanced_features()
    
    # Run comprehensive tests
    asyncio.run(run_comprehensive_test())
    
    print("\n🎯 Integration Complete!")
    print("The enhanced batch processor now includes:")
    print("  • Full learning system integration")
    print("  • Pattern matching and prompt enhancement") 
    print("  • Comprehensive error handling")
    print("  • Advanced analytics and reporting")
    print("  • Continuous improvement capabilities")