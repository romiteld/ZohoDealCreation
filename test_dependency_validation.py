#!/usr/bin/env python3
"""
Dependency Validation Test Script for Well Intake API
Tests that all Python dependencies can be installed and imported without conflicts
Focus on langchain compatibility and CrewAI initialization
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
from pathlib import Path

def print_header(message):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {message}")
    print("="*60)

def print_status(message, status="INFO"):
    """Print formatted status message"""
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "ENDC": "\033[0m"
    }
    print(f"{colors.get(status, '')}[{status}]{colors['ENDC']} {message}")

def create_test_venv(venv_path):
    """Create a fresh virtual environment"""
    print_status("Creating fresh virtual environment...", "INFO")
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_path], 
                      check=True, capture_output=True, text=True)
        print_status(f"Virtual environment created at: {venv_path}", "SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print_status(f"Failed to create venv: {e}", "ERROR")
        return False

def get_venv_python(venv_path):
    """Get path to Python executable in venv"""
    if os.name == 'nt':  # Windows
        return os.path.join(venv_path, "Scripts", "python.exe")
    else:  # Unix/Linux/Mac
        return os.path.join(venv_path, "bin", "python")

def get_venv_pip(venv_path):
    """Get path to pip executable in venv"""
    if os.name == 'nt':  # Windows
        return os.path.join(venv_path, "Scripts", "pip.exe")
    else:  # Unix/Linux/Mac
        return os.path.join(venv_path, "bin", "pip")

def install_dependencies(venv_path, requirements_file):
    """Install dependencies from requirements.txt"""
    pip_path = get_venv_pip(venv_path)
    
    print_status("Installing dependencies from requirements.txt...", "INFO")
    
    # First upgrade pip
    print_status("Upgrading pip...", "INFO")
    try:
        subprocess.run([pip_path, "install", "--upgrade", "pip"], 
                      check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print_status(f"Warning: Could not upgrade pip: {e.stderr}", "WARNING")
    
    # Install from requirements.txt
    try:
        result = subprocess.run(
            [pip_path, "install", "-r", requirements_file],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            print_status("Installation failed with errors:", "ERROR")
            print(result.stderr)
            return False
            
        print_status("Dependencies installed successfully", "SUCCESS")
        return True
        
    except subprocess.TimeoutExpired:
        print_status("Installation timed out after 5 minutes", "ERROR")
        return False
    except Exception as e:
        print_status(f"Installation failed: {e}", "ERROR")
        return False

def check_package_versions(venv_path):
    """Check installed versions of critical packages"""
    pip_path = get_venv_pip(venv_path)
    
    print_status("Checking installed package versions...", "INFO")
    
    critical_packages = [
        "langchain",
        "langchain-core", 
        "langchain-community",
        "langchain-openai",
        "crewai",
        "openai",
        "fastapi",
        "asyncpg",
        "firecrawl-py"
    ]
    
    versions = {}
    try:
        result = subprocess.run(
            [pip_path, "list", "--format=json"],
            capture_output=True, text=True, check=True
        )
        installed = json.loads(result.stdout)
        
        for package in installed:
            if package["name"] in critical_packages:
                versions[package["name"]] = package["version"]
                
        print("\nCritical Package Versions:")
        print("-" * 40)
        for pkg in critical_packages:
            if pkg in versions:
                print(f"  {pkg:25} {versions[pkg]:>10}")
            else:
                print_status(f"  {pkg:25} NOT INSTALLED", "WARNING")
                
        return versions
        
    except Exception as e:
        print_status(f"Failed to check versions: {e}", "ERROR")
        return {}

def test_imports(venv_path):
    """Test that critical imports work"""
    python_path = get_venv_python(venv_path)
    
    print_header("Testing Critical Imports")
    
    test_scripts = {
        "FastAPI": """
import fastapi
import uvicorn
print("FastAPI version:", fastapi.__version__)
""",
        "CrewAI Core": """
from crewai import Agent, Task, Crew, Process
print("CrewAI imported successfully")
""",
        "LangChain Core": """
import langchain
import langchain_core
print("LangChain version:", langchain.__version__)
print("LangChain-Core version:", langchain_core.__version__)
""",
        "LangChain OpenAI": """
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
print("LangChain OpenAI components imported successfully")
""",
        "AsyncPG": """
