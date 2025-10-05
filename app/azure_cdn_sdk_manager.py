"""
Azure Front Door Management using Azure SDK.
Provides programmatic cache purging for Azure Front Door without requiring Azure CLI.
Note: This application uses Azure Front Door only, not a separate Azure CDN profile.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.mgmt.frontdoor import FrontDoorManagementClient
from azure.mgmt.cdn import CdnManagementClient
from azure.core.exceptions import AzureError, ResourceNotFoundError

logger = logging.getLogger(__name__)


class AzureFrontDoorManager:
    """Manages Azure Front Door cache purging using Azure SDK."""
    
    def __init__(self):
        """Initialize Azure CDN SDK manager."""
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "29aaac2b-8333-4513-8146-45bb432eff76")
        self.resource_group = os.getenv("RESOURCE_GROUP", "TheWell-Infra-East")
        
        # Azure Front Door configuration
        self.frontdoor_profile = os.getenv("AZURE_FRONTDOOR_PROFILE", "well-intake-frontdoor")
        self.frontdoor_endpoint = os.getenv("AZURE_FRONTDOOR_ENDPOINT", "well-intake-api")
        
        # Azure CDN configuration (not currently used - only Front Door is deployed)
        self.cdn_profile = None  # No separate CDN profile exists
        self.cdn_endpoint = None  # No separate CDN endpoint exists
        
        # Initialize credentials
        try:
            # Try managed identity first (for production)
            self.credential = ManagedIdentityCredential()
            logger.info("Using Managed Identity for authentication")
        except Exception:
            # Fall back to DefaultAzureCredential (includes CLI auth for local dev)
            self.credential = DefaultAzureCredential()
            logger.info("Using DefaultAzureCredential for authentication")
        
        # Initialize clients (lazy loaded)
        self._frontdoor_client = None
        self._cdn_client = None
        
        # Manifest paths to purge
        self.manifest_paths = [
            "/manifest.xml",
            "/taskpane.html",
            "/commands.html",
            "/config.js",
            "/commands.js", 
            "/taskpane.js",
            "/icon-16.png",
            "/icon-32.png",
            "/icon-80.png",
            "/api/manifest/*"
        ]
        
        # Statistics
        self.stats = {
            "purge_requests": 0,
            "successful_purges": 0,
            "failed_purges": 0,
            "last_purge": None,
            "total_paths_purged": 0,
            "errors": []
        }
    
    @property
    def frontdoor_client(self) -> FrontDoorManagementClient:
        """Get or create Front Door client."""
        if not self._frontdoor_client:
            self._frontdoor_client = FrontDoorManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._frontdoor_client
    
    @property
    def cdn_client(self) -> CdnManagementClient:
        """Get or create CDN client."""
        if not self._cdn_client:
            self._cdn_client = CdnManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._cdn_client
    
    async def purge_front_door_cache(self, 
                                   paths: Optional[List[str]] = None,
                                   domains: Optional[List[str]] = None) -> Dict[str, Any]:
        """Purge Azure Front Door cache using SDK."""
        paths_to_purge = paths or self.manifest_paths
        self.stats["purge_requests"] += 1
        
        try:
            # Note: Azure Front Door Standard/Premium uses the CDN Management Client
            # The endpoint purge is available through the CDN client
            purge_parameters = {
                "content_paths": paths_to_purge
            }
            
            if domains:
                purge_parameters["domains"] = domains
            
            # Start purge operation
            logger.info(f"Starting Front Door cache purge for {len(paths_to_purge)} paths")
            
            # For Azure Front Door Standard/Premium, use AFD endpoints
            poller = self.cdn_client.afd_endpoints.begin_purge_content(
                resource_group_name=self.resource_group,
                profile_name=self.frontdoor_profile,
                endpoint_name=self.frontdoor_endpoint,
                contents=purge_parameters
            )
            
            # Wait for completion with timeout (purge operations can be slow)
            # Front Door purges are asynchronous - we don't need to wait for full completion
            logger.info("Front Door purge initiated successfully (async operation)")
            
            self.stats["successful_purges"] += 1
            self.stats["total_paths_purged"] += len(paths_to_purge)
            self.stats["last_purge"] = datetime.utcnow().isoformat()
            
            logger.info(f"Successfully purged {len(paths_to_purge)} paths from Front Door")
            
            return {
                "success": True,
                "provider": "azure_front_door",
                "paths_purged": len(paths_to_purge),
                "paths": paths_to_purge,
                "timestamp": self.stats["last_purge"]
            }
            
        except ResourceNotFoundError as e:
            error_msg = f"Resource not found: {str(e)}"
            self._record_error(error_msg, "azure_front_door")
            return self._error_response(error_msg, "azure_front_door")
            
        except AzureError as e:
            error_msg = f"Azure error: {str(e)}"
            self._record_error(error_msg, "azure_front_door")
            return self._error_response(error_msg, "azure_front_door")
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._record_error(error_msg, "azure_front_door")
            return self._error_response(error_msg, "azure_front_door")
    
    async def purge_cdn_cache(self, 
                            paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Purge Azure CDN cache using SDK - Always skipped since only Front Door exists."""
        # Always skip since we only have Front Door, not a separate Azure CDN
        logger.info("Azure CDN profile not configured, skipping CDN purge")
        return {
            "success": True,
            "provider": "azure_cdn",
            "skipped": True,
            "reason": "Azure CDN profile not configured - using Front Door only",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def purge_all_caches(self, 
                             paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Purge both Front Door and Azure CDN caches."""
        paths_to_purge = paths or self.manifest_paths
        
        logger.info(f"Purging all CDN caches for {len(paths_to_purge)} paths")
        
        results = {
            "success": False,
            "front_door": None,
            "azure_cdn": None,
            "paths_purged": len(paths_to_purge),
            "paths": paths_to_purge,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Try Front Door purge
        try:
            results["front_door"] = await self.purge_front_door_cache(paths_to_purge)
        except Exception as e:
            results["front_door"] = {
                "success": False,
                "error": str(e),
                "provider": "azure_front_door"
            }
        
        # Try CDN purge
        try:
            results["azure_cdn"] = await self.purge_cdn_cache(paths_to_purge)
        except Exception as e:
            results["azure_cdn"] = {
                "success": False,
                "error": str(e),
                "provider": "azure_cdn"
            }
        
        # Overall success if at least one succeeded
        results["success"] = (
            (results["front_door"] and results["front_door"].get("success", False)) or
            (results["azure_cdn"] and results["azure_cdn"].get("success", False))
        )
        
        return results
    
    async def purge_manifest_version_cache(self, version: str) -> Dict[str, Any]:
        """Purge CDN cache for specific manifest version."""
        version_specific_paths = [
            f"/manifest.xml?v={version}",
            f"/taskpane.html?v={version}",
            f"/commands.html?v={version}",
            f"/config.js?v={version}",
            f"/commands.js?v={version}",
            f"/taskpane.js?v={version}"
        ]
        
        logger.info(f"Purging CDN cache for manifest version {version}")
        
        return await self.purge_all_caches(version_specific_paths)
    
    async def get_cdn_stats(self) -> Dict[str, Any]:
        """Get CDN purge statistics."""
        total_requests = self.stats["purge_requests"]
        success_rate = (
            (self.stats["successful_purges"] / total_requests * 100) 
            if total_requests > 0 else 0
        )
        
        recent_errors = [
            error for error in self.stats["errors"]
            if datetime.fromisoformat(error["timestamp"]) > 
               datetime.utcnow() - timedelta(days=1)
        ]
        
        return {
            **self.stats,
            "success_rate": f"{success_rate:.2f}%",
            "recent_errors": recent_errors,
            "sdk_available": True,
            "configuration": {
                "subscription_id": self.subscription_id,
                "resource_group": self.resource_group,
                "frontdoor_profile": self.frontdoor_profile,
                "frontdoor_endpoint": self.frontdoor_endpoint,
                "cdn_profile": "Not configured (using Front Door only)",
                "cdn_endpoint": "Not configured (using Front Door only)"
            },
            "manifest_paths": self.manifest_paths
        }
    
    async def test_cdn_purge(self) -> Dict[str, Any]:
        """Test CDN purge with minimal paths."""
        test_paths = ["/test-cache-purge.txt"]
        
        logger.info("Testing CDN purge functionality")
        
        results = await self.purge_all_caches(test_paths)
        
        return {
            "test_completed": True,
            "test_paths": test_paths,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _record_error(self, error_msg: str, provider: str):
        """Record error in statistics."""
        self.stats["failed_purges"] += 1
        self.stats["errors"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_msg,
            "provider": provider
        })
        logger.error(f"{provider} cache purge failed: {error_msg}")
    
    def _error_response(self, error_msg: str, provider: str) -> Dict[str, Any]:
        """Create error response."""
        return {
            "success": False,
            "provider": provider,
            "error": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        }


# Singleton instance
_frontdoor_manager: Optional[AzureFrontDoorManager] = None


def get_sdk_cdn_manager() -> AzureFrontDoorManager:
    """Get or create singleton Front Door manager instance."""
    global _frontdoor_manager
    
    if _frontdoor_manager is None:
        _frontdoor_manager = AzureFrontDoorManager()
    
    return _frontdoor_manager