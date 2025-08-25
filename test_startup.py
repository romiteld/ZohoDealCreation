#!/usr/bin/env python3
"""
Comprehensive startup and dependency tests for Well Intake API
Tests all critical components and dependencies
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

class StartupTester:
    """Comprehensive startup and dependency tester for Well Intake API"""
    
    def __init__(self):
        self.results = {
            "python_version": None,
            "dependencies": {},
            "environment_vars": {},
            "imports": {},
            "app_startup": False,
            "api_endpoints": {},
            "external_services": {},
            "errors": [],
            "warnings": []
        }
        
    def test_python_version(self):
        """Test Python version compatibility"""
        print_test_header("Testing Python Version")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        self.results["python_version"] = version_str
        
        if version.major == 3 and version.minor >= 10:
            print_success(f"Python version {version_str} is compatible")
        else:
            print_error(f"Python version {version_str} may not be compatible (requires 3.10+)")
            self.results["errors"].append(f"Python version {version_str} may not be compatible")
    
    def test_dependencies(self):
        """Test all required dependencies"""
        print_test_header("Testing Dependencies")
        
        dependencies = [
            # Core Framework
            ("fastapi", "FastAPI web framework", None),
            ("uvicorn", "ASGI server", None),
            ("pydantic", "Data validation", None),
            ("dotenv", "Environment variable management", None),
            
            # AI/ML
            ("crewai", "CrewAI agent framework", None),
            ("openai", "OpenAI API client", None),
            
            # Azure
            ("azure.storage.blob", "Azure Blob Storage", "from azure.storage.blob import BlobServiceClient"),
            ("azure.cosmos", "Azure Cosmos DB", None),
            ("azure.identity", "Azure authentication", "from azure.identity import DefaultAzureCredential"),
            
            # Database
            ("psycopg2", "PostgreSQL adapter", None),
            ("pgvector", "PostgreSQL vector extension", None),
            
            # HTTP/API
            ("requests", "HTTP library", None),
            ("aiohttp", "Async HTTP client", None),
            
            # Utilities
            ("numpy", "Numerical computing", None),
            ("pandas", "Data analysis", None),
        ]
        
        for module_info in dependencies:
            module_name = module_info[0]
            description = module_info[1]
            import_test = module_info[2]
            
            try:
                if import_test:
                    # Use exec for specific import tests
                    exec(import_test)
                    version = "Imported successfully"
                elif '.' in module_name:
                    # Try importing as a submodule
                    exec(f"from {module_name} import *")
                    version = "Imported successfully"
                else:
                    # Standard import
                    module = __import__(module_name)
                    version = getattr(module, '__version__', 'Unknown')
                
                self.results["dependencies"][module_name] = {
                    "status": "installed",
                    "version": str(version),
                    "description": description
                }
                print_success(f"{description} ({module_name}) - Version: {version}")
                
            except (ImportError, AttributeError) as e:
                self.results["dependencies"][module_name] = {
                    "status": "missing",
                    "error": str(e),
                    "description": description
                }
                print_error(f"{description} ({module_name}) - {e}")
                self.results["errors"].append(f"Missing dependency: {module_name}")
    
    def test_environment_variables(self):
        """Test environment variable loading"""
        print_test_header("Testing Environment Variables")
        
        # Load .env.local
        from dotenv import load_dotenv
        env_file = Path(".env.local")
        
        if env_file.exists():
            load_dotenv(env_file)
            print_success(f"Loaded environment from {env_file}")
        else:
            print_warning(f"No {env_file} file found")
            self.results["warnings"].append(f"No {env_file} file found")
        
        # Check required environment variables
        required_vars = {
            "API_KEY": "API authentication key",
            "OPENAI_API_KEY": "OpenAI API key for GPT-5-mini",
            "DATABASE_URL": "PostgreSQL connection string",
            "AZURE_STORAGE_CONNECTION_STRING": "Azure Blob Storage connection",
            "AZURE_CONTAINER_NAME": "Azure container name",  # Changed from AZURE_STORAGE_CONTAINER_NAME
            "ZOHO_OAUTH_SERVICE_URL": "Zoho OAuth service URL",
            "ZOHO_CLIENT_ID": "Zoho OAuth client ID",  # Changed from CLIENT_ID
            "ZOHO_CLIENT_SECRET": "Zoho OAuth client secret",  # Changed from CLIENT_SECRET
        }
        
        optional_vars = {
            "FIRECRAWL_API_KEY": "Firecrawl API for web research",
            "ZOHO_DEFAULT_OWNER_ID": "Default Zoho owner ID",
            "ZOHO_DEFAULT_OWNER_EMAIL": "Default Zoho owner email",
            "LOG_ANALYTICS_WORKSPACE_ID": "Azure Log Analytics",
            "APPLICATION_INSIGHTS_KEY": "Application Insights",
        }
        
        # Test required variables
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if value:
                # Mask sensitive values
                masked_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                self.results["environment_vars"][var_name] = {
                    "status": "set",
                    "description": description,
                    "masked_value": masked_value
                }
                print_success(f"{var_name}: {description} (set: {masked_value})")
            else:
                self.results["environment_vars"][var_name] = {
                    "status": "missing",
                    "description": description
                }
                print_error(f"{var_name}: {description} (NOT SET)")
                self.results["errors"].append(f"Missing required env var: {var_name}")
        
        # Test optional variables
        print_info("Optional environment variables:")
        for var_name, description in optional_vars.items():
            value = os.getenv(var_name)
            if value:
                masked_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                print_success(f"  {var_name}: {description} (set: {masked_value})")
            else:
                print_warning(f"  {var_name}: {description} (not set)")
    
    def test_app_imports(self):
        """Test importing all app modules"""
        print_test_header("Testing App Module Imports")
        
        modules_to_test = {
            "app.main": "Main FastAPI application",
            "app.models": "Pydantic models",
            "app.business_rules": "Business logic rules",
            "app.crewai_manager": "CrewAI agent manager",
            "app.integrations": "External service integrations",
            "app.static_files": "Static file handling",
        }
        
        for module_name, description in modules_to_test.items():
            try:
                module = __import__(module_name, fromlist=[''])
                self.results["imports"][module_name] = {
                    "status": "success",
                    "description": description
                }
                print_success(f"{description} ({module_name})")
                
                # Check for specific attributes
                if module_name == "app.main":
                    if hasattr(module, 'app'):
                        print_info("  - FastAPI app instance found")
                    else:
                        print_warning("  - FastAPI app instance not found")
                        
            except Exception as e:
                self.results["imports"][module_name] = {
                    "status": "failed",
                    "error": str(e),
                    "description": description
                }
                print_error(f"{description} ({module_name}) - {e}")
                self.results["errors"].append(f"Import failed: {module_name}")
    
    def test_crewai_configuration(self):
        """Test CrewAI configuration and model settings"""
        print_test_header("Testing CrewAI Configuration")
        
        try:
            from app.crewai_manager import EmailProcessingCrew
            
            # Check if it uses correct model
            manager_code = Path("app/crewai_manager.py").read_text()
            
            if 'model="gpt-5-mini"' in manager_code or "model='gpt-5-mini'" in manager_code:
                print_success("CrewAI configured with GPT-5-mini model")
            else:
                print_warning("CrewAI model configuration should be GPT-5-mini")
                self.results["warnings"].append("CrewAI not using GPT-5-mini")
            
            if 'temperature=1' in manager_code:
                print_success("CrewAI temperature set to 1 (required for GPT-5-mini)")
            else:
                print_error("CrewAI temperature not set to 1 (required for GPT-5-mini)")
                self.results["errors"].append("CrewAI temperature must be 1")
            
            if 'memory=False' in manager_code:
                print_success("CrewAI memory disabled for performance")
            else:
                print_warning("CrewAI memory should be disabled for performance")
                
            if 'max_execution_time=30' in manager_code:
                print_success("CrewAI max execution time set to 30s")
            else:
                print_warning("CrewAI max execution time should be set to 30s")
                
        except Exception as e:
            print_error(f"Failed to test CrewAI configuration: {e}")
            self.results["errors"].append(f"CrewAI configuration test failed: {e}")
    
    def test_database_models(self):
        """Test database connection and models"""
        print_test_header("Testing Database Configuration")
        
        try:
            from app.integrations import PostgreSQLClient
            
            # Check if DATABASE_URL is set
            db_url = os.getenv("DATABASE_URL")
            if db_url:
                print_success("DATABASE_URL is configured")
                
                # Parse connection string
                if "postgresql://" in db_url:
                    print_info("  - PostgreSQL connection string detected")
                if "@c-" in db_url and "cosmos.azure.com" in db_url:
                    print_info("  - Azure Cosmos DB for PostgreSQL detected")
                if "sslmode=require" in db_url:
                    print_info("  - SSL mode enabled")
                    
            else:
                print_error("DATABASE_URL not configured")
                self.results["errors"].append("DATABASE_URL not configured")
                
        except Exception as e:
            print_error(f"Database configuration test failed: {e}")
            self.results["errors"].append(f"Database test failed: {e}")
    
    def test_azure_configuration(self):
        """Test Azure service configuration"""
        print_test_header("Testing Azure Configuration")
        
        # Test Azure Blob Storage
        conn_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
        
        if conn_string:
            print_success("Azure Storage connection string configured")
            if "AccountName=" in conn_string:
                account = conn_string.split("AccountName=")[1].split(";")[0]
                print_info(f"  - Storage account: {account}")
        else:
            print_error("Azure Storage connection string not configured")
            
        if container_name:
            print_success(f"Azure container configured: {container_name}")
        else:
            print_error("Azure container name not configured")
    
    def test_zoho_configuration(self):
        """Test Zoho CRM configuration"""
        print_test_header("Testing Zoho Configuration")
        
        oauth_url = os.getenv("ZOHO_OAUTH_SERVICE_URL")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        
        if oauth_url:
            print_success(f"Zoho OAuth service URL: {oauth_url}")
        else:
            print_error("Zoho OAuth service URL not configured")
            
        if client_id:
            print_success(f"Zoho Client ID configured: {client_id[:10]}...")
        else:
            print_error("Zoho Client ID not configured")
            
        if client_secret:
            print_success("Zoho Client Secret configured")
        else:
            print_error("Zoho Client Secret not configured")
        
        # Check for owner configuration
        owner_id = os.getenv("ZOHO_DEFAULT_OWNER_ID")
        owner_email = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL")
        
        if owner_id or owner_email:
            print_success("Zoho default owner configured (not hardcoded)")
        else:
            print_warning("No default Zoho owner configured (will use dynamic assignment)")
    
    def generate_report(self):
        """Generate final test report"""
        print_test_header("Test Summary Report")
        
        # Count results
        total_errors = len(self.results["errors"])
        total_warnings = len(self.results["warnings"])
        
        if total_errors == 0:
            print_success(f"All critical tests passed! 🎉")
        else:
            print_error(f"Found {total_errors} critical errors")
            
        if total_warnings > 0:
            print_warning(f"Found {total_warnings} warnings")
        
        # List errors
        if self.results["errors"]:
            print("\n❌ Critical Errors:")
            for error in self.results["errors"]:
                print(f"  • {error}")
        
        # List warnings
        if self.results["warnings"]:
            print("\n⚠️  Warnings:")
            for warning in self.results["warnings"]:
                print(f"  • {warning}")
        
        # Save detailed report
        report_file = Path("test_startup_report.json")
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return total_errors == 0

def main():
    """Run all startup tests"""
    print(f"{Colors.BOLD}Well Intake API - Comprehensive Startup Tests{Colors.ENDC}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    tester = StartupTester()
    
    # Run all tests
    tester.test_python_version()
    tester.test_dependencies()
    tester.test_environment_variables()
    tester.test_app_imports()
    tester.test_crewai_configuration()
    tester.test_database_models()
    tester.test_azure_configuration()
    tester.test_zoho_configuration()
    
    # Generate report
    success = tester.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()