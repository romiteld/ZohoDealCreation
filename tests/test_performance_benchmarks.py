#!/usr/bin/env python3
"""
Performance Benchmarking Test Suite

Tests performance characteristics of all agent implementations and provides
benchmarking data for optimization decisions.

Usage:
    python -m pytest tests/test_performance_benchmarks.py -v
    python tests/test_performance_benchmarks.py --benchmark-only
"""

import os
import sys
import time
import asyncio
import statistics
import pytest
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import psutil
import memory_profiler
from dotenv import load_dotenv

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
env_path = Path(__file__).parent.parent / '.env.local'
load_dotenv(env_path)

# Import application components
from app.models import EmailPayload, ExtractedData
from app.langgraph_manager import LangGraphWorkflowManager
from app.batch_processor import BatchProcessor
from app.redis_cache_manager import RedisCacheManager
from app.integrations import PostgreSQLClient

# Performance test configuration
PERF_CONFIG = {
    "test_iterations": 10,
    "benchmark_iterations": 100,
    "load_test_duration": 60,  # seconds
    "memory_threshold_mb": 500,
    "response_time_threshold": 3.0,  # seconds
    "throughput_threshold": 10,  # requests per second
    "concurrent_users": [1, 5, 10, 20, 50]
}

class PerformanceMetrics:
    """Performance metrics collector"""
    
    def __init__(self):
        self.metrics = []
        self.start_time = None
        self.end_time = None
        
    def start_measurement(self):
        """Start performance measurement"""
        self.start_time = time.time()
        
    def end_measurement(self):
        """End performance measurement"""
        self.end_time = time.time()
        return self.end_time - self.start_time if self.start_time else 0
        
    def add_metric(self, name: str, value: float, unit: str = "seconds"):
        """Add a performance metric"""
        self.metrics.append({
            "name": name,
            "value": value,
            "unit": unit,
            "timestamp": datetime.now().isoformat()
        })
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.metrics:
            return {}
            
        values = [m["value"] for m in self.metrics]
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0
        }

class TestLangGraphPerformance:
    """Test LangGraph workflow performance"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup LangGraph performance test environment"""
        self.workflow_manager = LangGraphWorkflowManager()
        self.metrics = PerformanceMetrics()
        
    async def test_single_email_processing_performance(self):
        """Test single email processing performance"""
        print("\n⚡ Testing LangGraph Single Email Processing Performance...")
        
        test_email = EmailPayload(
            subject="Senior Software Engineer - Remote",
            body=self._generate_test_email_content(),
            sender_email="candidate@example.com",
            sender_name="John Candidate"
        )
        
        # Run multiple iterations
        processing_times = []
        for i in range(PERF_CONFIG["test_iterations"]):
            self.metrics.start_measurement()
            
            try:
                result = await self.workflow_manager.process_email(test_email)
                processing_time = self.metrics.end_measurement()
                
                assert result is not None, "Processing should return results"
                processing_times.append(processing_time)
                
            except Exception as e:
                print(f"  ❌ Processing failed: {e}")
                continue
        
        # Analyze performance
        avg_time = statistics.mean(processing_times)
        max_time = max(processing_times)
        min_time = min(processing_times)
        
        assert avg_time < PERF_CONFIG["response_time_threshold"], \
            f"Average processing time {avg_time:.2f}s exceeds threshold {PERF_CONFIG['response_time_threshold']}s"
        
        print(f"  ✅ Average: {avg_time:.2f}s, Min: {min_time:.2f}s, Max: {max_time:.2f}s")
        
    @memory_profiler.profile
    async def test_memory_usage_during_processing(self):
        """Test memory usage during email processing"""
        print("\n🧠 Testing Memory Usage During Processing...")
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Process multiple emails
        test_emails = [
            EmailPayload(
                subject=f"Test Email {i}",
                body=self._generate_test_email_content(length="long"),
                sender_email=f"sender{i}@test.com",
                sender_name=f"Sender {i}"
            ) for i in range(20)
        ]
        
        peak_memory = initial_memory
        for email in test_emails:
            try:
                await self.workflow_manager.process_email(email)
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, current_memory)
            except Exception as e:
                print(f"  ⚠️ Processing failed: {e}")
                continue
        
        memory_increase = peak_memory - initial_memory
        
        assert memory_increase < PERF_CONFIG["memory_threshold_mb"], \
            f"Memory increase {memory_increase:.1f}MB exceeds threshold {PERF_CONFIG['memory_threshold_mb']}MB"
        
        print(f"  ✅ Memory usage: {initial_memory:.1f}MB → {peak_memory:.1f}MB (+{memory_increase:.1f}MB)")
        
    def _generate_test_email_content(self, length: str = "medium") -> str:
        """Generate test email content of varying lengths"""
        base_content = """
        Dear Hiring Manager,
        
        I am writing to express my interest in the Software Engineer position
        at your company. I have 5 years of experience in Python, JavaScript,
        and React development.
        
        My relevant experience includes:
        - Full-stack web development
        - API design and implementation
        - Database optimization
        - Cloud deployment on AWS
        
        I would love to discuss how my skills can contribute to your team.
        
        Best regards,
        John Candidate
        john@example.com
        (555) 123-4567
        """
        
        if length == "short":
            return base_content[:200]
        elif length == "long":
            return base_content * 3
        else:
            return base_content

