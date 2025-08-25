#!/usr/bin/env python3
"""
Requirements Optimizer for Azure App Service
Resolves dependency conflicts and creates compatible requirements
"""

import subprocess
import sys
import json
from pathlib import Path

class RequirementsOptimizer:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        
        # Known compatibility matrix for Azure App Service Python 3.12
        self.compatibility_matrix = {
            "langchain": {
                "version": "0.1.0",
                "requires": {
                    "langchain-core": "0.1.0",
                    "langchain-community": "0.0.10",
                    "langsmith": ">=0.0.63,<0.1.0",
                    "pydantic": ">=1,<3",
                }
            },
            "crewai": {
                "version": "0.159.0",
                "requires": {
                    "openai": ">=1.68.2",
                    "langchain": ">=0.1.0",
                    "pydantic": ">=2.0.0",
                }
            },
            "openai": {
                "version": "1.68.2",
                "requires": {
                    "httpx": ">=0.23.0",
                    "pydantic": ">=1.9.0",
                }
            }
        }
        
    def create_optimized_requirements(self):
        """Create an optimized requirements.txt with resolved dependencies"""
        
        print("Creating optimized requirements file...")
        
        optimized_requirements = """# Optimized Requirements for Azure App Service
# Python 3.12 Compatible - Resolved Dependencies

# === Core Web Framework ===
fastapi==0.104.1
uvicorn[standard]==0.24.0
gunicorn==21.2.0
flask==3.0.0

# === Essential Setup ===
setuptools==69.0.2
wheel
pip>=23.0

# === SQLite Override (for ChromaDB) ===
pysqlite3-binary

# === Azure Services ===
azure-storage-blob==12.19.0

# === Database ===
asyncpg==0.29.0
psycopg2-binary==2.9.9
pgvector==0.2.4

# === HTTP and Networking ===
requests==2.31.0
httpx==0.27.2
tenacity==8.2.3
aiohttp==3.9.1
urllib3<2.0.0

# === Data Models and Validation ===
pydantic==2.8.2
pydantic-core==2.20.1
typing-extensions>=4.0.0

# === AI/ML Core Dependencies (Order matters!) ===
numpy==1.26.2

# OpenAI SDK (must be before langchain)
openai==1.68.2
tiktoken>=0.5.1

# Langchain ecosystem (specific order required)
langsmith==0.0.92
langchain-core==0.1.0
langchain==0.1.0
langchain-community==0.0.10
langchain-openai==0.0.5

# ChromaDB (for vector storage)
chromadb==0.4.22
overrides>=7.3.1

# CrewAI (after all langchain dependencies)
crewai==0.159.0
crewai-tools>=0.0.15

# === Web Research ===
firecrawl-py==0.0.16

# === Email and HTML Processing ===
email-validator==2.1.0
beautifulsoup4==4.12.2
lxml==4.9.3
html5lib==1.1

# === File Handling ===
python-multipart==0.0.6
python-magic==0.4.27

# === Environment and Configuration ===
python-dotenv==1.0.0

# === Logging and Monitoring ===
structlog==23.2.0

# === Security ===
python-jose[cryptography]==3.3.0
cryptography>=41.0.0
passlib==1.7.4

# === Testing (optional for production) ===
# pytest==7.4.3
# pytest-asyncio==0.21.1

# === Additional CrewAI Dependencies ===
# These are installed automatically but listing for clarity
instructor>=1.0.0
regex>=2023.12.25
"""
        
        optimized_path = self.base_dir / "requirements_optimized.txt"
        with open(optimized_path, 'w') as f:
            f.write(optimized_requirements)
        
        print(f"✓ Created: {optimized_path}")
        return optimized_path
    
    def create_minimal_requirements(self):
        """Create minimal requirements for testing"""
        
        print("Creating minimal requirements file...")
        
        minimal_requirements = """# Minimal Requirements for Testing
# Use this to verify basic functionality

# Core only
fastapi==0.104.1
uvicorn[standard]==0.24.0
gunicorn==21.2.0
pydantic==2.8.2
python-dotenv==1.0.0
requests==2.31.0

# Azure
azure-storage-blob==12.19.0

# Database
psycopg2-binary==2.9.9
asyncpg==0.29.0

# Basic AI
openai==1.68.2
"""
        
        minimal_path = self.base_dir / "requirements_minimal.txt"
        with open(minimal_path, 'w') as f:
            f.write(minimal_requirements)
        
        print(f"✓ Created: {minimal_path}")
        return minimal_path
    
    def create_requirements_lock(self):
        """Create a locked requirements file with exact versions"""
        
        print("Creating requirements lock file...")
        
        try:
            # Try to generate from current environment
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                lock_path = self.base_dir / "requirements.lock"
                with open(lock_path, 'w') as f:
                    f.write("# Auto-generated requirements lock file\n")
                    f.write("# Generated from current environment\n\n")
                    f.write(result.stdout)
                
                print(f"✓ Created: {lock_path}")
                return lock_path
            else:
                print("⚠ Could not generate lock file from environment")
                return None
                
        except Exception as e:
            print(f"⚠ Error creating lock file: {e}")
            return None
    
    def create_dependency_check_script(self):
        """Create script to check for dependency conflicts"""
        
        print("Creating dependency check script...")
        
        check_script = '''#!/usr/bin/env python3
"""
Check for dependency conflicts in requirements
"""

import subprocess
import sys
import re

def check_conflicts(requirements_file):
    """Check for conflicts in requirements file"""
    
    print(f"Checking {requirements_file} for conflicts...")
    
    # Dry run pip install to check for conflicts
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "-r", requirements_file],
        capture_output=True,
        text=True
    )
    
    # Look for conflict messages
    conflicts = []
    for line in result.stderr.split('\\n'):
        if 'conflict' in line.lower() or 'incompatible' in line.lower():
            conflicts.append(line)
    
    if conflicts:
        print("⚠ Potential conflicts detected:")
        for conflict in conflicts:
            print(f"  - {conflict}")
        return False
    else:
        print("✓ No conflicts detected")
        return True

def check_azure_compatibility():
    """Check compatibility with Azure App Service"""
    
    print("\\nChecking Azure App Service compatibility...")
    
    # Packages known to have issues on Azure
    problematic = {
        "tensorflow": "May require additional system libraries",
        "torch": "Large size may exceed deployment limits",
        "opencv-python": "Requires additional system dependencies",
    }
    
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.read().lower()
        
        issues = []
        for package, issue in problematic.items():
            if package in requirements:
                issues.append(f"{package}: {issue}")
        
        if issues:
            print("⚠ Potential Azure compatibility issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✓ No known Azure compatibility issues")
            
    except FileNotFoundError:
        print("⚠ requirements.txt not found")

if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    files_to_check = [
        "requirements.txt",
        "requirements_optimized.txt",
        "requirements_minimal.txt"
    ]
    
    for req_file in files_to_check:
        if os.path.exists(req_file):
            check_conflicts(req_file)
    
    check_azure_compatibility()
'''
        
        check_path = self.base_dir / "check_dependencies.py"
        with open(check_path, 'w') as f:
            f.write(check_script)
        
        check_path.chmod(0o755)
        print(f"✓ Created: {check_path}")
        return check_path
    
    def run(self):
        """Run the optimization process"""
        
        print("\n" + "="*60)
        print("Requirements Optimization for Azure App Service")
        print("="*60 + "\n")
        
        # Create optimized files
        self.create_optimized_requirements()
        self.create_minimal_requirements()
        self.create_requirements_lock()
        self.create_dependency_check_script()
        
        print("\n" + "="*60)
        print("✓ Requirements optimization complete!")
        print("="*60)
        print("\nCreated files:")
        print("  - requirements_optimized.txt (recommended for production)")
        print("  - requirements_minimal.txt (for testing)")
        print("  - requirements.lock (exact versions if available)")
        print("  - check_dependencies.py (conflict checker)")
        print("\nNext steps:")
        print("1. Test with: pip install -r requirements_optimized.txt")
        print("2. Check conflicts: python check_dependencies.py")
        print("3. Deploy with: bash deploy_to_azure.sh")

if __name__ == "__main__":
    optimizer = RequirementsOptimizer()
    optimizer.run()