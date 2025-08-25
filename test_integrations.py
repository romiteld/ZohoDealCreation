#!/usr/bin/env python3
"""
Integration Tests for Well Intake API
Tests external service connections and integrations
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

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

class IntegrationTester:
    """Test all external service integrations"""
    
    def __init__(self):
        self.test_results = {
            "azure_storage": {},
            "postgresql": {},
            "zoho_oauth": {},
            "openai": {},
            "firecrawl": {},
            "errors": [],
            "warnings": []
        }
    
    def test_azure_blob_storage(self):
        """Test Azure Blob Storage connectivity"""
        print_test_header("Testing Azure Blob Storage")
        
        try:
            from azure.storage.blob import BlobServiceClient
            
            # Get connection string
            conn_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            container_name = os.getenv("AZURE_CONTAINER_NAME") or os.getenv("AZURE_STORAGE_CONTAINER_NAME")
            
            if not conn_string:
                print_error("Azure Storage connection string not configured")
                self.test_results["errors"].append("Missing Azure Storage connection string")
                return
            
            if not container_name:
                print_warning("Azure container name not configured")
                container_name = "email-attachments"  # Use default
                print_info(f"Using default container: {container_name}")
            
            # Create client
            print_info("Creating BlobServiceClient...")
            blob_service_client = BlobServiceClient.from_connection_string(conn_string)
            
            # Test account properties
            print_info("Testing account access...")
            account_info = blob_service_client.get_account_information()
            print_success(f"Connected to storage account")
            print_info(f"  Account kind: {account_info.get('account_kind', 'Unknown')}")
            print_info(f"  SKU: {account_info.get('sku_name', 'Unknown')}")
            
            # Test container access
            print_info(f"Testing container access: {container_name}")
            container_client = blob_service_client.get_container_client(container_name)
            
            try:
                # Check if container exists
                if container_client.exists():
                    print_success(f"Container '{container_name}' exists and is accessible")
                    
                    # Try to list blobs (limited to 5)
                    blobs = list(container_client.list_blobs(results_per_page=5))
                    print_info(f"  Found {len(blobs)} blob(s) in container")
                    
                else:
                    print_warning(f"Container '{container_name}' does not exist")
                    print_info("Attempting to create container...")
                    
                    try:
                        container_client.create_container()
                        print_success(f"Container '{container_name}' created successfully")
                    except Exception as e:
                        if "ContainerAlreadyExists" in str(e):
                            print_info("Container already exists (may be a timing issue)")
                        else:
                            print_error(f"Failed to create container: {e}")
                
                self.test_results["azure_storage"] = {
                    "status": "connected",
                    "container": container_name,
                    "accessible": True
                }
                
            except Exception as e:
                print_error(f"Container access failed: {e}")
                self.test_results["errors"].append(f"Azure container access failed: {e}")
                
        except Exception as e:
            print_error(f"Azure Blob Storage test failed: {e}")
            self.test_results["errors"].append(f"Azure Blob Storage connection failed: {e}")
    
    def test_postgresql_connection(self):
        """Test PostgreSQL database connection"""
        print_test_header("Testing PostgreSQL Database")
        
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Get database URL
            db_url = os.getenv("DATABASE_URL")
            
            if not db_url:
                print_error("DATABASE_URL not configured")
                self.test_results["errors"].append("Missing DATABASE_URL")
                return
            
            # Parse connection info
            if "@c-" in db_url and "cosmos.azure.com" in db_url:
                print_info("Connecting to Azure Cosmos DB for PostgreSQL...")
            else:
                print_info("Connecting to PostgreSQL database...")
            
            # Test connection
            print_info("Testing database connection...")
            
            try:
                conn = psycopg2.connect(db_url)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Test query
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                print_success("Database connection successful")
                print_info(f"  PostgreSQL version: {version['version'][:50]}...")
                
                # Check for pgvector extension
                cursor.execute("""
                    SELECT * FROM pg_extension 
                    WHERE extname = 'vector';
                """)
                vector_ext = cursor.fetchone()
                
                if vector_ext:
                    print_success("pgvector extension is installed")
                else:
                    print_warning("pgvector extension not found")
                    print_info("  To install: CREATE EXTENSION IF NOT EXISTS vector;")
                
                # Check tables
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    LIMIT 10;
                """)
                tables = cursor.fetchall()
                
                if tables:
                    print_info(f"  Found {len(tables)} table(s):")
                    for table in tables[:5]:
                        print(f"    • {table['table_name']}")
                else:
                    print_info("  No tables found (database may be empty)")
                
                self.test_results["postgresql"] = {
                    "status": "connected",
                    "pgvector": bool(vector_ext),
                    "tables": len(tables)
                }
                
                cursor.close()
                conn.close()
                
            except psycopg2.OperationalError as e:
                print_error(f"Database connection failed: {e}")
                self.test_results["errors"].append(f"PostgreSQL connection failed: {e}")
                
        except ImportError as e:
            print_error(f"psycopg2 not installed: {e}")
            self.test_results["errors"].append("psycopg2 module not installed")
        except Exception as e:
            print_error(f"PostgreSQL test failed: {e}")
            self.test_results["errors"].append(f"PostgreSQL test failed: {e}")
    
    def test_zoho_oauth_service(self):
        """Test Zoho OAuth service connectivity"""
        print_test_header("Testing Zoho OAuth Service")
        
        try:
            import requests
            
            # Get OAuth service URL
            oauth_url = os.getenv("ZOHO_OAUTH_SERVICE_URL")
            client_id = os.getenv("ZOHO_CLIENT_ID") or os.getenv("CLIENT_ID")
            client_secret = os.getenv("ZOHO_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")
            
            if not oauth_url:
                print_error("ZOHO_OAUTH_SERVICE_URL not configured")
                self.test_results["errors"].append("Missing ZOHO_OAUTH_SERVICE_URL")
                return
            
            print_info(f"OAuth Service URL: {oauth_url}")
            
            # Test service health
            print_info("Testing OAuth service health...")
            try:
                response = requests.get(f"{oauth_url}/health", timeout=10)
                
                if response.status_code == 200:
                    print_success("OAuth service is running")
                    
                    # Check for token endpoint
                    print_info("Checking token endpoint...")
                    token_response = requests.get(f"{oauth_url}/get_token", timeout=10)
                    
                    if token_response.status_code in [200, 401, 403]:
                        print_success("Token endpoint is accessible")
                        
                        if token_response.status_code == 200:
                            try:
                                token_data = token_response.json()
                                if "access_token" in token_data:
                                    print_success("Valid access token available")
                                    print_info(f"  Token type: {token_data.get('token_type', 'Unknown')}")
                                    print_info(f"  Expires in: {token_data.get('expires_in', 'Unknown')} seconds")
                                else:
                                    print_warning("No access token in response")
                            except:
                                print_warning("Could not parse token response")
                    else:
                        print_warning(f"Token endpoint returned: {token_response.status_code}")
                    
                else:
                    print_warning(f"OAuth service returned status: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print_error("Cannot connect to OAuth service")
                print_info("  Ensure the OAuth service is deployed and running")
                self.test_results["warnings"].append("OAuth service not accessible")
            except requests.exceptions.Timeout:
                print_error("OAuth service timeout")
                self.test_results["warnings"].append("OAuth service timeout")
            
            # Check credentials
            if client_id:
                print_success(f"Client ID configured: {client_id[:20]}...")
            else:
                print_error("Client ID not configured")
                self.test_results["errors"].append("Missing Zoho Client ID")
            
            if client_secret:
                print_success("Client Secret configured")
            else:
                print_error("Client Secret not configured")
                self.test_results["errors"].append("Missing Zoho Client Secret")
            
            self.test_results["zoho_oauth"] = {
                "service_url": oauth_url,
                "credentials_configured": bool(client_id and client_secret)
            }
            
        except Exception as e:
            print_error(f"Zoho OAuth test failed: {e}")
            self.test_results["errors"].append(f"Zoho OAuth test failed: {e}")
    
    def test_openai_connection(self):
        """Test OpenAI API connectivity"""
        print_test_header("Testing OpenAI API")
        
        try:
            import openai
            
            # Get API key
            api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                print_error("OPENAI_API_KEY not configured")
                self.test_results["errors"].append("Missing OPENAI_API_KEY")
                return
            
            print_info("Testing OpenAI API connection...")
            
            # Set up client
            client = openai.OpenAI(api_key=api_key)
            
            try:
                # Test with a simple completion
                response = client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {"role": "system", "content": "You are a test assistant."},
                        {"role": "user", "content": "Respond with 'OK' if you receive this."}
                    ],
                    temperature=1,  # Required for GPT-5-mini
                    max_tokens=10
                )
                
                if response.choices:
                    print_success("OpenAI API connection successful")
                    print_info(f"  Model: gpt-5-mini")
                    print_info(f"  Response: {response.choices[0].message.content}")
                    
                    self.test_results["openai"] = {
                        "status": "connected",
                        "model": "gpt-5-mini"
                    }
                else:
                    print_error("No response from OpenAI API")
                    self.test_results["errors"].append("OpenAI API returned no response")
                    
            except openai.AuthenticationError:
                print_error("OpenAI API authentication failed")
                print_info("  Check if your API key is valid")
                self.test_results["errors"].append("OpenAI API authentication failed")
                
            except openai.RateLimitError:
                print_warning("OpenAI API rate limit reached")
                print_info("  The API is working but you've hit rate limits")
                self.test_results["warnings"].append("OpenAI API rate limited")
                
            except Exception as e:
                if "temperature" in str(e) and "gpt-5-mini" in str(e).lower():
                    print_error("GPT-5-mini requires temperature=1")
                    self.test_results["errors"].append("GPT-5-mini temperature must be 1")
                else:
                    print_error(f"OpenAI API error: {e}")
                    self.test_results["errors"].append(f"OpenAI API error: {e}")
                    
        except ImportError:
            print_error("openai package not installed")
            self.test_results["errors"].append("openai package not installed")
        except Exception as e:
            print_error(f"OpenAI test failed: {e}")
            self.test_results["errors"].append(f"OpenAI test failed: {e}")
    
    def test_firecrawl_api(self):
        """Test Firecrawl API connectivity"""
        print_test_header("Testing Firecrawl API")
        
        try:
            import requests
            
            # Get API key
            api_key = os.getenv("FIRECRAWL_API_KEY")
            
            if not api_key:
                print_warning("FIRECRAWL_API_KEY not configured")
                print_info("  Firecrawl is optional for web research")
                self.test_results["warnings"].append("Firecrawl API key not configured")
                return
            
            print_info("Testing Firecrawl API connection...")
            
            # Test API with a simple request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test scraping a simple page
            test_url = "https://example.com"
            
            try:
                response = requests.post(
                    "https://api.firecrawl.dev/v0/scrape",
                    headers=headers,
                    json={"url": test_url},
                    timeout=10
                )
                
                if response.status_code == 200:
                    print_success("Firecrawl API connection successful")
                    data = response.json()
                    
                    if "data" in data:
                        print_info("  Successfully scraped test page")
                        self.test_results["firecrawl"] = {
                            "status": "connected",
                            "functional": True
                        }
                    else:
                        print_warning("Unexpected response format")
                        
                elif response.status_code == 401:
                    print_error("Firecrawl API authentication failed")
                    print_info("  Check if your API key is valid")
                    self.test_results["errors"].append("Firecrawl authentication failed")
                    
                elif response.status_code == 429:
                    print_warning("Firecrawl API rate limit reached")
                    self.test_results["warnings"].append("Firecrawl rate limited")
                    
                else:
                    print_warning(f"Firecrawl API returned: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print_warning("Firecrawl API timeout")
                self.test_results["warnings"].append("Firecrawl API timeout")
                
            except Exception as e:
                print_error(f"Firecrawl API error: {e}")
                self.test_results["warnings"].append(f"Firecrawl API error: {e}")
                
        except Exception as e:
            print_error(f"Firecrawl test failed: {e}")
            self.test_results["warnings"].append(f"Firecrawl test failed: {e}")
    
    def test_crewai_agents(self):
        """Test CrewAI agent initialization"""
        print_test_header("Testing CrewAI Agents")
        
        try:
            from app.crewai_manager import EmailProcessingCrew
            
            print_info("Testing CrewAI agent initialization...")
            
            # Get Firecrawl API key (optional)
            firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "dummy-key")
            
            # Create crew instance
            crew = EmailProcessingCrew(firecrawl_api_key=firecrawl_key)
            
            print_success("EmailProcessingCrew initialized")
            
            # Test crew setup
            try:
                crew_instance = crew.setup_crew()
                print_success("CrewAI crew setup successful")
                
                # Check agents
                if hasattr(crew_instance, 'agents'):
                    print_info(f"  Number of agents: {len(crew_instance.agents)}")
                    for i, agent in enumerate(crew_instance.agents):
                        print_info(f"    Agent {i+1}: {agent.role}")
                
                # Check tasks
                if hasattr(crew_instance, 'tasks'):
                    print_info(f"  Number of tasks: {len(crew_instance.tasks)}")
                
            except Exception as e:
                print_error(f"Crew setup failed: {e}")
                self.test_results["errors"].append(f"CrewAI setup failed: {e}")
                
        except ImportError as e:
            print_error(f"Failed to import CrewAI manager: {e}")
            self.test_results["errors"].append(f"CrewAI import failed: {e}")
        except Exception as e:
            print_error(f"CrewAI test failed: {e}")
            self.test_results["errors"].append(f"CrewAI test failed: {e}")
    
    def generate_report(self):
        """Generate test report"""
        print_test_header("Integration Test Summary")
        
        # Count results
        total_errors = len(self.test_results["errors"])
        total_warnings = len(self.test_results["warnings"])
        
        # Service status
        print_info("Service Status:")
        
        services = [
            ("Azure Blob Storage", self.test_results.get("azure_storage", {}).get("status")),
            ("PostgreSQL Database", self.test_results.get("postgresql", {}).get("status")),
            ("Zoho OAuth Service", "configured" if self.test_results.get("zoho_oauth", {}).get("credentials_configured") else "not configured"),
            ("OpenAI API", self.test_results.get("openai", {}).get("status")),
            ("Firecrawl API", self.test_results.get("firecrawl", {}).get("status", "not tested"))
        ]
        
        for service, status in services:
            if status == "connected" or status == "configured":
                print(f"  ✅ {service}: {status}")
            elif status == "not tested":
                print(f"  ⚠️  {service}: {status}")
            else:
                print(f"  ❌ {service}: {status or 'failed'}")
        
        # Overall result
        print()
        if total_errors == 0:
            print_success("All critical integrations passed! 🎉")
        else:
            print_error(f"Found {total_errors} integration errors")
        
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
        report_file = Path("test_integrations_report.json")
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return total_errors == 0

def main():
    """Run all integration tests"""
    print(f"{Colors.BOLD}Well Intake API - Integration Tests{Colors.ENDC}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    tester = IntegrationTester()
    
    # Run all integration tests
    tester.test_azure_blob_storage()
    tester.test_postgresql_connection()
    tester.test_zoho_oauth_service()
    tester.test_openai_connection()
    tester.test_firecrawl_api()
    tester.test_crewai_agents()
    
    # Generate report
    success = tester.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()