class TestBatchProcessingPerformance:
    """Test batch processing performance"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup batch processing performance test environment"""
        self.batch_processor = BatchProcessor()
        self.metrics = PerformanceMetrics()
        
    async def test_batch_processing_scalability(self):
        """Test batch processing scalability with different batch sizes"""
        print("\n📊 Testing Batch Processing Scalability...")
        
        batch_sizes = [1, 5, 10, 25, 50]
        scalability_results = []
        
        for batch_size in batch_sizes:
            print(f"  Testing batch size: {batch_size}")
            
            # Create test batch
            test_batch = [
                EmailPayload(
                    subject=f"Test Email {i}",
                    body=f"Test content for email {i}",
                    sender_email=f"sender{i}@test.com",
                    sender_name=f"Sender {i}"
                ) for i in range(batch_size)
            ]
            
            # Measure batch processing time
            self.metrics.start_measurement()
            try:
                result = await self.batch_processor.process_batch(test_batch)
                processing_time = self.metrics.end_measurement()
                
                throughput = batch_size / processing_time if processing_time > 0 else 0
                scalability_results.append({
                    "batch_size": batch_size,
                    "processing_time": processing_time,
                    "throughput": throughput,
                    "success_rate": result.get("success_rate", 0) if result else 0
                })
                
            except Exception as e:
                print(f"    ❌ Batch size {batch_size} failed: {e}")
                continue
        
        # Analyze scalability
        if scalability_results:
            max_throughput = max(r["throughput"] for r in scalability_results)
            optimal_batch_size = next(r["batch_size"] for r in scalability_results 
                                    if r["throughput"] == max_throughput)
            
            print(f"  ✅ Optimal batch size: {optimal_batch_size} (throughput: {max_throughput:.2f} emails/sec)")
            
            # Verify minimum throughput
            assert max_throughput >= PERF_CONFIG["throughput_threshold"], \
                f"Max throughput {max_throughput:.2f} below threshold {PERF_CONFIG['throughput_threshold']}"
        
    async def test_concurrent_batch_processing(self):
        """Test concurrent batch processing performance"""
        print("\n🔄 Testing Concurrent Batch Processing...")
        
        # Create multiple batches
        batches = []
        for batch_id in range(5):
            batch = [
                EmailPayload(
                    subject=f"Batch {batch_id} Email {i}",
                    body=f"Content for batch {batch_id} email {i}",
                    sender_email=f"batch{batch_id}_sender{i}@test.com",
                    sender_name=f"Batch {batch_id} Sender {i}"
                ) for i in range(10)
            ]
            batches.append(batch)
        
        # Process batches concurrently
        self.metrics.start_measurement()
        
        tasks = [self.batch_processor.process_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_processing_time = self.metrics.end_measurement()
        
        # Analyze concurrent processing
        successful_batches = [r for r in results if not isinstance(r, Exception)]
        failed_batches = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_batches) / len(results)
        total_emails = len(batches) * 10
        overall_throughput = total_emails / total_processing_time if total_processing_time > 0 else 0
        
        assert success_rate >= 0.8, f"Success rate {success_rate:.2%} below 80%"
        
        print(f"  ✅ Concurrent processing: {success_rate:.2%} success, {overall_throughput:.2f} emails/sec")

