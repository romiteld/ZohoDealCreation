#!/usr/bin/env python3
"""
Container Apps Deployment Test Suite
Tests all endpoints to ensure Microsoft is using the new Container Apps URLs
and not the old App Services deployment.
"""

import asyncio
import json
import base64
import requests
import os
from datetime import datetime
from typing import Dict, Any
import xml.etree.ElementTree as ET
from termcolor import colored
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Container Apps URL (new deployment)
CONTAINER_URL = "https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io"

# Old App Services URL (should NOT be used)
OLD_APP_SERVICE_URL = "https://well-intake-api.azurewebsites.net"

class DeploymentTester:
    def __init__(self):
        self.api_key = os.getenv('API_KEY')  # Load from environment
        if not self.api_key:
            raise ValueError("API_KEY not found in environment variables. Please set it in .env.local")
        self.results = []
        
    def print_header(self, text: str):
        """Print formatted header"""
        print("\n" + "="*60)
        print(colored(f"  {text}", "cyan", attrs=["bold"]))
        print("="*60)
        
    def print_result(self, test_name: str, success: bool, details: str = ""):
        """Print test result with color coding"""
        if success:
            status = colored("✓ PASS", "green", attrs=["bold"])
        else:
            status = colored("✗ FAIL", "red", attrs=["bold"])
        
        print(f"{status} - {test_name}")
        if details:
            print(f"       {details}")
        
        self.results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
    
    def test_health_endpoint(self) -> bool:
        """Test the health endpoint"""
        try:
            response = requests.get(f"{CONTAINER_URL}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.print_result(
                    "Health Endpoint",
                    True,
                    f"Version: {data.get('version', 'unknown')}, LangGraph: {data.get('services', {}).get('langgraph', 'unknown')}"
                )
                return True
        except Exception as e:
            self.print_result("Health Endpoint", False, str(e))
        return False
    
    def test_manifest_endpoint(self) -> Dict[str, Any]:
        """Test manifest.xml endpoint and validate URLs"""
        manifest_info = {
            "accessible": False,
            "uses_container_urls": False,
            "id": None,
            "version": None
        }
        
        try:
            response = requests.get(f"{CONTAINER_URL}/manifest.xml", timeout=5)
            if response.status_code == 200:
                manifest_info["accessible"] = True
                
                # Parse XML
                root = ET.fromstring(response.text)
                
                # Extract ID and Version
                ns = {'': 'http://schemas.microsoft.com/office/appforoffice/1.1'}
                manifest_id = root.find('Id', ns)
                manifest_version = root.find('Version', ns)
                
                if manifest_id is not None:
                    manifest_info["id"] = manifest_id.text
                if manifest_version is not None:
                    manifest_info["version"] = manifest_version.text
                
                # Check all URLs in manifest
                container_count = response.text.count('well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io')
                old_service_count = response.text.count('well-intake-api.azurewebsites.net')
                
                manifest_info["uses_container_urls"] = container_count > 0 and old_service_count == 0
                
                self.print_result(
                    "Manifest Endpoint",
                    manifest_info["accessible"] and manifest_info["uses_container_urls"],
                    f"ID: {manifest_info['id']}, Version: {manifest_info['version']}, Container URLs: {container_count}, Old URLs: {old_service_count}"
                )
            else:
                self.print_result("Manifest Endpoint", False, f"Status: {response.status_code}")
        except Exception as e:
            self.print_result("Manifest Endpoint", False, str(e))
        
        return manifest_info
    
    def test_static_files(self) -> bool:
        """Test all static file endpoints"""
        files_to_test = [
            ("commands.html", "Commands HTML"),
            ("commands.js", "Commands JavaScript"),
            ("taskpane.html", "Taskpane HTML"),
            ("taskpane.js", "Taskpane JavaScript"),
            ("config.js", "Config JavaScript"),
            ("icon-16.png", "Icon 16x16"),
            ("icon-32.png", "Icon 32x32"),
            ("icon-80.png", "Icon 80x80")
        ]
        
        all_success = True
        for file_path, description in files_to_test:
            try:
                response = requests.get(f"{CONTAINER_URL}/{file_path}", timeout=5)
                success = response.status_code == 200
                self.print_result(
                    f"Static File: {description}",
                    success,
                    f"Size: {len(response.content)} bytes" if success else f"Status: {response.status_code}"
                )
                all_success = all_success and success
            except Exception as e:
                self.print_result(f"Static File: {description}", False, str(e))
                all_success = False
        
        return all_success
    
    def test_api_endpoint(self) -> bool:
        """Test the main /intake/email API endpoint"""
        test_email = {
            "sender_name": "Test User",
            "sender_email": "test@example.com",
            "subject": "Test: Candidate Referral",
            "body": "I'd like to refer John Smith for the Senior Developer position in New York.",
            "attachments": []
        }
        
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{CONTAINER_URL}/intake/email",
                json=test_email,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.print_result(
                    "API Endpoint /intake/email",
                    True,
                    f"Response includes: {', '.join(data.keys())}"
                )
                return True
            elif response.status_code == 403:
                self.print_result(
                    "API Endpoint /intake/email",
                    False,
                    "403 Forbidden - Check API key configuration"
                )
            else:
                self.print_result(
                    "API Endpoint /intake/email",
                    False,
                    f"Status: {response.status_code}"
                )
        except Exception as e:
            self.print_result("API Endpoint /intake/email", False, str(e))
        
        return False
    
    def test_kevin_sullivan_endpoint(self) -> bool:
        """Test the Kevin Sullivan test endpoint"""
        headers = {"X-API-Key": self.api_key}
        
        try:
            response = requests.get(
                f"{CONTAINER_URL}/test/kevin-sullivan",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                extraction = data.get('extracted_data', {})
                self.print_result(
                    "Kevin Sullivan Test Endpoint",
                    True,
                    f"Extracted: {extraction.get('candidate_name', 'unknown')}, {extraction.get('job_title', 'unknown')}"
                )
                return True
            else:
                self.print_result(
                    "Kevin Sullivan Test Endpoint",
                    False,
                    f"Status: {response.status_code}"
                )
        except Exception as e:
            self.print_result("Kevin Sullivan Test Endpoint", False, str(e))
        
        return False
    
    def test_old_service_redirect(self) -> bool:
        """Check if old App Service is still responding (it shouldn't)"""
        try:
            response = requests.get(f"{OLD_APP_SERVICE_URL}/health", timeout=3)
            if response.status_code == 200:
                self.print_result(
                    "Old App Service Check",
                    False,
                    colored("WARNING: Old App Service is still active!", "yellow")
                )
                return False
            else:
                self.print_result(
                    "Old App Service Check",
                    True,
                    "Old service not responding (good)"
                )
                return True
        except:
            self.print_result(
                "Old App Service Check",
                True,
                "Old service not accessible (good)"
            )
            return True
    
    def test_cors_headers(self) -> bool:
        """Test CORS headers for Outlook access"""
        try:
            response = requests.options(
                f"{CONTAINER_URL}/taskpane.html",
                headers={"Origin": "https://outlook.office.com"}
            )
            
            cors_headers = {
                "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin", ""),
                "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods", "")
            }
            
            has_cors = "*" in cors_headers["Access-Control-Allow-Origin"] or "outlook" in cors_headers["Access-Control-Allow-Origin"].lower()
            
            self.print_result(
                "CORS Headers",
                has_cors,
                f"Origin: {cors_headers['Access-Control-Allow-Origin']}"
            )
            return has_cors
        except Exception as e:
            self.print_result("CORS Headers", False, str(e))
            return False
    
    def generate_manifest_update_instructions(self, manifest_info: Dict[str, Any]):
        """Generate instructions for updating manifest in Microsoft"""
        print("\n" + "="*60)
        print(colored("  MANIFEST UPDATE INSTRUCTIONS", "yellow", attrs=["bold"]))
        print("="*60)
        
        print("\n1. **Force Microsoft to Update Cached Manifest:**")
        print("   a) Increment version number in manifest.xml")
        print(f"      Current: {manifest_info.get('version', '1.0.0.0')}")
        print(f"      Update to: 1.0.0.{int(manifest_info.get('version', '1.0.0.0').split('.')[-1]) + 1}")
        print()
        print("   b) Remove and re-add the add-in:")
        print("      - Go to Outlook Web (outlook.office.com)")
        print("      - Click Get Add-ins → My Add-ins")
        print("      - Remove 'The Well - Send to Zoho'")
        print("      - Clear browser cache (Ctrl+Shift+Delete)")
        print("      - Add custom add-in from URL:")
        print(f"      {CONTAINER_URL}/manifest.xml")
        print()
        print("   c) Alternative - Use manifest with timestamp:")
        print(f"      {CONTAINER_URL}/manifest.xml?v={int(time.time())}")
        print()
        print("2. **For Organizational Deployment:**")
        print("   - Use Microsoft 365 Admin Center")
        print("   - Go to Settings → Integrated apps")
        print("   - Deploy the updated manifest")
        print("   - Allow 6-24 hours for propagation")
        print()
        print("3. **Test in Different Clients:**")
        print("   - Outlook Web: Should update immediately after cache clear")
        print("   - Outlook Desktop: May take 24 hours")
        print("   - Outlook Mobile: Not supported for custom add-ins")
    
    def run_all_tests(self):
        """Run all deployment tests"""
        print(colored("\n🚀 CONTAINER APPS DEPLOYMENT TESTER", "magenta", attrs=["bold"]))
        print(colored(f"   Testing: {CONTAINER_URL}", "white"))
        print(colored(f"   Time: {datetime.now().isoformat()}", "white"))
        
        # Run tests
        self.print_header("ENDPOINT TESTS")
        self.test_health_endpoint()
        manifest_info = self.test_manifest_endpoint()
        
        self.print_header("STATIC FILES")
        self.test_static_files()
        
        self.print_header("API FUNCTIONALITY")
        self.test_api_endpoint()
        self.test_kevin_sullivan_endpoint()
        
        self.print_header("DEPLOYMENT VALIDATION")
        self.test_old_service_redirect()
        self.test_cors_headers()
        
        # Summary
        self.print_header("TEST SUMMARY")
        passed = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - passed
        
        print(f"\n  Total Tests: {len(self.results)}")
        print(colored(f"  ✓ Passed: {passed}", "green"))
        if failed > 0:
            print(colored(f"  ✗ Failed: {failed}", "red"))
        
        success_rate = (passed / len(self.results)) * 100
        if success_rate == 100:
            print(colored(f"\n  🎉 SUCCESS: All tests passed! ({success_rate:.0f}%)", "green", attrs=["bold"]))
        elif success_rate >= 80:
            print(colored(f"\n  ⚠️  WARNING: Most tests passed ({success_rate:.0f}%)", "yellow", attrs=["bold"]))
        else:
            print(colored(f"\n  ❌ FAILURE: Many tests failed ({success_rate:.0f}%)", "red", attrs=["bold"]))
        
        # Show update instructions if needed
        if not manifest_info.get("uses_container_urls"):
            self.generate_manifest_update_instructions(manifest_info)
        
        return success_rate == 100


def main():
    """Main entry point"""
    tester = DeploymentTester()
    success = tester.run_all_tests()
    
    # Additional manual test instructions
    print("\n" + "="*60)
    print(colored("  MANUAL TESTING CHECKLIST", "cyan", attrs=["bold"]))
    print("="*60)
    print("\n1. **In Outlook Web (outlook.office.com):**")
    print("   ☐ Open any email")
    print("   ☐ Click 'Send to Zoho' button in ribbon")
    print("   ☐ Verify taskpane opens with email data")
    print("   ☐ Check that fields are pre-populated")
    print("   ☐ Test natural language corrections")
    print("   ☐ Add a custom field")
    print("   ☐ Click 'Send to Zoho CRM'")
    print("   ☐ Verify progress indicators work")
    print("   ☐ Check Zoho CRM for created records")
    print()
    print("2. **In Browser Developer Tools (F12):**")
    print("   ☐ Network tab shows requests to Container Apps URL")
    print("   ☐ No requests to old azurewebsites.net")
    print("   ☐ Console shows no CORS errors")
    print("   ☐ All static files load from Container Apps")
    print()
    print("3. **Version Verification:**")
    print("   Run in Outlook console:")
    print("   Office.context.mailbox.diagnostics.hostVersion")
    print()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())