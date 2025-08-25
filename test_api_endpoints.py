#!/usr/bin/env python3
"""
Comprehensive API Endpoint Tests for Well Intake API
Tests all endpoints with various scenarios
"""

import os
import sys
import json
import time
import asyncio
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Test configuration
BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("API_KEY", "your-secure-api-key-here")

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(title: str):
    """Print a formatted test section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")

def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")

def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}")

def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")

class APIEndpointTester:
    """Test all API endpoints"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.api_key = API_KEY
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.test_results = {
            "endpoints": {},
            "performance": {},
            "errors": [],
            "warnings": []
        }
        
    def test_health_endpoint(self):
        """Test /health endpoint"""
        print_test_header("Testing /health Endpoint")
        
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/health")
            duration = time.time() - start_time
            
            self.test_results["performance"]["/health"] = duration
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Health check passed (Status: {response.status_code})")
                print_info(f"Response time: {duration:.3f}s")
                print_info(f"Response: {json.dumps(data, indent=2)}")
                
                self.test_results["endpoints"]["/health"] = {
                    "status": "success",
                    "status_code": response.status_code,
                    "response": data,
                    "duration": duration
                }
                
                # Check response structure
                if "status" in data:
                    print_success(f"Health status: {data['status']}")
                if "timestamp" in data:
                    print_info(f"Timestamp: {data['timestamp']}")
                if "environment" in data:
                    print_info(f"Environment: {data['environment']}")
                    
            else:
                print_error(f"Health check failed (Status: {response.status_code})")
                self.test_results["errors"].append(f"/health returned {response.status_code}")
                
        except Exception as e:
            print_error(f"Failed to test /health: {e}")
            self.test_results["errors"].append(f"/health test failed: {e}")
    
    def test_manifest_endpoint(self):
        """Test /manifest.xml endpoint"""
        print_test_header("Testing /manifest.xml Endpoint")
        
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/manifest.xml")
            duration = time.time() - start_time
            
            self.test_results["performance"]["/manifest.xml"] = duration
            
            if response.status_code == 200:
                print_success(f"Manifest retrieved (Status: {response.status_code})")
                print_info(f"Response time: {duration:.3f}s")
                print_info(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                
                # Check if it's valid XML
                if '<?xml' in response.text and '<OfficeApp' in response.text:
                    print_success("Valid Office Add-in manifest structure detected")
                    
                    # Check for required elements
                    required_elements = [
                        '<Id>',
                        '<DisplayName',
                        '<Description',
                        '<Version>',
                        '<ProviderName>',
                        '<Hosts>',
                        '<Requirements>'
                    ]
                    
                    for element in required_elements:
                        if element in response.text:
                            print_success(f"Found required element: {element}")
                        else:
                            print_warning(f"Missing element: {element}")
                            self.test_results["warnings"].append(f"Manifest missing: {element}")
                
                self.test_results["endpoints"]["/manifest.xml"] = {
                    "status": "success",
                    "status_code": response.status_code,
                    "content_length": len(response.text),
                    "duration": duration
                }
                
            else:
                print_error(f"Manifest retrieval failed (Status: {response.status_code})")
                self.test_results["errors"].append(f"/manifest.xml returned {response.status_code}")
                
        except Exception as e:
            print_error(f"Failed to test /manifest.xml: {e}")
            self.test_results["errors"].append(f"/manifest.xml test failed: {e}")
    
    def test_intake_email_endpoint(self):
        """Test POST /intake/email endpoint"""
        print_test_header("Testing POST /intake/email Endpoint")
        
        # Test data
        test_email = {
            "subject": "Senior Financial Advisor - Fort Wayne",
            "from": "recruiter@example.com",
            "body": """Hi,

I have an exciting opportunity for a Senior Financial Advisor position in Fort Wayne.
The candidate we're looking for should have experience in wealth management.

This position is with a prestigious financial firm.

Best regards,
Test Recruiter""",
            "timestamp": datetime.now().isoformat(),
            "attachments": []
        }
        
        try:
            print_info("Testing with sample email data...")
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/intake/email",
                headers=self.headers,
                json=test_email
            )
            duration = time.time() - start_time
            
            self.test_results["performance"]["/intake/email"] = duration
            
            print_info(f"Response status: {response.status_code}")
            print_info(f"Response time: {duration:.3f}s")
            
            if response.status_code == 200:
                data = response.json()
                print_success("Email intake successful")
                print_info(f"Response: {json.dumps(data, indent=2)}")
                
                # Check response structure
                if "extracted_data" in data:
                    print_success("Extracted data present")
                    extracted = data["extracted_data"]
                    
                    # Validate extracted fields
                    fields = ["candidate_name", "job_title", "location", "company_name", "referrer"]
                    for field in fields:
                        if field in extracted:
                            print_info(f"  {field}: {extracted[field]}")
                
                if "zoho_records" in data:
                    print_success("Zoho records created/found")
                    
                self.test_results["endpoints"]["/intake/email"] = {
                    "status": "success",
                    "status_code": response.status_code,
                    "response": data,
                    "duration": duration
                }
                
            elif response.status_code == 403:
                print_error("Authentication failed - check API key")
                self.test_results["errors"].append("Authentication failed for /intake/email")
                
            elif response.status_code == 422:
                print_error("Validation error - check request format")
                print_info(f"Error details: {response.text}")
                self.test_results["errors"].append("Validation error for /intake/email")
                
            else:
                print_error(f"Email intake failed (Status: {response.status_code})")
                print_info(f"Response: {response.text}")
                self.test_results["errors"].append(f"/intake/email returned {response.status_code}")
                
        except Exception as e:
            print_error(f"Failed to test /intake/email: {e}")
            self.test_results["errors"].append(f"/intake/email test failed: {e}")
    
    def test_kevin_sullivan_endpoint(self):
        """Test GET /test/kevin-sullivan endpoint"""
        print_test_header("Testing GET /test/kevin-sullivan Endpoint")
        
        try:
            print_info("Running Kevin Sullivan test case...")
            start_time = time.time()
            response = requests.get(
                f"{self.base_url}/test/kevin-sullivan",
                headers={"X-API-Key": self.api_key}
            )
            duration = time.time() - start_time
            
            self.test_results["performance"]["/test/kevin-sullivan"] = duration
            
            print_info(f"Response status: {response.status_code}")
            print_info(f"Response time: {duration:.3f}s")
            
            if response.status_code == 200:
                data = response.json()
                print_success("Kevin Sullivan test successful")
                
                # Validate expected extraction
                if "extracted_data" in data:
                    extracted = data["extracted_data"]
                    
                    # Check for expected values
                    expected_values = {
                        "candidate_name": "Kevin Sullivan",
                        "job_title": "Senior Financial Advisor",
                        "location": "Fort Wayne"
                    }
                    
                    for field, expected in expected_values.items():
                        if field in extracted:
                            actual = extracted[field]
                            if expected.lower() in str(actual).lower():
                                print_success(f"Correctly extracted {field}: {actual}")
                            else:
                                print_warning(f"Unexpected value for {field}: {actual} (expected: {expected})")
                        else:
                            print_error(f"Missing field: {field}")
                
                # Check performance
                if duration < 60:
                    print_success(f"Good performance: {duration:.1f}s (target: <60s)")
                else:
                    print_warning(f"Slow performance: {duration:.1f}s (target: <60s)")
                
                self.test_results["endpoints"]["/test/kevin-sullivan"] = {
                    "status": "success",
                    "status_code": response.status_code,
                    "response": data,
                    "duration": duration
                }
                
            else:
                print_error(f"Kevin Sullivan test failed (Status: {response.status_code})")
                print_info(f"Response: {response.text}")
                self.test_results["errors"].append(f"/test/kevin-sullivan returned {response.status_code}")
                
        except Exception as e:
            print_error(f"Failed to test /test/kevin-sullivan: {e}")
            self.test_results["errors"].append(f"/test/kevin-sullivan test failed: {e}")
    
    def test_api_authentication(self):
        """Test API key authentication"""
        print_test_header("Testing API Authentication")
        
        # Test with no API key
        print_info("Testing without API key...")
        try:
            response = requests.get(f"{self.base_url}/test/kevin-sullivan")
            if response.status_code == 403:
                print_success("Correctly rejected request without API key")
            else:
                print_error(f"Security issue: Request without API key returned {response.status_code}")
                self.test_results["errors"].append("API allows access without key")
        except Exception as e:
            print_error(f"Error testing without API key: {e}")
        
        # Test with invalid API key
        print_info("Testing with invalid API key...")
        try:
            response = requests.get(
                f"{self.base_url}/test/kevin-sullivan",
                headers={"X-API-Key": "invalid-key-12345"}
            )
            if response.status_code == 403:
                print_success("Correctly rejected request with invalid API key")
            else:
                print_error(f"Security issue: Invalid API key returned {response.status_code}")
                self.test_results["errors"].append("API accepts invalid keys")
        except Exception as e:
            print_error(f"Error testing with invalid API key: {e}")
        
        # Test with valid API key
        print_info("Testing with valid API key...")
        try:
            response = requests.get(
                f"{self.base_url}/test/kevin-sullivan",
                headers={"X-API-Key": self.api_key}
            )
            if response.status_code == 200:
                print_success("Valid API key accepted")
            else:
                print_error(f"Valid API key rejected with status {response.status_code}")
                self.test_results["errors"].append("Valid API key rejected")
        except Exception as e:
            print_error(f"Error testing with valid API key: {e}")
    
    def test_error_handling(self):
        """Test error handling and validation"""
        print_test_header("Testing Error Handling")
        
        # Test with malformed JSON
        print_info("Testing with malformed JSON...")
        try:
            response = requests.post(
                f"{self.base_url}/intake/email",
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                },
                data="{'invalid': json}"  # Malformed JSON
            )
            
            if response.status_code in [400, 422]:
                print_success(f"Correctly handled malformed JSON (Status: {response.status_code})")
            else:
                print_warning(f"Unexpected status for malformed JSON: {response.status_code}")
                
        except Exception as e:
            print_error(f"Error testing malformed JSON: {e}")
        
        # Test with missing required fields
        print_info("Testing with missing required fields...")
        try:
            response = requests.post(
                f"{self.base_url}/intake/email",
                headers=self.headers,
                json={"subject": "Test"}  # Missing required fields
            )
            
            if response.status_code in [400, 422]:
                print_success(f"Correctly validated missing fields (Status: {response.status_code})")
            else:
                print_warning(f"Unexpected status for missing fields: {response.status_code}")
                
        except Exception as e:
            print_error(f"Error testing missing fields: {e}")
    
    def generate_report(self):
        """Generate test report"""
        print_test_header("API Test Summary Report")
        
        # Count results
        total_errors = len(self.test_results["errors"])
        total_warnings = len(self.test_results["warnings"])
        successful_endpoints = sum(
            1 for v in self.test_results["endpoints"].values() 
            if v.get("status") == "success"
        )
        total_endpoints = len(self.test_results["endpoints"])
        
        # Performance summary
        if self.test_results["performance"]:
            avg_response_time = sum(self.test_results["performance"].values()) / len(self.test_results["performance"])
            slowest = max(self.test_results["performance"].items(), key=lambda x: x[1])
            fastest = min(self.test_results["performance"].items(), key=lambda x: x[1])
            
            print_info(f"Performance Summary:")
            print(f"  • Average response time: {avg_response_time:.3f}s")
            print(f"  • Fastest endpoint: {fastest[0]} ({fastest[1]:.3f}s)")
            print(f"  • Slowest endpoint: {slowest[0]} ({slowest[1]:.3f}s)")
        
        # Endpoint summary
        print_info(f"\nEndpoint Summary:")
        print(f"  • Successful: {successful_endpoints}/{total_endpoints}")
        
        for endpoint, result in self.test_results["endpoints"].items():
            status = "✅" if result["status"] == "success" else "❌"
            duration = result.get("duration", 0)
            print(f"  {status} {endpoint} - {result.get('status_code', 'N/A')} ({duration:.3f}s)")
        
        # Overall result
        print()
        if total_errors == 0:
            print_success(f"All API tests passed! 🎉")
        else:
            print_error(f"Found {total_errors} errors in API tests")
        
        if total_warnings > 0:
            print_warning(f"Found {total_warnings} warnings")
        
        # List errors
        if self.test_results["errors"]:
            print("\n❌ Errors:")
            for error in self.test_results["errors"]:
                print(f"  • {error}")
        
        # List warnings
        if self.test_results["warnings"]:
            print("\n⚠️  Warnings:")
            for warning in self.test_results["warnings"]:
                print(f"  • {warning}")
        
        # Save detailed report
        report_file = Path("test_api_report.json")
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return total_errors == 0

def check_server_running():
    """Check if the API server is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def main():
    """Run all API endpoint tests"""
    print(f"{Colors.BOLD}Well Intake API - Endpoint Tests{Colors.ENDC}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Target: {BASE_URL}")
    
    # Check if server is running
    if not check_server_running():
        print_error("API server is not running!")
        print_info("Please start the server with: uvicorn app.main:app --reload --port 8000")
        sys.exit(1)
    
    print_success("API server is running")
    
    # Run tests
    tester = APIEndpointTester()
    
    # Test endpoints
    tester.test_health_endpoint()
    tester.test_manifest_endpoint()
    tester.test_api_authentication()
    tester.test_error_handling()
    tester.test_intake_email_endpoint()
    tester.test_kevin_sullivan_endpoint()
    
    # Generate report
    success = tester.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()