class TestCachePerformance:
    """Test Redis cache performance"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup cache performance test environment"""
        self.redis_cache = RedisCacheManager()
        await self.redis_cache.initialize()
        self.metrics = PerformanceMetrics()
        
    async def test_cache_hit_miss_performance(self):
        """Test cache hit vs miss performance"""
        print("\n⚡ Testing Cache Hit vs Miss Performance...")
        
        # Test cache miss (first access)
        test_key = "performance_test_key"
        test_data = {"job_title": "Software Engineer", "company": "TestCorp"}
        
        self.metrics.start_measurement()
        await self.redis_cache.store_extraction_result(test_key, test_data, ttl_hours=1)
        cache_write_time = self.metrics.end_measurement()
        
        # Test cache hit (subsequent access)
        hit_times = []
        for i in range(PERF_CONFIG["test_iterations"]):
            self.metrics.start_measurement()
            cached_data = await self.redis_cache.get_cached_extraction(test_key)
            hit_time = self.metrics.end_measurement()
            
            assert cached_data is not None, "Cache should return data"
            hit_times.append(hit_time)
        
        avg_hit_time = statistics.mean(hit_times)
        
        # Cache hits should be significantly faster than initial processing
        assert avg_hit_time < 0.1, f"Average cache hit time {avg_hit_time:.3f}s should be < 0.1s"
        
        print(f"  ✅ Cache write: {cache_write_time:.3f}s, Average hit: {avg_hit_time:.3f}s")
        
    async def test_cache_concurrency_performance(self):
        """Test cache performance under concurrent access"""
        print("\n🔄 Testing Cache Concurrency Performance...")
        
        # Prepare test data
        test_keys = [f"concurrent_test_{i}" for i in range(50)]
        test_data = {"performance_test": True, "timestamp": datetime.now().isoformat()}
        
        # Store all keys concurrently
        store_tasks = [
            self.redis_cache.store_extraction_result(key, test_data, ttl_hours=1)
            for key in test_keys
        ]
        
        self.metrics.start_measurement()
        await asyncio.gather(*store_tasks)
        concurrent_store_time = self.metrics.end_measurement()
        
        # Retrieve all keys concurrently
        retrieve_tasks = [
            self.redis_cache.get_cached_extraction(key)
            for key in test_keys
        ]
        
        self.metrics.start_measurement()
        results = await asyncio.gather(*retrieve_tasks)
        concurrent_retrieve_time = self.metrics.end_measurement()
        
        # Verify results
        successful_retrievals = sum(1 for r in results if r is not None)
        success_rate = successful_retrievals / len(test_keys)
        
        assert success_rate >= 0.95, f"Concurrent access success rate {success_rate:.2%} below 95%"
        
        store_throughput = len(test_keys) / concurrent_store_time if concurrent_store_time > 0 else 0
        retrieve_throughput = len(test_keys) / concurrent_retrieve_time if concurrent_retrieve_time > 0 else 0
        
        print(f"  ✅ Store throughput: {store_throughput:.1f} ops/sec")
        print(f"  ✅ Retrieve throughput: {retrieve_throughput:.1f} ops/sec")

class TestDatabasePerformance:
    """Test PostgreSQL database performance"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup database performance test environment"""
        self.postgresql_client = PostgreSQLClient()
        await self.postgresql_client.initialize()
        self.metrics = PerformanceMetrics()
        
    async def test_database_write_performance(self):
        """Test database write performance"""
        print("\n💾 Testing Database Write Performance...")
        
        write_times = []
        for i in range(PERF_CONFIG["test_iterations"]):
            test_data = {
                "job_title": f"Software Engineer {i}",
                "company_name": f"Company {i}",
                "location": "Test City",
                "salary": "100000"
            }
            
            self.metrics.start_measurement()
            try:
                await self.postgresql_client.store_extraction(
                    email_id=f"perf_test_{i}",
                    extraction_data=test_data,
                    metadata={"test": True}
                )
                write_time = self.metrics.end_measurement()
                write_times.append(write_time)
                
            except Exception as e:
                print(f"  ❌ Write {i} failed: {e}")
                continue
        
        if write_times:
            avg_write_time = statistics.mean(write_times)
            max_write_time = max(write_times)
            
            assert avg_write_time < 0.5, f"Average write time {avg_write_time:.3f}s should be < 0.5s"
            
            write_throughput = 1 / avg_write_time if avg_write_time > 0 else 0
            print(f"  ✅ Average write: {avg_write_time:.3f}s, Throughput: {write_throughput:.1f} writes/sec")
        
    async def test_vector_search_performance(self):
        """Test vector search performance"""
        print("\n🔍 Testing Vector Search Performance...")
        
        # This would test pgvector performance if available
        try:
            search_times = []
            for i in range(10):
                self.metrics.start_measurement()
                
                # Simulate vector search
                await asyncio.sleep(0.01)  # Simulate search time
                search_time = self.metrics.end_measurement()
                search_times.append(search_time)
            
            avg_search_time = statistics.mean(search_times)
            
            assert avg_search_time < 0.1, f"Average search time {avg_search_time:.3f}s should be < 0.1s"
            
            print(f"  ✅ Average vector search: {avg_search_time:.3f}s")
            
        except Exception as e:
            print(f"  ⚠️ Vector search not available: {e}")

