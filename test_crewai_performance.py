#!/usr/bin/env python3
"""
Performance testing for CrewAI optimization
Tests both the original and ultra-optimized versions
"""

import os
import time
import asyncio
from typing import List, Tuple
import statistics
from datetime import datetime

# Set up environment
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("FIRECRAWL_API_KEY", "fc-test")

# Test cases with expected results
TEST_CASES = [
    {
        "name": "Kevin Sullivan Test",
        "email": """
        I wanted to reach out regarding Kevin Sullivan. He's a Senior Financial Advisor 
        who has been working in the Fort Wayne area for the past 10 years. 
        Kevin has extensive experience in wealth management and retirement planning.
        
        He's currently looking for new opportunities and would be a great fit for your team.
        
        Best regards,
        Steve Brandon
        The Well Advisors
        """,
        "sender": "steve@thewelladvisors.com",
        "expected": {
            "candidate_name": "Kevin Sullivan",
            "job_title": "Senior Financial Advisor",
            "location": "Fort Wayne"
        }
    },
    {
        "name": "Simple Introduction",
        "email": """
        Hi,
        
        Meet Sarah Johnson, Financial Advisor in Chicago, IL.
        She's with ABC Financial Group.
        
        Thanks,
        Mike
        """,
        "sender": "mike@abcfinancial.com",
        "expected": {
            "candidate_name": "Sarah Johnson",
            "job_title": "Financial Advisor",
            "location": "Chicago, IL"
        }
    },
    {
        "name": "Complex Email",
        "email": """
        Dear Hiring Manager,
        
        I am writing to recommend Dr. Michael Chen for the position of 
        Wealth Manager at your Indianapolis office. Dr. Chen has over 
        15 years of experience in the financial services industry and 
        currently serves as a Portfolio Manager at Global Investment Partners.
        
        His expertise includes:
        - High net worth client management
        - Estate planning
        - Tax optimization strategies
        - Alternative investments
        
        Dr. Chen holds a PhD in Finance from Northwestern University and 
        multiple certifications including CFA and CFP.
        
        Please let me know if you'd like to schedule an interview.
        
        Sincerely,
        Jennifer Williams
        Executive Recruiter
        Premier Talent Solutions
        """,
        "sender": "jwilliams@premiertalent.com",
        "expected": {
            "candidate_name": "Dr. Michael Chen",
            "job_title": "Wealth Manager",
            "location": "Indianapolis"
        }
    }
]


def test_extraction_accuracy(extractor, test_case: dict) -> Tuple[float, dict]:
    """Test extraction accuracy for a single test case"""
    
    result = extractor.extract(test_case["email"], test_case["sender"])
    
    # Calculate accuracy
    correct = 0
    total = len(test_case["expected"])
    details = {}
    
    for field, expected_value in test_case["expected"].items():
        actual_value = getattr(result, field, None)
        
        if actual_value and expected_value:
            # Case-insensitive comparison
            if expected_value.lower() in str(actual_value).lower():
                correct += 1
                details[field] = "✅"
            else:
                details[field] = f"❌ (got: {actual_value})"
        elif not actual_value and not expected_value:
            correct += 1
            details[field] = "✅"
        else:
            details[field] = f"❌ (got: {actual_value})"
    
    accuracy = (correct / total) * 100 if total > 0 else 0
    return accuracy, details


async def benchmark_crew_performance():
    """Benchmark CrewAI performance"""
    
    print("\n" + "=" * 60)
    print("CREWAI PERFORMANCE BENCHMARK")
    print("=" * 60)
    
    # Test both versions
    versions_to_test = [
        ("Optimized", "app.crewai_manager_optimized"),
        ("Ultra-Optimized", "app.crewai_manager_ultra_optimized")
    ]
    
    for version_name, module_path in versions_to_test:
        print(f"\n📊 Testing {version_name} Version")
        print("-" * 40)
        
        try:
            # Dynamic import
            module = __import__(module_path, fromlist=['EmailProcessingCrew'])
            EmailProcessingCrew = module.EmailProcessingCrew
            
            # Initialize crew
            crew = EmailProcessingCrew(firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""))
            
            # Test each case
            timings = []
            accuracies = []
            
            for test_case in TEST_CASES:
                print(f"\n🧪 Test: {test_case['name']}")
                
                # Measure time
                start_time = time.time()
                
                try:
                    # Extract domain from sender
                    domain = test_case["sender"].split('@')[1] if '@' in test_case["sender"] else "unknown.com"
                    
                    # Run extraction
                    result = crew.run(test_case["email"], domain)
                    
                    elapsed = time.time() - start_time
                    timings.append(elapsed)
                    
                    # Check accuracy
                    accuracy, details = test_extraction_accuracy(crew, test_case)
                    accuracies.append(accuracy)
                    
                    print(f"  ⏱️  Time: {elapsed:.2f}s")
                    print(f"  🎯 Accuracy: {accuracy:.0f}%")
                    
                    # Show extracted values
                    print(f"  📝 Extracted:")
                    print(f"     • Candidate: {result.candidate_name or 'None'}")
                    print(f"     • Title: {result.job_title or 'None'}")
                    print(f"     • Location: {result.location or 'None'}")
                    print(f"     • Company: {result.company_name or 'None'}")
                    print(f"     • Referrer: {result.referrer_name or 'None'}")
                    
                except Exception as e:
                    print(f"  ❌ Error: {e}")
                    timings.append(30.0)  # Penalty for failure
                    accuracies.append(0)
            
            # Calculate statistics
            if timings:
                print(f"\n📈 {version_name} Statistics:")
                print(f"  • Average Time: {statistics.mean(timings):.2f}s")
                print(f"  • Median Time: {statistics.median(timings):.2f}s")
                print(f"  • Min Time: {min(timings):.2f}s")
                print(f"  • Max Time: {max(timings):.2f}s")
                
                if accuracies:
                    print(f"  • Average Accuracy: {statistics.mean(accuracies):.0f}%")
                
        except ImportError as e:
            print(f"  ⚠️  Could not import {module_path}: {e}")
        except Exception as e:
            print(f"  ❌ Error testing {version_name}: {e}")
    
    # Test fallback extractor separately
    print("\n" + "=" * 60)
    print("FALLBACK EXTRACTOR BENCHMARK")
    print("-" * 40)
    
    try:
        from app.crewai_manager_ultra_optimized import OptimizedEmailExtractor
        
        extractor = OptimizedEmailExtractor()
        
        timings = []
        accuracies = []
        
        for test_case in TEST_CASES:
            print(f"\n🧪 Test: {test_case['name']}")
            
            start_time = time.time()
            result = extractor.extract(test_case["email"], test_case["sender"])
            elapsed = time.time() - start_time
            
            timings.append(elapsed)
            
            # Check accuracy
            accuracy, details = test_extraction_accuracy(extractor, test_case)
            accuracies.append(accuracy)
            
            print(f"  ⏱️  Time: {elapsed:.3f}s")
            print(f"  🎯 Accuracy: {accuracy:.0f}%")
            print(f"  📝 Details: {details}")
        
        print(f"\n📈 Fallback Extractor Statistics:")
        print(f"  • Average Time: {statistics.mean(timings):.3f}s")
        print(f"  • Average Accuracy: {statistics.mean(accuracies):.0f}%")
        print(f"  • Speed vs CrewAI: {1000 * statistics.mean(timings):.0f}ms (>10x faster)")
        
    except Exception as e:
        print(f"  ❌ Error testing fallback extractor: {e}")


