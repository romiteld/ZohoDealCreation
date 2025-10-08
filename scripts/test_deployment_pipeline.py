#!/usr/bin/env python3
"""
Test script for the enhanced deployment pipeline.

This script validates the deployment system without actually deploying,
ensuring all components are working correctly.

Usage:
    python scripts/test_deployment_pipeline.py [--environment=dev]
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess
import xml.etree.ElementTree as ET

# Add the app directory to sys.path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

try:
    from well_shared.cache.redis_manager import RedisCacheManager
    REDIS_AVAILABLE = True
except ImportError:
    print("Warning: RedisCacheManager not available for testing")
    REDIS_AVAILABLE = False

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

class DeploymentPipelineTest:
    """Test suite for the enhanced deployment pipeline."""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.root_path = Path(__file__).parent.parent
        self.test_results: List[Tuple[str, bool, str]] = []
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = f"{Color.GREEN}PASS{Color.NC}" if passed else f"{Color.RED}FAIL{Color.NC}"
        print(f"[{status}] {test_name}: {message}")
        self.test_results.append((test_name, passed, message))
    
    def test_file_existence(self) -> bool:
        """Test that all required files exist."""
        logger.info("Testing file existence...")
        
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
                self.log_test(f"Script executable: {file_path}", is_executable, 
                            "Executable" if is_executable else "Not executable")
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
            version_parts = version.split('.')
            
            # Validate version format (should be major.minor.patch.build)
            if len(version_parts) != 4:
                self.log_test("Manifest version format", False, f"Version {version} should have 4 parts")
                return False
            
            # Check that all parts are numeric
            try:
                [int(part) for part in version_parts]
                self.log_test("Manifest version format", True, f"Version: {version}")
            except ValueError:
                self.log_test("Manifest version format", False, f"Non-numeric version parts: {version}")
                return False
            
            # Check for cache-busting URLs
            url_elements = root.findall('.//{http://schemas.microsoft.com/office/officeappbasictypes/1.0}Url')
            cache_busting_found = False
            
            for url_elem in url_elements:
                url = url_elem.get('DefaultValue', '')
                if '?v=' in url:
                    cache_busting_found = True
                    break
            
            self.log_test("Manifest cache-busting URLs", cache_busting_found, 
                         "Found versioned URLs" if cache_busting_found else "No versioned URLs found")
            
            return True
        except ET.ParseError as e:
            self.log_test("Manifest XML parsing", False, f"Parse error: {e}")
            return False
    
    def test_environment_variables(self) -> bool:
        """Test required environment variables."""
        logger.info("Testing environment variables...")
        
        required_vars = [
            'OPENAI_API_KEY',
            'DATABASE_URL'
        ]
        
        optional_vars = [
            'AZURE_REDIS_CONNECTION_STRING',
            'API_KEY'
        ]
        
        all_required_present = True
        for var in required_vars:
            value = os.getenv(var)
            present = bool(value)
            self.log_test(f"Environment variable: {var}", present, 
                         "Present" if present else "Missing")
            all_required_present = all_required_present and present
        
        for var in optional_vars:
            value = os.getenv(var)
            present = bool(value)
            self.log_test(f"Optional env variable: {var}", present, 
                         "Present" if present else "Missing (optional)")
        
        return all_required_present
    
    def test_azure_cli(self) -> bool:
        """Test Azure CLI availability and authentication."""
        logger.info("Testing Azure CLI...")
        
        # Check if Azure CLI is installed
        try:
            result = subprocess.run(['az', '--version'], capture_output=True, text=True, check=True)
            self.log_test("Azure CLI installed", True, "Available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_test("Azure CLI installed", False, "Not found or not working")
            return False
        
        # Check if logged in (non-blocking test)
        try:
            result = subprocess.run(['az', 'account', 'show'], capture_output=True, text=True, check=True)
            account_info = json.loads(result.stdout)
            account_name = account_info.get('name', 'Unknown')
            self.log_test("Azure CLI authentication", True, f"Logged in as: {account_name}")
            return True
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            self.log_test("Azure CLI authentication", False, "Not logged in (run 'az login')")
            return False
    
    def test_docker(self) -> bool:
        """Test Docker availability."""
        logger.info("Testing Docker...")
        
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, check=True)
            version_info = result.stdout.strip()
            self.log_test("Docker availability", True, version_info)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_test("Docker availability", False, "Docker not found or not working")
            return False
    
    async def test_redis_connection(self) -> bool:
        """Test Redis connection (non-blocking)."""
        logger.info("Testing Redis connection...")
        
        if not REDIS_AVAILABLE:
            self.log_test("Redis cache manager", False, "RedisCacheManager not available")
            return False
        
        redis_connection = os.getenv("AZURE_REDIS_CONNECTION_STRING")
        if not redis_connection:
            self.log_test("Redis connection string", False, "AZURE_REDIS_CONNECTION_STRING not set")
            return False
        
        try:
            redis_manager = RedisCacheManager(redis_connection)
            await redis_manager.connect()
            
            # Test basic operation
            test_key = "deployment:test"
            test_value = "pipeline_validation"
            
            await redis_manager.client.set(test_key, test_value, ex=10)  # 10 second TTL
            retrieved_value = await redis_manager.client.get(test_key)
            
            if retrieved_value and retrieved_value.decode() == test_value:
                self.log_test("Redis connection", True, "Connection and basic operations work")
                await redis_manager.client.delete(test_key)  # Cleanup
                success = True
            else:
                self.log_test("Redis connection", False, "Connection works but operations failed")
                success = False
            
            await redis_manager.disconnect()
            return success
        except Exception as e:
            self.log_test("Redis connection", False, f"Connection failed: {e}")
            return False
    
    def test_python_dependencies(self) -> bool:
        """Test Python dependencies."""
        logger.info("Testing Python dependencies...")
        
        required_modules = [
            'redis',
            'requests',
            'xml.etree.ElementTree',
            'json',
            'asyncio',
            'subprocess'
        ]
        
        all_available = True
        for module in required_modules:
            try:
                __import__(module)
                self.log_test(f"Python module: {module}", True, "Available")
            except ImportError:
                self.log_test(f"Python module: {module}", False, "Missing")
                all_available = False
        
        return all_available
    
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
    
    def test_import_deployment_script(self) -> bool:
        """Test importing the deployment script."""
        logger.info("Testing deployment script imports...")
        
        try:
            # Try to import the deployment script components
            sys.path.insert(0, str(self.root_path / 'scripts'))
            
            # This will test the basic syntax and imports
            import deploy_with_cache_bust
            
            # Check for key classes
            if hasattr(deploy_with_cache_bust, 'EnhancedDeploymentOrchestrator'):
                self.log_test("Deployment orchestrator class", True, "Available")
            else:
                self.log_test("Deployment orchestrator class", False, "Missing")
                return False
            
            return True
        except ImportError as e:
            self.log_test("Deployment script import", False, f"Import error: {e}")
            return False
        except SyntaxError as e:
            self.log_test("Deployment script syntax", False, f"Syntax error: {e}")
            return False
    
    async def run_all_tests(self) -> bool:
        """Run all tests and return overall success."""
        print(f"\n{Color.BLUE}{'='*80}{Color.NC}")
        print(f"{Color.BLUE}Well Intake API - Deployment Pipeline Test Suite{Color.NC}")
        print(f"{Color.BLUE}{'='*80}{Color.NC}")
        print(f"Environment: {Color.YELLOW}{self.environment}{Color.NC}")
        print(f"Root Path: {Color.BLUE}{self.root_path}{Color.NC}")
        print(f"{Color.BLUE}{'='*80}{Color.NC}\n")
        
        # Run synchronous tests
        sync_tests = [
            self.test_file_existence,
            self.test_script_permissions,
            self.test_manifest_structure,
            self.test_environment_variables,
            self.test_azure_cli,
            self.test_docker,
            self.test_python_dependencies,
            self.test_deployment_config,
            self.test_import_deployment_script
        ]
        
        sync_results = []
        for test in sync_tests:
            try:
                result = test()
                sync_results.append(result)
            except Exception as e:
                logger.error(f"Test failed with exception: {e}")
                sync_results.append(False)
        
        # Run async tests
        async_results = [
            await self.test_redis_connection()
        ]
        
        # Combine results
        all_results = sync_results + async_results
        
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
        
        overall_success = all(all_results)
        
        if overall_success:
            print(f"\n{Color.GREEN}✓ All tests passed! Deployment pipeline is ready.{Color.NC}")
        else:
            print(f"\n{Color.RED}✗ Some tests failed. Please fix issues before deployment.{Color.NC}")
        
        print(f"{Color.BLUE}{'='*80}{Color.NC}\n")
        
        return overall_success

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Test deployment pipeline components')
    parser.add_argument('--environment', choices=['dev', 'prod'], default='dev',
                        help='Environment to test configuration for (default: dev)')
    
    args = parser.parse_args()
    
    test_suite = DeploymentPipelineTest(args.environment)
    success = await test_suite.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    asyncio.run(main())