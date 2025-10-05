#!/usr/bin/env python3
"""
Test script to verify Apollo integration imports and dependencies
"""

import sys
import traceback

def test_imports():
    """Test all import paths for Apollo integration"""
    print("Testing Apollo integration imports...")

    try:
        print("1. Testing config_manager import...")
        from app.config_manager import get_config_manager, get_extraction_config
        print("   ✓ config_manager imports successful")

        print("2. Testing apollo_enricher import...")
        from app.apollo_enricher import enrich_contact_with_apollo
        print("   ✓ apollo_enricher imports successful")

        print("3. Testing enhanced_enrichment import...")
        from app.enhanced_enrichment import EnhancedEnrichmentService, SmartEnrichmentOrchestrator
        print("   ✓ enhanced_enrichment imports successful")

        print("4. Testing config manager initialization...")
        config_manager = get_config_manager()
        extraction_config = get_extraction_config()
        print(f"   ✓ Config manager initialized: {type(config_manager).__name__}")
        print(f"   ✓ Extraction config loaded: {type(extraction_config).__name__}")

        print("5. Testing Apollo API key configuration...")
        apollo_key_configured = bool(extraction_config.apollo_api_key)
        print(f"   ✓ Apollo API key configured: {apollo_key_configured}")

        print("6. Testing Enhanced Enrichment Service initialization...")
        enrichment_service = EnhancedEnrichmentService()
        orchestrator = SmartEnrichmentOrchestrator()
        print(f"   ✓ EnhancedEnrichmentService initialized: {type(enrichment_service).__name__}")
        print(f"   ✓ SmartEnrichmentOrchestrator initialized: {type(orchestrator).__name__}")

        print("\n🎉 All imports and dependencies working correctly!")
        return True

    except Exception as e:
        print(f"\n❌ Import error: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

def test_circular_dependencies():
    """Test for circular dependency issues"""
    print("\nTesting for circular dependencies...")

    try:
        # Clear sys.modules to force fresh imports
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        # Import in different orders to check for circular dependencies
        print("1. Testing import order: config -> apollo -> enhanced...")
        from app.config_manager import get_extraction_config
        from app.apollo_enricher import enrich_contact_with_apollo
        from app.enhanced_enrichment import SmartEnrichmentOrchestrator

        print("2. Testing import order: enhanced -> apollo -> config...")
        # Clear and try different order
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        from app.enhanced_enrichment import EnhancedEnrichmentService
        from app.apollo_enricher import enrich_contact_with_apollo
        from app.config_manager import get_config_manager

        print("   ✓ No circular dependencies detected")
        return True

    except Exception as e:
        print(f"❌ Circular dependency detected: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import_success = test_imports()
    circular_success = test_circular_dependencies()

    if import_success and circular_success:
        print("\n✅ All dependency tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some dependency tests failed!")
        sys.exit(1)