import asyncpg
print("AsyncPG version:", asyncpg.__version__)
""",
        "Azure Storage": """
from azure.storage.blob import BlobServiceClient
print("Azure Storage Blob imported successfully")
""",
        "Firecrawl": """
from firecrawl import FirecrawlApp
print("Firecrawl imported successfully")
"""
    }
    
    results = {}
    for name, script in test_scripts.items():
        print(f"\nTesting {name}...")
        try:
            result = subprocess.run(
                [python_path, "-c", script],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                print_status(f"{name}: SUCCESS", "SUCCESS")
                if result.stdout:
                    print(f"  Output: {result.stdout.strip()}")
                results[name] = True
            else:
                print_status(f"{name}: FAILED", "ERROR")
                print(f"  Error: {result.stderr.strip()}")
                results[name] = False
                
        except subprocess.TimeoutExpired:
            print_status(f"{name}: TIMEOUT", "ERROR")
            results[name] = False
        except Exception as e:
            print_status(f"{name}: ERROR - {e}", "ERROR")
            results[name] = False
            
    return results

def test_crewai_initialization(venv_path):
    """Test that CrewAI can initialize with LangChain"""
    python_path = get_venv_python(venv_path)
    
    print_header("Testing CrewAI Manager Initialization")
    
    test_script = """
import os
import sys
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langchain.tools import Tool

# Set dummy API key for testing
os.environ['OPENAI_API_KEY'] = 'sk-test-key-for-validation'

