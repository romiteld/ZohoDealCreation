#!/usr/bin/env python3
"""
Test script for manifest template system.

Tests the Jinja2 template engine and manifest generation
without dependencies on Redis or FastAPI.
"""

import os
import sys

# Add the scripts directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from scripts.manifest_warmup import ManifestConfig, ManifestTemplateEngine

def test_template_system():
    """Test the manifest template system."""
    
    print("=== Testing Manifest Template System ===")
    
    # Initialize template engine
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates', 'manifests')
    engine = ManifestTemplateEngine(templates_dir)
    
    print(f"Templates directory: {templates_dir}")
    
    # Create default templates
    print("Creating default templates...")
    engine.create_default_templates()
    
    # List created templates
    template_files = []
    if os.path.exists(templates_dir):
        template_files = [f for f in os.listdir(templates_dir) if f.endswith('.xml')]
    
    print(f"Created templates: {template_files}")
    
    # Test manifest generation
    print("\nTesting manifest generation...")
    
    # Create test configuration
    config = ManifestConfig(
        app_id="d2422753-f7f6-4a4a-9e1e-7512f37a50e5",
        version="1.3.0.2",
        provider_name="The Well Recruiting Solutions",
        app_name="The Well - Send to Zoho",
        description="Process recruitment emails and automatically create candidate records in Zoho CRM.",
        api_base_url="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
        environment="production",
        template_name="default",
        cache_busting=True,
        websocket_enabled=False,
        app_domains=[
            "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
            "https://*.azurecontainerapps.io"
        ],
        icon_16="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-16.png",
        icon_32="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-32.png",
        icon_64="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-64.png",
        icon_80="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-80.png",
        icon_128="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/icon-128.png"
    )
    
    # Generate manifest
    try:
        manifest_xml = engine.render_manifest(config)
        
        print("✅ Manifest generated successfully!")
        print(f"Manifest length: {len(manifest_xml)} characters")
        
        # Save test manifest
        test_manifest_path = os.path.join(os.path.dirname(__file__), 'test_manifest_output.xml')
        with open(test_manifest_path, 'w', encoding='utf-8') as f:
            f.write(manifest_xml)
        
        print(f"Test manifest saved to: {test_manifest_path}")
        
        # Show first few lines
        lines = manifest_xml.split('\n')[:10]
        print("\nFirst 10 lines of generated manifest:")
        for i, line in enumerate(lines, 1):
            print(f"{i:2d}: {line}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating manifest: {e}")
        return False

def test_different_environments():
    """Test manifest generation for different environments."""
    
    print("\n=== Testing Different Environment Configurations ===")
    
    engine = ManifestTemplateEngine()
    
    environments = [
        {
            "environment": "development",
            "api_base_url": "http://localhost:8000",
            "version": "1.0.0-dev",
            "template_name": "development",
            "websocket_enabled": True
        },
        {
            "environment": "staging",
            "api_base_url": "https://well-intake-api-staging.azurecontainerapps.io",
            "version": "1.3.0-staging",
            "template_name": "staging",
            "websocket_enabled": True
        },
        {
            "environment": "production",
            "api_base_url": "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
            "version": "1.3.0.2",
            "template_name": "production",
            "cache_busting": True
        }
    ]
    
    success_count = 0
    
    for env_config in environments:
        print(f"\nTesting {env_config['environment']} environment...")
        
        # Create configuration
        config = ManifestConfig(
            app_id="d2422753-f7f6-4a4a-9e1e-7512f37a50e5",
            provider_name="The Well Recruiting Solutions",
            app_name="The Well - Send to Zoho",
            description="Process recruitment emails and automatically create candidate records in Zoho CRM.",
            app_domains=[env_config["api_base_url"], "https://*.azurecontainerapps.io"],
            icon_16=f"{env_config['api_base_url']}/icon-16.png",
            icon_32=f"{env_config['api_base_url']}/icon-32.png",
            icon_64=f"{env_config['api_base_url']}/icon-64.png",
            icon_80=f"{env_config['api_base_url']}/icon-80.png",
            icon_128=f"{env_config['api_base_url']}/icon-128.png",
            **env_config
        )
        
        try:
            manifest_xml = engine.render_manifest(config)
            print(f"✅ {env_config['environment']}: {len(manifest_xml)} chars")
            
            # Save environment-specific test manifests
            test_path = os.path.join(
                os.path.dirname(__file__), 
                f'test_manifest_{env_config["environment"]}.xml'
            )
            with open(test_path, 'w', encoding='utf-8') as f:
                f.write(manifest_xml)
            
            success_count += 1
            
        except Exception as e:
            print(f"❌ {env_config['environment']}: Error - {e}")
    
    print(f"\nEnvironment test results: {success_count}/{len(environments)} successful")
    return success_count == len(environments)

def main():
    """Main test function."""
    print("Starting manifest template system tests...\n")
    
    try:
        # Test basic template system
        basic_test = test_template_system()
        
        # Test different environments
        env_test = test_different_environments()
        
        # Overall results
        print(f"\n=== Test Results ===")
        print(f"Basic template test: {'✅ PASS' if basic_test else '❌ FAIL'}")
        print(f"Environment test: {'✅ PASS' if env_test else '❌ FAIL'}")
        
        if basic_test and env_test:
            print("\n🎉 All tests passed! Manifest template system is working correctly.")
            return 0
        else:
            print("\n⚠️  Some tests failed. Please check the error messages above.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())