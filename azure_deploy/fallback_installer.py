#!/usr/bin/env python3
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
    print(f"\nInstalling {package}...")
    if install_with_fallback(package):
        print(f"✓ {package} installed")
    else:
        print(f"✗ Failed to install {package}")

print("\nFallback installation complete")
