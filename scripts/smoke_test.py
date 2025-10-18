#!/usr/bin/env python3
"""
Teams Bot Smoke Test Script
Performs basic validation of Teams Bot deployment
Usage: python smoke_test.py <base_url>
"""

import sys
import json
import time
import requests
from typing import Dict, List, Tuple
from datetime import datetime


class TeamsBotSmokeTest:
    """Smoke test suite for Teams Bot deployment."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.results = []
        self.start_time = time.time()

    def test_health_endpoint(self) -> Tuple[bool, str]:
        """Test the health endpoint."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    return True, "Health check passed"
            return False, f"Health check failed: {response.status_code}"
        except Exception as e:
            return False, f"Health check error: {str(e)}"

    def test_root_endpoint(self) -> Tuple[bool, str]:
        """Test the root endpoint."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("service") == "teams-bot":
                    return True, "Root endpoint accessible"
            return False, f"Root endpoint failed: {response.status_code}"
        except Exception as e:
            return False, f"Root endpoint error: {str(e)}"

    def test_response_time(self) -> Tuple[bool, str]:
        """Test response time is under threshold."""
        try:
            start = time.time()
            response = requests.get(f"{self.base_url}/health", timeout=5)
            elapsed = (time.time() - start) * 1000  # Convert to ms

            if elapsed < 3000:  # 3 second threshold
                return True, f"Response time OK: {elapsed:.0f}ms"
            else:
                return False, f"Response time slow: {elapsed:.0f}ms"
        except Exception as e:
            return False, f"Response time test error: {str(e)}"

    def test_webhook_endpoint_exists(self) -> Tuple[bool, str]:
        """Test that webhook endpoint exists (will return 401 without auth)."""
        try:
            response = requests.post(
                f"{self.base_url}/api/teams/webhook",
                json={"type": "test"},
                timeout=5
            )
            # We expect 401 (unauthorized) or 400 (bad request) - both mean endpoint exists
            if response.status_code in [400, 401, 403]:
                return True, "Webhook endpoint exists"
            elif response.status_code == 404:
                return False, "Webhook endpoint not found"
            else:
                return False, f"Unexpected webhook response: {response.status_code}"
        except Exception as e:
            return False, f"Webhook test error: {str(e)}"

    def run_all_tests(self) -> bool:
        """Run all smoke tests."""
        print("\n" + "="*50)
        print(f"Teams Bot Smoke Tests - {self.base_url}")
        print("="*50 + "\n")

        tests = [
            ("Health Check", self.test_health_endpoint),
            ("Root Endpoint", self.test_root_endpoint),
            ("Response Time", self.test_response_time),
            ("Webhook Exists", self.test_webhook_endpoint_exists),
        ]

        all_passed = True

        for test_name, test_func in tests:
            print(f"Running: {test_name}...", end=" ")
            passed, message = test_func()

            if passed:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
                all_passed = False

            self.results.append({
                "test": test_name,
                "passed": passed,
                "message": message
            })

        elapsed_time = time.time() - self.start_time

        print("\n" + "="*50)
        print("Summary")
        print("="*50)

        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)

        print(f"Tests Passed: {passed_count}/{total_count}")
        print(f"Total Time: {elapsed_time:.2f}s")

        if all_passed:
            print("\n✅ All smoke tests PASSED!")
        else:
            print("\n❌ Some smoke tests FAILED!")
            print("\nFailed tests:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")

        # Write results to file
        self.save_results()

        return all_passed

    def save_results(self):
        """Save test results to JSON file."""
        results_file = f"smoke_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(results_file, 'w') as f:
            json.dump({
                "url": self.base_url,
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": time.time() - self.start_time,
                "results": self.results
            }, f, indent=2)

        print(f"\nResults saved to: {results_file}")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python smoke_test.py <base_url>")
        print("Example: python smoke_test.py https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io")
        sys.exit(1)

    base_url = sys.argv[1]

    # Run smoke tests
    tester = TeamsBotSmokeTest(base_url)
    success = tester.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()