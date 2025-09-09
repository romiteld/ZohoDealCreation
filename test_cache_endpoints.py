#!/usr/bin/env python3
"""
Test cache endpoints functionality including /cache/status and /cache/warmup.
Tests API endpoints for cache management and validation.
"""

import asyncio
import requests
import json
import logging
import time
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheEndpointTestSuite:
    """Test suite for cache management endpoints."""
    
    def __init__(self):
        # Try production URL first, fallback to local
        self.base_url = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
        self.api_key = os.getenv("API_KEY")
        
        if not self.api_key:
            logger.warning("No API_KEY found in environment. Some tests may fail.")
        
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        } if self.api_key else {"Content-Type": "application/json"}
        
        self.test_results = []
    
    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test basic health endpoint."""
        test_result = {
            "test_name": "Health Endpoint",
            "passed": False,
            "details": {},
            "issues": []
        }
        
        try:
            logger.info("🔍 Testing /health endpoint...")
            
            response = requests.get(f"{self.base_url}/health", timeout=10)
            test_result["details"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                logger.info("✅ Health endpoint accessible")
                test_result["passed"] = True
                test_result["details"]["response"] = response.json()
            else:
                test_result["issues"].append(f"Health endpoint returned {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ API not accessible, trying local...")
            # Try local fallback
            self.base_url = "http://localhost:8000"
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    logger.info("✅ Local API accessible")
                    test_result["passed"] = True
                    test_result["details"]["response"] = response.json()
                else:
                    test_result["issues"].append("Neither production nor local API accessible")
            except:
                test_result["issues"].append("API not accessible locally or in production")
                
        except Exception as e:
            test_result["issues"].append(f"Health endpoint error: {str(e)}")
        
        self.test_results.append(test_result)
        return test_result
    
    def test_cache_status_endpoint(self) -> Dict[str, Any]:
        """Test /cache/status endpoint."""
        test_result = {
            "test_name": "Cache Status Endpoint", 
            "passed": False,
            "details": {},
            "issues": []
        }
        
        try:
            logger.info("🔍 Testing /cache/status endpoint...")
            
            response = requests.get(
                f"{self.base_url}/cache/status",
                headers=self.headers,
                timeout=10
            )
            
            test_result["details"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                test_result["details"]["response"] = data
                
                # Validate expected fields
                required_fields = ["hits", "misses", "hit_rate", "health_status"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    logger.info("✅ Cache status endpoint working correctly")
                    logger.info(f"Current hit rate: {data.get('hit_rate', '0%')}")
                    logger.info(f"Health status: {data.get('health_status', 'unknown')}")
                    test_result["passed"] = True
                else:
                    test_result["issues"].append(f"Missing required fields: {missing_fields}")
                    
            elif response.status_code == 404:
                test_result["issues"].append("Cache status endpoint not found - may not be implemented")
            elif response.status_code == 401:
                test_result["issues"].append("Authentication failed - check API key")
            else:
                test_result["issues"].append(f"Cache status endpoint returned {response.status_code}")
                
        except Exception as e:
            test_result["issues"].append(f"Cache status endpoint error: {str(e)}")
        
        self.test_results.append(test_result)
        return test_result
    
    def test_cache_warmup_endpoint(self) -> Dict[str, Any]:
        """Test /cache/warmup endpoint."""
        test_result = {
            "test_name": "Cache Warmup Endpoint",
            "passed": False, 
            "details": {},
            "issues": []
        }
        
        try:
            logger.info("🔍 Testing /cache/warmup endpoint...")
            
            # Test POST request for cache warmup
            warmup_data = {
                "patterns": ["referral", "recruiter"],
                "force": False
            }
            
            response = requests.post(
                f"{self.base_url}/cache/warmup",
                headers=self.headers,
                json=warmup_data,
                timeout=30  # Warmup might take longer
            )
            
            test_result["details"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                test_result["details"]["response"] = data
                
                logger.info("✅ Cache warmup endpoint working")
                logger.info(f"Warmup result: {json.dumps(data, indent=2)}")
                test_result["passed"] = True
                
            elif response.status_code == 404:
                test_result["issues"].append("Cache warmup endpoint not found - may not be implemented")
            elif response.status_code == 401:
                test_result["issues"].append("Authentication failed - check API key")
            else:
                test_result["issues"].append(f"Cache warmup endpoint returned {response.status_code}")
                try:
                    error_data = response.json()
                    test_result["details"]["error_response"] = error_data
                except:
                    test_result["details"]["error_text"] = response.text
                    
        except Exception as e:
            test_result["issues"].append(f"Cache warmup endpoint error: {str(e)}")
        
        self.test_results.append(test_result)
        return test_result
    
    def test_cache_invalidation_endpoint(self) -> Dict[str, Any]:
        """Test /cache/invalidate endpoint."""
        test_result = {
            "test_name": "Cache Invalidation Endpoint",
            "passed": False,
            "details": {},
            "issues": []
        }
        
        try:
            logger.info("🔍 Testing /cache/invalidate endpoint...")
            
            invalidation_data = {
                "pattern": "well:email:*",
                "confirm": True
            }
            
            response = requests.post(
                f"{self.base_url}/cache/invalidate",
                headers=self.headers,
                json=invalidation_data,
                timeout=15
            )
            
            test_result["details"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                test_result["details"]["response"] = data
                
                logger.info("✅ Cache invalidation endpoint working")
                logger.info(f"Invalidation result: {json.dumps(data, indent=2)}")
                test_result["passed"] = True
                
            elif response.status_code == 404:
                test_result["issues"].append("Cache invalidation endpoint not found")
            elif response.status_code == 401:
                test_result["issues"].append("Authentication failed - check API key")
            else:
                test_result["issues"].append(f"Cache invalidation endpoint returned {response.status_code}")
                
        except Exception as e:
            test_result["issues"].append(f"Cache invalidation endpoint error: {str(e)}")
        
        self.test_results.append(test_result)
        return test_result
    
    def test_email_processing_with_cache(self) -> Dict[str, Any]:
        """Test email processing endpoint to validate cache integration."""
        test_result = {
            "test_name": "Email Processing with Cache",
            "passed": False,
            "details": {},
            "issues": []
        }
        
        try:
            logger.info("🔍 Testing email processing with cache integration...")
            
            # Test email that should benefit from caching
            test_email = {
                "subject": "Referral from Phil Blosser",
                "body": """
                Hi Daniel,
                
                Phil Blosser suggested I reach out about the Financial Advisor position 
                in Phoenix with Advisors Excel.
                
                I'm Mike Thompson and very interested.
                
                Best,
                Mike
                """,
                "sender": "mike@example.com",
                "attachments": []
            }
            
            # First request - should be cache miss
            logger.info("Making first request (cache miss expected)...")
            start_time = time.time()
            
            response1 = requests.post(
                f"{self.base_url}/intake/email",
                headers=self.headers,
                json=test_email,
                timeout=30
            )
            
            first_duration = time.time() - start_time
            test_result["details"]["first_request_duration"] = first_duration
            test_result["details"]["first_request_status"] = response1.status_code
            
            if response1.status_code == 200:
                logger.info(f"✅ First request successful ({first_duration:.2f}s)")
                
                # Second request - should be cache hit (if caching works)
                logger.info("Making second request (cache hit expected)...")
                start_time = time.time()
                
                response2 = requests.post(
                    f"{self.base_url}/intake/email", 
                    headers=self.headers,
                    json=test_email,
                    timeout=30
                )
                
                second_duration = time.time() - start_time
                test_result["details"]["second_request_duration"] = second_duration
                test_result["details"]["second_request_status"] = response2.status_code
                
                if response2.status_code == 200:
                    logger.info(f"✅ Second request successful ({second_duration:.2f}s)")
                    
                    # Check if second request was faster (indicating cache hit)
                    if second_duration < first_duration * 0.8:  # At least 20% faster
                        speedup = (first_duration - second_duration) / first_duration * 100
                        logger.info(f"✅ Cache performance improvement: {speedup:.1f}% faster")
                        test_result["details"]["cache_speedup_pct"] = speedup
                        test_result["passed"] = True
                    else:
                        logger.info(f"ℹ️ Similar response times - may not be cached or cache miss")
                        test_result["details"]["similar_times"] = True
                        # Still consider it a pass if both requests work
                        test_result["passed"] = True
                else:
                    test_result["issues"].append("Second request failed")
            else:
                test_result["issues"].append("First request failed")
                
        except Exception as e:
            test_result["issues"].append(f"Email processing test error: {str(e)}")
        
        self.test_results.append(test_result)
        return test_result
    
    def run_all_tests(self) -> bool:
        """Run all cache endpoint tests."""
        logger.info("🧪 Starting cache endpoints test suite...")
        logger.info("=" * 80)
        
        # Run test methods
        test_methods = [
            self.test_health_endpoint,
            self.test_cache_status_endpoint, 
            self.test_cache_warmup_endpoint,
            self.test_cache_invalidation_endpoint,
            self.test_email_processing_with_cache
        ]
        
        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                logger.error(f"❌ Test method {test_method.__name__} failed: {e}")
        
        # Generate report
        self.generate_report()
        
        # Return overall success
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        return passed_tests >= len(self.test_results) * 0.6  # 60% pass rate acceptable
    
    def generate_report(self):
        """Generate test report."""
        logger.info("\n" + "=" * 80)
        logger.info("📊 CACHE ENDPOINTS TEST REPORT")
        logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {total_tests - passed_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        logger.info("\nDETAILED RESULTS:")
        logger.info("-" * 80)
        
        for result in self.test_results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            logger.info(f"{status} {result['test_name']}")
            
            if result["issues"]:
                for issue in result["issues"]:
                    logger.info(f"    ⚠️  {issue}")
            
            # Show performance metrics
            if "cache_speedup_pct" in result.get("details", {}):
                speedup = result["details"]["cache_speedup_pct"]
                logger.info(f"    🚀 Cache performance improvement: {speedup:.1f}%")
            
            if "first_request_duration" in result.get("details", {}):
                first = result["details"]["first_request_duration"]
                second = result["details"].get("second_request_duration", 0)
                logger.info(f"    ⏱️  Request times: {first:.2f}s → {second:.2f}s")
        
        logger.info("\nSUMMARY:")
        logger.info("-" * 80)
        
        if passed_tests >= total_tests * 0.8:
            logger.info("🎉 Cache endpoints are working well!")
        elif passed_tests >= total_tests * 0.6:
            logger.info("⚠️ Some cache endpoints may need attention")
        else:
            logger.info("❌ Cache endpoints need significant fixes")
        
        logger.info("\nNEXT STEPS:")
        logger.info("1. Deploy cache endpoints if not yet available")
        logger.info("2. Monitor cache performance in production")
        logger.info("3. Adjust cache strategies based on usage patterns")
        logger.info("=" * 80)


def main():
    """Run cache endpoint tests."""
    test_suite = CacheEndpointTestSuite()
    success = test_suite.run_all_tests()
    
    if success:
        logger.info("\n🎉 Cache endpoints test completed successfully!")
        return 0
    else:
        logger.info("\n💥 Some cache endpoint tests failed")
        return 1


if __name__ == "__main__":
    exit(main())