try:
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=1,
        api_key="sk-test-key-for-validation"
    )
    print("✓ ChatOpenAI initialized successfully")
    
    # Create test tool
    def dummy_func(x):
        return "test"
    
    test_tool = Tool(
        name="test_tool",
        func=dummy_func,
        description="Test tool"
    )
    print("✓ LangChain Tool created successfully")
    
    # Create test agent
    agent = Agent(
        role='Test Agent',
        goal='Test goal',
        backstory='Test backstory',
        verbose=True,
        allow_delegation=False,
        max_iter=3,
        max_execution_time=30,
        llm=llm,
        tools=[test_tool]
    )
    print("✓ CrewAI Agent created with LangChain LLM and tools")
    
    # Create test task
    task = Task(
        description="Test task",
        agent=agent,
        expected_output="Test output"
    )
    print("✓ CrewAI Task created successfully")
    
    # Create test crew
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=False,
        max_execution_time=30
    )
    print("✓ CrewAI Crew created successfully")
    
    print("\\n✅ All CrewAI components initialized successfully with LangChain!")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Failed to initialize CrewAI: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
    
    try:
        result = subprocess.run(
            [python_path, "-c", test_script],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            print_status("CrewAI initialization test: PASSED", "SUCCESS")
            print(result.stdout)
            return True
        else:
            print_status("CrewAI initialization test: FAILED", "ERROR")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print_status("CrewAI initialization test: TIMEOUT", "ERROR")
        return False
    except Exception as e:
        print_status(f"CrewAI initialization test: ERROR - {e}", "ERROR")
        return False

def check_dependency_conflicts(venv_path):
    """Check for dependency conflicts"""
    pip_path = get_venv_pip(venv_path)
    
    print_header("Checking for Dependency Conflicts")
    
    try:
        result = subprocess.run(
            [pip_path, "check"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print_status("No dependency conflicts found", "SUCCESS")
            return True
        else:
            print_status("Dependency conflicts detected:", "WARNING")
            print(result.stdout)
            return False
            
    except Exception as e:
        print_status(f"Failed to check conflicts: {e}", "ERROR")
        return False

def create_fixed_requirements():
    """Create a fixed requirements.txt with compatible versions"""
    print_header("Creating Fixed Requirements File")
    
    fixed_requirements = """# The Well Recruiting - Email Intake API Dependencies (Fixed Versions)

# Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
gunicorn==21.2.0
flask==3.0.0
pysqlite3-binary  # Required for ChromaDB on Azure App Service

# Azure Services
azure-storage-blob==12.19.0

# PostgreSQL (Azure Cosmos DB for PostgreSQL) with pgvector
asyncpg==0.29.0
psycopg2-binary==2.9.9
pgvector==0.2.4

# HTTP and API
requests==2.31.0
tenacity==8.2.3
httpx==0.27.2

# Data Processing
pydantic==2.8.2
python-multipart==0.0.6

# Email Processing
email-validator==2.1.0
beautifulsoup4==4.12.2
lxml==4.9.3

# Environment and Configuration
python-dotenv==1.0.0
setuptools==69.0.2

# AI and ML - CrewAI and OpenAI (FIXED VERSIONS)
crewai==0.159.0
openai==1.68.2  # Minimum version required by litellm (crewai dependency)
langchain==0.1.20  # Updated to compatible version
langchain-core==0.1.52  # Updated to match langchain requirements
langchain-community==0.0.38  # Updated to latest compatible
langchain-openai==0.1.7  # Updated to latest compatible
numpy==1.26.2

# Web Research
firecrawl-py==0.0.16

# Development and Testing
pytest==7.4.3
pytest-asyncio==0.21.1

# Logging and Monitoring
structlog==23.2.0

# CORS support
python-jose[cryptography]==3.3.0
"""
    
    fixed_file = "requirements_fixed.txt"
    with open(fixed_file, 'w') as f:
        f.write(fixed_requirements)
    
    print_status(f"Created {fixed_file} with compatible versions", "SUCCESS")
    print("\nKey changes made:")
    print("  - langchain: 0.1.0 → 0.1.20")
    print("  - langchain-core: 0.1.0 → 0.1.52")
    print("  - langchain-community: 0.0.10 → 0.0.38")
    print("  - langchain-openai: 0.0.5 → 0.1.7")
    
    return fixed_file

def main():
    """Main test function"""
    print_header("Well Intake API - Dependency Validation Test")
    
    # Create temporary directory for test venv
    temp_dir = tempfile.mkdtemp(prefix="well_intake_test_")
    venv_path = os.path.join(temp_dir, "test_venv")
    
    try:
        # Track overall success
        all_passed = True
        
        # Step 1: Create virtual environment
        if not create_test_venv(venv_path):
            all_passed = False
            return
        
        # Step 2: Test with original requirements
        print_header("Testing Original Requirements")
        original_req = "requirements.txt"
        
        if os.path.exists(original_req):
            print_status(f"Using {original_req}", "INFO")
            
            if install_dependencies(venv_path, original_req):
                versions = check_package_versions(venv_path)
                import_results = test_imports(venv_path)
                crewai_ok = test_crewai_initialization(venv_path)
                conflicts = check_dependency_conflicts(venv_path)
                
                if not all(import_results.values()) or not crewai_ok or not conflicts:
                    print_status("Issues found with original requirements", "WARNING")
                    all_passed = False
            else:
                print_status("Failed to install original requirements", "ERROR")
                all_passed = False
        
        # Step 3: If issues found, test with fixed requirements
        if not all_passed:
            print_header("Testing with Fixed Requirements")
            
            # Clean venv for fresh test
            shutil.rmtree(venv_path)
            create_test_venv(venv_path)
            
            fixed_req = create_fixed_requirements()
            
            if install_dependencies(venv_path, fixed_req):
                versions = check_package_versions(venv_path)
                import_results = test_imports(venv_path)
                crewai_ok = test_crewai_initialization(venv_path)
                conflicts = check_dependency_conflicts(venv_path)
                
                if all(import_results.values()) and crewai_ok and conflicts:
                    print_status("All tests passed with fixed requirements!", "SUCCESS")
                    print("\n📝 RECOMMENDATION:")
                    print("  Replace requirements.txt with requirements_fixed.txt:")
                    print("  $ cp requirements_fixed.txt requirements.txt")
                    all_passed = True
                else:
                    print_status("Some issues remain with fixed requirements", "WARNING")
        
        # Final summary
        print_header("Test Summary")
        
        if all_passed:
            print_status("✅ All dependency tests PASSED", "SUCCESS")
            print("\nYour environment is ready for the Well Intake API!")
        else:
            print_status("⚠️ Some dependency issues detected", "WARNING")
            print("\nRecommended actions:")
            print("1. Use requirements_fixed.txt for compatible versions")
            print("2. Review the specific errors above")
            print("3. Consider updating individual packages as needed")
            
    finally:
        # Cleanup
        print("\nCleaning up test environment...")
        try:
            shutil.rmtree(temp_dir)
            print_status("Cleanup complete", "SUCCESS")
        except Exception as e:
            print_status(f"Warning: Could not clean up {temp_dir}: {e}", "WARNING")

if __name__ == "__main__":
    main()