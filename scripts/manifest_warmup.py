#!/usr/bin/env python3
"""
Manifest Template System with Cache Warming for Outlook Add-in

This script implements a comprehensive template system for dynamic manifest generation
with intelligent cache warming capabilities. It pre-populates Redis cache during
deployments and supports multiple manifest templates for different environments.

Features:
- Jinja2 template engine for manifest.xml generation
- Redis cache warming during application startup
- Bulk cache operations for multiple manifest variants
- Template versioning and rollback capabilities
- Validation of generated manifests
- Performance optimization for template rendering

Integration with existing caching infrastructure from RedisCacheManager.
"""

import os
import json
import logging
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from xml.etree import ElementTree as ET

# Third-party imports
from jinja2 import Environment, FileSystemLoader, Template, TemplateError
import xml.dom.minidom as minidom
from dotenv import load_dotenv

# Local imports - integrate with existing caching
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from well_shared.cache.redis_manager import RedisCacheManager

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ManifestConfig:
    """Configuration for manifest template generation."""
    
    # Basic manifest properties
    app_id: str
    version: str
    provider_name: str
    app_name: str
    description: str
    
    # API endpoints and domains
    api_base_url: str
    app_domains: List[str]
    
    # Resources and icons
    icon_16: str
    icon_32: str
    icon_64: str
    icon_80: str
    icon_128: str
    
    # Add-in specific settings
    requested_height: int = 250
    permissions: str = "ReadWriteItem"
    support_url: str = "https://thewell.solutions/"
    
    # Environment-specific settings
    environment: str = "production"
    cache_busting: bool = True
    websocket_enabled: bool = False
    
    # Template metadata
    template_name: str = "default"
    template_version: str = "1.0.0"
    created_at: str = ""
    
    def __post_init__(self):
        """Initialize computed fields."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        data = asdict(self)
        
        # Add computed values for template
        data['cache_version'] = f"v={self.version}" if self.cache_busting else ""
        data['timestamp'] = int(datetime.utcnow().timestamp())
        
        # Build full URLs with cache busting
        if self.cache_busting:
            cache_param = data['cache_version']
            data['commands_url'] = f"{self.api_base_url}/commands.html?{cache_param}"
            data['taskpane_url'] = f"{self.api_base_url}/taskpane.html?{cache_param}"
        else:
            data['commands_url'] = f"{self.api_base_url}/commands.html"
            data['taskpane_url'] = f"{self.api_base_url}/taskpane.html"
        
        return data


class ManifestTemplateEngine:
    """Template engine for generating Outlook manifest files."""
    
    def __init__(self, templates_dir: str = None):
        """
        Initialize template engine.
        
        Args:
            templates_dir: Directory containing Jinja2 templates
        """
        self.templates_dir = templates_dir or os.path.join(
            os.path.dirname(__file__), '..', 'templates', 'manifests'
        )
        
        # Ensure templates directory exists
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['xmlescape'] = self._xml_escape
        self.env.filters['generate_guid'] = self._generate_guid
        
        # Template cache for performance
        self._template_cache: Dict[str, Template] = {}
    
    def _xml_escape(self, value: str) -> str:
        """Custom Jinja2 filter for XML escaping."""
        if not isinstance(value, str):
            value = str(value)
        
        return (value
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))
    
    def _generate_guid(self, seed: str = None) -> str:
        """Generate a deterministic GUID from seed."""
        import uuid
        if seed:
            # Generate deterministic UUID from seed
            namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
            return str(uuid.uuid5(namespace, seed))
        else:
            return str(uuid.uuid4())
    
    def load_template(self, template_name: str) -> Template:
        """
        Load and cache a Jinja2 template.
        
        Args:
            template_name: Name of the template file (e.g., 'default.xml')
        
        Returns:
            Compiled Jinja2 template
        """
        if template_name in self._template_cache:
            return self._template_cache[template_name]
        
        try:
            template = self.env.get_template(template_name)
            self._template_cache[template_name] = template
            return template
        except TemplateError as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            raise
    
    def render_manifest(self, config: ManifestConfig, template_name: str = None) -> str:
        """
        Render manifest XML from template and configuration.
        
        Args:
            config: Manifest configuration
            template_name: Template file name (defaults to config.template_name + '.xml')
        
        Returns:
            Rendered manifest XML as string
        """
        template_file = template_name or f"{config.template_name}.xml"
        
        try:
            template = self.load_template(template_file)
            rendered = template.render(**config.to_dict())
            
            # Validate and format XML
            return self._format_xml(rendered)
            
        except Exception as e:
            logger.error(f"Failed to render manifest with template {template_file}: {e}")
            raise
    
    def _format_xml(self, xml_content: str) -> str:
        """
        Format and validate XML content.
        
        Args:
            xml_content: Raw XML string
        
        Returns:
            Formatted XML string
        """
        try:
            # Parse and validate XML
            root = ET.fromstring(xml_content)
            
            # Pretty print with minidom
            rough_string = ET.tostring(root, encoding='unicode')
            reparsed = minidom.parseString(rough_string)
            
            # Return formatted XML without the XML declaration line
            pretty = reparsed.toprettyxml(indent="  ")
            lines = pretty.split('\n')[1:]  # Remove XML declaration
            return '\n'.join(line for line in lines if line.strip())
            
        except ET.ParseError as e:
            logger.error(f"Invalid XML generated: {e}")
            logger.debug(f"XML content: {xml_content}")
            raise
    
    def create_default_templates(self):
        """Create default manifest templates if they don't exist."""
        templates = {
            'default.xml': self._get_default_template(),
            'development.xml': self._get_development_template(),
            'staging.xml': self._get_staging_template(),
            'production.xml': self._get_production_template(),
        }
        
        for template_name, content in templates.items():
            template_path = os.path.join(self.templates_dir, template_name)
            
            if not os.path.exists(template_path):
                with open(template_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Created template: {template_path}")
    
    def _get_default_template(self) -> str:
        """Get the default manifest template."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
           xmlns:mailappor="http://schemas.microsoft.com/office/mailappversionoverrides/1.0"
           xsi:type="MailApp">
  
  <Id>{{ app_id }}</Id>
  <Version>{{ version }}</Version>
  <ProviderName>{{ provider_name | xmlescape }}</ProviderName>
  <DefaultLocale>en-US</DefaultLocale>
  <DisplayName DefaultValue="{{ app_name | xmlescape }}"/>
  <Description DefaultValue="{{ description | xmlescape }}"/>
  <IconUrl DefaultValue="{{ icon_64 }}"/>
  <HighResolutionIconUrl DefaultValue="{{ icon_128 }}"/>
  <SupportUrl DefaultValue="{{ support_url }}"/>
  
  <AppDomains>
    {% for domain in app_domains -%}
    <AppDomain>{{ domain }}</AppDomain>
    {% endfor %}
  </AppDomains>
  
  <Hosts>
    <Host Name="Mailbox"/>
  </Hosts>
  
  <Requirements>
    <Sets DefaultMinVersion="1.1">
      <Set Name="Mailbox"/>
    </Sets>
  </Requirements>
  
  <FormSettings>
    <Form xsi:type="ItemRead">
      <DesktopSettings>
        <SourceLocation DefaultValue="{{ taskpane_url }}"/>
        <RequestedHeight>{{ requested_height }}</RequestedHeight>
      </DesktopSettings>
    </Form>
  </FormSettings>
  
  <Permissions>{{ permissions }}</Permissions>
  
  <Rule xsi:type="RuleCollection" Mode="Or">
    <Rule xsi:type="ItemIs" ItemType="Message" FormType="Read"/>
  </Rule>
  
  <DisableEntityHighlighting>false</DisableEntityHighlighting>
  
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/mailappversionoverrides" xsi:type="VersionOverridesV1_0">
    <VersionOverrides xmlns="http://schemas.microsoft.com/office/mailappversionoverrides/1.1" xsi:type="VersionOverridesV1_1">
      <Requirements>
        <bt:Sets DefaultMinVersion="1.3">
          <bt:Set Name="Mailbox"/>
        </bt:Sets>
      </Requirements>
      
      <Hosts>
        <Host xsi:type="MailHost">
          <DesktopFormFactor>
            <FunctionFile resid="Commands.Url"/>
            
            <ExtensionPoint xsi:type="MessageReadCommandSurface">
              <OfficeTab id="TabDefault">
                <Group id="msgReadGroup">
                  <Label resid="GroupLabel"/>
                  <Control xsi:type="Button" id="msgReadOpenButton">
                    <Label resid="TaskpaneButton.Label"/>
                    <Supertip>
                      <Title resid="TaskpaneButton.Label"/>
                      <Description resid="TaskpaneButton.Tooltip"/>
                    </Supertip>
                    <Icon>
                      <bt:Image size="16" resid="Icon.16x16"/>
                      <bt:Image size="32" resid="Icon.32x32"/>
                      <bt:Image size="80" resid="Icon.80x80"/>
                    </Icon>
                    <Action xsi:type="ShowTaskpane">
                      <SourceLocation resid="Taskpane.Url"/>
                    </Action>
                  </Control>
                </Group>
              </OfficeTab>
            </ExtensionPoint>
          </DesktopFormFactor>
        </Host>
      </Hosts>
      
      <Resources>
        <bt:Images>
          <bt:Image id="Icon.16x16" DefaultValue="{{ icon_16 }}"/>
          <bt:Image id="Icon.32x32" DefaultValue="{{ icon_32 }}"/>
          <bt:Image id="Icon.64x64" DefaultValue="{{ icon_64 }}"/>
          <bt:Image id="Icon.80x80" DefaultValue="{{ icon_80 }}"/>
          <bt:Image id="Icon.128x128" DefaultValue="{{ icon_128 }}"/>
        </bt:Images>
        
        <bt:Urls>
          <bt:Url id="Commands.Url" DefaultValue="{{ commands_url }}"/>
          <bt:Url id="Taskpane.Url" DefaultValue="{{ taskpane_url }}"/>
        </bt:Urls>
        
        <bt:ShortStrings>
          <bt:String id="GroupLabel" DefaultValue="The Well"/>
          <bt:String id="TaskpaneButton.Label" DefaultValue="Send to Zoho"/>
        </bt:ShortStrings>
        
        <bt:LongStrings>
          <bt:String id="TaskpaneButton.Tooltip" DefaultValue="Process this email and create candidate records in Zoho CRM"/>
        </bt:LongStrings>
      </Resources>
    </VersionOverrides>
  </VersionOverrides>
</OfficeApp>'''
    
    def _get_development_template(self) -> str:
        """Get development environment template with debug features."""
        base = self._get_default_template()
        # Add development-specific modifications
        return base.replace(
            '<DisableEntityHighlighting>false</DisableEntityHighlighting>',
            '<DisableEntityHighlighting>false</DisableEntityHighlighting>\n  <!-- Development Build -->'
        )
    
    def _get_staging_template(self) -> str:
        """Get staging environment template."""
        return self._get_default_template()  # Same as default for now
    
    def _get_production_template(self) -> str:
        """Get production environment template with optimizations."""
        return self._get_default_template()  # Same as default for now


class ManifestCacheManager:
    """Manages manifest caching with Redis integration."""
    
    def __init__(self, cache_manager: RedisCacheManager = None):
        """
        Initialize manifest cache manager.
        
        Args:
            cache_manager: Redis cache manager instance
        """
        self.cache_manager = cache_manager or RedisCacheManager()
        self.template_engine = ManifestTemplateEngine()
        
        # Cache configuration
        self.manifest_ttl = timedelta(days=7)  # 7-day TTL for manifests
        self.template_ttl = timedelta(days=30)  # 30-day TTL for templates
        
        # Performance metrics
        self.metrics = {
            "manifests_cached": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "templates_cached": 0
        }
    
    async def get_cached_manifest(self, 
                                 config_hash: str,
                                 template_name: str = "default") -> Optional[str]:
        """
        Retrieve cached manifest XML.
        
        Args:
            config_hash: Hash of the manifest configuration
            template_name: Template name used
        
        Returns:
            Cached manifest XML or None if not found
        """
        if not await self.cache_manager.connect():
            return None
        
        cache_key = f"well:manifest:{template_name}:{config_hash}"
        
        try:
            cached_manifest = await self.cache_manager.client.get(cache_key)
            
            if cached_manifest:
                self.metrics["cache_hits"] += 1
                logger.debug(f"Manifest cache HIT: {cache_key}")
                return json.loads(cached_manifest)["xml"]
            else:
                self.metrics["cache_misses"] += 1
                logger.debug(f"Manifest cache MISS: {cache_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving cached manifest: {e}")
            return None
    
    async def cache_manifest(self,
                           config: ManifestConfig,
                           manifest_xml: str,
                           config_hash: str = None) -> bool:
        """
        Cache generated manifest XML.
        
        Args:
            config: Manifest configuration used
            manifest_xml: Generated manifest XML
            config_hash: Pre-computed hash (optional)
        
        Returns:
            True if successfully cached
        """
        if not await self.cache_manager.connect():
            return False
        
        config_hash = config_hash or self._hash_config(config)
        cache_key = f"well:manifest:{config.template_name}:{config_hash}"
        
        cache_data = {
            "xml": manifest_xml,
            "config": asdict(config),
            "cached_at": datetime.utcnow().isoformat(),
            "template_version": config.template_version
        }
        
        try:
            await self.cache_manager.client.setex(
                cache_key,
                int(self.manifest_ttl.total_seconds()),
                json.dumps(cache_data)
            )
            
            self.metrics["manifests_cached"] += 1
            logger.info(f"Cached manifest: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching manifest: {e}")
            return False
    
    def _hash_config(self, config: ManifestConfig) -> str:
        """
        Generate deterministic hash from manifest configuration.
        
        Args:
            config: Manifest configuration
        
        Returns:
            SHA-256 hash string (first 16 chars)
        """
        # Create normalized config dict for hashing
        config_dict = config.to_dict()
        
        # Remove volatile fields that shouldn't affect caching
        volatile_fields = ['created_at', 'timestamp']
        for field in volatile_fields:
            config_dict.pop(field, None)
        
        # Sort keys for consistent hashing
        config_json = json.dumps(config_dict, sort_keys=True)
        
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]
    
    async def warm_manifest_cache(self, configs: List[ManifestConfig]) -> int:
        """
        Pre-warm cache with common manifest configurations.
        
        Args:
            configs: List of manifest configurations to cache
        
        Returns:
            Number of successfully cached manifests
        """
        if not await self.cache_manager.connect():
            return 0
        
        cached_count = 0
        
        for config in configs:
            try:
                # Generate manifest
                manifest_xml = self.template_engine.render_manifest(config)
                
                # Cache it
                success = await self.cache_manifest(config, manifest_xml)
                if success:
                    cached_count += 1
                    
            except Exception as e:
                logger.error(f"Error warming cache for config {config.template_name}: {e}")
        
        logger.info(f"Warmed manifest cache: {cached_count}/{len(configs)} configs cached")
        return cached_count
    
    async def invalidate_manifest_cache(self, pattern: str = None) -> int:
        """
        Invalidate cached manifests matching a pattern.
        
        Args:
            pattern: Redis pattern to match keys (defaults to all manifests)
        
        Returns:
            Number of keys deleted
        """
        if not await self.cache_manager.connect():
            return 0
        
        pattern = pattern or "well:manifest:*"
        
        try:
            keys = []
            async for key in self.cache_manager.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.cache_manager.client.delete(*keys)
                logger.info(f"Invalidated {deleted} manifest cache entries")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Error invalidating manifest cache: {e}")
            return 0


class ManifestWarmupService:
    """Service for warming up manifest cache during deployment."""
    
    def __init__(self, cache_manager: RedisCacheManager = None):
        """Initialize the warmup service."""
        self.cache_manager = ManifestCacheManager(cache_manager)
        
    def create_environment_configs(self) -> List[ManifestConfig]:
        """
        Create manifest configurations for different environments.
        
        Returns:
            List of manifest configurations to cache
        """
        base_config = {
            "app_id": "d2422753-f7f6-4a4a-9e1e-7512f37a50e5",
            "provider_name": "The Well Recruiting Solutions",
            "app_name": "The Well - Send to Zoho",
            "description": "Process recruitment emails and automatically create candidate records in Zoho CRM.",
            "support_url": "https://thewell.solutions/",
            "permissions": "ReadWriteItem"
        }
        
        environments = [
            {
                "environment": "development",
                "api_base_url": "http://localhost:8000",
                "version": "1.0.0-dev",
                "template_name": "development",
                "app_domains": ["http://localhost:8000", "https://*.ngrok.io"],
                "websocket_enabled": True
            },
            {
                "environment": "staging", 
                "api_base_url": "https://well-intake-api-staging.azurecontainerapps.io",
                "version": "1.3.0-staging",
                "template_name": "staging",
                "app_domains": [
                    "https://well-intake-api-staging.azurecontainerapps.io",
                    "https://*.azurecontainerapps.io"
                ],
                "websocket_enabled": True
            },
            {
                "environment": "production",
                "api_base_url": "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
                "version": "1.3.0.2",
                "template_name": "production",
                "app_domains": [
                    "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
                    "https://*.azurecontainerapps.io"
                ],
                "cache_busting": True
            }
        ]
        
        configs = []
        
        for env_config in environments:
            # Create base configuration
            config_dict = {**base_config, **env_config}
            
            # Add icon URLs
            base_url = config_dict["api_base_url"]
            config_dict.update({
                "icon_16": f"{base_url}/icon-16.png",
                "icon_32": f"{base_url}/icon-32.png",
                "icon_64": f"{base_url}/icon-64.png",
                "icon_80": f"{base_url}/icon-80.png",
                "icon_128": f"{base_url}/icon-128.png"
            })
            
            config = ManifestConfig(**config_dict)
            configs.append(config)
            
            # Create version variants
            if env_config["environment"] == "production":
                # Create configs for different versions
                for patch in range(5):  # Cache next 5 patch versions
                    version_config = config_dict.copy()
                    version_config["version"] = f"1.3.{patch}.2"
                    configs.append(ManifestConfig(**version_config))
        
        return configs
    
    def create_feature_variants(self, base_config: ManifestConfig) -> List[ManifestConfig]:
        """
        Create manifest variants for different feature combinations.
        
        Args:
            base_config: Base configuration to create variants from
        
        Returns:
            List of feature variant configurations
        """
        variants = []
        base_dict = asdict(base_config)
        
        # WebSocket variants
        for websocket_enabled in [True, False]:
            variant_dict = base_dict.copy()
            variant_dict["websocket_enabled"] = websocket_enabled
            variant_dict["template_name"] = f"{base_config.template_name}_ws_{websocket_enabled}"
            variants.append(ManifestConfig(**variant_dict))
        
        # Cache busting variants
        for cache_busting in [True, False]:
            variant_dict = base_dict.copy()
            variant_dict["cache_busting"] = cache_busting
            variant_dict["template_name"] = f"{base_config.template_name}_cb_{cache_busting}"
            variants.append(ManifestConfig(**variant_dict))
        
        # Height variants for different UI modes
        for height in [200, 250, 300, 400]:
            variant_dict = base_dict.copy()
            variant_dict["requested_height"] = height
            variant_dict["template_name"] = f"{base_config.template_name}_h{height}"
            variants.append(ManifestConfig(**variant_dict))
        
        return variants
    
    async def perform_warmup(self, include_variants: bool = True) -> Dict[str, Any]:
        """
        Perform complete cache warmup.
        
        Args:
            include_variants: Whether to include feature variants
        
        Returns:
            Warmup statistics
        """
        logger.info("Starting manifest cache warmup...")
        start_time = datetime.utcnow()
        
        # Create default templates
        self.cache_manager.template_engine.create_default_templates()
        
        # Get base configurations
        configs = self.create_environment_configs()
        total_configs = len(configs)
        
        # Add feature variants if requested
        if include_variants:
            all_variants = []
            for config in configs:
                if config.environment == "production":  # Only variants for production
                    variants = self.create_feature_variants(config)
                    all_variants.extend(variants)
            
            configs.extend(all_variants)
            logger.info(f"Added {len(all_variants)} feature variants")
        
        # Perform cache warmup
        cached_count = await self.cache_manager.warm_manifest_cache(configs)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        stats = {
            "total_configs": len(configs),
            "base_configs": total_configs,
            "cached_successfully": cached_count,
            "cache_hits": self.cache_manager.metrics["cache_hits"],
            "cache_misses": self.cache_manager.metrics["cache_misses"],
            "templates_created": 4,  # default, development, staging, production
            "duration_seconds": duration,
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "success_rate": f"{cached_count / len(configs) * 100:.1f}%" if configs else "0%"
        }
        
        logger.info(f"Manifest cache warmup completed: {cached_count}/{len(configs)} configs cached in {duration:.2f}s")
        return stats


async def main():
    """Main function for running manifest cache warmup."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Manifest Template Cache Warmup')
    parser.add_argument('--action', choices=['warmup', 'invalidate', 'status'], 
                       default='warmup', help='Action to perform')
    parser.add_argument('--variants', action='store_true', 
                       help='Include feature variants during warmup')
    parser.add_argument('--pattern', type=str,
                       help='Pattern for cache invalidation')
    
    args = parser.parse_args()
    
    # Initialize service
    warmup_service = ManifestWarmupService()
    
    try:
        if args.action == 'warmup':
            stats = await warmup_service.perform_warmup(include_variants=args.variants)
            print("\n=== Manifest Cache Warmup Results ===")
            for key, value in stats.items():
                print(f"{key}: {value}")
        
        elif args.action == 'invalidate':
            count = await warmup_service.cache_manager.invalidate_manifest_cache(args.pattern)
            print(f"Invalidated {count} cache entries")
        
        elif args.action == 'status':
            # Get cache metrics
            cache_metrics = await warmup_service.cache_manager.cache_manager.get_metrics()
            manifest_metrics = warmup_service.cache_manager.metrics
            
            print("\n=== Cache Status ===")
            print(f"Redis Connection: {'Connected' if warmup_service.cache_manager.cache_manager._connected else 'Disconnected'}")
            print(f"Cache Hit Rate: {cache_metrics.get('hit_rate', 'N/A')}")
            print(f"Total Requests: {cache_metrics.get('total_requests', 0)}")
            print(f"Manifests Cached: {manifest_metrics['manifests_cached']}")
            print(f"Templates Cached: {manifest_metrics['templates_cached']}")
            
    except Exception as e:
        logger.error(f"Error during {args.action}: {e}")
        return 1
    
    finally:
        # Clean up connections
        if warmup_service.cache_manager.cache_manager:
            await warmup_service.cache_manager.cache_manager.disconnect()
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))