"""
FastAPI endpoints for manifest template system integration.

Provides enhanced manifest generation with cache warming, template management,
and dynamic manifest generation with environment-specific configurations.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel

# Import the manifest template system
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.manifest_warmup import (
    ManifestConfig, 
    ManifestTemplateEngine, 
    ManifestCacheManager, 
    ManifestWarmupService
)
from app.redis_cache_manager import get_cache_manager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/manifest", tags=["manifest"])

# Global instances
_template_engine: Optional[ManifestTemplateEngine] = None
_cache_manager: Optional[ManifestCacheManager] = None
_warmup_service: Optional[ManifestWarmupService] = None


async def get_template_engine() -> ManifestTemplateEngine:
    """Get or create the template engine instance."""
    global _template_engine
    if _template_engine is None:
        _template_engine = ManifestTemplateEngine()
        _template_engine.create_default_templates()
    return _template_engine


async def get_manifest_cache_manager() -> ManifestCacheManager:
    """Get or create the manifest cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        redis_cache = await get_cache_manager()
        _cache_manager = ManifestCacheManager(redis_cache)
    return _cache_manager


async def get_warmup_service() -> ManifestWarmupService:
    """Get or create the warmup service instance."""
    global _warmup_service
    if _warmup_service is None:
        cache_manager = await get_manifest_cache_manager()
        _warmup_service = ManifestWarmupService()
        # Use the same cache manager instance
        _warmup_service.cache_manager = cache_manager
    return _warmup_service


# Pydantic models for API
class ManifestConfigRequest(BaseModel):
    """Request model for manifest generation."""
    app_id: str = "d2422753-f7f6-4a4a-9e1e-7512f37a50e5"
    version: str = "1.3.0.2"
    provider_name: str = "The Well Recruiting Solutions"
    app_name: str = "The Well - Send to Zoho"
    description: str = "Process recruitment emails and automatically create candidate records in Zoho CRM."
    api_base_url: str = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
    environment: str = "production"
    template_name: str = "default"
    cache_busting: bool = True
    websocket_enabled: bool = False
    requested_height: int = 250


class WarmupRequest(BaseModel):
    """Request model for cache warmup."""
    include_variants: bool = True
    force_refresh: bool = False


class WarmupResponse(BaseModel):
    """Response model for cache warmup."""
    success: bool
    stats: Dict[str, Any]
    message: str


class TemplateListResponse(BaseModel):
    """Response model for template listing."""
    templates: List[str]
    total_count: int


class CacheStatusResponse(BaseModel):
    """Response model for cache status."""
    connected: bool
    total_manifests_cached: int
    cache_hit_rate: str
    redis_memory_used: str
    last_warmup: Optional[str]


# API Endpoints

@router.get("/generate")
async def generate_manifest(
    request: Request,
    environment: str = Query("production", description="Target environment"),
    version: str = Query("1.3.0.2", description="App version"),
    template: str = Query("default", description="Template name"),
    cache_busting: bool = Query(True, description="Enable cache busting"),
    websocket: bool = Query(False, description="Enable WebSocket features"),
    height: int = Query(250, description="Requested height in pixels"),
    cache_manager: ManifestCacheManager = Depends(get_manifest_cache_manager),
    template_engine: ManifestTemplateEngine = Depends(get_template_engine)
):
    """
    Generate manifest XML dynamically with caching.
    
    This endpoint generates a manifest on-demand with the specified parameters.
    Results are cached for performance optimization.
    """
    try:
        # Build manifest configuration
        config = ManifestConfig(
            app_id="d2422753-f7f6-4a4a-9e1e-7512f37a50e5",
            version=version,
            provider_name="The Well Recruiting Solutions",
            app_name="The Well - Send to Zoho",
            description="Process recruitment emails and automatically create candidate records in Zoho CRM.",
            api_base_url=str(request.base_url).rstrip('/'),
            environment=environment,
            template_name=template,
            cache_busting=cache_busting,
            websocket_enabled=websocket,
            requested_height=height,
            app_domains=[str(request.base_url).rstrip('/'), "https://*.azurecontainerapps.io"],
            icon_16=f"{request.base_url}icon-16.png",
            icon_32=f"{request.base_url}icon-32.png",
            icon_64=f"{request.base_url}icon-64.png",
            icon_80=f"{request.base_url}icon-80.png",
            icon_128=f"{request.base_url}icon-128.png"
        )
        
        # Check cache first
        config_hash = cache_manager._hash_config(config)
        cached_manifest = await cache_manager.get_cached_manifest(config_hash, template)
        
        if cached_manifest:
            logger.info(f"Serving cached manifest for {environment}/{version}/{template}")
            return FastAPIResponse(
                content=cached_manifest,
                media_type="application/xml",
                headers={"X-Cache-Status": "HIT"}
            )
        
        # Generate manifest
        manifest_xml = template_engine.render_manifest(config)
        
        # Cache the result
        await cache_manager.cache_manifest(config, manifest_xml, config_hash)
        
        logger.info(f"Generated and cached manifest for {environment}/{version}/{template}")
        
        return FastAPIResponse(
            content=manifest_xml,
            media_type="application/xml",
            headers={"X-Cache-Status": "MISS"}
        )
        
    except Exception as e:
        logger.error(f"Error generating manifest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate manifest: {str(e)}")


