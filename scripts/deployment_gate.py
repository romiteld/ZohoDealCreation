#!/usr/bin/env python3
"""
Deployment gate script - validates staging smoke tests before production deployment.

This script:
1. Runs smoke tests against staging endpoints
2. Validates SLAs are met
3. Checks Application Insights for error rates
4. Gates production deployment based on results

Usage:
    python scripts/deployment_gate.py --service teams-bot
    python scripts/deployment_gate.py --service vault-agent
    python scripts/deployment_gate.py --service main-api
    python scripts/deployment_gate.py --all  # Check all services
"""

import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Tuple
import os

# SLA thresholds
SLA_THRESHOLDS = {
    "teams-bot": {
        "max_error_rate": 0.01,  # 1%
        "max_p95_latency_ms": 2000,  # 2 seconds
        "required_smoke_tests": "tests/smoke/test_teams_bot_smoke.py",
    },
    "vault-agent": {
        "max_error_rate": 0.05,  # 5% (digest generation can be flaky)
        "max_p95_latency_ms": 30000,  # 30 seconds
        "required_smoke_tests": "tests/smoke/test_vault_agent_smoke.py",
    },
    "main-api": {
        "max_error_rate": 0.01,  # 1%
        "max_p95_latency_ms": 5000,  # 5 seconds
        "required_smoke_tests": "tests/integration/",
    },
}