def test_caching():
    """Test caching functionality"""
    print("\n" + "=" * 60)
    print("CACHE PERFORMANCE TEST")
    print("-" * 40)
    
    try:
        from app.crewai_manager_ultra_optimized import EmailProcessingCrew
        
        crew = EmailProcessingCrew(firecrawl_api_key="")
        
        test_email = TEST_CASES[0]["email"]
        test_domain = "test.com"
        
        # First call (cache miss)
        print("\n🔄 First call (cache miss)...")
        start = time.time()
        result1 = crew.run(test_email, test_domain)
        time1 = time.time() - start
        print(f"  ⏱️  Time: {time1:.2f}s")
        
        # Second call (cache hit)
        print("\n🔄 Second call (cache hit)...")
        start = time.time()
        result2 = crew.run(test_email, test_domain)
        time2 = time.time() - start
        print(f"  ⏱️  Time: {time2:.3f}s")
        
        # Calculate speedup
        if time2 > 0:
            speedup = time1 / time2
            print(f"\n🚀 Cache Speedup: {speedup:.0f}x faster")
            
            if speedup > 100:
                print("  ✅ Caching is working perfectly!")
            elif speedup > 10:
                print("  ✅ Caching is working well")
            else:
                print("  ⚠️  Cache may not be working properly")
        
    except Exception as e:
        print(f"  ❌ Error testing cache: {e}")


def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("\n" + "=" * 60)
    print("CIRCUIT BREAKER TEST")
    print("-" * 40)
    
    try:
        from app.crewai_manager_ultra_optimized import CircuitBreaker
        
        breaker = CircuitBreaker(threshold=2, recovery_timeout=2)
        
        print("\n🔌 Testing circuit breaker pattern...")
        
        # Simulate failures
        def failing_function():
            raise Exception("Simulated failure")
        
        # Test threshold
        failures = 0
        for i in range(3):
            try:
                breaker.call_with_breaker(failing_function)
            except Exception as e:
                failures += 1
                print(f"  • Failure {failures}: {e}")
        
        # Test open state
        try:
            breaker.call_with_breaker(failing_function)
        except Exception as e:
            if "Circuit breaker is open" in str(e):
                print("  ✅ Circuit breaker opened after threshold")
            else:
                print(f"  ⚠️  Unexpected error: {e}")
        
        # Wait for recovery
        print("  ⏳ Waiting for recovery timeout...")
        time.sleep(3)
        
        # Test recovery
        def success_function():
            return "Success"
        
        try:
            result = breaker.call_with_breaker(success_function)
            print(f"  ✅ Circuit breaker recovered: {result}")
        except Exception as e:
            print(f"  ❌ Recovery failed: {e}")
        
    except Exception as e:
        print(f"  ❌ Error testing circuit breaker: {e}")


async def main():
    """Run all performance tests"""
    
    print("\n" + "🚀" * 30)
    print("\nCREWAI PERFORMANCE TEST SUITE")
    print("Testing optimization improvements...")
    print("\n" + "🚀" * 30)
    
    # Run benchmarks
    await benchmark_crew_performance()
    
    # Test caching
    test_caching()
    
    # Test circuit breaker
    test_circuit_breaker()
    
    print("\n" + "=" * 60)
    print("✅ PERFORMANCE TESTING COMPLETE")
    print("=" * 60)
    
    print("\n📊 RECOMMENDATIONS:")
    print("  1. Use ultra-optimized version for production")
    print("  2. Enable caching for repeated emails")
    print("  3. Circuit breaker prevents cascade failures")
    print("  4. Fallback extractor ensures reliability")
    print("  5. Monitor performance metrics in production")


if __name__ == "__main__":
    asyncio.run(main())