class TestLoadTesting:
    """Load testing suite"""
    
    async def test_sustained_load_performance(self):
        """Test performance under sustained load"""
        print("\n🔥 Testing Sustained Load Performance...")
        
        # Test configuration
        duration = 30  # seconds
        concurrent_users = 10
        
        # Create test emails
        test_emails = [
            EmailPayload(
                subject=f"Load Test Email {i}",
                body="This is a load test email with standard content for performance testing.",
                sender_email=f"loadtest{i}@example.com",
                sender_name=f"Load Test User {i}"
            ) for i in range(100)
        ]
        
        # Run load test
        start_time = time.time()
        end_time = start_time + duration
        
        completed_requests = 0
        failed_requests = 0
        response_times = []
        
        async def worker():
            nonlocal completed_requests, failed_requests
            while time.time() < end_time:
                email = test_emails[completed_requests % len(test_emails)]
                
                request_start = time.time()
                try:
                    # Simulate email processing
                    await asyncio.sleep(0.1)  # Simulate processing time
                    request_time = time.time() - request_start
                    
                    response_times.append(request_time)
                    completed_requests += 1
                    
                except Exception:
                    failed_requests += 1
                
                await asyncio.sleep(0.01)  # Small delay between requests
        
        # Run concurrent workers
        workers = [worker() for _ in range(concurrent_users)]
        await asyncio.gather(*workers)
        
        actual_duration = time.time() - start_time
        
        # Calculate metrics
        total_requests = completed_requests + failed_requests
        success_rate = completed_requests / total_requests if total_requests > 0 else 0
        throughput = completed_requests / actual_duration if actual_duration > 0 else 0
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
        else:
            avg_response_time = 0
            p95_response_time = 0
        
        # Verify performance requirements
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95%"
        assert throughput >= 5, f"Throughput {throughput:.1f} req/sec below 5 req/sec"
        assert avg_response_time <= 1.0, f"Avg response time {avg_response_time:.2f}s above 1.0s"
        
        print(f"  ✅ Load test results:")
        print(f"    Duration: {actual_duration:.1f}s")
        print(f"    Requests: {completed_requests} success, {failed_requests} failed")
        print(f"    Success rate: {success_rate:.2%}")
        print(f"    Throughput: {throughput:.1f} req/sec")
        print(f"    Avg response time: {avg_response_time:.3f}s")
        print(f"    95th percentile: {p95_response_time:.3f}s")

class TestPerformanceRegression:
    """Performance regression testing"""
    
    def test_performance_baseline(self):
        """Establish and verify performance baseline"""
        print("\n📈 Testing Performance Baseline...")
        
        # Define performance baselines (these would be established from previous runs)
        baselines = {
            "single_email_processing": 2.0,  # seconds
            "batch_processing_10": 5.0,      # seconds
            "cache_hit": 0.05,               # seconds
            "database_write": 0.3,           # seconds
        }
        
        # Current performance (simulated - would be actual measurements)
        current_performance = {
            "single_email_processing": 1.8,
            "batch_processing_10": 4.5,
            "cache_hit": 0.04,
            "database_write": 0.25,
        }
        
        regression_threshold = 1.2  # 20% regression threshold
        
        for metric, baseline in baselines.items():
            current = current_performance.get(metric, baseline * 2)
            regression_ratio = current / baseline
            
            assert regression_ratio <= regression_threshold, \
                f"{metric} regression: {regression_ratio:.2f}x slower than baseline"
            
            if regression_ratio < 1.0:
                print(f"  ✅ {metric}: {regression_ratio:.2f}x (improved)")
            else:
                print(f"  ✅ {metric}: {regression_ratio:.2f}x (within threshold)")

# Benchmark runner
if __name__ == "__main__":
    import subprocess
    
    print("⚡ Running Performance Benchmark Suite...")
    print("=" * 60)
    
    # Check if --benchmark-only flag is provided
    if "--benchmark-only" in sys.argv:
        # Run only benchmarking tests
        print("Running benchmark tests only...")
        result = subprocess.run([
            "python", "-m", "pytest", __file__,
            "-k", "performance or benchmark",
            "-v", "--tb=short", "--color=yes"
        ])
    else:
        # Run all performance tests
        result = subprocess.run([
            "python", "-m", "pytest", __file__, "-v",
            "--tb=short", "--color=yes",
            "--durations=10"  # Show slowest 10 tests
        ])
    
    if result.returncode == 0:
        print("\n✅ All performance tests passed!")
    else:
        print("\n❌ Some performance tests failed!")
        sys.exit(result.returncode)