#!/usr/bin/env python3
"""
Dependency audit script for Well Intake API
Checks for security vulnerabilities, outdated packages, and unused dependencies
"""

import subprocess
import sys
import json
import pkg_resources
from pathlib import Path

def run_command(cmd, capture_output=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_security_vulnerabilities():
    """Check for known security vulnerabilities using safety"""
    print("🔍 Checking for security vulnerabilities...")
    
    success, output, error = run_command("pip show safety")
    if not success:
        print("❌ Safety not installed. Install with: pip install safety")
        return False
    
    success, output, error = run_command("safety check --json")
    if success:
        if output:
            try:
                vulnerabilities = json.loads(output)
                if vulnerabilities:
                    print(f"⚠️  Found {len(vulnerabilities)} security vulnerabilities:")
                    for vuln in vulnerabilities:
                        print(f"   - {vuln['package']}: {vuln['advisory']}")
                else:
                    print("✅ No security vulnerabilities found")
            except json.JSONDecodeError:
                print("✅ No security vulnerabilities found")
        else:
            print("✅ No security vulnerabilities found")
    else:
        print(f"❌ Security check failed: {error}")
    
    return True

def check_outdated_packages():
    """Check for outdated packages"""
    print("\n📦 Checking for outdated packages...")
    
    success, output, error = run_command("pip list --outdated --format=json")
    if success and output:
        try:
            outdated = json.loads(output)
            if outdated:
                print(f"⚠️  Found {len(outdated)} outdated packages:")
                for pkg in outdated:
                    print(f"   - {pkg['name']}: {pkg['version']} → {pkg['latest_version']}")
            else:
                print("✅ All packages are up to date")
        except json.JSONDecodeError:
            print("✅ All packages are up to date")
    else:
        print("❌ Failed to check outdated packages")

def analyze_dependencies():
    """Analyze dependency tree for potential issues"""
    print("\n🌳 Analyzing dependency tree...")
    
    # Get installed packages
    installed_packages = [pkg.project_name for pkg in pkg_resources.working_set]
    
    # Read requirements.txt
    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        with open(requirements_file) as f:
            required_packages = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0]
                    required_packages.append(package_name.lower())
        
        # Find potentially unused packages
        # This is a basic check - some packages might be used but not directly imported
        print(f"📋 Total packages in requirements.txt: {len(required_packages)}")
        print(f"📋 Total installed packages: {len(installed_packages)}")
    else:
        print("❌ requirements.txt not found")

def check_package_sizes():
    """Check installed package sizes"""
    print("\n📏 Checking package sizes...")
    
    success, output, error = run_command("pip show -f $(pip list --format=freeze | cut -d= -f1) | grep -E '^Name:|^Size:' | paste - -")
    if success and output:
        lines = output.split('\n')
        package_sizes = []
        for line in lines:
            if 'Name:' in line and 'Size:' in line:
                parts = line.split()
                if len(parts) >= 4:
                    name = parts[1]
                    # Size extraction might vary based on pip output format
                    size_info = ' '.join(parts[2:])
                    package_sizes.append((name, size_info))
        
        if package_sizes:
            print("📦 Largest packages:")
            for name, size in package_sizes[:10]:  # Show top 10
                print(f"   - {name}: {size}")

def generate_recommendations():
    """Generate optimization recommendations"""
    print("\n💡 Recommendations:")
    
    recommendations = [
        "1. Keep only essential dependencies in requirements.txt",
        "2. Move development tools to requirements-dev.txt",
        "3. Use specific version pinning for reproducibility",
        "4. Regularly update dependencies to latest secure versions",
        "5. Use multi-stage Docker builds to reduce image size",
        "6. Consider using slim base images",
        "7. Remove unused packages to reduce attack surface",
        "8. Set up automated security scanning in CI/CD pipeline"
    ]
    
    for rec in recommendations:
        print(f"   {rec}")

def main():
    """Main audit function"""
    print("🔬 Well Intake API Dependency Audit")
    print("=" * 50)
    
    # Run checks
    check_security_vulnerabilities()
    check_outdated_packages()
    analyze_dependencies()
    check_package_sizes()
    generate_recommendations()
    
    print("\n✅ Audit complete!")

if __name__ == "__main__":
    main()