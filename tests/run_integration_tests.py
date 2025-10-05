#!/usr/bin/env python3
"""
Comprehensive Integration Test Runner

Orchestrates all integration tests for the 10-agent system and provides
detailed reporting on the validation results.

Usage:
    python tests/run_integration_tests.py                    # Run all tests
    python tests/run_integration_tests.py --quick            # Run quick smoke tests
    python tests/run_integration_tests.py --performance     # Run performance tests only
    python tests/run_integration_tests.py --report          # Generate detailed report
"""

import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import concurrent.futures
from tabulate import tabulate
from colorama import init, Fore, Style, Back

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Test configuration
TEST_CONFIG = {
    "test_files": [
        "test_agent_integrations.py",
        "test_data_validation.py", 
        "test_performance_benchmarks.py",
        "test_migrated_infrastructure.py"
    ],
    "quick_tests": [
        "test_agent_integrations.py::TestStorageIntegration::test_comprehensive_storage_vs_basic",
        "test_data_validation.py::TestDataValidation::test_email_payload_validation",
        "test_migrated_infrastructure.py::TestContainerApp::test_health_endpoint"
    ],
    "performance_tests": [
        "test_performance_benchmarks.py"
    ],
    "timeout_seconds": 300,
    "max_workers": 4
}

@dataclass
class TestResult:
    """Test result data structure"""
    test_file: str
    test_class: str
    test_method: str
    status: str  # passed, failed, skipped, error
    duration: float
    error_message: Optional[str] = None
    output: Optional[str] = None

