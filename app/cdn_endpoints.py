"""
CDN Management API Endpoints for Azure Front Door and CDN cache operations.
Provides REST API for CDN cache purging and monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Use SDK-based manager (works in container with managed identity)
from app.azure_cdn_sdk_manager import get_sdk_cdn_manager as get_cdn_manager
logger.info("Using SDK-based CDN manager")

router = APIRouter(prefix="/api/cdn", tags=["cdn-management"])


@router.get("/health")
async def cdn_health_check():
    """Simple health check for CDN endpoints."""
    return {"status": "healthy", "message": "CDN endpoints are operational"}


class CDNPurgeRequest(BaseModel):
    """Request model for CDN cache purging."""
    paths: Optional[List[str]] = None
    manifest_version: Optional[str] = None
    provider: Optional[str] = None  # "front_door", "azure_cdn", or "all"


class CDNTestRequest(BaseModel):
    """Request model for CDN functionality testing."""
    test_type: str = "basic"  # "basic", "manifest_version", "all_paths"


@router.post("/purge")
async def purge_cdn_cache(request: CDNPurgeRequest):
    """
    Purge CDN cache for specified paths or manifest version.
    
    This endpoint triggers cache purging across Azure Front Door and/or Azure CDN
    based on the specified provider. If no provider is specified, all CDNs are purged.
    """
    try:
        cdn_manager = get_cdn_manager()
        
        # Determine purge strategy
        if request.manifest_version:
            # Purge specific manifest version
            result = await cdn_manager.purge_manifest_version_cache(request.manifest_version)
            return JSONResponse(
                content={
                    "success": result.get("success", False),
                    "message": f"CDN cache purged for manifest version {request.manifest_version}",
                    "details": result
                }
            )
        
        elif request.paths:
            # Purge specific paths
            if request.provider == "front_door":
                result = await cdn_manager.purge_front_door_cache(request.paths)
            elif request.provider == "azure_cdn":
                result = await cdn_manager.purge_cdn_cache(request.paths)
            else:
                result = await cdn_manager.purge_all_caches(request.paths)
            
            return JSONResponse(
                content={
                    "success": result.get("success", False),
                    "message": f"CDN cache purged for {len(request.paths)} paths",
                    "details": result
                }
            )
        
        else:
            # Purge all manifest-related paths
            if request.provider == "front_door":
                result = await cdn_manager.purge_front_door_cache()
            elif request.provider == "azure_cdn":
                result = await cdn_manager.purge_cdn_cache()
            else:
                result = await cdn_manager.purge_all_caches()
            
            return JSONResponse(
                content={
                    "success": result.get("success", False),
                    "message": "CDN cache purged for all manifest paths",
                    "details": result
                }
            )
    
    except Exception as e:
        logger.error(f"CDN purge endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CDN purge failed: {str(e)}"
        )


@router.get("/status")
async def get_cdn_status():
    """
    Get CDN cache management status and statistics.
    
    Returns comprehensive information about CDN purge operations,
    success rates, configuration, and recent errors.
    """
    try:
        cdn_manager = get_cdn_manager()
        
        stats = await cdn_manager.get_cdn_stats()
        
        return JSONResponse(
            content={
                "success": True,
                "cdn_status": stats,
                "recommendations": _generate_cdn_recommendations(stats),
                "timestamp": stats.get("timestamp", "unknown")
            }
        )
    
    except Exception as e:
        logger.error(f"CDN status endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CDN status: {str(e)}"
        )


@router.post("/test")
async def test_cdn_functionality(request: CDNTestRequest):
    """
    Test CDN purge functionality with minimal impact.
    
    Performs various tests to validate CDN configuration and connectivity.
    Useful for monitoring and troubleshooting CDN integration.
    """
    try:
        cdn_manager = get_cdn_manager()
        
        if request.test_type == "basic":
            # Basic connectivity and authentication test
            result = await cdn_manager.test_cdn_purge()
            
        elif request.test_type == "manifest_version":
            # Test with a fake manifest version
            result = await cdn_manager.purge_manifest_version_cache("test-1.0.0")
            
        elif request.test_type == "all_paths":
            # Test purging all configured paths
            result = await cdn_manager.purge_all_caches(["/test-path.html"])
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown test type: {request.test_type}"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"CDN test '{request.test_type}' completed",
                "test_results": result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CDN test endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CDN test failed: {str(e)}"
        )


@router.get("/configuration")
async def get_cdn_configuration():
    """
    Get current CDN configuration and endpoints.
    
    Returns configuration details for troubleshooting and monitoring.
    Does not expose sensitive information like connection strings.
    """
    try:
        cdn_manager = get_cdn_manager()
        stats = await cdn_manager.get_cdn_stats()
        
        config = stats.get("configuration", {})
        
        return JSONResponse(
            content={
                "success": True,
                "configuration": {
                    "resource_group": config.get("resource_group"),
                    "frontdoor_profile": config.get("frontdoor_profile"),
                    "frontdoor_endpoint": config.get("frontdoor_endpoint"),
                    "cdn_profile": config.get("cdn_profile"),
                    "cdn_endpoint": config.get("cdn_endpoint"),
                    "azure_cli_available": stats.get("azure_cli_available", False)
                },
                "manifest_paths": config.get("manifest_paths", []),
                "purge_statistics": {
                    "total_requests": stats.get("purge_requests", 0),
                    "success_rate": stats.get("success_rate", "0%"),
                    "last_purge": stats.get("last_purge")
                }
            }
        )
    
    except Exception as e:
        logger.error(f"CDN configuration endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CDN configuration: {str(e)}"
        )


@router.post("/warmup")
async def warmup_cdn_cache():
    """
    Warm up CDN cache by pre-loading common manifest requests.
    
    This endpoint can be called after deployments to ensure
    CDN edge locations have fresh content cached.
    """
    try:
        # This is a placeholder for future implementation
        # CDN warmup typically involves making requests to the origin
        # to ensure content is cached at edge locations
        
        logger.info("CDN cache warmup requested")
        
        return JSONResponse(
            content={
                "success": True,
                "message": "CDN cache warmup initiated",
                "note": "Warmup functionality is planned for future implementation"
            }
        )
    
    except Exception as e:
        logger.error(f"CDN warmup endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CDN warmup failed: {str(e)}"
        )


def _generate_cdn_recommendations(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate CDN optimization recommendations based on statistics."""
    recommendations = []
    
    # Check success rate
    success_rate_str = stats.get("success_rate", "0%")
    success_rate = float(success_rate_str.replace("%", ""))
    
    if success_rate < 80:
        recommendations.append({
            "type": "reliability",
            "message": f"CDN purge success rate is low ({success_rate_str}). Check Azure CLI authentication and network connectivity.",
            "impact": "high"
        })
    
    # Check for recent errors
    recent_errors = stats.get("recent_errors", [])
    if len(recent_errors) > 5:
        recommendations.append({
            "type": "error_rate",
            "message": f"High error rate detected ({len(recent_errors)} errors in 24h). Review error logs and Azure service health.",
            "impact": "medium"
        })
    
    # Check Azure CLI availability
    if not stats.get("azure_cli_available", False):
        recommendations.append({
            "type": "configuration",
            "message": "Azure CLI is not available or authenticated. CDN purging will not work.",
            "impact": "critical"
        })
    
    # Check if no purges have been performed
    if stats.get("purge_requests", 0) == 0:
        recommendations.append({
            "type": "usage",
            "message": "No CDN purge operations have been performed. Test the functionality to ensure it works correctly.",
            "impact": "low"
        })
    
    return recommendations