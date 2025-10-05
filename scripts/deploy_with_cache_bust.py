#!/usr/bin/env python3
"""
Enhanced deployment script with cache busting automation for Well Intake API.

Features:
- Auto-detect manifest changes and bump version numbers
- Clear Redis cache before deployment
- Deploy to Azure Container Apps with zero-downtime
- Warm cache with new manifest versions
- Verify deployment success
- Rollback on failure
- Integration with existing Azure infrastructure

Usage:
    python scripts/deploy_with_cache_bust.py [--environment=prod] [--rollback=revision_name] [--force-version-bump]
"""

import os
import sys
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import hashlib
import asyncio
import argparse
import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError
import requests
from dotenv import load_dotenv

# Add the app directory to sys.path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

try:
    from app.redis_cache_manager import RedisCacheManager
except ImportError:
    print("Warning: Could not import RedisCacheManager, cache operations may not work")
    RedisCacheManager = None

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('deployment.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class Color:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color

class DeploymentConfig:
    """Configuration for deployment environments."""
    
    ENVIRONMENTS = {
        'dev': {
            'resource_group': 'TheWell-Dev-East',
            'container_app_name': 'well-intake-api-dev',
            'registry_name': 'wellintakeregistrydev',
            'key_vault_name': 'well-intake-kv-dev',
            'redis_name': 'well-intake-redis-dev',
            'app_insights_name': 'well-intake-insights-dev'
        },
        'prod': {
            'resource_group': 'TheWell-Infra-East',
            'container_app_name': 'well-intake-api',
            'registry_name': 'wellintakeregistry',
            'key_vault_name': 'well-intake-kv',
            'redis_name': 'well-intake-redis',
            'app_insights_name': 'well-intake-insights'
        }
    }
    
    @classmethod
    def get_config(cls, environment: str) -> Dict:
        """Get configuration for specified environment."""
        if environment not in cls.ENVIRONMENTS:
            raise ValueError(f"Unknown environment: {environment}. Available: {list(cls.ENVIRONMENTS.keys())}")
        
        config = cls.ENVIRONMENTS[environment].copy()
        config['environment'] = environment
        config['location'] = 'eastus'
        
        return config

class ManifestVersionManager:
    """Manages Outlook add-in manifest version bumping and cache busting."""
    
    def __init__(self, manifest_path: str = "addin/manifest.xml"):
        self.manifest_path = Path(manifest_path)
        self.backup_path = self.manifest_path.with_suffix('.xml.backup')
        
    def get_current_version(self) -> str:
        """Get current version from manifest.xml."""
        try:
            tree = ET.parse(self.manifest_path)
            root = tree.getroot()
            
            # Find Version element
            version_elem = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Version')
            if version_elem is not None:
                return version_elem.text
            
            logger.warning("Version element not found in manifest")
            return "1.0.0.0"
        except Exception as e:
            logger.error(f"Error reading manifest version: {e}")
            return "1.0.0.0"
    
    def bump_version(self, version_type: str = 'patch') -> str:
        """
        Bump version number in manifest.xml.
        
        Args:
            version_type: 'major', 'minor', 'patch', or 'build'
        
        Returns:
            New version string
        """
        current_version = self.get_current_version()
        parts = current_version.split('.')
        
        # Ensure we have 4 parts (major.minor.patch.build)
        while len(parts) < 4:
            parts.append('0')
        
        # Convert to integers
        major, minor, patch, build = map(int, parts[:4])
        
        # Bump appropriate version part
        if version_type == 'major':
            major += 1
            minor = patch = build = 0
        elif version_type == 'minor':
            minor += 1
            patch = build = 0
        elif version_type == 'patch':
            patch += 1
            build = 0
        else:  # build
            build += 1
        
        new_version = f"{major}.{minor}.{patch}.{build}"
        
        # Create backup
        if self.manifest_path.exists():
            self.manifest_path.rename(self.backup_path)
            logger.info(f"Created backup: {self.backup_path}")
        
        # Update manifest
        try:
            tree = ET.parse(self.backup_path)
            root = tree.getroot()
            
            # Update Version element
            version_elem = root.find('.//{http://schemas.microsoft.com/office/appforoffice/1.1}Version')
            if version_elem is not None:
                version_elem.text = new_version
            
            # Update cache-busting parameters in URLs
            for url_elem in root.findall('.//{http://schemas.microsoft.com/office/officeappbasictypes/1.0}Url'):
                default_value = url_elem.get('DefaultValue', '')
                if '?' in default_value:
                    base_url = default_value.split('?')[0]
                    url_elem.set('DefaultValue', f"{base_url}?v={new_version}")
                elif default_value and not default_value.endswith('.png'):
                    url_elem.set('DefaultValue', f"{default_value}?v={new_version}")
            
            # Write updated manifest
            tree.write(self.manifest_path, encoding='utf-8', xml_declaration=True)
            logger.info(f"Updated manifest version: {current_version} -> {new_version}")
            
            return new_version
        except Exception as e:
            # Restore backup on error
            if self.backup_path.exists():
                self.backup_path.rename(self.manifest_path)
            raise RuntimeError(f"Error updating manifest version: {e}")
    
    def restore_backup(self):
        """Restore manifest from backup."""
        if self.backup_path.exists():
            self.backup_path.rename(self.manifest_path)
            logger.info("Restored manifest from backup")
        else:
            logger.warning("No backup found to restore")
    
    def detect_manifest_changes(self) -> bool:
        """Detect if manifest has been modified since last deployment."""
        try:
            # Check git status for manifest changes
            result = subprocess.run(
                ['git', 'status', '--porcelain', str(self.manifest_path)],
                capture_output=True, text=True, cwd=self.manifest_path.parent.parent
            )
            
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            logger.warning("Could not check git status for manifest changes")
            return True  # Assume changes if can't verify

class CacheBustingManager:
    """Manages Redis cache invalidation and warming during deployments."""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.config = DeploymentConfig.get_config(environment)
        self.redis_manager = None
        
        # Initialize Redis manager if available
        redis_connection = os.getenv("AZURE_REDIS_CONNECTION_STRING")
        if redis_connection and RedisCacheManager:
            self.redis_manager = RedisCacheManager(redis_connection)
    
    async def clear_cache(self, patterns: Optional[List[str]] = None) -> bool:
        """
        Clear Redis cache before deployment.
        
        Args:
            patterns: Specific cache key patterns to clear. If None, clears all.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_manager:
            logger.warning("Redis manager not available, skipping cache clear")
            return True
        
        try:
            await self.redis_manager.connect()
            
            if patterns:
                # Clear specific patterns
                for pattern in patterns:
                    await self.redis_manager.invalidate_pattern(pattern)
                    logger.info(f"Cleared cache pattern: {pattern}")
            else:
                # Clear all cache
                await self.redis_manager.client.flushdb()
                logger.info("Cleared all cache data")
            
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
        finally:
            if self.redis_manager:
                await self.redis_manager.disconnect()
    
    async def warm_cache(self, manifest_version: str) -> bool:
        """
        Warm cache with new manifest version after deployment.
        
        Args:
            manifest_version: New manifest version for cache warming
        
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_manager:
            logger.warning("Redis manager not available, skipping cache warm")
            return True
        
        try:
            await self.redis_manager.connect()
            
            # Store deployment metadata
            deployment_info = {
                'version': manifest_version,
                'timestamp': datetime.utcnow().isoformat(),
                'environment': self.environment
            }
            
            await self.redis_manager.client.set(
                'deployment:latest',
                json.dumps(deployment_info),
                ex=int(self.redis_manager.default_ttl.total_seconds())
            )
            
            # Pre-populate common patterns (optional)
            common_patterns = [
                'manifest:version',
                'config:endpoints',
                'health:status'
            ]
            
            for pattern in common_patterns:
                cache_key = f"{pattern}:{manifest_version}"
                await self.redis_manager.client.set(
                    cache_key,
                    json.dumps({'warmed': True, 'version': manifest_version}),
                    ex=3600  # 1 hour TTL for warm data
                )
            
            logger.info(f"Cache warmed with version {manifest_version}")
            return True
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return False
        finally:
            if self.redis_manager:
                await self.redis_manager.disconnect()

class AzureDeploymentManager:
    """Manages Azure Container Apps deployment with zero-downtime and rollback."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.image_tag = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def run_azure_cli(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run Azure CLI command with proper error handling."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )
            
            if result.stdout:
                logger.debug(f"Azure CLI output: {result.stdout}")
            
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Azure CLI error: {e.stderr}")
            raise
    
    def check_prerequisites(self) -> bool:
        """Check deployment prerequisites."""
        logger.info("Checking deployment prerequisites...")
        
        # Check Azure CLI
        try:
            self.run_azure_cli(['az', '--version'])
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Azure CLI not found or not working")
            return False
        
        # Check Docker
        try:
            subprocess.run(['docker', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Docker not found or not working")
            return False
        
        # Check Azure login
        try:
            self.run_azure_cli(['az', 'account', 'show'])
        except subprocess.CalledProcessError:
            logger.error("Not logged into Azure. Please run 'az login' first.")
            return False
        
        logger.info("Prerequisites check passed")
        return True
    
    def build_and_push_image(self) -> bool:
        """Build and push Docker image to Azure Container Registry."""
        logger.info(f"Building Docker image with tag: {self.image_tag}")
        
        image_name = f"{self.config['registry_name']}.azurecr.io/{self.config['container_app_name']}:{self.image_tag}"
        
        try:
            # Build image
            build_cmd = ['docker', 'build', '-t', image_name, '.']
            result = subprocess.run(build_cmd, capture_output=True, text=True, check=True)
            logger.info("Docker build completed successfully")
            
            # Login to ACR
            self.run_azure_cli(['az', 'acr', 'login', '--name', self.config['registry_name']])
            
            # Push image
            push_cmd = ['docker', 'push', image_name]
            result = subprocess.run(push_cmd, capture_output=True, text=True, check=True)
            logger.info(f"Image pushed successfully: {image_name}")
            
            self.image_name = image_name
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error building/pushing image: {e}")
            return False
    
    def get_current_revision(self) -> Optional[str]:
        """Get current active revision name."""
        try:
            result = self.run_azure_cli([
                'az', 'containerapp', 'revision', 'list',
                '--name', self.config['container_app_name'],
                '--resource-group', self.config['resource_group'],
                '--query', '[?properties.active==`true`].name',
                '-o', 'tsv'
            ])
            
            active_revisions = [r.strip() for r in result.stdout.strip().split('\n') if r.strip()]
            return active_revisions[0] if active_revisions else None
        except subprocess.CalledProcessError:
            logger.warning("Could not get current revision")
            return None
    
    def deploy_container_app(self, manifest_version: str) -> bool:
        """Deploy to Azure Container Apps with zero-downtime."""
        logger.info("Deploying to Azure Container Apps...")
        
        try:
            # Create revision suffix with version and timestamp
            revision_suffix = f"v{manifest_version.replace('.', '')}-{datetime.now().strftime('%m%d%H%M')}"
            
            # Deploy new revision
            deploy_cmd = [
                'az', 'containerapp', 'update',
                '--name', self.config['container_app_name'],
                '--resource-group', self.config['resource_group'],
                '--image', self.image_name,
                '--revision-suffix', revision_suffix,
                '--min-replicas', '2',
                '--max-replicas', '10',
                '--cpu', '2',
                '--memory', '4Gi',
                '--set-env-vars',
                'USE_MANAGED_IDENTITY=true',
                f'KEY_VAULT_URL=https://{self.config["key_vault_name"]}.vault.azure.net/',
                f'ENVIRONMENT={self.config["environment"]}',
                'USE_LANGGRAPH=true',
                'OPENAI_MODEL=gpt-4o-mini'
            ]
            
            self.run_azure_cli(deploy_cmd)
            
            # Wait for deployment to be ready
            logger.info("Waiting for new revision to be ready...")
            import time
            time.sleep(60)  # Wait 1 minute for revision to stabilize
            
            # Verify new revision is running
            new_revision_name = f"{self.config['container_app_name']}--{revision_suffix}"
            self.current_revision = new_revision_name
            
            logger.info(f"Deployment completed successfully: {new_revision_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error deploying container app: {e}")
            return False
    
    def verify_deployment(self) -> bool:
        """Verify deployment health and functionality."""
        logger.info("Verifying deployment...")
        
        try:
            # Get app URL
            result = self.run_azure_cli([
                'az', 'containerapp', 'show',
                '--name', self.config['container_app_name'],
                '--resource-group', self.config['resource_group'],
                '--query', 'properties.configuration.ingress.fqdn',
                '-o', 'tsv'
            ])
            
            app_url = result.stdout.strip()
            if not app_url:
                logger.error("Could not get application URL")
                return False
            
            # Health check
            health_url = f"https://{app_url}/health"
            logger.info(f"Checking health endpoint: {health_url}")
            
            response = requests.get(health_url, timeout=30)
            
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Health check passed: {health_data}")
                return True
            else:
                logger.error(f"Health check failed with status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying deployment: {e}")
            return False
    
    def rollback_deployment(self, target_revision: str = None) -> bool:
        """
        Rollback to previous revision.
        
        Args:
            target_revision: Specific revision to rollback to. If None, uses previous revision.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Rolling back deployment...")
        
        try:
            if not target_revision:
                # Get list of revisions
                result = self.run_azure_cli([
                    'az', 'containerapp', 'revision', 'list',
                    '--name', self.config['container_app_name'],
                    '--resource-group', self.config['resource_group'],
                    '--query', '[?properties.active==`false`] | [0].name',
                    '-o', 'tsv'
                ])
                
                target_revision = result.stdout.strip()
                
                if not target_revision:
                    logger.error("No previous revision found for rollback")
                    return False
            
            # Set traffic to target revision
            self.run_azure_cli([
                'az', 'containerapp', 'ingress', 'traffic', 'set',
                '--name', self.config['container_app_name'],
                '--resource-group', self.config['resource_group'],
                '--revision-weight', f"{target_revision}=100"
            ])
            
            logger.info(f"Rollback completed to revision: {target_revision}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during rollback: {e}")
            return False
    
    def cleanup_old_revisions(self, keep_count: int = 3):
        """Clean up old revisions, keeping specified number."""
        logger.info(f"Cleaning up old revisions (keeping {keep_count})...")
        
        try:
            # Get all revisions sorted by creation date
            result = self.run_azure_cli([
                'az', 'containerapp', 'revision', 'list',
                '--name', self.config['container_app_name'],
                '--resource-group', self.config['resource_group'],
                '--query', f"[{keep_count}:].name",
                '-o', 'tsv'
            ])
            
            old_revisions = [r.strip() for r in result.stdout.strip().split('\n') if r.strip()]
            
            for revision in old_revisions:
                try:
                    self.run_azure_cli([
                        'az', 'containerapp', 'revision', 'deactivate',
                        '--name', self.config['container_app_name'],
                        '--resource-group', self.config['resource_group'],
                        '--revision', revision
                    ])
                    logger.info(f"Deactivated old revision: {revision}")
                except subprocess.CalledProcessError:
                    logger.warning(f"Could not deactivate revision: {revision}")
            
            logger.info("Cleanup completed")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error during cleanup: {e}")

class EnhancedDeploymentOrchestrator:
    """Main orchestrator for enhanced deployment with cache busting."""
    
    def __init__(self, environment: str = 'prod'):
        self.environment = environment
        self.config = DeploymentConfig.get_config(environment)
        self.manifest_manager = ManifestVersionManager()
        self.cache_manager = CacheBustingManager(environment)
        self.azure_manager = AzureDeploymentManager(self.config)
        self.deployment_start_time = datetime.utcnow()
    
    def print_banner(self):
        """Print deployment banner."""
        print(f"\n{Color.CYAN}{'='*80}{Color.NC}")
        print(f"{Color.CYAN}Well Intake API - Enhanced Deployment with Cache Busting{Color.NC}")
        print(f"{Color.CYAN}{'='*80}{Color.NC}")
        print(f"Environment: {Color.YELLOW}{self.environment.upper()}{Color.NC}")
        print(f"Resource Group: {Color.BLUE}{self.config['resource_group']}{Color.NC}")
        print(f"Container App: {Color.BLUE}{self.config['container_app_name']}{Color.NC}")
        print(f"Start Time: {Color.GREEN}{self.deployment_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}{Color.NC}")
        print(f"{Color.CYAN}{'='*80}{Color.NC}\n")
    
    def print_summary(self, success: bool, manifest_version: str = None):
        """Print deployment summary."""
        end_time = datetime.utcnow()
        duration = end_time - self.deployment_start_time
        
        status_color = Color.GREEN if success else Color.RED
        status_text = "SUCCESS" if success else "FAILED"
        
        print(f"\n{Color.CYAN}{'='*80}{Color.NC}")
        print(f"{Color.CYAN}Deployment Summary{Color.NC}")
        print(f"{Color.CYAN}{'='*80}{Color.NC}")
        print(f"Status: {status_color}{status_text}{Color.NC}")
        print(f"Environment: {Color.YELLOW}{self.environment.upper()}{Color.NC}")
        print(f"Duration: {Color.BLUE}{duration.total_seconds():.1f} seconds{Color.NC}")
        
        if manifest_version:
            print(f"Manifest Version: {Color.GREEN}{manifest_version}{Color.NC}")
        
        if success:
            # Get app URL for summary
            try:
                result = self.azure_manager.run_azure_cli([
                    'az', 'containerapp', 'show',
                    '--name', self.config['container_app_name'],
                    '--resource-group', self.config['resource_group'],
                    '--query', 'properties.configuration.ingress.fqdn',
                    '-o', 'tsv'
                ])
                app_url = result.stdout.strip()
                if app_url:
                    print(f"Application URL: {Color.BLUE}https://{app_url}{Color.NC}")
                    print(f"Health Check: {Color.BLUE}https://{app_url}/health{Color.NC}")
                    print(f"Manifest: {Color.BLUE}https://{app_url}/manifest.xml{Color.NC}")
            except:
                pass
        
        print(f"{Color.CYAN}{'='*80}{Color.NC}\n")
    
    async def deploy(self, force_version_bump: bool = False) -> bool:
        """
        Execute full deployment with cache busting.
        
        Args:
            force_version_bump: Force version bump even if no changes detected
        
        Returns:
            True if successful, False otherwise
        """
        self.print_banner()
        manifest_version = None
        
        try:
            # Step 1: Check prerequisites
            logger.info(f"{Color.BLUE}[1/8]{Color.NC} Checking prerequisites...")
            if not self.azure_manager.check_prerequisites():
                logger.error("Prerequisites check failed")
                return False
            
            # Step 2: Handle manifest versioning
            logger.info(f"{Color.BLUE}[2/8]{Color.NC} Managing manifest versioning...")
            
            manifest_changed = self.manifest_manager.detect_manifest_changes()
            if manifest_changed or force_version_bump:
                manifest_version = self.manifest_manager.bump_version('build')
                logger.info(f"Bumped manifest version to: {manifest_version}")
            else:
                manifest_version = self.manifest_manager.get_current_version()
                logger.info(f"Using current manifest version: {manifest_version}")
            
            # Step 3: Clear cache
            logger.info(f"{Color.BLUE}[3/8]{Color.NC} Clearing Redis cache...")
            cache_cleared = await self.cache_manager.clear_cache([
                "manifest:*",
                "config:*",
                "email:pattern:*"
            ])
            
            if not cache_cleared:
                logger.warning("Cache clear failed, continuing deployment")
            
            # Step 4: Build and push Docker image
            logger.info(f"{Color.BLUE}[4/8]{Color.NC} Building and pushing Docker image...")
            if not self.azure_manager.build_and_push_image():
                logger.error("Image build/push failed")
                return False
            
            # Step 5: Deploy to Container Apps
            logger.info(f"{Color.BLUE}[5/8]{Color.NC} Deploying to Azure Container Apps...")
            if not self.azure_manager.deploy_container_app(manifest_version):
                logger.error("Container app deployment failed")
                return False
            
            # Step 6: Verify deployment
            logger.info(f"{Color.BLUE}[6/8]{Color.NC} Verifying deployment...")
            if not self.azure_manager.verify_deployment():
                logger.error("Deployment verification failed")
                # Attempt rollback on verification failure
                logger.warning("Attempting automatic rollback...")
                self.azure_manager.rollback_deployment()
                return False
            
            # Step 7: Warm cache
            logger.info(f"{Color.BLUE}[7/8]{Color.NC} Warming cache...")
            cache_warmed = await self.cache_manager.warm_cache(manifest_version)
            
            if not cache_warmed:
                logger.warning("Cache warming failed, but deployment successful")
            
            # Step 8: Cleanup old revisions
            logger.info(f"{Color.BLUE}[8/8]{Color.NC} Cleaning up old revisions...")
            self.azure_manager.cleanup_old_revisions(keep_count=3)
            
            logger.info(f"{Color.GREEN}Deployment completed successfully!{Color.NC}")
            self.print_summary(True, manifest_version)
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed with error: {e}")
            
            # Attempt to restore manifest backup
            try:
                self.manifest_manager.restore_backup()
            except Exception:
                pass
            
            self.print_summary(False, manifest_version)
            return False
    
    async def rollback(self, target_revision: str = None) -> bool:
        """
        Rollback to previous revision.
        
        Args:
            target_revision: Specific revision to rollback to
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting rollback procedure...")
        
        try:
            # Rollback Azure deployment
            if not self.azure_manager.rollback_deployment(target_revision):
                return False
            
            # Clear cache after rollback
            await self.cache_manager.clear_cache()
            
            # Restore manifest backup if available
            self.manifest_manager.restore_backup()
            
            logger.info("Rollback completed successfully")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Enhanced deployment with cache busting for Well Intake API')
    parser.add_argument('--environment', choices=['dev', 'prod'], default='prod',
                        help='Deployment environment (default: prod)')
    parser.add_argument('--rollback', type=str, metavar='REVISION',
                        help='Rollback to specific revision')
    parser.add_argument('--force-version-bump', action='store_true',
                        help='Force version bump even if no changes detected')
    
    args = parser.parse_args()
    
    orchestrator = EnhancedDeploymentOrchestrator(args.environment)
    
    if args.rollback:
        success = await orchestrator.rollback(args.rollback)
    else:
        success = await orchestrator.deploy(args.force_version_bump)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    asyncio.run(main())