#!/usr/bin/env python3
"""
Test script for batch email processing functionality
Tests both direct batch processing and Service Bus queue operations
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('.env.local')

# Import the batch processing components
from app.service_bus_manager import ServiceBusManager, EmailBatchMessage, BatchAggregator
from app.batch_processor import BatchEmailProcessor, BatchProcessingOrchestrator
from app.models import EmailPayload as EmailRequest


def create_test_emails(count: int = 5) -> List[Dict[str, Any]]:
    """Create test email data"""
    test_emails = []
    
    templates = [
        {
            "sender_email": "recruiter1@example.com",
            "subject": "Great candidate for Senior Advisor role",
            "body": """
            Hi Team,
            
            I'd like to introduce Sarah Johnson for the Senior Financial Advisor position 
            in Chicago. She has 12 years of experience at Morgan Stanley and is looking 
            for new opportunities.
            
            Best regards,
            John Recruiter
            """
        },
        {
            "sender_email": "referrer@wellpartners.com",
            "subject": "Referral - Michael Chen",
            "body": """
            Hello,
            
            Michael Chen would be perfect for your Wealth Manager opening in San Francisco.
            He's currently at Goldman Sachs with 8 years of experience.
            
            Referred by: Lisa Wong
            
            Thanks,
            Partner Team
            """
        },
        {
            "sender_email": "candidate@gmail.com",
            "subject": "Application for Investment Advisor Position",
            "body": """
            Dear Hiring Team,
            
            I'm Emily Rodriguez, applying for the Investment Advisor role in Miami.
            I have 6 years of experience at JP Morgan and specialize in portfolio management.
            
            Looking forward to discussing this opportunity.
            
            Best,
            Emily Rodriguez
            """
        },
        {
            "sender_email": "hr@recruitingfirm.com",
            "subject": "Top candidate - David Park",
            "body": """
            Team,
            
            David Park is interested in the Portfolio Manager position in Boston.
            He's been with Fidelity for 10 years and has an excellent track record.
            
            Let me know if you'd like to schedule an interview.
            
            HR Team
            """
        },
        {
            "sender_email": "talent@headhunters.com",
            "subject": "Executive placement opportunity",
            "body": """
            Good morning,
            
            I represent Jennifer Williams who is exploring opportunities as a 
            Chief Investment Officer in the New York area. She's currently 
            leading a team at BlackRock.
            
            Best,
            Executive Search Team
            """
        }
    ]
    
    # Generate requested number of emails by cycling through templates
    for i in range(count):
        template = templates[i % len(templates)]
        email = {
            "sender_email": template["sender_email"],
            "sender_name": f"Sender {i+1}",
            "subject": f"{template['subject']} #{i+1}",
            "body": template["body"],
            "attachments": []
        }
        test_emails.append(email)
    
    return test_emails


async def test_service_bus_connection():
    """Test Azure Service Bus connection"""
    print("\n=== Testing Service Bus Connection ===")
    
    try:
        async with ServiceBusManager() as sb_manager:
            status = await sb_manager.get_queue_status()
            print(f"✓ Connected to Service Bus")
            print(f"  Queue: {status.get('queue_name')}")
            print(f"  Messages in queue: {status.get('message_count', 0)}")
            print(f"  Max batch size: {status.get('max_batch_size')}")
            return True
    except Exception as e:
        print(f"✗ Service Bus connection failed: {e}")
        print("  Make sure SERVICE_BUS_CONNECTION_STRING is configured in .env.local")
        return False


async def test_batch_aggregator():
    """Test batch aggregation logic"""
    print("\n=== Testing Batch Aggregator ===")
    
    try:
        async with ServiceBusManager() as sb_manager:
            aggregator = await sb_manager.create_batch_aggregator()
            
            test_emails = create_test_emails(100)
            batch_count = 0
            
            for email in test_emails:
                if not aggregator.add_email(email):
                    # Batch is full
                    batch = aggregator.get_batch()
                    batch_count += 1
                    print(f"  Batch {batch_count}: {len(batch)} emails, "
                          f"~{aggregator.estimated_tokens} tokens")
                    aggregator.add_email(email)
            
            # Get final batch
            if aggregator.pending_emails:
                batch = aggregator.get_batch()
                batch_count += 1
                print(f"  Batch {batch_count}: {len(batch)} emails")
            
            print(f"✓ Created {batch_count} optimized batches from 100 emails")
            return True
            
    except Exception as e:
        print(f"✗ Batch aggregation failed: {e}")
        return False


async def test_direct_batch_processing():
    """Test direct batch processing without Service Bus"""
    print("\n=== Testing Direct Batch Processing ===")
    
    try:
        processor = BatchEmailProcessor()
        
        # Create small test batch
        test_emails = create_test_emails(3)
        
        # Create batch message
        batch_msg = EmailBatchMessage(
            batch_id=f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            emails=test_emails,
            total_count=len(test_emails),
            created_at=datetime.utcnow().isoformat()
        )
        
        print(f"  Processing {len(test_emails)} emails...")
        
        # Process batch
        result = await processor.process_batch(batch_msg)
        
        print(f"✓ Batch processed:")
        print(f"  Status: {result.status.value}")
        print(f"  Processed: {result.processed_count}/{result.total_count}")
        print(f"  Failed: {result.failed_count}")
        print(f"  Time: {result.processing_time_seconds:.2f}s")
        
        if result.errors:
            print(f"  Errors: {result.errors}")
        
        return result.processed_count > 0
        
    except Exception as e:
        print(f"✗ Direct batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_queue_submission():
    """Test submitting batches to Service Bus queue"""
    print("\n=== Testing Queue Submission ===")
    
    try:
        async with ServiceBusManager() as sb_manager:
            # Create test batch
            test_emails = create_test_emails(10)
            
            # Submit to queue
            batch_id = await sb_manager.send_batch(test_emails, priority=5)
            
            print(f"✓ Batch submitted to queue:")
            print(f"  Batch ID: {batch_id}")
            print(f"  Email count: {len(test_emails)}")
            print(f"  Priority: 5")
            
            # Check queue status
            status = await sb_manager.get_queue_status()
            print(f"  Queue now has {status.get('message_count', 0)} messages")
            
            return True
            
    except Exception as e:
        print(f"✗ Queue submission failed: {e}")
        return False


async def test_queue_processing():
    """Test processing batches from queue"""
    print("\n=== Testing Queue Processing ===")
    
    try:
        async with ServiceBusManager() as sb_manager:
            processor = BatchEmailProcessor(service_bus_manager=sb_manager)
            
            # Check if there are messages to process
            status = await sb_manager.get_queue_status()
            if status.get('message_count', 0) == 0:
                print("  No messages in queue to process")
                print("  Run test_queue_submission first to add messages")
                return True
            
            print(f"  Processing {status.get('message_count')} messages from queue...")
            
            # Process one batch
            results = await processor.process_from_queue(max_batches=1)
            
            if results:
                stats = processor.get_processing_stats(results)
                print(f"✓ Processed {len(results)} batch(es):")
                print(f"  Total emails: {stats['total_emails']}")
                print(f"  Processed: {stats['processed_emails']}")
                print(f"  Failed: {stats['failed_emails']}")
                print(f"  Success rate: {stats['success_rate']:.2%}")
                print(f"  Avg time per email: {stats['avg_time_per_email']:.2f}s")
            else:
                print("  No batches processed")
            
            return True
            
    except Exception as e:
        print(f"✗ Queue processing failed: {e}")
        return False


async def test_dead_letter_processing():
    """Test dead letter queue handling"""
    print("\n=== Testing Dead Letter Queue ===")
    
    try:
        async with ServiceBusManager() as sb_manager:
            # Process dead letters
            dead_letters = await sb_manager.process_dead_letter_queue(max_messages=5)
            
            if dead_letters:
                print(f"✓ Processed {len(dead_letters)} dead letter messages:")
                for dl in dead_letters:
                    print(f"  - {dl.get('batch_id', 'unknown')}: {dl.get('action')}")
            else:
                print("✓ No dead letter messages to process")
            
            return True
            
    except Exception as e:
        print(f"✗ Dead letter processing failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("BATCH EMAIL PROCESSING TEST SUITE")
    print("=" * 60)
    
    # Check environment
    print("\n=== Environment Check ===")
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_service_bus = bool(os.getenv("SERVICE_BUS_CONNECTION_STRING"))
    has_zoho = bool(os.getenv("ZOHO_OAUTH_SERVICE_URL"))
    
    print(f"  OpenAI API: {'✓ Configured' if has_openai else '✗ Missing'}")
    print(f"  Service Bus: {'✓ Configured' if has_service_bus else '✗ Missing (will use direct mode)'}")
    print(f"  Zoho API: {'✓ Configured' if has_zoho else '✗ Missing'}")
    
    # Run tests
    results = {}
    
    if has_service_bus:
        results['service_bus'] = await test_service_bus_connection()
        results['aggregator'] = await test_batch_aggregator()
        results['queue_submission'] = await test_queue_submission()
        results['queue_processing'] = await test_queue_processing()
        results['dead_letter'] = await test_dead_letter_processing()
    else:
        print("\n⚠ Service Bus not configured, skipping queue tests")
    
    if has_openai:
        results['direct_processing'] = await test_direct_batch_processing()
    else:
        print("\n⚠ OpenAI not configured, skipping processing tests")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name:20} {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for p in results.values() if p)
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Batch processing is ready.")
    elif passed_tests > 0:
        print(f"\n⚠ {total_tests - passed_tests} test(s) failed. Check the output above.")
    else:
        print("\n❌ All tests failed. Please check your configuration.")


if __name__ == "__main__":
    asyncio.run(main())