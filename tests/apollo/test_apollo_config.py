#!/usr/bin/env python3
"""
Test script to verify Apollo API key configuration loading and usage
"""

import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

def test_config_loading():
    """Test Apollo API key configuration loading"""
    print("Testing Apollo API key configuration loading...")

    try:
        from app.config_manager import get_extraction_config

        print("1. Testing extraction config loading...")
        config = get_extraction_config()
        print(f"   ✓ Config type: {type(config).__name__}")

        print("2. Testing Apollo API key access...")
        apollo_key = config.apollo_api_key
        apollo_key_env = os.getenv("APOLLO_API_KEY")

        print(f"   • Apollo key from config: {'***configured***' if apollo_key else 'NOT SET'}")
        print(f"   • Apollo key from env: {'***configured***' if apollo_key_env else 'NOT SET'}")
        print(f"   • Keys match: {apollo_key == apollo_key_env}")

        print("3. Testing config structure...")
        print(f"   • Use LangGraph: {config.use_langgraph}")
        print(f"   • OpenAI model: {config.openai_model}")
        print(f"   • OpenAI temperature: {config.openai_temperature}")
        print(f"   • Apollo key type: {type(apollo_key)}")

        return True, apollo_key

    except Exception as e:
        print(f"❌ Config loading error: {e}")
        import traceback
        traceback.print_exc()
        return False, None

async def test_apollo_enricher_config_usage():
    """Test that Apollo enricher correctly uses config manager"""
    print("\nTesting Apollo enricher configuration usage...")

    try:
        from app.apollo_enricher import enrich_contact_with_apollo

        print("1. Testing enrichment function with no email (should return None)...")
        result = await enrich_contact_with_apollo("")
        print(f"   ✓ Empty email result: {result}")

        print("2. Testing enrichment function with test email...")
        # This will test the config loading but fail gracefully due to test email
        test_email = "test@example.com"
        result = await enrich_contact_with_apollo(test_email)
        print(f"   • Test email result: {result}")
        print("   ✓ Function executed without errors (API call expected to fail for test email)")

        return True

    except Exception as e:
        print(f"❌ Apollo enricher error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_enrichment_integration():
    """Test Enhanced Enrichment Service Apollo integration"""
    print("\nTesting Enhanced Enrichment Service Apollo integration...")

    try:
        from app.enhanced_enrichment import EnhancedEnrichmentService

        print("1. Testing EnhancedEnrichmentService initialization...")
        service = EnhancedEnrichmentService()

        print("2. Testing Apollo API key access in enhanced service...")
        apollo_key = service.apollo_api_key
        print(f"   • Apollo key configured in service: {'***configured***' if apollo_key else 'NOT SET'}")

        print("3. Testing service provider detection...")
        providers = []
        if service.clay_api_key:
            providers.append("Clay")
        if service.apollo_api_key:
            providers.append("Apollo")
        if service.clearbit_api_key:
            providers.append("Clearbit")
        if service.pdl_api_key:
            providers.append("PDL")
        if service.firecrawl_api_key:
            providers.append("Firecrawl")

        print(f"   • Active providers: {providers}")
        print(f"   • Apollo provider active: {'Apollo' in providers}")

        return True

    except Exception as e:
        print(f"❌ Enhanced enrichment error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all configuration tests"""
    print("=" * 60)
    print("Apollo Integration Configuration Test Suite")
    print("=" * 60)

    # Test 1: Config loading
    config_success, apollo_key = test_config_loading()

    # Test 2: Apollo enricher config usage
    enricher_success = await test_apollo_enricher_config_usage()

    # Test 3: Enhanced enrichment integration
    enhanced_success = test_enhanced_enrichment_integration()

    print("\n" + "=" * 60)
    print("Configuration Test Summary:")
    print("=" * 60)
    print(f"Config Loading:           {'✅ PASS' if config_success else '❌ FAIL'}")
    print(f"Apollo Enricher Config:   {'✅ PASS' if enricher_success else '❌ FAIL'}")
    print(f"Enhanced Enrichment:      {'✅ PASS' if enhanced_success else '❌ FAIL'}")
    print(f"Apollo Key Available:     {'✅ YES' if apollo_key else '❌ NO'}")

    all_success = config_success and enricher_success and enhanced_success
    print(f"\nOverall Status:           {'✅ ALL TESTS PASSED' if all_success else '❌ SOME TESTS FAILED'}")

    return all_success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)