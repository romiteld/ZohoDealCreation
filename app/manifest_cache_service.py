"""
Redis-powered manifest cache service for dynamic Outlook Add-in manifest generation.
Provides intelligent caching, version management, and A/B testing capabilities.
"""

import os
import json
import hashlib
import logging
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Tuple, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request, HTTPException
from fastapi.responses import Response
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Supported deployment environments"""
    DEVELOPMENT = "dev"
    STAGING = "staging" 
    PRODUCTION = "prod"
    TESTING = "test"


class ManifestVariant(Enum):
    """Manifest variants for A/B testing"""
    DEFAULT = "default"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"
    BETA = "beta"


@dataclass
class ManifestMetadata:
    """Metadata for cached manifest entries"""
    version: str
    environment: Environment
    variant: ManifestVariant
    created_at: datetime
    last_accessed: datetime
    access_count: int
    cache_busting_params: Dict[str, str]


@dataclass 
class ManifestTemplate:
    """Template configuration for manifest generation"""
    base_url: str
    app_domain: str
    version: str
    display_name: str
    description: str
    provider_name: str
    support_url: str
    icon_urls: Dict[str, str]
    permissions: List[str]
    hosts: List[str]
    requirements: Dict[str, Any]
    custom_settings: Dict[str, Any] = None


class ManifestCacheService:
    """
    Comprehensive Redis-powered manifest cache service with version management,
    environment support, A/B testing, and intelligent cache busting.
    """
    
    def __init__(self, redis_manager=None):
        """
        Initialize manifest cache service.
        
        Args:
            redis_manager: Optional Redis cache manager instance
        """
        self.redis_manager = redis_manager
        self._templates: Dict[Tuple[Environment, ManifestVariant], ManifestTemplate] = {}
        
        # Cache configuration
        self.cache_ttl = timedelta(minutes=5)  # 5-minute TTL as requested
        self.metadata_ttl = timedelta(hours=24)  # Metadata retention
        self.key_prefix = "manifest"
        
        # Performance metrics
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "generation_time_ms": 0,
            "total_requests": 0,
            "a_b_test_distributions": {},
            "environment_usage": {},
            "error_count": 0,
            "last_warmup": None
        }
        
        # A/B testing configuration
        self.ab_test_enabled = os.getenv("MANIFEST_AB_TEST_ENABLED", "false").lower() == "true"
        self.ab_test_split = float(os.getenv("MANIFEST_AB_TEST_SPLIT", "0.5"))  # 50/50 split
        
        # Initialize default templates
        self._initialize_templates()
    
    async def get_redis_manager(self):
        """Get or create Redis manager instance"""
        if self.redis_manager is None:
            # Import here to avoid circular imports
            from app.redis_cache_manager import get_cache_manager
            self.redis_manager = await get_cache_manager()
        return self.redis_manager
    
    def _initialize_templates(self):
        """Initialize manifest templates for different environments"""
        
        # Get current environment from environment variable or default to production
        current_env_str = os.getenv("ENVIRONMENT", "prod").lower()
        current_env = Environment.PRODUCTION
        for env in Environment:
            if env.value == current_env_str:
                current_env = env
                break
        
        # Base URLs for different environments
        base_urls = {
            Environment.DEVELOPMENT: "http://localhost:8000",
            Environment.TESTING: "https://well-intake-api-test.azurecontainerapps.io",
            Environment.STAGING: "https://well-intake-api-staging.azurecontainerapps.io",
            Environment.PRODUCTION: "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
        }
        
        # Get current production URL from environment variable or use default
        prod_url = os.getenv("MANIFEST_BASE_URL", base_urls[Environment.PRODUCTION])
        if current_env == Environment.PRODUCTION:
            base_urls[Environment.PRODUCTION] = prod_url
        
        for env in Environment:
            base_url = base_urls.get(env, base_urls[Environment.PRODUCTION])
            
            # Default variant
            self._templates[(env, ManifestVariant.DEFAULT)] = ManifestTemplate(
                base_url=base_url,
                app_domain=base_url,
                version=os.getenv("MANIFEST_VERSION", "1.3.0.2"),
                display_name="The Well - Send to Zoho",
                description="Process recruitment emails and automatically create candidate records in Zoho CRM.",
                provider_name="The Well Recruiting Solutions",
                support_url="https://thewell.solutions/",
                icon_urls={
                    "small": f"{base_url}/icon-64.png",
                    "large": f"{base_url}/icon-128.png"
                },
                permissions=["ReadWriteItem"],
                hosts=["Mailbox"],
                requirements={
                    "sets": [{"name": "Mailbox", "min_version": "1.1"}]
                }
            )
            
            # Variant A (Enhanced UI)
            self._templates[(env, ManifestVariant.VARIANT_A)] = ManifestTemplate(
                base_url=base_url,
                app_domain=base_url,
                version=os.getenv("MANIFEST_VERSION", "1.3.1.0"),
                display_name="The Well - Smart Recruitment Assistant",
                description="AI-powered recruitment email processing with enhanced candidate matching and automated CRM integration.",
                provider_name="The Well Recruiting Solutions",
                support_url="https://thewell.solutions/support",
                icon_urls={
                    "small": f"{base_url}/icon-64-variant-a.png",
                    "large": f"{base_url}/icon-128-variant-a.png"
                },
                permissions=["ReadWriteItem", "ReadWriteMailbox"],
                hosts=["Mailbox"],
                requirements={
                    "sets": [{"name": "Mailbox", "min_version": "1.3"}]
                },
                custom_settings={
                    "enhanced_ui": True,
                    "ai_suggestions": True
                }
            )
            
            # Variant B (Simplified)
            self._templates[(env, ManifestVariant.VARIANT_B)] = ManifestTemplate(
                base_url=base_url,
                app_domain=base_url,
                version=os.getenv("MANIFEST_VERSION", "1.3.1.1"),
                display_name="Well CRM Sync",
                description="Quick and simple recruitment email processing for Zoho CRM.",
                provider_name="The Well Recruiting Solutions",
                support_url="https://thewell.solutions/",
                icon_urls={
                    "small": f"{base_url}/icon-64-simple.png",
                    "large": f"{base_url}/icon-128-simple.png"
                },
                permissions=["ReadWriteItem"],
                hosts=["Mailbox"],
                requirements={
                    "sets": [{"name": "Mailbox", "min_version": "1.1"}]
                },
                custom_settings={
                    "simplified_ui": True,
                    "quick_actions": True
                }
            )
            
            # Beta variant (Latest features)
            self._templates[(env, ManifestVariant.BETA)] = ManifestTemplate(
                base_url=base_url,
                app_domain=base_url,
                version=os.getenv("MANIFEST_BETA_VERSION", "1.4.0.0"),
                display_name="The Well - Beta Features",
                description="Try the latest recruitment processing features with real-time WebSocket integration.",
                provider_name="The Well Recruiting Solutions",
                support_url="https://thewell.solutions/beta-support",
                icon_urls={
                    "small": f"{base_url}/icon-64-beta.png",
                    "large": f"{base_url}/icon-128-beta.png"
                },
                permissions=["ReadWriteItem", "ReadWriteMailbox"],
                hosts=["Mailbox"],
                requirements={
                    "sets": [{"name": "Mailbox", "min_version": "1.4"}]
                },
                custom_settings={
                    "websocket_enabled": True,
                    "beta_features": True,
                    "real_time_updates": True
                }
            )
    
    def _generate_cache_key(self, 
                           environment: Environment, 
                           variant: ManifestVariant,
                           version: str = None,
                           timestamp: str = None) -> str:
        """
        Generate cache key for manifest.
        Pattern: manifest:{environment}:{variant}:{version}:{timestamp}
        """
        parts = [self.key_prefix, environment.value, variant.value]
        
        if version:
            parts.append(version)
        if timestamp:
            parts.append(timestamp)
            
        return ":".join(parts)
    
    def _determine_variant(self, request: Request, user_agent: str = None) -> ManifestVariant:
        """
        Determine which manifest variant to serve based on A/B testing rules
        """
        # Check for explicit variant in query parameters
        variant_param = request.query_params.get("variant", "").lower()
        if variant_param:
            try:
                return ManifestVariant(variant_param)
            except ValueError:
                logger.warning(f"Invalid variant parameter: {variant_param}")
        
        # Check for beta access
        if request.query_params.get("beta") == "true":
            return ManifestVariant.BETA
        
        # A/B testing logic
        if self.ab_test_enabled:
            user_id = self._extract_user_identifier(request)
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            
            if (hash_val % 100) / 100.0 < self.ab_test_split:
                variant = ManifestVariant.VARIANT_A
            else:
                variant = ManifestVariant.VARIANT_B
            
            # Track A/B test distribution
            variant_key = variant.value
            self.metrics["a_b_test_distributions"][variant_key] = \
                self.metrics["a_b_test_distributions"].get(variant_key, 0) + 1
            
            return variant
        
        return ManifestVariant.DEFAULT
    
    def _extract_user_identifier(self, request: Request) -> str:
        """Extract unique identifier for A/B testing"""
        # Use IP address and User-Agent as identifier
        ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        user_agent = request.headers.get("user-agent", "unknown")
        return f"{ip}:{user_agent}"
    
    def _determine_environment(self, request: Request) -> Environment:
        """Determine environment from request"""
        # Check explicit environment parameter
        env_param = request.query_params.get("env", "").lower()
        if env_param:
            for env in Environment:
                if env.value == env_param:
                    return env
        
        # Determine from host header
        host = request.headers.get("host", "")
        if "localhost" in host or "127.0.0.1" in host:
            return Environment.DEVELOPMENT
        elif "test" in host:
            return Environment.TESTING
        elif "staging" in host:
            return Environment.STAGING
        else:
            return Environment.PRODUCTION
    
    def _generate_cache_busting_params(self, request: Request) -> Dict[str, str]:
        """Generate cache-busting parameters"""
        params = {}
        
        # Timestamp parameter
        if request.query_params.get("v"):
            params["v"] = request.query_params["v"]
        elif request.query_params.get("timestamp"):
            params["timestamp"] = request.query_params["timestamp"]
        else:
            params["v"] = str(int(datetime.now().timestamp()))
        
        # Additional parameters
        if request.query_params.get("cache_bust"):
            params["cache_bust"] = request.query_params["cache_bust"]
        
        return params
    
    def _generate_manifest_xml(self, 
                              template: ManifestTemplate, 
                              variant: ManifestVariant,
                              cache_busting_params: Dict[str, str]) -> str:
        """Generate manifest XML from template"""
        
        # Create cache-busted URLs
        cache_param = f"?v={cache_busting_params.get('v', int(datetime.now().timestamp()))}"
        
        # Build the manifest XML
        root = ET.Element("OfficeApp")
        root.set("xmlns", "http://schemas.microsoft.com/office/appforoffice/1.1")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance") 
        root.set("xmlns:bt", "http://schemas.microsoft.com/office/officeappbasictypes/1.0")
        root.set("xmlns:mailappor", "http://schemas.microsoft.com/office/mailappversionoverrides/1.0")
        root.set("xsi:type", "MailApp")
        
        # Basic information
        ET.SubElement(root, "Id").text = os.getenv("MANIFEST_APP_ID", "d2422753-f7f6-4a4a-9e1e-7512f37a50e5")
        ET.SubElement(root, "Version").text = template.version
        ET.SubElement(root, "ProviderName").text = template.provider_name
        ET.SubElement(root, "DefaultLocale").text = "en-US"
        ET.SubElement(root, "DisplayName").set("DefaultValue", template.display_name)
        ET.SubElement(root, "Description").set("DefaultValue", template.description)
        
        # Icons with cache busting
        ET.SubElement(root, "IconUrl").set("DefaultValue", f"{template.icon_urls['small']}{cache_param}")
        ET.SubElement(root, "HighResolutionIconUrl").set("DefaultValue", f"{template.icon_urls['large']}{cache_param}")
        
        ET.SubElement(root, "SupportUrl").set("DefaultValue", template.support_url)
        
        # App domains
        app_domains = ET.SubElement(root, "AppDomains")
        ET.SubElement(app_domains, "AppDomain").text = template.app_domain
        ET.SubElement(app_domains, "AppDomain").text = "https://*.azurecontainerapps.io"
        
        # Hosts
        hosts = ET.SubElement(root, "Hosts")
        for host in template.hosts:
            ET.SubElement(hosts, "Host").set("Name", host)
        
        # Requirements
        requirements = ET.SubElement(root, "Requirements")
        sets = ET.SubElement(requirements, "Sets")
        sets.set("DefaultMinVersion", "1.1")
        
        for req_set in template.requirements["sets"]:
            set_elem = ET.SubElement(sets, "Set")
            set_elem.set("Name", req_set["name"])
            if "min_version" in req_set:
                set_elem.set("MinVersion", req_set["min_version"])
        
        # Form settings with cache busting
        form_settings = ET.SubElement(root, "FormSettings")
        form = ET.SubElement(form_settings, "Form")
        form.set("xsi:type", "ItemRead")
        
        desktop_settings = ET.SubElement(form, "DesktopSettings")
        ET.SubElement(desktop_settings, "SourceLocation").set(
            "DefaultValue", 
            f"{template.base_url}/taskpane.html{cache_param}"
        )
        ET.SubElement(desktop_settings, "RequestedHeight").text = "250"
        
        # Permissions
        permissions_text = " ".join(template.permissions)
        ET.SubElement(root, "Permissions").text = permissions_text
        
        # Rule
        rule = ET.SubElement(root, "Rule")
        rule.set("xsi:type", "RuleCollection")
        rule.set("Mode", "Or")
        
        item_rule = ET.SubElement(rule, "Rule")
        item_rule.set("xsi:type", "ItemIs")
        item_rule.set("ItemType", "Message")
        item_rule.set("FormType", "Read")
        
        ET.SubElement(root, "DisableEntityHighlighting").text = "false"
        
        # Version overrides with cache busting
        version_overrides = ET.SubElement(root, "VersionOverrides")
        version_overrides.set("xmlns", "http://schemas.microsoft.com/office/mailappversionoverrides")
        version_overrides.set("xsi:type", "VersionOverridesV1_0")
        
        description_elem = ET.SubElement(version_overrides, "Description")
        description_elem.set("resid", "residDescription")
        
        requirements_v2 = ET.SubElement(version_overrides, "Requirements")
        sets_v2 = ET.SubElement(requirements_v2, "Sets")
        sets_v2.set("DefaultMinVersion", "1.1")
        
        set_v2 = ET.SubElement(sets_v2, "Set")
        set_v2.set("Name", "Mailbox")
        set_v2.set("MinVersion", template.requirements["sets"][0].get("min_version", "1.1"))
        
        # Hosts
        hosts_v2 = ET.SubElement(version_overrides, "Hosts")
        host_v2 = ET.SubElement(hosts_v2, "Host")
        host_v2.set("xsi:type", "MailHost")
        
        desktop_form_factor = ET.SubElement(host_v2, "DesktopFormFactor")
        function_file = ET.SubElement(desktop_form_factor, "FunctionFile")
        function_file.set("resid", "residFunctionFileUrl")
        
        # Extension point
        extension_point = ET.SubElement(desktop_form_factor, "ExtensionPoint")
        extension_point.set("xsi:type", "MessageReadCommandSurface")
        
        office_tab = ET.SubElement(extension_point, "OfficeTab")
        office_tab.set("id", "TabDefault")
        
        group = ET.SubElement(office_tab, "Group")
        group.set("id", "msgReadGroup")
        
        label = ET.SubElement(group, "Label")
        label.set("resid", "residGroupLabel")
        
        control = ET.SubElement(group, "Control")
        control.set("xsi:type", "Button")
        control.set("id", "msgReadOpenPaneButton")
        
        control_label = ET.SubElement(control, "Label")
        control_label.set("resid", "residButtonLabel")
        
        supertip = ET.SubElement(control, "Supertip")
        ET.SubElement(supertip, "Title").set("resid", "residButtonTooltipTitle")
        ET.SubElement(supertip, "Description").set("resid", "residButtonTooltipDescription")
        
        icon = ET.SubElement(control, "Icon")
        icon16 = ET.SubElement(icon, "bt:Image")
        icon16.set("size", "16")
        icon16.set("resid", "residIcon16")
        
        icon32 = ET.SubElement(icon, "bt:Image")
        icon32.set("size", "32")
        icon32.set("resid", "residIcon32")
        
        icon80 = ET.SubElement(icon, "bt:Image")
        icon80.set("size", "80")
        icon80.set("resid", "residIcon80")
        
        action = ET.SubElement(control, "Action")
        action.set("xsi:type", "ShowTaskpane")
        
        ET.SubElement(action, "TaskpaneId").text = "ButtonId1"
        source_location = ET.SubElement(action, "SourceLocation")
        source_location.set("resid", "residTaskpaneUrl")
        
        # Resources with cache busting
        resources = ET.SubElement(version_overrides, "Resources")
        
        # Images
        images = ET.SubElement(resources, "bt:Images")
        
        for size in ["16", "32", "80"]:
            img = ET.SubElement(images, "bt:Image")
            img.set("id", f"residIcon{size}")
            img.set("DefaultValue", f"{template.base_url}/icon-{size}.png{cache_param}")
        
        # URLs  
        urls = ET.SubElement(resources, "bt:Urls")
        
        function_url = ET.SubElement(urls, "bt:Url")
        function_url.set("id", "residFunctionFileUrl")
        function_url.set("DefaultValue", f"{template.base_url}/commands.html{cache_param}")
        
        taskpane_url = ET.SubElement(urls, "bt:Url")
        taskpane_url.set("id", "residTaskpaneUrl")
        taskpane_url.set("DefaultValue", f"{template.base_url}/taskpane.html{cache_param}")
        
        # Short strings
        short_strings = ET.SubElement(resources, "bt:ShortStrings")
        
        group_label = ET.SubElement(short_strings, "bt:String")
        group_label.set("id", "residGroupLabel")
        group_label.set("DefaultValue", "Well Recruiting")
        
        button_label = ET.SubElement(short_strings, "bt:String") 
        button_label.set("id", "residButtonLabel")
        button_label.set("DefaultValue", "Send to Zoho")
        
        tooltip_title = ET.SubElement(short_strings, "bt:String")
        tooltip_title.set("id", "residButtonTooltipTitle")
        tooltip_title.set("DefaultValue", template.display_name)
        
        # Long strings
        long_strings = ET.SubElement(resources, "bt:LongStrings")
        
        description = ET.SubElement(long_strings, "bt:String")
        description.set("id", "residDescription")
        description.set("DefaultValue", template.description)
        
        tooltip_desc = ET.SubElement(long_strings, "bt:String")
        tooltip_desc.set("id", "residButtonTooltipDescription")
        tooltip_desc.set("DefaultValue", template.description)
        
        # Convert to string with pretty formatting
        ET.indent(root, space="  ")
        xml_str = ET.tostring(root, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
    
    async def get_cached_manifest(self, 
                                 environment: Environment, 
                                 variant: ManifestVariant,
                                 version: str = None,
                                 timestamp: str = None) -> Optional[Tuple[str, ManifestMetadata]]:
        """
        Retrieve cached manifest if available.
        
        Returns:
            Tuple of (manifest_xml, metadata) or None if not cached
        """
        redis_manager = await self.get_redis_manager()
        if not redis_manager._connected:
            return None
        
        try:
            cache_key = self._generate_cache_key(environment, variant, version, timestamp)
            
            # Get manifest content
            manifest_data = await redis_manager.client.get(cache_key)
            if not manifest_data:
                self.metrics["cache_misses"] += 1
                return None
            
            # Get metadata
            metadata_key = f"{cache_key}:metadata"
            metadata_data = await redis_manager.client.get(metadata_key)
            
            manifest_content = json.loads(manifest_data)
            
            if metadata_data:
                metadata_dict = json.loads(metadata_data)
                metadata = ManifestMetadata(
                    version=metadata_dict["version"],
                    environment=Environment(metadata_dict["environment"]),
                    variant=ManifestVariant(metadata_dict["variant"]),
                    created_at=datetime.fromisoformat(metadata_dict["created_at"]),
                    last_accessed=datetime.fromisoformat(metadata_dict["last_accessed"]),
                    access_count=metadata_dict["access_count"],
                    cache_busting_params=metadata_dict["cache_busting_params"]
                )
                
                # Update access statistics
                metadata.last_accessed = datetime.now()
                metadata.access_count += 1
                
                # Update metadata in cache
                updated_metadata = {
                    "version": metadata.version,
                    "environment": metadata.environment.value,
                    "variant": metadata.variant.value,
                    "created_at": metadata.created_at.isoformat(),
                    "last_accessed": metadata.last_accessed.isoformat(),
                    "access_count": metadata.access_count,
                    "cache_busting_params": metadata.cache_busting_params
                }
                await redis_manager.client.setex(
                    metadata_key,
                    int(self.metadata_ttl.total_seconds()),
                    json.dumps(updated_metadata)
                )
            else:
                # Create default metadata
                metadata = ManifestMetadata(
                    version=version or "1.0.0.0",
                    environment=environment,
                    variant=variant,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    access_count=1,
                    cache_busting_params={}
                )
            
            self.metrics["cache_hits"] += 1
            logger.info(f"Cache HIT for manifest: {cache_key}")
            
            return manifest_content["xml"], metadata
            
        except Exception as e:
            logger.error(f"Error retrieving cached manifest: {e}")
            self.metrics["error_count"] += 1
            return None
    
    async def cache_manifest(self,
                           manifest_xml: str,
                           environment: Environment,
                           variant: ManifestVariant, 
                           version: str,
                           cache_busting_params: Dict[str, str],
                           ttl: timedelta = None) -> bool:
        """
        Cache manifest with metadata.
        
        Returns:
            True if successfully cached
        """
        redis_manager = await self.get_redis_manager()
        if not redis_manager._connected:
            return False
        
        try:
            cache_key = self._generate_cache_key(
                environment, variant, version, 
                cache_busting_params.get("v")
            )
            
            ttl = ttl or self.cache_ttl
            
            # Prepare manifest data
            manifest_data = {
                "xml": manifest_xml,
                "cached_at": datetime.now().isoformat(),
                "environment": environment.value,
                "variant": variant.value
            }
            
            # Prepare metadata
            metadata = {
                "version": version,
                "environment": environment.value,
                "variant": variant.value,
                "created_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "access_count": 0,
                "cache_busting_params": cache_busting_params
            }
            
            # Cache manifest and metadata
            await redis_manager.client.setex(
                cache_key,
                int(ttl.total_seconds()),
                json.dumps(manifest_data)
            )
            
            metadata_key = f"{cache_key}:metadata"
            await redis_manager.client.setex(
                metadata_key,
                int(self.metadata_ttl.total_seconds()),
                json.dumps(metadata)
            )
            
            logger.info(f"Cached manifest: {cache_key} with TTL: {ttl}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching manifest: {e}")
            self.metrics["error_count"] += 1
            return False
    
    async def generate_manifest(self, request: Request) -> Tuple[str, Dict[str, Any]]:
        """
        Generate or retrieve cached manifest based on request.
        
        Returns:
            Tuple of (manifest_xml, response_headers)
        """
        start_time = datetime.now()
        
        try:
            # Determine request parameters
            environment = self._determine_environment(request)
            variant = self._determine_variant(request)
            cache_busting_params = self._generate_cache_busting_params(request)
            
            # Update metrics
            self.metrics["total_requests"] += 1
            self.metrics["environment_usage"][environment.value] = \
                self.metrics["environment_usage"].get(environment.value, 0) + 1
            
            # Check cache first
            cached_result = await self.get_cached_manifest(
                environment, variant, 
                cache_busting_params.get("v")
            )
            
            if cached_result:
                manifest_xml, metadata = cached_result
                
                # Prepare response headers
                headers = {
                    "Content-Type": "application/xml; charset=utf-8",
                    "Cache-Control": "public, max-age=300",  # 5 minutes browser cache
                    "ETag": f'"{hashlib.md5(manifest_xml.encode()).hexdigest()}"',
                    "X-Manifest-Source": "cache",
                    "X-Manifest-Environment": environment.value,
                    "X-Manifest-Variant": variant.value,
                    "X-Cache-Created": metadata.created_at.isoformat(),
                    "X-Access-Count": str(metadata.access_count)
                }
                
                return manifest_xml, headers
            
            # Generate new manifest
            template_key = (environment, variant)
            if template_key not in self._templates:
                # Fallback to default template
                template_key = (environment, ManifestVariant.DEFAULT)
                if template_key not in self._templates:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"No template found for {environment.value}/{variant.value}"
                    )
            
            template = self._templates[template_key]
            manifest_xml = self._generate_manifest_xml(template, variant, cache_busting_params)
            
            # Cache the generated manifest
            await self.cache_manifest(
                manifest_xml, environment, variant,
                template.version, cache_busting_params
            )
            
            # Calculate generation time
            generation_time = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics["generation_time_ms"] = generation_time
            
            # Prepare response headers
            headers = {
                "Content-Type": "application/xml; charset=utf-8",
                "Cache-Control": "public, max-age=300",  # 5 minutes browser cache
                "ETag": f'"{hashlib.md5(manifest_xml.encode()).hexdigest()}"',
                "X-Manifest-Source": "generated",
                "X-Manifest-Environment": environment.value,
                "X-Manifest-Variant": variant.value,
                "X-Generation-Time-Ms": str(int(generation_time))
            }
            
            logger.info(f"Generated manifest for {environment.value}/{variant.value} in {generation_time:.2f}ms")
            
            return manifest_xml, headers
            
        except Exception as e:
            self.metrics["error_count"] += 1
            logger.error(f"Error generating manifest: {e}")
            raise HTTPException(status_code=500, detail=f"Manifest generation failed: {str(e)}")
    
    async def invalidate_cache(self, 
                             environment: Environment = None,
                             variant: ManifestVariant = None,
                             pattern: str = None) -> int:
        """
        Invalidate cached manifests with instant invalidation.
        
        Args:
            environment: Specific environment to invalidate
            variant: Specific variant to invalidate  
            pattern: Custom Redis pattern to match
            
        Returns:
            Number of cache entries invalidated
        """
        redis_manager = await self.get_redis_manager()
        if not redis_manager._connected:
            return 0
        
        try:
            if pattern:
                search_pattern = pattern
            else:
                # Build pattern based on parameters
                parts = [self.key_prefix]
                if environment:
                    parts.append(environment.value)
                    if variant:
                        parts.append(variant.value)
                        parts.append("*")
                    else:
                        parts.append("*")
                else:
                    parts.append("*")
                
                search_pattern = ":".join(parts)
            
            # Find and delete matching keys (including metadata)
            deleted_count = 0
            async for key in redis_manager.client.scan_iter(match=search_pattern):
                await redis_manager.client.delete(key)
                deleted_count += 1
                
                # Also delete corresponding metadata
                metadata_key = f"{key}:metadata"
                if await redis_manager.client.exists(metadata_key):
                    await redis_manager.client.delete(metadata_key)
                    deleted_count += 1
            
            logger.info(f"Invalidated {deleted_count} manifest cache entries with pattern: {search_pattern}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error invalidating manifest cache: {e}")
            self.metrics["error_count"] += 1
            return 0
    
    async def update_template(self, 
                            environment: Environment,
                            variant: ManifestVariant, 
                            template_updates: Dict[str, Any]) -> bool:
        """
        Update manifest template and invalidate related cache entries.
        
        Args:
            environment: Target environment
            variant: Target variant
            template_updates: Dictionary of template fields to update
            
        Returns:
            True if successfully updated
        """
        try:
            template_key = (environment, variant)
            if template_key not in self._templates:
                logger.error(f"Template not found: {environment.value}/{variant.value}")
                return False
            
            # Update template
            template = self._templates[template_key]
            for field, value in template_updates.items():
                if hasattr(template, field):
                    setattr(template, field, value)
                else:
                    logger.warning(f"Unknown template field: {field}")
            
            # Invalidate related cache entries
            await self.invalidate_cache(environment, variant)
            
            logger.info(f"Updated template for {environment.value}/{variant.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating template: {e}")
            return False
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """
        Get comprehensive cache status and metrics.
        
        Returns:
            Dictionary with cache statistics, A/B testing data, and performance metrics
        """
        redis_manager = await self.get_redis_manager()
        
        status = {
            "cache_metrics": self.metrics.copy(),
            "redis_connected": redis_manager._connected if redis_manager else False,
            "cache_ttl_minutes": self.cache_ttl.total_seconds() / 60,
            "ab_test_enabled": self.ab_test_enabled,
            "ab_test_split": self.ab_test_split,
            "environments": [env.value for env in Environment],
            "variants": [variant.value for variant in ManifestVariant],
            "templates_configured": len(self._templates)
        }
        
        if redis_manager and redis_manager._connected:
            try:
                # Get cache key count
                cache_keys = []
                async for key in redis_manager.client.scan_iter(match=f"{self.key_prefix}:*"):
                    if not key.endswith(":metadata"):
                        cache_keys.append(key)
                
                status["cached_manifests"] = len(cache_keys)
                
                # Get Redis info
                redis_info = await redis_manager.client.info()
                status["redis_memory_used"] = redis_info.get("used_memory_human", "Unknown")
                status["redis_connected_clients"] = redis_info.get("connected_clients", 0)
                
            except Exception as e:
                logger.error(f"Error getting Redis status: {e}")
                status["redis_error"] = str(e)
        
        # Calculate performance metrics
        total_requests = status["cache_metrics"]["total_requests"]
        if total_requests > 0:
            hit_rate = (status["cache_metrics"]["cache_hits"] / total_requests) * 100
            status["cache_hit_rate"] = f"{hit_rate:.2f}%"
        else:
            status["cache_hit_rate"] = "N/A"
        
        return status
    
    async def warmup_cache(self, environments: List[Environment] = None) -> Dict[str, int]:
        """
        Pre-warm cache with manifest variants for specified environments.
        
        Args:
            environments: List of environments to warm up (defaults to all)
            
        Returns:
            Dictionary with warmup results per environment
        """
        if environments is None:
            environments = list(Environment)
        
        results = {}
        
        for environment in environments:
            env_results = {"success": 0, "errors": 0}
            
            for variant in ManifestVariant:
                try:
                    template_key = (environment, variant)
                    if template_key not in self._templates:
                        continue
                    
                    template = self._templates[template_key]
                    cache_busting_params = {"v": str(int(datetime.now().timestamp()))}
                    
                    manifest_xml = self._generate_manifest_xml(template, variant, cache_busting_params)
                    
                    success = await self.cache_manifest(
                        manifest_xml, environment, variant,
                        template.version, cache_busting_params
                    )
                    
                    if success:
                        env_results["success"] += 1
                    else:
                        env_results["errors"] += 1
                        
                except Exception as e:
                    logger.error(f"Error warming up {environment.value}/{variant.value}: {e}")
                    env_results["errors"] += 1
            
            results[environment.value] = env_results
        
        # Update last warmup time tracking
        self.metrics["last_warmup"] = datetime.now().isoformat()
        
        logger.info(f"Cache warmup completed: {results}")
        return results


# Singleton instance
_manifest_cache_service: Optional[ManifestCacheService] = None


async def get_manifest_cache_service() -> ManifestCacheService:
    """Get or create the singleton manifest cache service instance."""
    global _manifest_cache_service
    
    if _manifest_cache_service is None:
        _manifest_cache_service = ManifestCacheService()
    
    return _manifest_cache_service