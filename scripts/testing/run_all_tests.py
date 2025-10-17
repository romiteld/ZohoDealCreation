#!/usr/bin/env python3
"""
Comprehensive test runner for TalentWell backend implementation.
Runs all test suites and provides a summary report.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv('.env.local')

# Color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
ENDC = '\033[0m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 60}{ENDC}")
    print(f"{BOLD}{BLUE}{text.center(60)}{ENDC}")
    print(f"{BOLD}{BLUE}{'=' * 60}{ENDC}\n")

def print_section(text):
    """Print a section header."""
    print(f"\n{BOLD}{text}{ENDC}")
    print("-" * 40)

async def check_environment():
    """Verify all required environment variables are set."""
    print_section("🔍 Environment Check")
    
    required_vars = {
        "Core": [
            "API_KEY",
            "OPENAI_API_KEY",
            "DATABASE_URL",
            "AZURE_REDIS_CONNECTION_STRING"
        ],
        "Zoho": [
            "ZOHO_OAUTH_SERVICE_URL",
            "ZOHO_DEFAULT_OWNER_EMAIL"
        ],
        "Apollo": [
            "APOLLO_API_KEY"
        ],
        "Firecrawl": [
            "FIRECRAWL_API_KEY"
        ],
        "Zoom": [
            "ZOOM_ACCOUNT_ID",
            "ZOOM_CLIENT_ID",
            "ZOOM_CLIENT_SECRET",
            "ZOOM_SECRET_TOKEN",
            "ZOOM_VERIFICATION_TOKEN"
        ],
        "TalentWell": [
            "TALENTWELL_ENABLED",
            "TALENTWELL_RECIPIENT_EMAIL",
            "TALENTWELL_API_KEY"
        ]
    }
    
    all_present = True
    for category, vars in required_vars.items():
        print(f"\n{category}:")
        for var in vars:
            value = os.getenv(var)
            if value:
                # Mask sensitive values
                if "KEY" in var or "SECRET" in var or "TOKEN" in var:
                    display = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
                else:
                    display = value[:30] + "..." if len(value) > 30 else value
                print(f"  {GREEN}✓{ENDC} {var}: {display}")
            else:
                print(f"  {RED}✗{ENDC} {var}: Not set")
                all_present = False
    
    return all_present

async def run_zoom_tests():
    """Run Zoom integration tests."""
    print_section("🎥 Zoom Integration Tests")

    try:
        from tests.test_zoom_integration import main as zoom_main
        success = await zoom_main()
        return success
    except Exception as e:
        print(f"{RED}Failed to run Zoom tests: {e}{ENDC}")
        return False

async def run_apollo_tests():
    """Run Apollo.io integration tests."""
    print_section("🚀 Apollo.io Integration Tests")

    try:
        # Import and run key Apollo tests
        success = True

        # Test Apollo quick functionality
        from tests.apollo.test_apollo_quick import main as apollo_quick
        if not await apollo_quick():
            success = False

        # Test Apollo deep integration
        from tests.apollo.test_apollo_deep_integration import main as apollo_deep
        if not await apollo_deep():
            success = False

        print(f"{GREEN if success else RED}Apollo tests {'passed' if success else 'failed'}{ENDC}")
        return success
    except Exception as e:
        print(f"{RED}Failed to run Apollo tests: {e}{ENDC}")
        return False

async def run_firecrawl_tests():
    """Run Firecrawl integration tests."""
    print_section("🔥 Firecrawl Integration Tests")

    try:
        # Import and run key Firecrawl tests
        success = True

        # Test Firecrawl SDK
        from tests.firecrawl.test_firecrawl_sdk import main as firecrawl_sdk
        if not await firecrawl_sdk():
            success = False

        print(f"{GREEN if success else RED}Firecrawl tests {'passed' if success else 'failed'}{ENDC}")
        return success
    except Exception as e:
        print(f"{RED}Failed to run Firecrawl tests: {e}{ENDC}")
        return False

async def run_candidate_tests():
    """Run candidate selection tests."""
    print_section("👥 Candidate Selection Tests")
    
    try:
        from tests.test_candidate_selection import main as candidate_main
        success = await candidate_main()
        return success
    except Exception as e:
        print(f"{RED}Failed to run candidate tests: {e}{ENDC}")
        return False

async def run_email_tests():
    """Run email rendering tests."""
    print_section("📧 Email Rendering Tests")
    
    try:
        from tests.test_email_rendering import main as email_main
        success = await email_main()
        return success
    except Exception as e:
        print(f"{RED}Failed to run email tests: {e}{ENDC}")
        return False

async def check_zoom_scopes():
    """Check if Zoom app has required scopes."""
    print_section("🔐 Zoom Scope Check")
    
    from app.zoom_client import ZoomClient
    client = ZoomClient()
    
    # Try to get access token
    token = await client.get_access_token()
    if token:
        print(f"{GREEN}✓ Authentication successful{ENDC}")
        
        # Try to fetch a test recording
        test_meeting_id = "85725475967"
        recording = await client.fetch_meeting_recording(test_meeting_id)
        
        if recording:
            print(f"{GREEN}✓ Recording access granted{ENDC}")
        else:
            print(f"{YELLOW}⚠ Recording access denied - add these scopes in Zoom App:{ENDC}")
            print("  - recording:read:admin")
            print("  - cloud_recording:read:list_recording_files")
            print("\nVisit: https://marketplace.zoom.us/develop/apps")
            return False
    else:
        print(f"{RED}✗ Authentication failed{ENDC}")
        return False
    
    return True

async def test_redis_connection():
    """Test Redis connection."""
    print_section("🔄 Redis Connection Test")
    
    try:
        from well_shared.cache.redis_manager import get_cache_manager
        cache_mgr = await get_cache_manager()
        
        if cache_mgr and cache_mgr.client:
            # Try a simple operation
            test_key = "test:connection"
            await cache_mgr.client.set(test_key, "connected", ex=10)
            value = await cache_mgr.client.get(test_key)
            
            if value:
                print(f"{GREEN}✓ Redis connected and operational{ENDC}")
                return True
        
        print(f"{RED}✗ Redis connection failed{ENDC}")
        return False
        
    except Exception as e:
        print(f"{RED}✗ Redis error: {e}{ENDC}")
        return False

async def main():
    """Run all tests and provide summary."""
    start_time = datetime.now()
    
    print_header("TALENTWELL BACKEND TEST SUITE")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Track results
    results = {}
    
    # 1. Environment check
    env_ok = await check_environment()
    results["Environment"] = env_ok
    
    if not env_ok:
        print(f"\n{YELLOW}⚠ Some environment variables are missing.{ENDC}")
        print("Please update .env.local with all required values.")
    
    # 2. Test connections
    redis_ok = await test_redis_connection()
    results["Redis"] = redis_ok
    
    zoom_scopes_ok = await check_zoom_scopes()
    results["Zoom Scopes"] = zoom_scopes_ok
    
    # 3. Run test suites
    print(f"\n{BOLD}Running Test Suites...{ENDC}")

    apollo_tests_ok = await run_apollo_tests()
    results["Apollo Tests"] = apollo_tests_ok

    firecrawl_tests_ok = await run_firecrawl_tests()
    results["Firecrawl Tests"] = firecrawl_tests_ok

    zoom_tests_ok = await run_zoom_tests()
    results["Zoom Tests"] = zoom_tests_ok

    candidate_tests_ok = await run_candidate_tests()
    results["Candidate Tests"] = candidate_tests_ok

    email_tests_ok = await run_email_tests()
    results["Email Tests"] = email_tests_ok
    
    # 4. Summary
    print_header("TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = f"{GREEN}PASSED{ENDC}" if passed else f"{RED}FAILED{ENDC}"
        print(f"{test_name:.<30} {status}")
    
    print(f"\n{BOLD}Overall: {passed_tests}/{total_tests} passed{ENDC}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"Duration: {duration:.2f} seconds")
    
    # 5. Next steps
    if passed_tests < total_tests:
        print_section("📋 Next Steps")
        
        if not results.get("Zoom Scopes"):
            print("1. Add required scopes to your Zoom Server-to-Server OAuth app:")
            print("   - Visit: https://marketplace.zoom.us/develop/apps")
            print("   - Edit your app and add: recording:read:admin")
            print("   - Save and reauthorize")
        
        if not results.get("Environment"):
            print("2. Complete .env.local configuration")
            print("   - Ensure all API keys and credentials are set")
        
        if not results.get("Redis"):
            print("3. Check Azure Redis connection string")
            print("   - Verify AZURE_REDIS_CONNECTION_STRING is correct")
        
        print("\n4. After fixing issues, redeploy:")
        print("   ./deploy.sh")
    else:
        print(f"\n{GREEN}{BOLD}✅ All tests passed! Ready for deployment.{ENDC}")
        print("\nDeploy with: ./deploy.sh")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)