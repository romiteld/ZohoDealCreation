#!/usr/bin/env python3
"""
Azure App Service Deployment Troubleshooting Tool
Diagnoses and fixes common deployment issues
"""

import subprocess
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

class AzureTroubleshooter:
    def __init__(self):
        self.resource_group = "TheWell-App-East"
        self.app_name = "well-intake-api"
        self.issues_found = []
        self.fixes_applied = []
        
    def run_command(self, cmd, capture=True):
        """Run a shell command and return output"""
        try:
            if capture:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.stdout.strip(), result.stderr.strip(), result.returncode
            else:
                subprocess.run(cmd, shell=True)
                return None, None, 0
        except Exception as e:
            return None, str(e), 1
    
    def check_azure_cli(self):
        """Check if Azure CLI is installed and logged in"""
        print("🔍 Checking Azure CLI...")
        
        # Check if az is installed
        stdout, stderr, code = self.run_command("az --version")
        if code != 0:
            self.issues_found.append("Azure CLI not installed")
            print("  ❌ Azure CLI not found")
            return False
        
        print("  ✅ Azure CLI installed")
        
        # Check if logged in
        stdout, stderr, code = self.run_command("az account show")
        if code != 0:
            self.issues_found.append("Not logged in to Azure")
            print("  ❌ Not logged in to Azure")
            print("  💡 Run: az login")
            return False
        
        account_info = json.loads(stdout)
        print(f"  ✅ Logged in as: {account_info.get('user', {}).get('name', 'Unknown')}")
        return True
    
    def check_app_status(self):
        """Check the status of the Azure Web App"""
        print("\n🔍 Checking App Service status...")
        
        cmd = f"az webapp show --resource-group {self.resource_group} --name {self.app_name} --query state -o tsv"
        stdout, stderr, code = self.run_command(cmd)
        
        if code != 0:
            self.issues_found.append("Cannot access Web App")
            print(f"  ❌ Cannot access {self.app_name}")
            return False
        
        state = stdout.strip()
        if state == "Running":
            print(f"  ✅ App is running")
        else:
            self.issues_found.append(f"App state is {state}, not Running")
            print(f"  ⚠️  App state: {state}")
        
        return state == "Running"
    
    def check_app_settings(self):
        """Check critical app settings"""
        print("\n🔍 Checking app settings...")
        
        critical_settings = [
            "WEBSITES_PORT",
            "SCM_DO_BUILD_DURING_DEPLOYMENT",
            "PYTHON_ENABLE_WORKER_EXTENSIONS"
        ]
        
        cmd = f"az webapp config appsettings list --resource-group {self.resource_group} --name {self.app_name}"
        stdout, stderr, code = self.run_command(cmd)
        
        if code != 0:
            self.issues_found.append("Cannot retrieve app settings")
            print("  ❌ Cannot retrieve settings")
            return False
        
        settings = json.loads(stdout)
        settings_dict = {s['name']: s['value'] for s in settings}
        
        missing = []
        for setting in critical_settings:
            if setting not in settings_dict:
                missing.append(setting)
                print(f"  ❌ Missing: {setting}")
            else:
                print(f"  ✅ {setting} = {settings_dict[setting]}")
        
        if missing:
            self.issues_found.append(f"Missing settings: {', '.join(missing)}")
            return False
        
        return True
    
    def check_runtime(self):
        """Check Python runtime configuration"""
        print("\n🔍 Checking Python runtime...")
        
        cmd = f"az webapp config show --resource-group {self.resource_group} --name {self.app_name} --query linuxFxVersion -o tsv"
        stdout, stderr, code = self.run_command(cmd)
        
        if code != 0:
            print("  ❌ Cannot check runtime")
            return False
        
        runtime = stdout.strip()
        if "PYTHON|3.12" in runtime:
            print(f"  ✅ Python 3.12 runtime configured")
        else:
            self.issues_found.append(f"Wrong runtime: {runtime}")
            print(f"  ⚠️  Runtime: {runtime}")
            print(f"  💡 Expected: PYTHON|3.12")
        
        return "PYTHON|3.12" in runtime
    
    def check_deployment_logs(self):
        """Check recent deployment logs for errors"""
        print("\n🔍 Checking deployment logs...")
        
        cmd = f"az webapp log deployment show --resource-group {self.resource_group} --name {self.app_name} --deployment-id latest"
        stdout, stderr, code = self.run_command(cmd)
        
        if code != 0:
            print("  ⚠️  No recent deployment logs available")
            return True
        
        if stdout:
            logs = json.loads(stdout)
            if "error" in stdout.lower() or "failed" in stdout.lower():
                self.issues_found.append("Errors found in deployment logs")
                print("  ❌ Errors found in deployment")
                return False
            else:
                print("  ✅ No errors in recent deployment")
        
        return True
    
    def check_application_logs(self):
        """Get recent application logs"""
        print("\n🔍 Fetching recent application logs...")
        
        cmd = f"az webapp log tail --resource-group {self.resource_group} --name {self.app_name} --timeout 10"
        print("  📝 Getting last 10 seconds of logs...")
        stdout, stderr, code = self.run_command(cmd)
        
        if stdout:
            # Look for common error patterns
            error_patterns = [
                "ModuleNotFoundError",
                "ImportError",
                "SyntaxError",
                "Connection refused",
                "ECONNREFUSED",
                "Failed to start"
            ]
            
            errors_detected = []
            for pattern in error_patterns:
                if pattern in stdout:
                    errors_detected.append(pattern)
            
            if errors_detected:
                self.issues_found.append(f"Application errors: {', '.join(errors_detected)}")
                print(f"  ❌ Errors detected: {', '.join(errors_detected)}")
                return False
            else:
                print("  ✅ No critical errors in recent logs")
        else:
            print("  ⚠️  No recent logs available")
        
        return True
    
    def test_endpoints(self):
        """Test application endpoints"""
        print("\n🔍 Testing application endpoints...")
        
        base_url = f"https://{self.app_name}.azurewebsites.net"
        endpoints = [
            ("/health", 200),
            ("/docs", 200),
            ("/openapi.json", 200)
        ]
        
        import requests
        
        all_ok = True
        for endpoint, expected_status in endpoints:
            url = base_url + endpoint
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == expected_status:
                    print(f"  ✅ {endpoint}: {response.status_code}")
                else:
                    print(f"  ❌ {endpoint}: {response.status_code} (expected {expected_status})")
                    self.issues_found.append(f"{endpoint} returned {response.status_code}")
                    all_ok = False
            except requests.exceptions.Timeout:
                print(f"  ❌ {endpoint}: Timeout")
                self.issues_found.append(f"{endpoint} timeout")
                all_ok = False
            except Exception as e:
                print(f"  ❌ {endpoint}: {str(e)}")
                self.issues_found.append(f"{endpoint} error: {str(e)}")
                all_ok = False
        
        return all_ok
    
    def apply_fixes(self):
        """Apply fixes for common issues"""
        print("\n🔧 Applying fixes...")
        
        fixes_to_apply = []
        
        # Fix missing app settings
        if any("Missing settings" in issue for issue in self.issues_found):
            fixes_to_apply.append({
                "name": "Configure app settings",
                "command": f"""az webapp config appsettings set \
                    --resource-group {self.resource_group} \
                    --name {self.app_name} \
                    --settings \
                    WEBSITES_PORT=8000 \
                    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
                    PYTHON_ENABLE_WORKER_EXTENSIONS=1 \
                    WEBSITE_RUN_FROM_PACKAGE=0"""
            })
        
        # Fix runtime if needed
        if any("Wrong runtime" in issue for issue in self.issues_found):
            fixes_to_apply.append({
                "name": "Set Python 3.12 runtime",
                "command": f"""az webapp config set \
                    --resource-group {self.resource_group} \
                    --name {self.app_name} \
                    --linux-fx-version 'PYTHON|3.12'"""
            })
        
        # Apply fixes
        for fix in fixes_to_apply:
            print(f"\n  🔧 {fix['name']}...")
            stdout, stderr, code = self.run_command(fix['command'])
            if code == 0:
                print(f"  ✅ {fix['name']} completed")
                self.fixes_applied.append(fix['name'])
            else:
                print(f"  ❌ Failed to {fix['name']}")
        
        # Restart if fixes were applied
        if self.fixes_applied:
            print("\n  🔄 Restarting application...")
            cmd = f"az webapp restart --resource-group {self.resource_group} --name {self.app_name}"
            stdout, stderr, code = self.run_command(cmd)
            if code == 0:
                print("  ✅ Application restarted")
            else:
                print("  ❌ Failed to restart")
    
    def generate_report(self):
        """Generate troubleshooting report"""
        print("\n" + "="*60)
        print("📋 TROUBLESHOOTING REPORT")
        print("="*60)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n📅 Generated: {timestamp}")
        print(f"🎯 App: {self.app_name}")
        print(f"📦 Resource Group: {self.resource_group}")
        
        if self.issues_found:
            print(f"\n❌ Issues Found ({len(self.issues_found)}):")
            for issue in self.issues_found:
                print(f"  • {issue}")
        else:
            print("\n✅ No issues found!")
        
        if self.fixes_applied:
            print(f"\n🔧 Fixes Applied ({len(self.fixes_applied)}):")
            for fix in self.fixes_applied:
                print(f"  • {fix}")
        
        print("\n💡 Recommended Actions:")
        
        if self.issues_found:
            if any("ModuleNotFoundError" in issue or "ImportError" in issue for issue in self.issues_found):
                print("  1. Redeploy with staged requirements:")
                print("     python azure_deploy_setup.py")
                print("     bash deploy_to_azure.sh")
            
            if any("timeout" in issue.lower() for issue in self.issues_found):
                print("  2. Increase startup timeout:")
                print(f"     az webapp config set --resource-group {self.resource_group} --name {self.app_name} --startup-file 'timeout 900 bash startup.sh'")
            
            if any("Connection refused" in issue for issue in self.issues_found):
                print("  3. Check environment variables:")
                print(f"     az webapp config appsettings list --resource-group {self.resource_group} --name {self.app_name}")
        else:
            print("  • Application appears to be running correctly")
            print("  • Monitor logs for any runtime issues:")
            print(f"    az webapp log tail --resource-group {self.resource_group} --name {self.app_name}")
        
        print("\n📚 Useful Commands:")
        print(f"  • SSH into container: az webapp ssh --resource-group {self.resource_group} --name {self.app_name}")
        print(f"  • Download logs: az webapp log download --resource-group {self.resource_group} --name {self.app_name} --log-file logs.zip")
        print(f"  • View metrics: az monitor metrics list --resource {self.app_name} --resource-group {self.resource_group} --resource-type Microsoft.Web/sites")
        
        # Save report to file
        report_path = Path("troubleshooting_report.txt")
        with open(report_path, 'w') as f:
            f.write(f"Azure App Service Troubleshooting Report\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"App: {self.app_name}\n")
            f.write(f"Resource Group: {self.resource_group}\n\n")
            
            if self.issues_found:
                f.write(f"Issues Found:\n")
                for issue in self.issues_found:
                    f.write(f"  - {issue}\n")
            else:
                f.write("No issues found.\n")
            
            if self.fixes_applied:
                f.write(f"\nFixes Applied:\n")
                for fix in self.fixes_applied:
                    f.write(f"  - {fix}\n")
        
        print(f"\n📄 Report saved to: {report_path}")
    
    def run(self):
        """Run the complete troubleshooting process"""
        print("\n" + "="*60)
        print("🔍 Azure App Service Troubleshooting Tool")
        print("="*60)
        
        # Run checks
        if not self.check_azure_cli():
            print("\n❌ Cannot proceed without Azure CLI access")
            return False
        
        self.check_app_status()
        self.check_app_settings()
        self.check_runtime()
        self.check_deployment_logs()
        self.check_application_logs()
        
        # Test endpoints if app is running
        if not any("Cannot access Web App" in issue for issue in self.issues_found):
            self.test_endpoints()
        
        # Apply fixes if needed
        if self.issues_found:
            print("\n" + "="*60)
            response = input("🔧 Would you like to apply automatic fixes? (y/n): ")
            if response.lower() == 'y':
                self.apply_fixes()
        
        # Generate report
        self.generate_report()
        
        return len(self.issues_found) == 0

if __name__ == "__main__":
    troubleshooter = AzureTroubleshooter()
    success = troubleshooter.run()
    sys.exit(0 if success else 1)