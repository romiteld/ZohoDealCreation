#!/usr/bin/env python3
"""
Test script for local OAuth Service with .env.local loading
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('../.env.local')  # Try parent directory first
load_dotenv('.env.local')      # Then current directory

def test_env_loading():
    """Test that environment variables are loaded correctly"""
    print("=" * 50)
    print("Testing .env.local Configuration Loading")
    print("=" * 50)
    
    required_vars = {
        'API_KEY': 'Main API Key',
        'ZOHO_CLIENT_ID': 'Zoho Client ID',
        'ZOHO_CLIENT_SECRET': 'Zoho Client Secret',
        'ZOHO_REFRESH_TOKEN': 'Zoho Refresh Token',
        'DATABASE_URL': 'Database URL',
        'OPENAI_API_KEY': 'OpenAI API Key'
    }
    
    all_present = True
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            # Show first 10 chars for security
            preview = value[:10] + "..." if len(value) > 10 else value
            print(f"✅ {description} ({var}): {preview}")
        else:
            print(f"❌ {description} ({var}): NOT FOUND")
            all_present = False
    
    print("\nProxy-specific configuration:")
    print(f"MAIN_API_URL: {os.environ.get('MAIN_API_URL', 'Using default')}")
    print(f"PROXY_TIMEOUT: {os.environ.get('PROXY_TIMEOUT', '30')} seconds")
    print(f"PROXY_RATE_LIMIT: {os.environ.get('PROXY_RATE_LIMIT', '100')} requests/minute")
    
    return all_present

def test_flask_app():
    """Test Flask app initialization"""
    print("\n" + "=" * 50)
    print("Testing Flask App Initialization")
    print("=" * 50)
    
    try:
        # Import the app
        from oauth_app_with_proxy import app, token_cache, ZOHO_CLIENT_ID, MAIN_API_KEY
        
        print(f"✅ Flask app imported successfully")
        print(f"✅ Zoho Client ID loaded: {'Yes' if ZOHO_CLIENT_ID else 'No'}")
        print(f"✅ Main API Key loaded: {'Yes' if MAIN_API_KEY else 'No'}")
        print(f"✅ Token cache initialized: {token_cache}")
        
        # Test app routes
        with app.test_client() as client:
            # Test root endpoint
            response = client.get('/')
            if response.status_code == 200:
                print(f"✅ Root endpoint working")
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
            
            # Test health endpoint
            response = client.get('/health')
            if response.status_code == 200:
                data = response.get_json()
                print(f"✅ Health endpoint working")
                print(f"   OAuth configured: {data.get('oauth_configured')}")
                print(f"   Proxy configured: {data.get('proxy_configured')}")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize Flask app: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "#" * 50)
    print("# OAuth Service Local Configuration Test")
    print("#" * 50)
    
    # Test environment loading
    env_success = test_env_loading()
    
    # Test Flask app
    app_success = test_flask_app()
    
    # Summary
    print("\n" + "#" * 50)
    print("# Test Summary")
    print("#" * 50)
    
    if env_success and app_success:
        print("✅ All tests passed! Ready for deployment.")
        return 0
    else:
        print("❌ Some tests failed. Please check configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())