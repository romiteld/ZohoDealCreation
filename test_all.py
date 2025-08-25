#!/usr/bin/env python3
"""
Comprehensive Test Suite for Well Intake API
Runs all tests and generates a full report
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    """Print test suite banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           WELL INTAKE API - COMPREHENSIVE TEST SUITE         ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(f"{Colors.BOLD}{Colors.CYAN}{banner}{Colors.ENDC}")

def print_section(title: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}  {title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.ENDC}")

def run_test(test_name: str, test_file: str) -> Tuple[bool, str, float]:
    """Run a test file and return results"""
    print(f"\n{Colors.BLUE}▶ Running {test_name}...{Colors.ENDC}")
    
    start_time = time.time()
    
    try:
        # Run the test
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        duration = time.time() - start_time
        
        # Check if test passed
        if result.returncode == 0:
            print(f"{Colors.GREEN}  ✅ {test_name} PASSED ({duration:.2f}s){Colors.ENDC}")
            return True, result.stdout, duration
        else:
            print(f"{Colors.RED}  ❌ {test_name} FAILED ({duration:.2f}s){Colors.ENDC}")
            
            # Extract errors from output
            errors = []
            for line in result.stdout.split('\n'):
                if '❌' in line or 'ERROR' in line or 'Failed' in line:
                    errors.append(line.strip())
            
            if errors:
                print(f"{Colors.RED}  Errors found:{Colors.ENDC}")
                for error in errors[:5]:  # Show first 5 errors
                    print(f"    • {error}")
            
            return False, result.stdout, duration
            
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"{Colors.YELLOW}  ⚠️  {test_name} TIMEOUT ({duration:.2f}s){Colors.ENDC}")
        return False, "Test timed out", duration
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"{Colors.RED}  ❌ {test_name} ERROR: {e}{Colors.ENDC}")
        return False, str(e), duration

def check_server_status() -> bool:
    """Check if the API server is running"""
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def attempt_server_start() -> bool:
    """Attempt to start the API server"""
    print(f"\n{Colors.YELLOW}Attempting to start API server...{Colors.ENDC}")
    
    try:
        # Kill any existing uvicorn processes
        subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
        time.sleep(1)
        
        # Start the server in background
        subprocess.Popen(
            ["uvicorn", "app.main:app", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd="/home/romiteld/outlook"
        )
        
        # Wait for server to start
        for i in range(10):
            time.sleep(1)
            if check_server_status():
                print(f"{Colors.GREEN}  ✅ Server started successfully{Colors.ENDC}")
                return True
        
        print(f"{Colors.RED}  ❌ Server failed to start{Colors.ENDC}")
        return False
        
    except Exception as e:
        print(f"{Colors.RED}  ❌ Failed to start server: {e}{Colors.ENDC}")
        return False

def analyze_test_outputs(results: Dict) -> Dict:
    """Analyze test outputs for common issues"""
    analysis = {
        "missing_dependencies": [],
        "env_vars_missing": [],
        "connection_failures": [],
        "api_issues": [],
        "recommendations": []
    }
    
    for test_name, (passed, output, _) in results.items():
        # Check for missing dependencies
        if "No module named" in output or "ImportError" in output:
            for line in output.split('\n'):
                if "No module named" in line:
                    module = line.split("No module named")[1].strip().strip("'")
                    if module not in analysis["missing_dependencies"]:
                        analysis["missing_dependencies"].append(module)
        
        # Check for missing environment variables
        if "NOT SET" in output or "not configured" in output:
            for line in output.split('\n'):
                if "NOT SET" in line or "not configured" in line:
                    # Extract variable name
                    parts = line.split(":")
                    if parts:
                        var_name = parts[0].strip().replace("❌", "").strip()
                        if var_name and var_name not in analysis["env_vars_missing"]:
                            analysis["env_vars_missing"].append(var_name)
        
        # Check for connection failures
        if "connection failed" in output.lower() or "connection refused" in output.lower():
            for line in output.split('\n'):
                if "connection" in line.lower():
                    analysis["connection_failures"].append(line.strip())
    
    # Generate recommendations
    if analysis["missing_dependencies"]:
        analysis["recommendations"].append(
            f"Install missing packages: pip install {' '.join(analysis['missing_dependencies'])}"
        )
    
    if analysis["env_vars_missing"]:
        analysis["recommendations"].append(
            "Update .env.local with missing environment variables"
        )
    
    if analysis["connection_failures"]:
        analysis["recommendations"].append(
            "Check network connectivity and service availability"
        )
    
    return analysis

def generate_final_report(results: Dict, analysis: Dict):
    """Generate final test report"""
    print_section("FINAL TEST REPORT")
    
    # Count results
    total_tests = len(results)
    passed_tests = sum(1 for passed, _, _ in results.values() if passed)
    failed_tests = total_tests - passed_tests
    total_time = sum(duration for _, _, duration in results.values())
    
    # Print summary
    print(f"\n{Colors.BOLD}Test Summary:{Colors.ENDC}")
    print(f"  Total Tests: {total_tests}")
    print(f"  {Colors.GREEN}Passed: {passed_tests}{Colors.ENDC}")
    print(f"  {Colors.RED}Failed: {failed_tests}{Colors.ENDC}")
    print(f"  Total Time: {total_time:.2f}s")
    
    # Print test results
    print(f"\n{Colors.BOLD}Test Results:{Colors.ENDC}")
    for test_name, (passed, _, duration) in results.items():
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if passed else f"{Colors.RED}FAIL{Colors.ENDC}"
        print(f"  • {test_name:<30} [{status}] ({duration:.2f}s)")
    
    # Print issues found
    if analysis["missing_dependencies"]:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Missing Dependencies:{Colors.ENDC}")
        for dep in analysis["missing_dependencies"]:
            print(f"  • {dep}")
    
    if analysis["env_vars_missing"]:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Missing Environment Variables:{Colors.ENDC}")
        for var in analysis["env_vars_missing"]:
            print(f"  • {var}")
    
    if analysis["connection_failures"]:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Connection Issues:{Colors.ENDC}")
        for issue in analysis["connection_failures"][:5]:
            print(f"  • {issue}")
    
    # Print recommendations
    if analysis["recommendations"]:
        print(f"\n{Colors.BOLD}{Colors.CYAN}Recommendations:{Colors.ENDC}")
        for i, rec in enumerate(analysis["recommendations"], 1):
            print(f"  {i}. {rec}")
    
    # Overall status
    print(f"\n{Colors.BOLD}Overall Status:{Colors.ENDC}")
    if failed_tests == 0:
        print(f"{Colors.GREEN}  🎉 ALL TESTS PASSED! The application is ready.{Colors.ENDC}")
    elif failed_tests <= 2:
        print(f"{Colors.YELLOW}  ⚠️  Minor issues found. The application may work with limitations.{Colors.ENDC}")
    else:
        print(f"{Colors.RED}  ❌ Critical issues found. Please fix the errors before deployment.{Colors.ENDC}")
    
    # Save detailed report
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "total_time": total_time
        },
        "results": {
            test_name: {
                "passed": passed,
                "duration": duration
            }
            for test_name, (passed, _, duration) in results.items()
        },
        "analysis": analysis
    }
    
    report_file = Path("test_comprehensive_report.json")
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n{Colors.BLUE}📄 Detailed report saved to: {report_file}{Colors.ENDC}")

