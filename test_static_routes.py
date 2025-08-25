#!/usr/bin/env python3
"""
Test script to verify static file routes are working correctly in main_optimized.py
"""

import asyncio
from fastapi.testclient import TestClient
from app.main_optimized import app
import os

def test_static_routes():
    """Test that static file routes are accessible"""
    client = TestClient(app)
    
    # Test routes that should be available
    test_routes = [
        ("/manifest.xml", "application/xml"),
        ("/commands.js", "application/javascript"),
        ("/health", None),  # JSON response
    ]
    
    print("Testing static routes in main_optimized.py...")
    print("-" * 50)
    
    all_passed = True
    
    for route, expected_content_type in test_routes:
        try:
            response = client.get(route)
            status = "✅" if response.status_code == 200 else "❌"
            
            if response.status_code != 200:
                all_passed = False
                
            print(f"{status} {route}: Status {response.status_code}")
            
            if response.status_code == 200 and expected_content_type:
                content_type = response.headers.get("content-type", "")
                if expected_content_type in content_type:
                    print(f"   Content-Type: {content_type}")
                else:
                    print(f"   ⚠️  Unexpected Content-Type: {content_type}")
                    print(f"      Expected: {expected_content_type}")
                    
            # Show first 100 chars of response for debugging
            if response.status_code != 200:
                print(f"   Response: {response.text[:100]}...")
                
        except Exception as e:
            print(f"❌ {route}: Error - {e}")
            all_passed = False
    
    print("-" * 50)
    
    # List all available routes
    print("\nAll registered routes:")
    for route in app.routes:
        print(f"  - {route.path}")
    
    # Check middleware
    print("\nMiddleware stack:")
    for middleware in app.user_middleware:
        print(f"  - {middleware.cls.__name__ if hasattr(middleware, 'cls') else middleware}")
    
    # Check exception handlers
    print("\nException handlers registered:")
    handler_count = len(app.exception_handlers)
    print(f"  - Total: {handler_count} handlers")
    
    print("-" * 50)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    
    return all_passed

if __name__ == "__main__":
    # Set environment for testing
    os.environ["API_KEY"] = "test-key"
    
    success = test_static_routes()
    exit(0 if success else 1)