class TestReporter:
    """Test results reporter"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = None
        self.end_time = None
        
    def start_testing(self):
        """Start testing session"""
        self.start_time = datetime.now()
        print(f"{Fore.CYAN}🚀 Starting Integration Test Suite")
        print(f"📅 Test session started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
    def end_testing(self):
        """End testing session"""
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time if self.start_time else timedelta(0)
        
        print("\n" + "=" * 80)
        print(f"{Fore.CYAN}🏁 Integration Test Suite Completed")
        print(f"⏱️  Total duration: {duration}")
        print(f"📅 Test session ended at: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
    def add_result(self, result: TestResult):
        """Add test result"""
        self.results.append(result)
        
    def print_summary(self):
        """Print test summary"""
        if not self.results:
            print(f"{Fore.YELLOW}⚠️  No test results to summarize")
            return
            
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.status == "passed")
        failed_tests = sum(1 for r in self.results if r.status == "failed")
        error_tests = sum(1 for r in self.results if r.status == "error")
        skipped_tests = sum(1 for r in self.results if r.status == "skipped")
        
        total_duration = sum(r.duration for r in self.results)
        
        print(f"\n{Fore.CYAN}📊 Test Summary")
        print("-" * 40)
        print(f"Total Tests: {total_tests}")
        print(f"{Fore.GREEN}✅ Passed: {passed_tests}")
        print(f"{Fore.RED}❌ Failed: {failed_tests}")
        print(f"{Fore.YELLOW}🔥 Errors: {error_tests}")
        print(f"{Fore.BLUE}⏭️  Skipped: {skipped_tests}")
        print(f"⏱️  Total Time: {total_duration:.2f}s")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        # Color-coded result
        if failed_tests == 0 and error_tests == 0:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}🎉 ALL TESTS PASSED! 🎉")
        elif failed_tests > 0:
            print(f"\n{Fore.RED}{Style.BRIGHT}💥 SOME TESTS FAILED! 💥")
        else:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}⚠️  TESTS HAD ERRORS! ⚠️")
            
    def print_detailed_report(self):
        """Print detailed test report"""
        print(f"\n{Fore.CYAN}📋 Detailed Test Report")
        print("=" * 80)
        
        # Group results by test file
        by_file = {}
        for result in self.results:
            if result.test_file not in by_file:
                by_file[result.test_file] = []
            by_file[result.test_file].append(result)
        
        for test_file, file_results in by_file.items():
            print(f"\n{Fore.MAGENTA}📁 {test_file}")
            print("-" * 60)
            
            table_data = []
            for result in file_results:
                status_icon = {
                    "passed": "✅",
                    "failed": "❌", 
                    "error": "🔥",
                    "skipped": "⏭️"
                }.get(result.status, "❓")
                
                table_data.append([
                    f"{status_icon} {result.test_class}::{result.test_method}",
                    result.status.upper(),
                    f"{result.duration:.2f}s"
                ])
            
            print(tabulate(table_data, headers=["Test", "Status", "Duration"], tablefmt="grid"))
            
        # Print failures and errors
        failures = [r for r in self.results if r.status in ["failed", "error"]]
        if failures:
            print(f"\n{Fore.RED}💥 Failures and Errors")
            print("-" * 60)
            
            for failure in failures:
                print(f"\n{Fore.RED}❌ {failure.test_file}::{failure.test_class}::{failure.test_method}")
                if failure.error_message:
                    print(f"   Error: {failure.error_message}")
                    
    def generate_json_report(self, output_file: str = "test_results.json"):
        """Generate JSON test report"""
        report_data = {
            "test_session": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
            },
            "summary": {
                "total_tests": len(self.results),
                "passed": sum(1 for r in self.results if r.status == "passed"),
                "failed": sum(1 for r in self.results if r.status == "failed"),
                "errors": sum(1 for r in self.results if r.status == "error"),
                "skipped": sum(1 for r in self.results if r.status == "skipped"),
                "success_rate": (sum(1 for r in self.results if r.status == "passed") / len(self.results) * 100) if self.results else 0
            },
            "results": [
                {
                    "test_file": r.test_file,
                    "test_class": r.test_class,
                    "test_method": r.test_method,
                    "status": r.status,
                    "duration": r.duration,
                    "error_message": r.error_message
                } for r in self.results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)
            
        print(f"\n📄 JSON report saved to: {output_file}")

class IntegrationTestRunner:
    """Integration test runner"""
    
    def __init__(self):
        self.reporter = TestReporter()
        self.tests_dir = Path(__file__).parent
        
    def run_pytest_command(self, test_target: str, extra_args: List[str] = None) -> subprocess.CompletedProcess:
        """Run pytest command"""
        cmd = [
            "python", "-m", "pytest",
            str(self.tests_dir / test_target),
            "-v",
            "--tb=short",
            "--color=yes",
            "--json-report",
            "--json-report-file=temp_test_results.json"
        ]
        
        if extra_args:
            cmd.extend(extra_args)
            
        print(f"{Fore.YELLOW}🏃 Running: {' '.join(cmd[-4:])}")  # Show simplified command
        
        return subprocess.run(cmd, capture_output=True, text=True)
        
    def parse_pytest_results(self, result: subprocess.CompletedProcess, test_file: str) -> List[TestResult]:
        """Parse pytest results"""
        test_results = []
        
        # Try to parse JSON report if available
        json_report_file = "temp_test_results.json"
        if os.path.exists(json_report_file):
            try:
                with open(json_report_file) as f:
                    report_data = json.load(f)
                    
                for test in report_data.get("tests", []):
                    # Parse test nodeid (e.g., "test_file.py::TestClass::test_method")
                    nodeid_parts = test["nodeid"].split("::")
                    if len(nodeid_parts) >= 3:
                        test_class = nodeid_parts[-2]
                        test_method = nodeid_parts[-1]
                    else:
                        test_class = "Unknown"
                        test_method = nodeid_parts[-1] if nodeid_parts else "unknown"
                    
                    test_results.append(TestResult(
                        test_file=test_file,
                        test_class=test_class,
                        test_method=test_method,
                        status=test["outcome"],
                        duration=test["duration"],
                        error_message=test.get("call", {}).get("longrepr") if test["outcome"] in ["failed", "error"] else None
                    ))
                    
                os.remove(json_report_file)  # Cleanup
                
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                # Fall back to parsing stdout
                pass
        
        # Fallback: simple parsing of stdout
        if not test_results:
            lines = result.stdout.split('\n')
            for line in lines:
                if "::" in line and any(status in line for status in ["PASSED", "FAILED", "ERROR", "SKIPPED"]):
                    # Basic parsing - this is a fallback
                    test_results.append(TestResult(
                        test_file=test_file,
                        test_class="Parsed",
                        test_method=line,
                        status="passed" if "PASSED" in line else "failed",
                        duration=0.0
                    ))
        
        return test_results
        
    def run_all_tests(self, test_filter: Optional[str] = None) -> bool:
        """Run all integration tests"""
        self.reporter.start_testing()
        
        test_files = TEST_CONFIG["test_files"]
        if test_filter:
            test_files = [f for f in test_files if test_filter in f]
        
        all_success = True
        
        for test_file in test_files:
            print(f"\n{Fore.CYAN}📝 Running {test_file}...")
            
            try:
                result = self.run_pytest_command(test_file)
                test_results = self.parse_pytest_results(result, test_file)
                
                for test_result in test_results:
                    self.reporter.add_result(test_result)
                
                # Check if any tests failed
                if result.returncode != 0:
                    all_success = False
                    print(f"{Fore.RED}❌ {test_file} had failures")
                else:
                    print(f"{Fore.GREEN}✅ {test_file} completed successfully")
                    
            except Exception as e:
                print(f"{Fore.RED}🔥 Error running {test_file}: {e}")
                all_success = False
                
                # Add error result
                self.reporter.add_result(TestResult(
                    test_file=test_file,
                    test_class="Runner",
                    test_method="execution", 
                    status="error",
                    duration=0.0,
                    error_message=str(e)
                ))
        
        self.reporter.end_testing()
        return all_success
        
    def run_quick_tests(self) -> bool:
        """Run quick smoke tests"""
        self.reporter.start_testing()
        
        print(f"{Fore.YELLOW}⚡ Running Quick Smoke Tests...")
        
        all_success = True
        for test_target in TEST_CONFIG["quick_tests"]:
            print(f"\n{Fore.CYAN}🔍 Running {test_target}...")
            
            try:
                result = self.run_pytest_command(test_target, ["--maxfail=1"])
                
                # Simple success/failure check for quick tests
                if result.returncode == 0:
                    print(f"{Fore.GREEN}✅ {test_target} passed")
                    self.reporter.add_result(TestResult(
                        test_file=test_target.split("::")[0],
                        test_class="Quick",
                        test_method=test_target,
                        status="passed",
                        duration=0.0
                    ))
                else:
                    print(f"{Fore.RED}❌ {test_target} failed")
                    all_success = False
                    self.reporter.add_result(TestResult(
                        test_file=test_target.split("::")[0],
                        test_class="Quick",
                        test_method=test_target,
                        status="failed", 
                        duration=0.0,
                        error_message=result.stdout
                    ))
                    
            except Exception as e:
                print(f"{Fore.RED}🔥 Error running {test_target}: {e}")
                all_success = False
        
        self.reporter.end_testing()
        return all_success
        
    def run_performance_tests(self) -> bool:
        """Run performance tests only"""
        self.reporter.start_testing()
        
        print(f"{Fore.YELLOW}⚡ Running Performance Tests...")
        
        all_success = True
        for test_file in TEST_CONFIG["performance_tests"]:
            print(f"\n{Fore.CYAN}📊 Running {test_file}...")
            
            try:
                result = self.run_pytest_command(test_file, ["--durations=10"])
                test_results = self.parse_pytest_results(result, test_file)
                
                for test_result in test_results:
                    self.reporter.add_result(test_result)
                
                if result.returncode != 0:
                    all_success = False
                    print(f"{Fore.RED}❌ {test_file} had performance issues")
                else:
                    print(f"{Fore.GREEN}✅ {test_file} performance acceptable")
                    
            except Exception as e:
                print(f"{Fore.RED}🔥 Error running performance tests: {e}")
                all_success = False
        
        self.reporter.end_testing()
        return all_success

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Integration Test Runner for 10-Agent System")
    parser.add_argument("--quick", action="store_true", help="Run quick smoke tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--report", action="store_true", help="Generate detailed test report")
    parser.add_argument("--filter", type=str, help="Filter tests by filename pattern")
    parser.add_argument("--json", type=str, default="test_results.json", help="JSON report output file")
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = IntegrationTestRunner()
    
    # Run tests based on arguments
    success = True
    
    if args.quick:
        success = runner.run_quick_tests()
    elif args.performance:
        success = runner.run_performance_tests()
    else:
        success = runner.run_all_tests(test_filter=args.filter)
    
    # Generate reports
    runner.reporter.print_summary()
    
    if args.report:
        runner.reporter.print_detailed_report()
        
    runner.reporter.generate_json_report(args.json)
    
    # Print final result
    print("\n" + "=" * 80)
    if success:
        print(f"{Fore.GREEN}{Style.BRIGHT}🎉 INTEGRATION TESTS SUCCESSFUL! 🎉")
        print(f"{Fore.GREEN}All agent implementations validated successfully!")
    else:
        print(f"{Fore.RED}{Style.BRIGHT}💥 INTEGRATION TESTS FAILED! 💥")
        print(f"{Fore.RED}Some agent implementations need attention!")
        
    print("=" * 80)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()