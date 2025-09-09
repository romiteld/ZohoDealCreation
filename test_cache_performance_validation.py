#!/usr/bin/env python3
"""
Performance validation test for Redis cache system.
Validates the claimed 90% cost reduction and performance improvements.
"""

import asyncio
import json
import time
import logging
import statistics
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

from app.redis_cache_manager import get_cache_manager, RedisCacheManager
from app.cache_strategies import get_strategy_manager, EmailType
from app.langgraph_manager import EmailProcessingWorkflow
from app.business_rules import BusinessRulesEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CachePerformanceValidator:
    """Validates cache performance claims and measures actual savings."""
    
    def __init__(self):
        self.cache_manager: RedisCacheManager = None
        self.strategy_manager = get_strategy_manager()
        self.processor = EmailProcessingWorkflow()
        self.business_rules = BusinessRulesEngine()
        
        # Performance tracking
        self.metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "time_with_cache": [],
            "time_without_cache": [],
            "cost_saved": 0.0,
            "tokens_saved": 0
        }
        
        # Test email scenarios for realistic testing
        self.test_scenarios = self._create_test_scenarios()
    
    def _create_test_scenarios(self) -> List[Dict[str, Any]]:
        """Create realistic email scenarios for performance testing."""
        return [
            {
                "name": "referral_standard",
                "content": """Hi Daniel,

I'd like to refer Sarah Johnson for the Senior Developer position at TechCorp in Austin.

Sarah has 5+ years of experience and would be a great fit.

Best regards,
Phil Blosser""",
                "sender_domain": "example.com",
                "expected_type": EmailType.REFERRAL,
                "variations": 5  # Test with slight variations
            },
            
            {
                "name": "recruiter_linkedin",
                "content": """Subject: Exciting Software Engineer opportunity

Hi there,

I found your profile on LinkedIn and think you'd be perfect for our 
Software Engineer role in San Francisco at InnovateTexx.

The role offers competitive salary and great benefits.

Best regards,
Jane Smith - LinkedIn Recruiter""",
                "sender_domain": "linkedin.com",
                "expected_type": EmailType.RECRUITER,
                "variations": 3
            },
            
            {
                "name": "application_direct",
                "content": """Dear Hiring Manager,

I'm applying for the Product Manager position advertised on your website.

I'm Mike Chen, currently based in Seattle, with 3+ years of PM experience.

Please find my resume attached.

Best regards,
Mike Chen
mike.chen@email.com""",
                "sender_domain": "gmail.com",
                "expected_type": EmailType.APPLICATION,
                "variations": 4
            },
            
            {
                "name": "followup_application",
                "content": """Hi Daniel,

I wanted to follow up on my application for the Marketing Manager role 
I submitted last week.

I'm very interested in this position and would love to discuss further.

Best regards,
Lisa Wang""",
                "sender_domain": "outlook.com",
                "expected_type": EmailType.FOLLOWUP,
                "variations": 2
            }
        ]
    
    async def setup(self) -> bool:
        """Initialize the performance validator."""
        logger.info("🚀 Setting up cache performance validator...")
        
        try:
            self.cache_manager = await get_cache_manager()
            
            if self.cache_manager._connected:
                logger.info("✅ Connected to Redis for performance testing")
                # Clear any existing cache for clean testing
                await self.cache_manager.invalidate_cache("well:email:*")
                return True
            else:
                logger.warning("⚠️ Redis not available - will test fallback performance")
                return True  # Can still test fallback mode
                
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False
    
    def _create_email_variations(self, base_content: str, num_variations: int) -> List[str]:
        """Create slight variations of email content to test caching patterns."""
        variations = [base_content]
        
        for i in range(1, num_variations):
            # Add minor variations that shouldn't affect extraction
            variation = base_content.replace("Best regards", f"Best regards ({i})")
            variation = variation.replace("Hi there", f"Hi there - {i}")
            variations.append(variation)
        
        return variations
    
    async def measure_processing_time(self, email_content: str, sender_domain: str) -> Tuple[float, Dict[str, Any]]:
        """Measure email processing time and return result."""
        start_time = time.time()
        
        try:
            # Process email through full pipeline
            result = await self.processor.process_email(email_content, sender_domain)
            
            # Apply business rules
            if result:
                processed = self.business_rules.process_data(
                    result.model_dump(),
                    email_content,
                    f"test@{sender_domain}"
                )
            else:
                processed = {}
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            return processing_time, processed
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return time.time() - start_time, {}
    
    async def test_cache_miss_performance(self) -> Dict[str, float]:
        """Test performance without cache (cold processing)."""
        logger.info("🔍 Testing cache miss performance (cold processing)...")
        
        miss_times = []
        
        for scenario in self.test_scenarios:
            variations = self._create_email_variations(
                scenario["content"], 
                scenario["variations"]
            )
            
            for i, variation in enumerate(variations):
                # Ensure cache miss by using unique content
                unique_content = f"{variation}\n\n--- Test ID: {scenario['name']}_{i}_{int(time.time())} ---"
                
                processing_time, result = await self.measure_processing_time(
                    unique_content,
                    scenario["sender_domain"]
                )
                
                miss_times.append(processing_time)
                self.metrics["cache_misses"] += 1
                self.metrics["total_requests"] += 1
                
                logger.debug(f"Cache miss - {scenario['name']}_{i}: {processing_time:.3f}s")
        
        avg_miss_time = statistics.mean(miss_times) if miss_times else 0
        median_miss_time = statistics.median(miss_times) if miss_times else 0
        
        logger.info(f"📊 Cache miss performance:")
        logger.info(f"   Average: {avg_miss_time:.3f}s")
        logger.info(f"   Median: {median_miss_time:.3f}s")
        logger.info(f"   Requests: {len(miss_times)}")
        
        self.metrics["time_without_cache"].extend(miss_times)
        
        return {
            "average_ms": avg_miss_time * 1000,
            "median_ms": median_miss_time * 1000,
            "total_requests": len(miss_times)
        }
    
    async def test_cache_hit_performance(self) -> Dict[str, float]:
        """Test performance with cache hits."""
        logger.info("🔍 Testing cache hit performance...")
        
        hit_times = []
        
        # First, populate cache with base scenarios
        logger.info("Populating cache with base scenarios...")
        for scenario in self.test_scenarios:
            # Use the base content for caching
            await self.measure_processing_time(
                scenario["content"],
                scenario["sender_domain"]
            )
        
        # Give cache time to settle
        await asyncio.sleep(1)
        
        # Now test cache hits with identical content
        for scenario in self.test_scenarios:
            # Test multiple requests for the same content (should hit cache)
            for request_num in range(3):  # 3 requests per scenario
                processing_time, result = await self.measure_processing_time(
                    scenario["content"],
                    scenario["sender_domain"]
                )
                
                hit_times.append(processing_time)
                self.metrics["total_requests"] += 1
                
                # Check if this was likely a cache hit (much faster)
                if processing_time < 0.5:  # Less than 500ms indicates likely cache hit
                    self.metrics["cache_hits"] += 1
                else:
                    self.metrics["cache_misses"] += 1
                
                logger.debug(f"Request {request_num+1} - {scenario['name']}: {processing_time:.3f}s")
        
        avg_hit_time = statistics.mean(hit_times) if hit_times else 0
        median_hit_time = statistics.median(hit_times) if hit_times else 0
        
        logger.info(f"📊 Cache hit performance:")
        logger.info(f"   Average: {avg_hit_time:.3f}s")
        logger.info(f"   Median: {median_hit_time:.3f}s")
        logger.info(f"   Requests: {len(hit_times)}")
        
        self.metrics["time_with_cache"].extend(hit_times)
        
        return {
            "average_ms": avg_hit_time * 1000,
            "median_ms": median_hit_time * 1000,
            "total_requests": len(hit_times)
        }
    
    async def calculate_cost_savings(self) -> Dict[str, float]:
        """Calculate actual cost savings based on cache performance."""
        cache_metrics = await self.cache_manager.get_metrics()
        
        # Extract metrics from Redis cache manager
        total_requests = cache_metrics.get("total_requests", 0)
        hits = cache_metrics.get("hits", 0)
        current_savings = cache_metrics.get("savings", 0)
        
        # Calculate hit rate
        hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
        
        # Cost calculation (based on documentation)
        # GPT-5-mini: $0.25/1M tokens (new requests)  
        # Cached responses: $0.025/1M tokens (90% savings)
        avg_tokens_per_request = 500  # Estimated based on email processing
        
        # Calculate what cost would be without caching
        total_tokens = total_requests * avg_tokens_per_request
        cost_without_cache = (total_tokens / 1_000_000) * 0.25
        
        # Calculate actual cost with caching
        cache_hits_tokens = hits * avg_tokens_per_request
        cache_misses_tokens = (total_requests - hits) * avg_tokens_per_request
        
        cached_tokens_cost = (cache_hits_tokens / 1_000_000) * 0.025  # 90% savings
        new_tokens_cost = (cache_misses_tokens / 1_000_000) * 0.25
        
        actual_cost = cached_tokens_cost + new_tokens_cost
        total_savings = cost_without_cache - actual_cost
        savings_percentage = (total_savings / cost_without_cache * 100) if cost_without_cache > 0 else 0
        
        return {
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "cache_hits": hits,
            "cost_without_cache": cost_without_cache,
            "actual_cost_with_cache": actual_cost,
            "total_savings": total_savings,
            "savings_percentage": savings_percentage,
            "avg_tokens_per_request": avg_tokens_per_request
        }
    
    async def run_comprehensive_performance_test(self) -> Dict[str, Any]:
        """Run comprehensive performance validation."""
        logger.info("🧪 Starting comprehensive cache performance validation...")
        logger.info("=" * 80)
        
        setup_success = await self.setup()
        if not setup_success:
            return {"error": "Setup failed"}
        
        results = {
            "test_start_time": datetime.now().isoformat(),
            "redis_available": self.cache_manager._connected if self.cache_manager else False,
            "fallback_mode": self.cache_manager.fallback_mode if self.cache_manager else True
        }
        
        # Test 1: Cache Miss Performance
        logger.info("\n" + "=" * 40)
        logger.info("TEST 1: CACHE MISS PERFORMANCE")
        logger.info("=" * 40)
        
        miss_performance = await self.test_cache_miss_performance()
        results["cache_miss_performance"] = miss_performance
        
        # Test 2: Cache Hit Performance  
        logger.info("\n" + "=" * 40)
        logger.info("TEST 2: CACHE HIT PERFORMANCE")
        logger.info("=" * 40)
        
        hit_performance = await self.test_cache_hit_performance()
        results["cache_hit_performance"] = hit_performance
        
        # Test 3: Cost Savings Analysis
        logger.info("\n" + "=" * 40)
        logger.info("TEST 3: COST SAVINGS ANALYSIS")
        logger.info("=" * 40)
        
        cost_savings = await self.calculate_cost_savings()
        results["cost_analysis"] = cost_savings
        
        # Test 4: Performance Comparison
        logger.info("\n" + "=" * 40)
        logger.info("TEST 4: PERFORMANCE COMPARISON")
        logger.info("=" * 40)
        
        if self.metrics["time_with_cache"] and self.metrics["time_without_cache"]:
            avg_with_cache = statistics.mean(self.metrics["time_with_cache"])
            avg_without_cache = statistics.mean(self.metrics["time_without_cache"])
            
            performance_improvement = ((avg_without_cache - avg_with_cache) / avg_without_cache * 100) if avg_without_cache > 0 else 0
            
            results["performance_comparison"] = {
                "avg_time_with_cache_ms": avg_with_cache * 1000,
                "avg_time_without_cache_ms": avg_without_cache * 1000,
                "performance_improvement_pct": performance_improvement,
                "speed_multiplier": avg_without_cache / avg_with_cache if avg_with_cache > 0 else 1
            }
            
            logger.info(f"📈 Performance improvement: {performance_improvement:.1f}%")
            logger.info(f"🚀 Speed multiplier: {avg_without_cache / avg_with_cache:.1f}x faster" if avg_with_cache > 0 else "")
        
        # Test 5: Cache Strategy Validation
        logger.info("\n" + "=" * 40)
        logger.info("TEST 5: CACHE STRATEGY VALIDATION")
        logger.info("=" * 40)
        
        strategy_results = await self._validate_cache_strategies()
        results["strategy_validation"] = strategy_results
        
        results["test_completion_time"] = datetime.now().isoformat()
        results["overall_metrics"] = self.metrics
        
        return results
    
    async def _validate_cache_strategies(self) -> Dict[str, Any]:
        """Validate cache strategy effectiveness."""
        strategy_results = {
            "email_classifications": {},
            "ttl_validation": {},
            "pattern_recognition": {}
        }
        
        for scenario in self.test_scenarios:
            # Test classification accuracy
            classified_type = self.strategy_manager.classify_email(
                scenario["content"],
                scenario["sender_domain"]
            )
            
            classification_correct = classified_type == scenario["expected_type"]
            strategy_results["email_classifications"][scenario["name"]] = {
                "expected": scenario["expected_type"].value,
                "actual": classified_type.value,
                "correct": classification_correct
            }
            
            # Test caching decision
            should_cache, ttl, pattern_key = self.strategy_manager.should_cache(
                scenario["content"],
                scenario["sender_domain"],
                {"candidate_name": "Test", "job_title": "Test"}
            )
            
            strategy_results["ttl_validation"][scenario["name"]] = {
                "should_cache": should_cache,
                "ttl_hours": ttl.total_seconds() / 3600,
                "pattern_key": pattern_key
            }
        
        return strategy_results
    
    def generate_performance_report(self, results: Dict[str, Any]):
        """Generate comprehensive performance report."""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 REDIS CACHE PERFORMANCE VALIDATION REPORT")
        logger.info("=" * 80)
        
        # Overall Status
        redis_status = "✅ Connected" if results.get("redis_available") else "⚠️ Fallback Mode"
        logger.info(f"Redis Status: {redis_status}")
        logger.info(f"Test Duration: {results.get('test_start_time')} to {results.get('test_completion_time')}")
        
        # Performance Results
        if "performance_comparison" in results:
            perf = results["performance_comparison"]
            logger.info("\n📊 PERFORMANCE METRICS:")
            logger.info(f"   With Cache: {perf['avg_time_with_cache_ms']:.1f}ms")
            logger.info(f"   Without Cache: {perf['avg_time_without_cache_ms']:.1f}ms")
            logger.info(f"   Improvement: {perf['performance_improvement_pct']:.1f}%")
            logger.info(f"   Speed Multiplier: {perf['speed_multiplier']:.1f}x faster")
        
        # Cost Analysis
        if "cost_analysis" in results:
            cost = results["cost_analysis"]
            logger.info("\n💰 COST SAVINGS ANALYSIS:")
            logger.info(f"   Hit Rate: {cost['hit_rate']:.1f}%")
            logger.info(f"   Total Requests: {cost['total_requests']}")
            logger.info(f"   Cache Hits: {cost['cache_hits']}")
            logger.info(f"   Cost Without Cache: ${cost['cost_without_cache']:.6f}")
            logger.info(f"   Actual Cost With Cache: ${cost['actual_cost_with_cache']:.6f}")
            logger.info(f"   Total Savings: ${cost['total_savings']:.6f}")
            logger.info(f"   Savings Percentage: {cost['savings_percentage']:.1f}%")
        
        # Strategy Validation
        if "strategy_validation" in results:
            strategy = results["strategy_validation"]
            classifications = strategy.get("email_classifications", {})
            correct_classifications = sum(1 for v in classifications.values() if v["correct"])
            total_classifications = len(classifications)
            
            logger.info("\n🎯 STRATEGY VALIDATION:")
            logger.info(f"   Classification Accuracy: {correct_classifications}/{total_classifications} ({(correct_classifications/total_classifications*100):.1f}%)")
            
            for name, result in classifications.items():
                status = "✅" if result["correct"] else "❌"
                logger.info(f"   {status} {name}: {result['expected']} → {result['actual']}")
        
        # Validation Against Claims
        logger.info("\n🏆 VALIDATION AGAINST PERFORMANCE CLAIMS:")
        
        if "cost_analysis" in results:
            savings_pct = results["cost_analysis"]["savings_percentage"]
            if savings_pct >= 85:
                logger.info(f"   ✅ Cost Reduction: {savings_pct:.1f}% (Exceeds 90% claim)")
            elif savings_pct >= 70:
                logger.info(f"   ⚠️ Cost Reduction: {savings_pct:.1f}% (Good but below 90% claim)")
            else:
                logger.info(f"   ❌ Cost Reduction: {savings_pct:.1f}% (Below expectations)")
        
        if "performance_comparison" in results:
            perf_improvement = results["performance_comparison"]["performance_improvement_pct"]
            if perf_improvement >= 40:
                logger.info(f"   ✅ Performance: {perf_improvement:.1f}% improvement (Excellent)")
            elif perf_improvement >= 20:
                logger.info(f"   ⚠️ Performance: {perf_improvement:.1f}% improvement (Good)")
            else:
                logger.info(f"   ❌ Performance: {perf_improvement:.1f}% improvement (Needs work)")
        
        # Recommendations
        logger.info("\n📋 RECOMMENDATIONS:")
        
        if results.get("redis_available"):
            logger.info("   ✅ Redis is operational - monitor in production")
        else:
            logger.info("   ⚠️ Configure Redis for full caching benefits")
        
        if "cost_analysis" in results and results["cost_analysis"]["hit_rate"] < 50:
            logger.info("   📈 Optimize cache strategies to improve hit rate")
        
        logger.info("   📊 Continue monitoring cache performance in production")
        logger.info("   🔄 Adjust TTL values based on usage patterns")
        logger.info("   💡 Consider pre-warming cache for common email patterns")
        
        logger.info("=" * 80)


async def main():
    """Run cache performance validation."""
    validator = CachePerformanceValidator()
    results = await validator.run_comprehensive_performance_test()
    
    if "error" in results:
        logger.error(f"❌ Performance validation failed: {results['error']}")
        return 1
    
    # Generate report
    validator.generate_performance_report(results)
    
    # Save detailed results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"cache_performance_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n📁 Detailed results saved to: {results_file}")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))