@router.post("/generate")
async def generate_custom_manifest(
    config_request: ManifestConfigRequest,
    request: Request,
    cache_manager: ManifestCacheManager = Depends(get_manifest_cache_manager),
    template_engine: ManifestTemplateEngine = Depends(get_template_engine)
):
    """
    Generate manifest XML from custom configuration.
    
    Allows full customization of manifest parameters via POST request body.
    """
    try:
        # Use request base URL if not provided
        if not config_request.api_base_url or config_request.api_base_url == "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io":
            api_base_url = str(request.base_url).rstrip('/')
        else:
            api_base_url = config_request.api_base_url
        
        # Build full configuration
        config = ManifestConfig(
            **config_request.dict(),
            api_base_url=api_base_url,
            app_domains=[api_base_url, "https://*.azurecontainerapps.io"],
            icon_16=f"{api_base_url}/icon-16.png",
            icon_32=f"{api_base_url}/icon-32.png",
            icon_64=f"{api_base_url}/icon-64.png",
            icon_80=f"{api_base_url}/icon-80.png",
            icon_128=f"{api_base_url}/icon-128.png"
        )
        
        # Check cache first
        config_hash = cache_manager._hash_config(config)
        cached_manifest = await cache_manager.get_cached_manifest(config_hash, config.template_name)
        
        if cached_manifest:
            return FastAPIResponse(
                content=cached_manifest,
                media_type="application/xml",
                headers={"X-Cache-Status": "HIT"}
            )
        
        # Generate manifest
        manifest_xml = template_engine.render_manifest(config)
        
        # Cache the result
        await cache_manager.cache_manifest(config, manifest_xml, config_hash)
        
        return FastAPIResponse(
            content=manifest_xml,
            media_type="application/xml",
            headers={"X-Cache-Status": "MISS"}
        )
        
    except Exception as e:
        logger.error(f"Error generating custom manifest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate manifest: {str(e)}")


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    template_engine: ManifestTemplateEngine = Depends(get_template_engine)
):
    """List available manifest templates."""
    try:
        templates_dir = template_engine.templates_dir
        templates = []
        
        if os.path.exists(templates_dir):
            for filename in os.listdir(templates_dir):
                if filename.endswith('.xml'):
                    templates.append(filename[:-4])  # Remove .xml extension
        
        return TemplateListResponse(
            templates=templates,
            total_count=len(templates)
        )
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.get("/templates/{template_name}")
async def get_template_content(
    template_name: str,
    template_engine: ManifestTemplateEngine = Depends(get_template_engine)
):
    """Get raw template content for inspection."""
    try:
        template_file = f"{template_name}.xml"
        template_path = os.path.join(template_engine.templates_dir, template_file)
        
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return FastAPIResponse(
            content=content,
            media_type="text/plain"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading template {template_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read template: {str(e)}")


@router.post("/warmup", response_model=WarmupResponse)
async def warmup_cache(
    warmup_request: WarmupRequest = WarmupRequest(),
    warmup_service: ManifestWarmupService = Depends(get_warmup_service)
):
    """
    Warm up the manifest cache with common configurations.
    
    This endpoint pre-generates and caches common manifest variants
    to improve performance during actual requests.
    """
    try:
        # Invalidate cache first if force refresh requested
        if warmup_request.force_refresh:
            await warmup_service.cache_manager.invalidate_manifest_cache()
            logger.info("Cache invalidated before warmup")
        
        # Perform cache warmup
        stats = await warmup_service.perform_warmup(
            include_variants=warmup_request.include_variants
        )
        
        return WarmupResponse(
            success=True,
            stats=stats,
            message=f"Cache warmed successfully. Cached {stats['cached_successfully']}/{stats['total_configs']} configurations."
        )
        
    except Exception as e:
        logger.error(f"Error during cache warmup: {e}")
        return WarmupResponse(
            success=False,
            stats={},
            message=f"Cache warmup failed: {str(e)}"
        )


@router.get("/cache/status", response_model=CacheStatusResponse)
async def get_cache_status(
    cache_manager: ManifestCacheManager = Depends(get_manifest_cache_manager)
):
    """Get manifest cache status and metrics."""
    try:
        # Get Redis metrics
        redis_metrics = await cache_manager.cache_manager.get_metrics()
        
        return CacheStatusResponse(
            connected=cache_manager.cache_manager._connected,
            total_manifests_cached=cache_manager.metrics["manifests_cached"],
            cache_hit_rate=redis_metrics.get("hit_rate", "0%"),
            redis_memory_used=redis_metrics.get("redis_memory_used", "N/A"),
            last_warmup=cache_manager.metrics.get("last_warmup")
        )
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache status: {str(e)}")


@router.post("/cache/invalidate")
async def invalidate_cache(
    pattern: Optional[str] = None,
    cache_manager: ManifestCacheManager = Depends(get_manifest_cache_manager)
):
    """Invalidate manifest cache entries."""
    try:
        deleted_count = await cache_manager.invalidate_manifest_cache(pattern)
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "pattern": pattern or "well:manifest:*",
            "message": f"Invalidated {deleted_count} cache entries"
        }
        
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")


@router.get("/environments")
async def list_environments():
    """List available environment configurations."""
    return {
        "environments": [
            {
                "name": "development",
                "description": "Local development with debug features",
                "default_url": "http://localhost:8000"
            },
            {
                "name": "staging",
                "description": "Staging environment for testing",
                "default_url": "https://well-intake-api-staging.azurecontainerapps.io"
            },
            {
                "name": "production",
                "description": "Production environment",
                "default_url": "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
            }
        ],
        "default_config": {
            "app_id": "d2422753-f7f6-4a4a-9e1e-7512f37a50e5",
            "provider_name": "The Well Recruiting Solutions",
            "app_name": "The Well - Send to Zoho",
            "description": "Process recruitment emails and automatically create candidate records in Zoho CRM.",
            "requested_height": 250,
            "permissions": "ReadWriteItem"
        }
    }