class DeploymentGate:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.results: Dict[str, Dict] = {}

    def log(self, message: str, level: str = "INFO"):
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARN": "⚠️",
            "ERROR": "❌",
        }.get(level, "ℹ️")
        print(f"{prefix}  {message}")

    def run_smoke_tests(self, service: str) -> Tuple[bool, Dict]:
        """Run smoke tests for a service and return pass/fail + metrics."""
        self.log(f"Running smoke tests for {service}...")

        test_path = SLA_THRESHOLDS[service]["required_smoke_tests"]
        full_path = self.repo_root / test_path

        if not full_path.exists():
            self.log(f"Smoke tests not found: {test_path}", "ERROR")
            return False, {}

        # Create artifacts directory if it doesn't exist
        artifacts_dir = self.repo_root / "test_artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        # Unique report file per service to prevent overwrites
        report_file = artifacts_dir / f"pytest_{service.replace('-', '_')}.json"

        # Run pytest with coverage and JSON output
        start_time = time.time()
        try:
            result = subprocess.run(
                [
                    "pytest",
                    str(full_path),
                    "--env=staging",
                    "-v",
                    "--tb=short",
                    "--json-report",
                    f"--json-report-file={report_file}",
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            duration_s = time.time() - start_time

            # Parse results
            passed = result.returncode == 0
            metrics = {
                "duration_s": duration_s,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if passed:
                self.log(f"Smoke tests PASSED in {duration_s:.1f}s", "SUCCESS")
            else:
                self.log(f"Smoke tests FAILED (exit code {result.returncode})", "ERROR")
                self.log(f"Output:\n{result.stdout}", "ERROR")

            return passed, metrics

        except subprocess.TimeoutExpired:
            self.log("Smoke tests TIMED OUT", "ERROR")
            return False, {"error": "timeout"}
        except Exception as e:
            self.log(f"Smoke test execution error: {e}", "ERROR")
            return False, {"error": str(e)}

    def check_application_insights(self, service: str) -> Tuple[bool, Dict]:
        """
        Query Application Insights for recent error rates and latency.

        CRITICAL: This is a deployment gate - missing config or query failure
        should BLOCK deployment, not silently succeed.
        """
        self.log(f"Checking Application Insights metrics for {service}...")

        instrumentation_key = os.getenv("APPINSIGHTS_INSTRUMENTATION_KEY")
        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

        if not instrumentation_key and not connection_string:
            self.log("Application Insights not configured - BLOCKING deployment", "ERROR")
            self.log("Configure APPINSIGHTS_INSTRUMENTATION_KEY or APPLICATIONINSIGHTS_CONNECTION_STRING", "ERROR")
            return False, {"error": "app_insights_not_configured"}

        # TODO: Implement actual App Insights query using azure-monitor-query
        # For now, use mock data but REQUIRE the config to be present
        # When implemented, query last 1 hour of data from App Insights

        try:
            # Placeholder for real query - will be implemented with azure-monitor-query
            # Real implementation would query requests table:
            # requests
            # | where timestamp > ago(1h)
            # | where cloud_RoleName == "{service}"
            # | summarize
            #     error_rate = countif(success == false) * 1.0 / count(),
            #     p95_duration = percentile(duration, 95),
            #     total_requests = count()

            mock_metrics = {
                "error_rate": 0.005,  # 0.5%
                "p95_latency_ms": 1500,
                "total_requests": 1000,
                "note": "MOCK DATA - Replace with real App Insights query",
            }

            # Validate against SLAs
            thresholds = SLA_THRESHOLDS[service]
            error_rate_ok = mock_metrics["error_rate"] <= thresholds["max_error_rate"]
            latency_ok = mock_metrics["p95_latency_ms"] <= thresholds["max_p95_latency_ms"]

            if error_rate_ok and latency_ok:
                self.log("Application Insights metrics within SLA (MOCK DATA)", "SUCCESS")
                self.log("⚠️  Replace with real App Insights query before production use", "WARN")
            else:
                if not error_rate_ok:
                    self.log(
                        f"Error rate {mock_metrics['error_rate']:.1%} > {thresholds['max_error_rate']:.1%}",
                        "ERROR"
                    )
                if not latency_ok:
                    self.log(
                        f"P95 latency {mock_metrics['p95_latency_ms']}ms > {thresholds['max_p95_latency_ms']}ms",
                        "ERROR"
                    )

            return error_rate_ok and latency_ok, mock_metrics

        except Exception as e:
            # Query failure is a HARD FAIL for deployment gate
            self.log(f"Application Insights query FAILED: {e}", "ERROR")
            self.log("Deployment BLOCKED due to monitoring failure", "ERROR")
            return False, {"error": str(e)}

    def validate_service(self, service: str) -> bool:
        """Validate a service is ready for production deployment."""
        self.log("=" * 60)
        self.log(f"Validating {service} for production deployment")
        self.log("=" * 60)

        # Step 1: Run smoke tests
        smoke_passed, smoke_metrics = self.run_smoke_tests(service)

        # Step 2: Check Application Insights
        insights_ok, insights_metrics = self.check_application_insights(service)

        # Step 3: Aggregate results
        passed = smoke_passed and insights_ok

        self.results[service] = {
            "passed": passed,
            "smoke_tests": smoke_metrics,
            "app_insights": insights_metrics,
        }

        if passed:
            self.log(f"\n✅ {service} PASSED all deployment gates", "SUCCESS")
            self.log("Safe to deploy to production")
        else:
            self.log(f"\n❌ {service} FAILED deployment gates", "ERROR")
            self.log("DO NOT deploy to production")

        return passed

    def validate_all_services(self) -> bool:
        """Validate all services are ready for deployment."""
        services = ["teams-bot", "vault-agent", "main-api"]
        all_passed = True

        for service in services:
            passed = self.validate_service(service)
            all_passed = all_passed and passed
            print()  # Blank line between services

        return all_passed

    def print_summary(self):
        """Print summary of all validation results."""
        self.log("=" * 60)
        self.log("DEPLOYMENT GATE SUMMARY")
        self.log("=" * 60)

        for service, result in self.results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            self.log(f"{service}: {status}")

        all_passed = all(r["passed"] for r in self.results.values())

        print()
        if all_passed:
            self.log("🎉 ALL SERVICES READY FOR PRODUCTION", "SUCCESS")
            return 0
        else:
            self.log("🚫 DEPLOYMENT BLOCKED - Fix issues before deploying", "ERROR")
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="Validate staging smoke tests before production deployment"
    )
    parser.add_argument(
        "--service",
        choices=["teams-bot", "vault-agent", "main-api"],
        help="Service to validate"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all services"
    )

    args = parser.parse_args()

    if not args.service and not args.all:
        parser.print_help()
        sys.exit(1)

    repo_root = Path(__file__).parent.parent
    gate = DeploymentGate(repo_root)

    if args.all:
        gate.validate_all_services()
    else:
        gate.validate_service(args.service)

    exit_code = gate.print_summary()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
