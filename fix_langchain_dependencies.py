#!/usr/bin/env python3
"""
Quick fix script to update requirements.txt with compatible langchain versions
"""

import os
import shutil
from datetime import datetime

def fix_requirements():
    """Update requirements.txt with compatible langchain versions"""
    
    print("="*60)
    print("  Fixing LangChain Dependencies")
    print("="*60)
    
    requirements_file = "requirements.txt"
    backup_file = f"requirements.txt.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if not os.path.exists(requirements_file):
        print(f"❌ {requirements_file} not found!")
        return False
    
    # Create backup
    print(f"\n📁 Creating backup: {backup_file}")
    shutil.copy2(requirements_file, backup_file)
    
    # Read current requirements
    with open(requirements_file, 'r') as f:
        lines = f.readlines()
    
    # Define replacements
    replacements = {
        "langchain==0.1.0": "langchain==0.1.20",
        "langchain-core==0.1.0": "langchain-core==0.1.52",
        "langchain-community==0.0.10": "langchain-community==0.0.38",
        "langchain-openai==0.0.5": "langchain-openai==0.1.7"
    }
    
    # Apply replacements
    updated_lines = []
    changes_made = []
    
    for line in lines:
        original_line = line
        for old_version, new_version in replacements.items():
            if old_version in line:
                line = line.replace(old_version, new_version)
                changes_made.append(f"  {old_version} → {new_version}")
                break
        updated_lines.append(line)
    
    # Write updated requirements
    with open(requirements_file, 'w') as f:
        f.writelines(updated_lines)
    
    print("\n✅ Changes applied:")
    for change in changes_made:
        print(change)
    
    print(f"\n📝 Backup saved as: {backup_file}")
    print(f"✅ {requirements_file} updated successfully!")
    
    # Create verification script
    verify_script = """#!/bin/bash
# Verify the fix by installing in a fresh venv

echo "Creating test virtual environment..."
python -m venv test_fix_venv

echo "Activating virtual environment..."
source test_fix_venv/bin/activate 2>/dev/null || test_fix_venv\\Scripts\\activate

echo "Installing updated requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Testing imports..."
python -c "
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
print('✅ All imports successful!')
"

echo "Cleaning up..."
deactivate 2>/dev/null || true
rm -rf test_fix_venv

echo "✅ Verification complete!"
"""
    
    with open("verify_fix.sh", 'w') as f:
        f.write(verify_script)
    
    os.chmod("verify_fix.sh", 0o755)
    
    print("\n🔧 To verify the fix, run:")
    print("  ./verify_fix.sh")
    
    print("\n⚠️  To restore the original requirements.txt:")
    print(f"  cp {backup_file} requirements.txt")
    
    return True

if __name__ == "__main__":
    success = fix_requirements()
    
    if success:
        print("\n" + "="*60)
        print("  Next Steps:")
        print("="*60)
        print("1. Run ./verify_fix.sh to test the changes")
        print("2. If successful, commit the updated requirements.txt")
        print("3. Deploy to Azure App Service")
        print("\nIf issues persist, run:")
        print("  python test_dependency_validation.py")
        print("  python test_langchain_compatibility.py")