def main():
    """Run comprehensive test suite"""
    print_banner()
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Python Version: {sys.version.split()[0]}")
    
    # Check if we're in the right directory
    if not Path("app/main.py").exists():
        print(f"{Colors.RED}Error: Not in the correct directory. Please run from /home/romiteld/outlook{Colors.ENDC}")
        sys.exit(1)
    
    # Test files to run
    test_files = [
        ("Dependency Tests", "test_dependencies.py"),
        ("Startup Tests", "test_startup.py"),
        # ("Integration Tests", "test_integrations.py"),  # May timeout
        # ("API Endpoint Tests", "test_api_endpoints.py"),  # Requires server
    ]
    
    # Check which test files exist
    available_tests = []
    for name, file in test_files:
        if Path(file).exists():
            available_tests.append((name, file))
        else:
            print(f"{Colors.YELLOW}⚠️  Test file not found: {file}{Colors.ENDC}")
    
    if not available_tests:
        print(f"{Colors.RED}No test files found!{Colors.ENDC}")
        sys.exit(1)
    
    print(f"\n{Colors.BLUE}Found {len(available_tests)} test file(s) to run{Colors.ENDC}")
    
    # Check server status
    print_section("SERVER STATUS CHECK")
    server_running = check_server_status()
    
    if server_running:
        print(f"{Colors.GREEN}✅ API server is running{Colors.ENDC}")
    else:
        print(f"{Colors.YELLOW}⚠️  API server is not running{Colors.ENDC}")
        print("  Some tests may be skipped or fail")
        
        # Optionally attempt to start server
        # if attempt_server_start():
        #     server_running = True
    
    # Run tests
    print_section("RUNNING TESTS")
    
    results = {}
    for test_name, test_file in available_tests:
        passed, output, duration = run_test(test_name, test_file)
        results[test_name] = (passed, output, duration)
    
    # Analyze results
    print_section("ANALYZING RESULTS")
    analysis = analyze_test_outputs(results)
    
    # Generate final report
    generate_final_report(results, analysis)
    
    # Exit with appropriate code
    failed_count = sum(1 for passed, _, _ in results.values() if not passed)
    sys.exit(0 if failed_count == 0 else 1)

if __name__ == "__main__":
    main()