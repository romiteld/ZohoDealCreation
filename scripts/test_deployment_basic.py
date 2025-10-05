#!/usr/bin/env python3
"""
Basic test script for the enhanced deployment pipeline.

This script validates the core deployment system components without
requiring complex dependencies like Redis.

Usage:
    python scripts/test_deployment_basic.py [--environment=dev]
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess
import xml.etree.ElementTree as ET

from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Color:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

class BasicDeploymentTest:
    """Basic test suite for the enhanced deployment pipeline."""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.root_path = Path(__file__).parent.parent
        self.test_results: List[Tuple[str, bool, str]] = []
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = f"{Color.GREEN}PASS{Color.NC}" if passed else f"{Color.RED}FAIL{Color.NC}"
        print(f"[{status}] {test_name}: {message}")
        self.test_results.append((test_name, passed, message))
    
    def test_core_files_exist(self) -> bool:
        """Test that all core deployment files exist."""
        logger.info("Testing core file existence...")
        
        required_files = [
            'scripts/deploy_with_cache_bust.py',
            'deploy.sh',
            'addin/manifest.xml',
            'scripts/deployment_config.json'
        ]
        
        all_exist = True
        for file_path in required_files:
            full_path = self.root_path / file_path
            exists = full_path.exists()
            self.log_test(f"File exists: {file_path}", exists, str(full_path) if exists else "Not found")
            all_exist = all_exist and exists
        
        return all_exist
    
    def test_script_permissions(self) -> bool:
        """Test that scripts are executable."""
        logger.info("Testing script permissions...")
        
        executable_files = [
            'scripts/deploy_with_cache_bust.py',
            'deploy.sh'
        ]
        
        all_executable = True
        for file_path in executable_files:
            full_path = self.root_path / file_path
            if full_path.exists():
                is_executable = os.access(full_path, os.X_OK)
                self.log_test(f"Script executable: {file_path}", is_executable)
                all_executable = all_executable and is_executable
            else:
                self.log_test(f"Script executable: {file_path}", False, "File not found")
                all_executable = False
        
        return all_executable
    
    def test_manifest_structure(self) -> bool:
        """Test manifest.xml structure and version format."""
        logger.info("Testing manifest.xml structure...")
        
        manifest_path = self.root_path / 'addin' / 'manifest.xml'
        if not manifest_path.exists():
            self.log_test("Manifest XML structure", False, "manifest.xml not found")
            return False
        
        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()
            
            # Check for Version element
            version_elem = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Version')
            if version_elem is None:
                self.log_test("Manifest version element", False, "Version element not found")
                return False
            
            version = version_elem.text
            self.log_test("Manifest current version", True, f"Version: {version}")
            
            # Check version format (should be major.minor.patch.build)
            version_parts = version.split('.')
            if len(version_parts) != 4:
                self.log_test("Manifest version format", False, f"Version {version} should have 4 parts")
                return False
            
            # Check that all parts are numeric
            try:
                [int(part) for part in version_parts]
                self.log_test("Manifest version format", True, f"Valid format: {version}")
            except ValueError:
                self.log_test("Manifest version format", False, f"Non-numeric version parts: {version}")
                return False
            
            # Check for cache-busting URLs
            url_elements = root.findall('.//{http://schemas.microsoft.com/office/officeappbasictypes/1.0}Url')
            cache_busting_found = any('?v=' in url_elem.get('DefaultValue', '') for url_elem in url_elements)
            
            self.log_test("Manifest cache-busting URLs", cache_busting_found, 
                         "Found versioned URLs" if cache_busting_found else "No versioned URLs found")
            
            return True
        except ET.ParseError as e:
            self.log_test("Manifest XML parsing", False, f"Parse error: {e}")
            return False
    
    def test_environment_variables(self) -> bool:
        """Test key environment variables."""
        logger.info("Testing environment variables...")
        
        required_vars = [
            'OPENAI_API_KEY'
        ]
        
        optional_vars = [
            'DATABASE_URL',
            'AZURE_REDIS_CONNECTION_STRING',
            'API_KEY'
        ]
        
        all_required_present = True
        for var in required_vars:
            value = os.getenv(var)
            present = bool(value and value.strip())
            self.log_test(f"Required env variable: {var}", present)
            all_required_present = all_required_present and present
        
        for var in optional_vars:
            value = os.getenv(var)
            present = bool(value and value.strip())
            self.log_test(f"Optional env variable: {var}", present, "Present" if present else "Missing (optional)")
        
        return all_required_present
    
    def test_azure_cli_availability(self) -> bool:
        """Test Azure CLI availability."""
        logger.info("Testing Azure CLI...")
        
        try:
            result = subprocess.run(['az', '--version'], capture_output=True, text=True, check=True)
            self.log_test("Azure CLI installed", True, "Available")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_test("Azure CLI installed", False, "Not found - install Azure CLI")
            return False
    
    def test_docker_availability(self) -> bool:
        """Test Docker availability."""
        logger.info("Testing Docker...")
        
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, check=True)
            version_info = result.stdout.strip()
            self.log_test("Docker availability", True, version_info)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_test("Docker availability", False, "Docker not found - install Docker")
            return False
    
    def test_deployment_config(self) -> bool:
        """Test deployment configuration file."""
        logger.info("Testing deployment configuration...")
        
        config_path = self.root_path / 'scripts' / 'deployment_config.json'
        if not config_path.exists():
            self.log_test("Deployment config file", False, "deployment_config.json not found")
            return False
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Check required sections
            required_sections = ['deployment_pipeline', 'environments', 'deployment_features']
            for section in required_sections:
                if section not in config:
                    self.log_test(f"Config section: {section}", False, "Missing")
                    return False
                else:
                    self.log_test(f"Config section: {section}", True, "Present")
            
            # Check environment configuration
            env_config = config.get('environments', {}).get(self.environment)
            if not env_config:
                self.log_test(f"Environment config: {self.environment}", False, "Missing")
                return False
            else:
                self.log_test(f"Environment config: {self.environment}", True, 
                             f"Resource group: {env_config.get('resource_group')}")
            
            return True
        except (json.JSONDecodeError, IOError) as e:
            self.log_test("Deployment config parsing", False, f"Error: {e}")
            return False
    
    def test_python_syntax(self) -> bool:
        """Test Python script syntax."""
        logger.info("Testing Python script syntax...")
        
        script_path = self.root_path / 'scripts' / 'deploy_with_cache_bust.py'
        
        try:
            # Test syntax by compiling
            with open(script_path, 'r') as f:
                source = f.read()
            
            compile(source, script_path, 'exec')
            self.log_test("Python script syntax", True, "Valid syntax")
            return True
        except SyntaxError as e:
            self.log_test("Python script syntax", False, f"Syntax error at line {e.lineno}: {e.msg}")
            return False
        except FileNotFoundError:
            self.log_test("Python script syntax", False, "Script file not found")
            return False
    
    def test_bash_script_syntax(self) -> bool:
        """Test bash script syntax."""
        logger.info("Testing bash script syntax...")
        
        script_path = self.root_path / 'deploy.sh'
        
        try:
            # Test bash syntax
            result = subprocess.run(['bash', '-n', str(script_path)], 
                                  capture_output=True, text=True, check=True)
            self.log_test("Bash script syntax", True, "Valid syntax")
            return True
        except subprocess.CalledProcessError as e:
            self.log_test("Bash script syntax", False, f"Syntax error: {e.stderr}")
            return False
        except FileNotFoundError:
            self.log_test("Bash script syntax", False, "Script file not found")
            return False
    
    def test_deployment_help(self) -> bool:
        """Test deployment script help functionality."""
        logger.info("Testing deployment script help...")
        
        try:
            result = subprocess.run([str(self.root_path / 'deploy.sh'), '--help'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and 'Usage:' in result.stdout:
                self.log_test("Deployment help", True, "Help documentation available")
                return True
            else:
                self.log_test("Deployment help", False, "Help not working properly")
                return False
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            self.log_test("Deployment help", False, f"Error: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tests and return overall success."""
        print(f"\n{Color.BLUE}{'='*80}{Color.NC}")
        print(f"{Color.BLUE}Well Intake API - Basic Deployment Pipeline Test{Color.NC}")
        print(f"{Color.BLUE}{'='*80}{Color.NC}")
        print(f"Environment: {Color.YELLOW}{self.environment}{Color.NC}")
        print(f"Root Path: {Color.BLUE}{self.root_path}{Color.NC}")
        print(f"{Color.BLUE}{'='*80}{Color.NC}\n")
        
        # Run all tests
        tests = [
            self.test_core_files_exist,
            self.test_script_permissions,
            self.test_manifest_structure,
            self.test_environment_variables,
            self.test_azure_cli_availability,
            self.test_docker_availability,
            self.test_deployment_config,
            self.test_python_syntax,
            self.test_bash_script_syntax,
            self.test_deployment_help
        ]
        
        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
            except Exception as e:
                logger.error(f"Test failed with exception: {e}")
                results.append(False)
        
        # Print summary
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        total_tests = len(self.test_results)
        
        print(f"\n{Color.BLUE}{'='*80}{Color.NC}")
        print(f"{Color.BLUE}Test Summary{Color.NC}")
        print(f"{Color.BLUE}{'='*80}{Color.NC}")
        print(f"Passed: {Color.GREEN}{passed_tests}{Color.NC}")
        print(f"Failed: {Color.RED}{total_tests - passed_tests}{Color.NC}")
        print(f"Total:  {Color.BLUE}{total_tests}{Color.NC}")
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"Success Rate: {Color.GREEN if success_rate >= 90 else Color.YELLOW if success_rate >= 70 else Color.RED}{success_rate:.1f}%{Color.NC}")
        
        overall_success = all(results)
        
        if overall_success:
            print(f"\n{Color.GREEN}✓ All basic tests passed! Core deployment pipeline is ready.{Color.NC}")
            print(f"{Color.GREEN}  You can now run: ./deploy.sh {self.environment} status{Color.NC}")
        else:
            print(f"\n{Color.RED}✗ Some tests failed. Please fix issues before deployment.{Color.NC}")
            
            # Show failed tests
            print(f"\n{Color.RED}Failed Tests:{Color.NC}")
            for name, passed, message in self.test_results:
                if not passed:
                    print(f"  • {name}: {message}")
        
        print(f"{Color.BLUE}{'='*80}{Color.NC}\n")
        
        return overall_success

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Test basic deployment pipeline components')
    parser.add_argument('--environment', choices=['dev', 'prod'], default='dev',
                        help='Environment to test configuration for (default: dev)')
    
    args = parser.parse_args()
    
    test_suite = BasicDeploymentTest(args.environment)
    success = test_suite.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()