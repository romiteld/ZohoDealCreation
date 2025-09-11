#!/usr/bin/env python3
"""
Test runner for TalentWell import and persistence system tests.
Runs the comprehensive test suite with proper configuration.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_files=None, coverage=True, verbose=True, parallel=False, markers=None):
    """Run pytest with specified configuration."""
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test files or run all TalentWell tests
    if test_files:
        cmd.extend(test_files)
    else:
        cmd.extend([
            "tests/test_import_exports.py",
            "tests/test_seed_policies.py", 
            "tests/test_intake_outlook.py"
        ])
    
    # Add verbose output
    if verbose:
        cmd.append("-v")
    
    # Add coverage reporting
    if coverage:
        cmd.extend([
            "--cov=app.admin.import_exports",
            "--cov=app.admin.seed_policies",
            "--cov=app.main",
            "--cov-report=term-missing",
            "--cov-report=html:tests/htmlcov",
        ])
    
    # Add parallel execution
    if parallel:
        cmd.extend(["-n", "auto"])
    
    # Add marker filtering
    if markers:
        for marker in markers:
            cmd.extend(["-m", marker])
    
    # Add additional pytest options
    cmd.extend([
        "--tb=short",  # Shorter traceback format
        "--strict-markers",  # Strict marker checking
        "--disable-warnings",  # Disable warnings for cleaner output
        "--timeout=60",  # 60 second timeout per test
    ])
    
    # Set environment for testing
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(Path(__file__).parent.parent),
        "TESTING": "true"
    })
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 60)
    
    # Run the tests
    result = subprocess.run(cmd, env=env, cwd=Path(__file__).parent.parent)
    
    return result.returncode


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run TalentWell tests")
    
    parser.add_argument(
        "files", 
        nargs="*", 
        help="Specific test files to run (default: all TalentWell tests)"
    )
    
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Disable coverage reporting"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true", 
        help="Reduce output verbosity"
    )
    
    parser.add_argument(
        "--parallel", "-n",
        action="store_true",
        help="Run tests in parallel"
    )
    
    parser.add_argument(
        "--markers", "-m",
        nargs="*",
        help="Run only tests with specific markers (unit, integration, slow)"
    )
    
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies before running"
    )
    
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        print("Installing test dependencies...")
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "-r", "tests/requirements-test.txt"
        ])
        print("-" * 60)
    
    # Check if required files exist
    required_files = [
        "tests/test_import_exports.py",
        "tests/test_seed_policies.py", 
        "tests/test_intake_outlook.py",
        "tests/conftest.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"Error: Missing test files: {', '.join(missing_files)}")
        return 1
    
    # Run the tests
    exit_code = run_tests(
        test_files=args.files,
        coverage=not args.no_coverage,
        verbose=not args.quiet,
        parallel=args.parallel,
        markers=args.markers
    )
    
    # Print summary
    if exit_code == 0:
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        if not args.no_coverage:
            print("📊 Coverage report generated in tests/htmlcov/index.html")
    else:
        print("\n" + "=" * 60)
        print("❌ Some tests failed!")
        print(f"Exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())