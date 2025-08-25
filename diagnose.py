#!/usr/bin/env python3
"""
Diagnostic script for Azure App Service deployment issues
"""
import os
import sys
import subprocess
import json

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error running command: {e}"

def check_python():
    """Check Python installation"""
    print("=" * 60)
    print("PYTHON CONFIGURATION")
    print("=" * 60)
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Path: {sys.path}")
    print()

def check_environment():
    """Check environment variables"""
    print("=" * 60)
    print("ENVIRONMENT VARIABLES")
    print("=" * 60)
    important_vars = [
        'WEBSITE_INSTANCE_ID', 'PORT', 'WEBSITES_PORT', 
        'SCM_DO_BUILD_DURING_DEPLOYMENT', 'ENABLE_ORYX_BUILD',
        'PYTHON_VERSION', 'HOME', 'PATH'
    ]
    for var in important_vars:
        value = os.environ.get(var, 'NOT SET')
        print(f"{var}: {value}")
    print()

def check_files():
    """Check file structure"""
    print("=" * 60)
    print("FILE STRUCTURE")
    print("=" * 60)
    print("Current Directory:", os.getcwd())
    print("\nFiles in /home/site/wwwroot:")
    print(run_command("ls -la /home/site/wwwroot/"))
    print("\nChecking for key files:")
    key_files = ['requirements.txt', 'startup.sh', 'app/main.py', 'app.py']
    for file in key_files:
        path = f"/home/site/wwwroot/{file}"
        exists = os.path.exists(path)
        print(f"  {file}: {'✓ EXISTS' if exists else '✗ MISSING'}")
    print()

def check_packages():
    """Check installed packages"""
    print("=" * 60)
    print("INSTALLED PACKAGES")
    print("=" * 60)
    print("Checking critical packages:")
    critical_packages = [
        'fastapi', 'uvicorn', 'gunicorn', 'crewai', 
        'langchain', 'openai', 'azure-storage-blob'
    ]
    
    for package in critical_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  {package}: ✓ INSTALLED")
        except ImportError:
            print(f"  {package}: ✗ NOT INSTALLED")
    
    print("\nAll installed packages (first 30):")
    print(run_command("pip list | head -30"))
    print()

def check_app_import():
    """Try to import the main application"""
    print("=" * 60)
    print("APPLICATION IMPORT TEST")
    print("=" * 60)
    
    sys.path.insert(0, '/home/site/wwwroot')
    
    try:
        from app import main
        print("✓ Successfully imported app.main")
        print(f"  App object type: {type(main.app)}")
    except ImportError as e:
        print(f"✗ Failed to import app.main: {e}")
        
        # Try importing individual modules to identify the issue
        print("\nTrying individual imports:")
        modules = ['app', 'app.models', 'app.business_rules', 'app.integrations']
        for module in modules:
            try:
                __import__(module)
                print(f"  {module}: ✓")
            except ImportError as e:
                print(f"  {module}: ✗ ({e})")
    print()

def check_startup():
    """Check startup configuration"""
    print("=" * 60)
    print("STARTUP CONFIGURATION")
    print("=" * 60)
    
    # Check startup script
    startup_file = "/home/site/wwwroot/startup.sh"
    if os.path.exists(startup_file):
        print("✓ startup.sh exists")
        print(f"  Executable: {os.access(startup_file, os.X_OK)}")
        print("\nFirst 10 lines of startup.sh:")
        print(run_command(f"head -10 {startup_file}"))
    else:
        print("✗ startup.sh not found")
    print()

def main():
    """Run all diagnostic checks"""
    print("\n" + "=" * 60)
    print("AZURE APP SERVICE DIAGNOSTIC REPORT")
    print("=" * 60 + "\n")
    
    check_python()
    check_environment()
    check_files()
    check_packages()
    check_app_import()
    check_startup()
    
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()