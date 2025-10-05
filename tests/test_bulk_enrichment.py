#!/usr/bin/env python3
"""
Test script for bulk Apollo enrichment functionality.

This script tests:
1. Creating bulk enrichment jobs
2. Checking job status
3. Creating scheduled enrichment jobs
4. Getting enrichment statistics
"""

import os
import asyncio
import json
from datetime import datetime, timedelta
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change to production URL when testing deployed version
API_KEY = os.getenv("API_KEY", "your-api-key-here")

# Test data
TEST_EMAILS = [
    "john.doe@example.com",
    "jane.smith@techcorp.com",
    "mike.wilson@startup.io"
]

TEST_RECORD_IDS = []  # Will be populated if records exist


async def test_bulk_enrichment():
    """Test the bulk enrichment endpoints"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"X-API-Key": API_KEY}

        print("\n" + "="*60)
        print("TESTING BULK APOLLO ENRICHMENT")
        print("="*60)

        # Test 1: Create bulk enrichment job with emails
        print("\n1. Creating bulk enrichment job with emails...")
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/apollo/bulk/enrich",
                headers=headers,
                json={
                    "emails": TEST_EMAILS[:2],
                    "priority": "HIGH",
                    "batch_size": 10,
                    "include_company": True,
                    "include_employees": False,
                    "update_zoho": False  # Don't update Zoho in test
                }
            )

            if response.status_code == 200:
                result = response.json()
                job_id = result.get("job_id")
                print(f"✅ Job created successfully: {job_id}")
                print(f"   Tracking URL: {result.get('tracking_url')}")

                # Wait a bit for processing
                await asyncio.sleep(2)

                # Check job status
                print(f"\n2. Checking job status for {job_id}...")
                status_response = await client.get(
                    f"{API_BASE_URL}/api/apollo/bulk/status/{job_id}",
                    headers=headers
                )

                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"✅ Job Status: {status.get('status')}")
                    print(f"   Metrics: {json.dumps(status.get('metrics', {}), indent=2)}")
                else:
                    print(f"❌ Failed to get job status: {status_response.status_code}")
                    print(f"   Error: {status_response.text}")

            else:
                print(f"❌ Failed to create job: {response.status_code}")
                print(f"   Error: {response.text}")

        except Exception as e:
            print(f"❌ Error creating enrichment job: {str(e)}")

        # Test 2: Create bulk enrichment with filters
        print("\n3. Creating bulk enrichment job with filters...")
        try:
            # Calculate date for filter
            created_after = (datetime.utcnow() - timedelta(days=30)).isoformat()

            response = await client.post(
                f"{API_BASE_URL}/api/apollo/bulk/enrich",
                headers=headers,
                json={
                    "filters": {
                        "created_after": created_after,
                        "missing_linkedin": True,
                        "has_email": True
                    },
                    "priority": "BACKGROUND",
                    "batch_size": 25,
                    "include_company": True
                }
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Filter-based job created: {result.get('job_id')}")
            else:
                print(f"❌ Failed to create filter job: {response.status_code}")
                print(f"   Error: {response.text}")

        except Exception as e:
            print(f"❌ Error creating filter job: {str(e)}")

        # Test 3: Get enrichment statistics
        print("\n4. Getting enrichment statistics...")
        try:
            response = await client.get(
                f"{API_BASE_URL}/api/apollo/bulk/stats?days=7",
                headers=headers
            )

            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Statistics retrieved successfully:")
                print(f"   {json.dumps(stats.get('statistics', {}), indent=2)}")
            else:
                print(f"❌ Failed to get statistics: {response.status_code}")

        except Exception as e:
            print(f"❌ Error getting statistics: {str(e)}")

        # Test 4: Create scheduled enrichment
        print("\n5. Creating scheduled enrichment job...")
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/apollo/schedule/create",
                headers=headers,
                json={
                    "name": "Test Daily Enrichment",
                    "schedule_type": "DAILY",
                    "filters": {
                        "missing_linkedin": True,
                        "created_after": created_after
                    },
                    "config": {
                        "priority": "BACKGROUND",
                        "batch_size": 50,
                        "include_company": True,
                        "update_zoho": False
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                schedule_id = result.get("schedule_id")
                print(f"✅ Schedule created: {schedule_id}")
                print(f"   Name: {result.get('message')}")

                # List schedules
                print("\n6. Listing all schedules...")
                list_response = await client.get(
                    f"{API_BASE_URL}/api/apollo/schedule/list",
                    headers=headers
                )

                if list_response.status_code == 200:
                    schedules = list_response.json()
                    print(f"✅ Found {schedules.get('count')} schedules:")
                    for schedule in schedules.get("schedules", []):
                        print(f"   - {schedule.get('name')} ({schedule.get('schedule_id')})")
                        print(f"     Cron: {schedule.get('cron_expression')}")
                        print(f"     Next run: {schedule.get('next_run')}")

                # Update schedule
                print(f"\n7. Updating schedule {schedule_id}...")
                update_response = await client.put(
                    f"{API_BASE_URL}/api/apollo/schedule/{schedule_id}",
                    headers=headers,
                    json={
                        "is_active": False,
                        "config": {
                            "priority": "LOW",
                            "batch_size": 100
                        }
                    }
                )

                if update_response.status_code == 200:
                    print(f"✅ Schedule updated successfully")
                else:
                    print(f"❌ Failed to update schedule: {update_response.status_code}")

                # Delete schedule
                print(f"\n8. Deleting schedule {schedule_id}...")
                delete_response = await client.delete(
                    f"{API_BASE_URL}/api/apollo/schedule/{schedule_id}",
                    headers=headers
                )

                if delete_response.status_code == 200:
                    print(f"✅ Schedule deleted successfully")
                else:
                    print(f"❌ Failed to delete schedule: {delete_response.status_code}")

            else:
                print(f"❌ Failed to create schedule: {response.status_code}")
                print(f"   Error: {response.text}")

        except Exception as e:
            print(f"❌ Error with scheduled enrichment: {str(e)}")

        print("\n" + "="*60)
        print("BULK ENRICHMENT TESTS COMPLETED")
        print("="*60)


async def test_webhook_notification():
    """Test webhook notification for job completion"""
    print("\n" + "="*60)
    print("TESTING WEBHOOK NOTIFICATION")
    print("="*60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"X-API-Key": API_KEY}

        # You would need a webhook URL to test this
        # For testing, you could use webhook.site or similar service
        webhook_url = "https://webhook.site/your-unique-url"  # Replace with actual webhook URL

        print("\n1. Creating job with webhook notification...")
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/apollo/bulk/enrich",
                headers=headers,
                json={
                    "emails": [TEST_EMAILS[0]],
                    "priority": "HIGH",
                    "batch_size": 1,
                    "webhook_url": webhook_url
                }
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Job created with webhook: {result.get('job_id')}")
                print(f"   Webhook will be called at: {webhook_url}")
                print(f"   Check your webhook service for the notification")
            else:
                print(f"❌ Failed to create job with webhook: {response.status_code}")

        except Exception as e:
            print(f"❌ Error creating job with webhook: {str(e)}")


async def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n" + "="*60)
    print("TESTING EDGE CASES")
    print("="*60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"X-API-Key": API_KEY}

        # Test 1: Invalid batch size
        print("\n1. Testing invalid batch size...")
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/apollo/bulk/enrich",
                headers=headers,
                json={
                    "emails": TEST_EMAILS,
                    "batch_size": 200  # Exceeds maximum
                }
            )

            if response.status_code == 422:
                print(f"✅ Correctly rejected invalid batch size")
            else:
                print(f"❌ Should have rejected batch size: {response.status_code}")

        except Exception as e:
            print(f"❌ Error testing batch size: {str(e)}")

        # Test 2: Non-existent job status
        print("\n2. Testing non-existent job status...")
        try:
            response = await client.get(
                f"{API_BASE_URL}/api/apollo/bulk/status/non_existent_job",
                headers=headers
            )

            if response.status_code == 404:
                print(f"✅ Correctly returned 404 for non-existent job")
            else:
                print(f"❌ Should have returned 404: {response.status_code}")

        except Exception as e:
            print(f"❌ Error testing non-existent job: {str(e)}")

        # Test 3: Invalid cron expression
        print("\n3. Testing invalid cron expression...")
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/apollo/schedule/create",
                headers=headers,
                json={
                    "name": "Invalid Schedule",
                    "schedule_type": "CUSTOM",
                    "custom_cron": "invalid cron"
                }
            )

            if response.status_code in [400, 422, 500]:
                print(f"✅ Correctly rejected invalid cron expression")
            else:
                print(f"❌ Should have rejected invalid cron: {response.status_code}")

        except Exception as e:
            print(f"❌ Error testing invalid cron: {str(e)}")


async def main():
    """Run all tests"""
    print("\n🚀 Starting Bulk Apollo Enrichment Tests")
    print(f"   API URL: {API_BASE_URL}")
    print(f"   API Key: {'*' * 20}{API_KEY[-4:] if len(API_KEY) > 4 else 'NOT SET'}")

    # Run main tests
    await test_bulk_enrichment()

    # Optional: Test webhook notifications
    # await test_webhook_notification()

    # Test edge cases
    await test_edge_cases()

    print("\n✨ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())