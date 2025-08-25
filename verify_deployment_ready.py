#!/usr/bin/env python3
"""
Verify that main_optimized.py is ready for Azure deployment
"""

import os
import sys
import importlib.util

def check_module_imports():
    """Check that all required modules can be imported"""
    required_modules = [
        "fastapi",
        "fastapi.middleware.cors",
        "fastapi.middleware.trustedhost",
        "app.models",
        "app.static_files",
        "app.error_handlers",
        "app.business_rules",
        "app.crewai_manager_optimized",
        "app.integrations_optimized"
    ]
    
    print("Checking module imports...")
    all_good = True
    
    for module_name in required_modules:
        try:
            if module_name.startswith("app."):
                # Check local app modules
                file_name = module_name.replace("app.", "").replace(".", "/") + ".py"
                file_path = os.path.join("app", file_name.split("/")[-1])
                if os.path.exists(file_path):
                    print(f"  ✅ {module_name} - Found")
                else:
                    print(f"  ❌ {module_name} - File not found: {file_path}")
                    all_good = False
            else:
                # Try importing external modules
                spec = importlib.util.find_spec(module_name)
                if spec:
                    print(f"  ✅ {module_name} - Available")
                else:
                    print(f"  ⚠️  {module_name} - Not installed (will be installed during deployment)")
        except Exception as e:
            print(f"  ⚠️  {module_name} - Check error: {e}")
    
    return all_good

def check_critical_features():
    """Check that critical features are present in main_optimized.py"""
    print("\nChecking critical features in main_optimized.py...")
    
    with open("app/main_optimized.py", "r") as f:
        content = f.read()
    
    features = [
        ("CORSMiddleware", "CORS middleware for Outlook Add-in"),
        ("TrustedHostMiddleware", "Security middleware for production"),
        ("app.include_router(static_router)", "Static file routing"),
        ("register_error_handlers", "Error handling registration"),
        ("openapi_url", "OpenAPI specification URL"),
        ("app.debug", "Debug mode configuration"),
        ("lifespan", "Async lifespan management"),
        ("PostgreSQLClient", "Database connection pooling"),
        ("process_attachments_async", "Async attachment processing"),
        ("background_tasks", "Background task processing")
    ]
    
    all_good = True
    for feature, description in features:
        if feature in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ {description} - NOT FOUND!")
            all_good = False
    
    return all_good

def check_environment_variables():
    """Check for required environment variables"""
    print("\nChecking environment configuration...")
    
    env_vars = [
        "API_KEY",
        "AZURE_STORAGE_CONNECTION_STRING",
        "OPENAI_API_KEY",
        "ZOHO_OAUTH_SERVICE_URL",
        "ENVIRONMENT"
    ]
    
    env_file = ".env.local"
    if os.path.exists(env_file):
        print(f"  ✅ {env_file} exists")
        
        with open(env_file, "r") as f:
            env_content = f.read()
        
        for var in env_vars:
            if var in env_content:
                print(f"  ✅ {var} configured")
            else:
                print(f"  ⚠️  {var} not found in .env.local")
    else:
        print(f"  ❌ {env_file} not found - Required for local testing")
    
    return True  # Not critical for deployment as Azure has env vars

def check_static_files():
    """Check that static files exist"""
    print("\nChecking static files for Outlook Add-in...")
    
    static_files = [
        "addin/manifest.xml",
        "addin/commands.js",
        "addin/taskpane.html"
    ]
    
    all_good = True
    for file_path in static_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✅ {file_path} ({size} bytes)")
        else:
            print(f"  ❌ {file_path} - NOT FOUND!")
            all_good = False
    
    return all_good

def main():
    print("=" * 70)
    print("AZURE DEPLOYMENT READINESS CHECK FOR main_optimized.py")
    print("=" * 70)
    
    checks = [
        ("Module Imports", check_module_imports()),
        ("Critical Features", check_critical_features()),
        ("Environment Config", check_environment_variables()),
        ("Static Files", check_static_files())
    ]
    
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("-" * 50)
    
    all_passed = all(result for _, result in checks)
    
    for check_name, result in checks:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{check_name}: {status}")
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("✅ main_optimized.py is READY for Azure deployment!")
        print("\nDeploy with:")
        print("  1. Create deployment package:")
        print('     zip -r deploy.zip . -x "zoho/*" "*.pyc" "__pycache__/*" ".env*" "*.git*" "test_*.py"')
        print("  2. Deploy to Azure:")
        print("     az webapp deploy --resource-group TheWell-App-East --name well-intake-api --src-path deploy.zip --type zip")
        print("  3. Set startup command in Azure:")
        print('     gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main_optimized:app')
    else:
        print("❌ Some checks failed. Please fix the issues above before deployment.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())