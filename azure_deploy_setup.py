#!/usr/bin/env python3
"""
Azure App Service Deployment Setup Script
Handles dependency installation issues and creates optimized deployment package
"""

import os
import sys
import subprocess
import json
import shutil
import zipfile
from pathlib import Path

class AzureDeploymentPreparer:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.deploy_dir = self.base_dir / "azure_deploy"
        self.wheels_dir = self.deploy_dir / "wheels"
        self.scripts_dir = self.deploy_dir / "scripts"
        
    def create_directory_structure(self):
        """Create deployment directory structure"""
        print("Creating deployment directory structure...")
        
        # Clean and recreate deploy directory
        if self.deploy_dir.exists():
            shutil.rmtree(self.deploy_dir)
        
        self.deploy_dir.mkdir()
        self.wheels_dir.mkdir()
        self.scripts_dir.mkdir()
        
        # Copy application files
        for item in ['app', 'addin', 'requirements.txt', '.env.sample']:
            src = self.base_dir / item
            if src.exists():
                if src.is_dir():
                    shutil.copytree(src, self.deploy_dir / item)
                else:
                    shutil.copy2(src, self.deploy_dir / item)
        
        print("✓ Directory structure created")
    
    def create_staged_requirements(self):
        """Split requirements into stages for better installation success"""
        print("Creating staged requirements files...")
        
        # Stage 1: Core dependencies
        stage1_deps = [
            "setuptools==69.0.2",
            "wheel",
            "pip>=23.0",
            "gunicorn==21.2.0",
            "uvicorn[standard]==0.24.0",
            "fastapi==0.104.1",
            "pydantic==2.8.2",
            "python-dotenv==1.0.0",
            "pysqlite3-binary"
        ]
        
        # Stage 2: Database and Azure
        stage2_deps = [
            "azure-storage-blob==12.19.0",
            "asyncpg==0.29.0",
            "psycopg2-binary==2.9.9",
            "pgvector==0.2.4",
            "requests==2.31.0",
            "httpx==0.27.2",
            "tenacity==8.2.3"
        ]
        
        # Stage 3: AI/ML dependencies with correct versions
        stage3_deps = [
            "numpy==1.26.2",
            "openai==1.68.2",
            "langchain-core==0.1.0",
            "langchain==0.1.0",
            "langchain-community==0.0.10",
            "langchain-openai==0.0.5"
        ]
        
        # Stage 4: CrewAI and remaining dependencies
        stage4_deps = [
            "crewai==0.159.0",
            "firecrawl-py==0.0.16",
            "flask==3.0.0",
            "email-validator==2.1.0",
            "beautifulsoup4==4.12.2",
            "lxml==4.9.3",
            "python-multipart==0.0.6",
            "structlog==23.2.0",
            "python-jose[cryptography]==3.3.0"
        ]
        
        # Write staged requirement files
        for i, deps in enumerate([stage1_deps, stage2_deps, stage3_deps, stage4_deps], 1):
            req_file = self.deploy_dir / f"requirements_stage{i}.txt"
            with open(req_file, 'w') as f:
                f.write('\n'.join(deps))
        
        print("✓ Staged requirements created")
    
    def create_deployment_script(self):
        """Create Azure deployment script"""
        print("Creating deployment script...")
        
        deployment_script = '''#!/bin/bash
# Azure App Service Deployment Script
# Handles staged dependency installation

echo "========================================="
echo "Azure App Service Deployment Starting..."
echo "========================================="

# Set Python path
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Function to install requirements with retry
install_requirements() {
    local req_file=$1
    local max_attempts=3
    local attempt=1
    
    echo "Installing from $req_file..."
    
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt of $max_attempts..."
        
        if pip install --no-cache-dir --upgrade -r "$req_file"; then
            echo "✓ Successfully installed $req_file"
            return 0
        else
            echo "✗ Failed attempt $attempt"
            attempt=$((attempt + 1))
            
            if [ $attempt -le $max_attempts ]; then
                echo "Retrying in 5 seconds..."
                sleep 5
            fi
        fi
    done
    
    echo "ERROR: Failed to install $req_file after $max_attempts attempts"
    return 1
}

# Upgrade pip first
echo "Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel

# Install SQLite binary for ChromaDB compatibility
echo "Installing SQLite binary..."
pip install pysqlite3-binary

# Override sqlite3 with pysqlite3
echo "Setting up SQLite override..."
cat > /home/site/wwwroot/sqlite_override.py << 'EOF'
import sys
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
except ImportError:
    pass
EOF

# Stage 1: Core dependencies
echo ""
echo "Stage 1: Installing core dependencies..."
install_requirements "requirements_stage1.txt"

# Stage 2: Database and Azure
echo ""
echo "Stage 2: Installing database and Azure dependencies..."
install_requirements "requirements_stage2.txt"

# Stage 3: AI/ML dependencies
echo ""
echo "Stage 3: Installing AI/ML dependencies..."
install_requirements "requirements_stage3.txt"

# Stage 4: CrewAI and remaining
echo ""
echo "Stage 4: Installing CrewAI and remaining dependencies..."
install_requirements "requirements_stage4.txt"

# Verify installation
echo ""
echo "Verifying installation..."
python verify_imports.py

if [ $? -eq 0 ]; then
    echo "✓ All dependencies installed successfully"
else
    echo "✗ Some dependencies failed verification"
    echo "Attempting fallback installation..."
    pip install --no-cache-dir -r requirements.txt
fi

echo ""
echo "========================================="
echo "Deployment Script Completed"
echo "========================================="
'''
        
        script_path = self.scripts_dir / "deploy.sh"
        with open(script_path, 'w') as f:
            f.write(deployment_script)
        
        # Make script executable
        script_path.chmod(0o755)
        
        print("✓ Deployment script created")
    
    def create_startup_command(self):
        """Create startup command for Azure App Service"""
        print("Creating startup command...")
        
        startup_script = '''#!/bin/bash
# Azure App Service Startup Script

# Set environment
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Import SQLite override
export PYTHONPATH="/home/site/wwwroot:${PYTHONPATH}"

# Run deployment script if needed
if [ ! -f "/home/.deployment_done" ]; then
    echo "Running deployment script..."
    bash /home/site/wwwroot/scripts/deploy.sh
    touch /home/.deployment_done
fi

# Start the application with Gunicorn and Uvicorn workers
echo "Starting application..."
exec gunicorn \
    --bind=0.0.0.0:8000 \
    --timeout 600 \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app.main:app
'''
        
        startup_path = self.deploy_dir / "startup.sh"
        with open(startup_path, 'w') as f:
            f.write(startup_script)
        
        startup_path.chmod(0o755)
        
        print("✓ Startup command created")
    
    def create_verification_script(self):
        """Create import verification script"""
        print("Creating verification script...")
        
        verify_script = '''#!/usr/bin/env python3
"""
Verify all required imports work correctly
"""

import sys
import traceback

# Override sqlite3 with pysqlite3 first
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
    print("✓ SQLite override successful")
except ImportError:
    print("⚠ SQLite override not available")

def verify_imports():
    """Test all critical imports"""
    
    imports_to_test = [
        # Core web framework
        ("fastapi", "FastAPI"),
        ("uvicorn", None),
        ("gunicorn", None),
        
        # Azure
        ("azure.storage.blob", "BlobServiceClient"),
        
        # Database
        ("asyncpg", None),
        ("psycopg2", None),
        ("pgvector", None),
        
        # AI/ML
        ("openai", None),
        ("langchain", None),
        ("langchain.chat_models", None),
        ("langchain_openai", "ChatOpenAI"),
        ("crewai", "Crew"),
        
        # Utilities
        ("pydantic", None),
        ("dotenv", "load_dotenv"),
        ("requests", None),
        ("tenacity", None),
        
        # Web research
        ("firecrawl", None),
    ]
    
    failed_imports = []
    
    for module_name, attr in imports_to_test:
        try:
            if '.' in module_name:
                parts = module_name.split('.')
                module = __import__(module_name, fromlist=[parts[-1]])
            else:
                module = __import__(module_name)
            
            if attr:
                getattr(module, attr)
            
            print(f"✓ {module_name}")
        except ImportError as e:
            failed_imports.append((module_name, str(e)))
            print(f"✗ {module_name}: {e}")
        except AttributeError as e:
            print(f"⚠ {module_name}: Module imported but {attr} not found")
        except Exception as e:
            failed_imports.append((module_name, str(e)))
            print(f"✗ {module_name}: Unexpected error - {e}")
    
    # Test CrewAI specifically
    try:
        from crewai import Crew, Agent, Task
        print("✓ CrewAI components available")
    except ImportError as e:
        print(f"✗ CrewAI components: {e}")
        failed_imports.append(("crewai components", str(e)))
    
    # Summary
    print("\\n" + "="*50)
    if failed_imports:
        print(f"Failed imports: {len(failed_imports)}")
        for module, error in failed_imports:
            print(f"  - {module}")
        return False
    else:
        print("All imports successful!")
        return True

if __name__ == "__main__":
    success = verify_imports()
    sys.exit(0 if success else 1)
'''
        
        verify_path = self.deploy_dir / "verify_imports.py"
        with open(verify_path, 'w') as f:
            f.write(verify_script)
        
        print("✓ Verification script created")
    
    def create_app_service_config(self):
        """Create Azure App Service configuration"""
        print("Creating App Service configuration...")
        
        # Create web.config for IIS (Azure App Service on Windows)
        web_config = '''<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" 
           path="*" 
           verb="*" 
           modules="FastCgiModule" 
           scriptProcessor="D:\\home\\python364x64\\python.exe|D:\\home\\python364x64\\wfastcgi.py"
           resourceType="Unspecified" 
           requireAccess="Script" />
    </handlers>
    <rewrite>
      <rules>
        <rule name="Configure Python" stopProcessing="true">
          <match url="(.*)" ignoreCase="false" />
          <action type="Rewrite" url="handler.fcgi/{R:1}" appendQueryString="true" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>'''
        
        with open(self.deploy_dir / "web.config", 'w') as f:
            f.write(web_config)
        
        # Create .deployment file
        deployment_config = '''[config]
command = bash scripts/deploy.sh
'''
        
        with open(self.deploy_dir / ".deployment", 'w') as f:
            f.write(deployment_config)
        
        # Create runtime.txt
        with open(self.deploy_dir / "runtime.txt", 'w') as f:
            f.write("python-3.12\n")
        
        print("✓ App Service configuration created")
    
    def create_fallback_installer(self):
        """Create fallback installer for problematic packages"""
        print("Creating fallback installer...")
        
        fallback_script = '''#!/usr/bin/env python3
"""
Fallback installer for problematic packages
"""

import subprocess
import sys
import os

def install_with_fallback(package_spec):
    """Try multiple installation methods"""
    
    # Method 1: Standard pip install
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec])
        return True
    except:
        pass
    
    # Method 2: Install without dependencies first
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-deps", package_spec])
        return True
    except:
        pass
    
    # Method 3: Install from wheel if available
    package_name = package_spec.split("==")[0]
    wheel_path = f"wheels/{package_name}*.whl"
    
    import glob
    wheels = glob.glob(wheel_path)
    if wheels:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", wheels[0]])
            return True
        except:
            pass
    
    return False

# Problematic packages that might need special handling
problematic_packages = [
    "crewai==0.159.0",
    "langchain==0.1.0",
    "langchain-openai==0.0.5",
    "pgvector==0.2.4"
]

print("Running fallback installer for problematic packages...")

for package in problematic_packages:
    print(f"\\nInstalling {package}...")
    if install_with_fallback(package):
        print(f"✓ {package} installed")
    else:
        print(f"✗ Failed to install {package}")

print("\\nFallback installation complete")
'''
        
        with open(self.deploy_dir / "fallback_installer.py", 'w') as f:
            f.write(fallback_script)
        
        print("✓ Fallback installer created")
    
    def download_wheels(self):
        """Download pre-built wheels for problematic packages"""
        print("Downloading pre-built wheels...")
        
        # Create a script to download wheels
        download_script = '''#!/bin/bash
# Download pre-built wheels for faster installation

cd wheels

# Download wheels for critical packages
pip download --only-binary :all: --platform linux_x86_64 --python-version 312 \
    numpy==1.26.2 \
    psycopg2-binary==2.9.9 \
    lxml==4.9.3 \
    2>/dev/null || true

echo "✓ Wheels downloaded (if available)"
'''
        
        script_path = self.scripts_dir / "download_wheels.sh"
        with open(script_path, 'w') as f:
            f.write(download_script)
        
        script_path.chmod(0o755)
        
        # Try to download wheels locally
        try:
            subprocess.run(["bash", str(script_path)], cwd=self.deploy_dir, check=False)
        except:
            print("⚠ Could not download wheels locally (not critical)")
        
        print("✓ Wheel download script created")
    
    def create_deployment_package(self):
        """Create the final deployment ZIP package"""
        print("Creating deployment package...")
        
        zip_path = self.base_dir / "deploy.zip"
        
        # Remove old zip if exists
        if zip_path.exists():
            zip_path.unlink()
        
        # Create ZIP file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from deploy directory
            for root, dirs, files in os.walk(self.deploy_dir):
                # Skip __pycache__ and other unnecessary directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'zoho']]
                
                for file in files:
                    # Skip .pyc and other unnecessary files
                    if file.endswith(('.pyc', '.pyo', '.pyd', '.so', '.log')):
                        continue
                    
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.deploy_dir)
                    zipf.write(file_path, arcname)
        
        # Get file size
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"✓ Deployment package created: deploy.zip ({size_mb:.2f} MB)")
        
        return zip_path
    
    def create_deployment_instructions(self):
        """Create deployment instructions"""
        print("Creating deployment instructions...")
        
        instructions = '''# Azure App Service Deployment Instructions

## Prerequisites
- Azure CLI installed and logged in
- Access to TheWell-App-East resource group
- Python 3.12 runtime selected in Azure App Service

## Deployment Steps

### 1. Deploy the Package

```bash
# Deploy using ZIP deployment
az webapp deploy \\
    --resource-group TheWell-App-East \\
    --name well-intake-api \\
    --src-path deploy.zip \\
    --type zip

# Set the startup command
az webapp config set \\
    --resource-group TheWell-App-East \\
    --name well-intake-api \\
    --startup-file "bash startup.sh"
```

### 2. Configure Environment Variables

```bash
# Set required environment variables
az webapp config appsettings set \\
    --resource-group TheWell-App-East \\
    --name well-intake-api \\
    --settings \\
    WEBSITES_PORT=8000 \\
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \\
    PYTHON_ENABLE_WORKER_EXTENSIONS=1 \\
    WEBSITE_RUN_FROM_PACKAGE=0
```

### 3. Monitor Deployment

```bash
# Watch deployment logs
az webapp log tail \\
    --resource-group TheWell-App-East \\
    --name well-intake-api

# Check deployment status
az webapp show \\
    --resource-group TheWell-App-East \\
    --name well-intake-api \\
    --query state
```

### 4. Verify Deployment

```bash
# Test health endpoint
curl https://well-intake-api.azurewebsites.net/health

# Check API documentation
curl https://well-intake-api.azurewebsites.net/docs
```

### 5. Troubleshooting

If deployment fails:

1. Check logs:
```bash
az webapp log download \\
    --resource-group TheWell-App-East \\
    --name well-intake-api \\
    --log-file app-logs.zip
```

2. SSH into the container:
```bash
az webapp ssh \\
    --resource-group TheWell-App-East \\
    --name well-intake-api
```

3. Run verification script manually:
```bash
python verify_imports.py
```

4. Try fallback installer:
```bash
python fallback_installer.py
```

## Package Contents

- **startup.sh**: Main startup script
- **scripts/deploy.sh**: Staged dependency installation
- **requirements_stage*.txt**: Staged requirement files
- **verify_imports.py**: Import verification script
- **fallback_installer.py**: Fallback for problematic packages
- **wheels/**: Pre-built wheels directory
- **app/**: Application code
- **addin/**: Outlook add-in files

## Important Notes

1. The deployment uses staged installation to avoid dependency conflicts
2. SQLite is overridden with pysqlite3-binary for ChromaDB compatibility
3. Gunicorn with Uvicorn workers handles the ASGI application
4. Deployment script runs only once (creates marker file)
5. All logs are sent to stdout for Azure monitoring

## Rollback Procedure

If you need to rollback:

```bash
# List deployment history
az webapp deployment list \\
    --resource-group TheWell-App-East \\
    --name well-intake-api

# Rollback to previous deployment
az webapp deployment rollback \\
    --resource-group TheWell-App-East \\
    --name well-intake-api
```
'''
        
        with open(self.base_dir / "AZURE_DEPLOYMENT.md", 'w') as f:
            f.write(instructions)
        
        print("✓ Deployment instructions created")
    
    def run(self):
        """Run the complete deployment preparation"""
        print("\n" + "="*60)
        print("Azure App Service Deployment Preparation")
        print("="*60 + "\n")
        
        try:
            self.create_directory_structure()
            self.create_staged_requirements()
            self.create_deployment_script()
            self.create_startup_command()
            self.create_verification_script()
            self.create_app_service_config()
            self.create_fallback_installer()
            self.download_wheels()
            zip_path = self.create_deployment_package()
            self.create_deployment_instructions()
            
            print("\n" + "="*60)
            print("✓ Deployment package created successfully!")
            print("="*60)
            print(f"\nPackage location: {zip_path}")
            print("Instructions: AZURE_DEPLOYMENT.md")
            print("\nNext steps:")
            print("1. Review AZURE_DEPLOYMENT.md")
            print("2. Run the deployment command")
            print("3. Monitor the logs")
            
            return True
            
        except Exception as e:
            print(f"\n✗ Error during preparation: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    preparer = AzureDeploymentPreparer()
    success = preparer.run()
    sys.exit(0 if success else 1)