"""
Startup warmup service for manifest template system.

This module provides cache warming functionality that runs during
application startup to pre-populate Redis cache with common
manifest configurations.
"""

import asyncio
import logging
from typing import Dict, Any
from app.manifest_cache_service import get_manifest_cache_service

logger = logging.getLogger(__name__)


class StartupWarmupService:
    """Service for performing cache warmup during application startup."""
    
    def __init__(self):
        """Initialize the startup warmup service."""
        self.warmup_completed = False
        self.warmup_stats: Dict[str, Any] = {}
    
    async def perform_startup_warmup(self) -> Dict[str, Any]:
        """
        Perform cache warmup during application startup.
        
        This function is called during the FastAPI startup lifecycle
        to pre-warm the cache with common manifest configurations.
        
        Returns:
            Dictionary with warmup statistics
        """
        if self.warmup_completed:
            logger.info("Startup warmup already completed")
            return self.warmup_stats
        
        logger.info("Starting manifest cache warmup during application startup...")
        
        try:
            # Get the manifest cache service
            manifest_service = await get_manifest_cache_service()
            
            # Perform cache warmup with common configurations
            # Use include_variants=False for faster startup
            stats = await manifest_service.warm_cache(include_variants=False)
            
            if 'error' not in stats:
                self.warmup_completed = True
                self.warmup_stats = stats
                
                logger.info(
                    f"Startup warmup completed successfully: "
                    f"{stats.get('cached_successfully', 0)}/{stats.get('total_configs', 0)} "
                    f"configurations cached in {stats.get('duration_seconds', 0):.2f}s"
                )
                
                return stats
            else:
                logger.error(f"Startup warmup failed: {stats['error']}")
                return {"error": "Warmup failed", "details": stats}
                
        except Exception as e:
            logger.error(f"Unexpected error during startup warmup: {e}")
            return {"error": "Unexpected warmup failure", "exception": str(e)}
    
    async def schedule_background_warmup(self) -> None:
        """
        Schedule a more comprehensive warmup to run in the background.
        
        This includes feature variants and additional configurations
        that aren't needed immediately but improve cache hit rates.
        """
        if not self.warmup_completed:
            logger.warning("Basic warmup not completed, skipping background warmup")
            return
        
        logger.info("Scheduling background warmup with feature variants...")
        
        try:
            # Run background warmup after a delay to avoid startup congestion
            await asyncio.sleep(30)  # Wait 30 seconds after startup
            
            manifest_service = await get_manifest_cache_service()
            
            # Perform comprehensive warmup with variants
            stats = await manifest_service.warm_cache(include_variants=True)
            
            if 'error' not in stats:
                logger.info(
                    f"Background warmup completed: "
                    f"{stats.get('cached_successfully', 0)} total configurations cached"
                )
            else:
                logger.warning(f"Background warmup failed: {stats['error']}")
                
        except Exception as e:
            logger.error(f"Background warmup error: {e}")
    
    def get_warmup_status(self) -> Dict[str, Any]:
        """
        Get the current warmup status.
        
        Returns:
            Dictionary with warmup status information
        """
        return {
            "completed": self.warmup_completed,
            "stats": self.warmup_stats,
            "total_configs": self.warmup_stats.get('total_configs', 0),
            "cached_successfully": self.warmup_stats.get('cached_successfully', 0),
            "success_rate": self.warmup_stats.get('success_rate', '0%')
        }


# Global warmup service instance
_startup_warmup_service: StartupWarmupService = None


async def get_startup_warmup_service() -> StartupWarmupService:
    """Get or create the singleton startup warmup service."""
    global _startup_warmup_service
    
    if _startup_warmup_service is None:
        _startup_warmup_service = StartupWarmupService()
    
    return _startup_warmup_service


async def perform_manifest_startup_warmup() -> Dict[str, Any]:
    """
    Convenience function for performing startup warmup.
    
    This function is called from the FastAPI lifespan manager.
    
    Returns:
        Dictionary with warmup statistics
    """
    warmup_service = await get_startup_warmup_service()
    return await warmup_service.perform_startup_warmup()


async def schedule_background_manifest_warmup() -> None:
    """
    Convenience function for scheduling background warmup.
    
    This function schedules a comprehensive cache warmup to run
    in the background after the application has fully started.
    """
    warmup_service = await get_startup_warmup_service()
    
    # Create background task for comprehensive warmup
    asyncio.create_task(warmup_service.schedule_background_warmup())


async def get_manifest_warmup_status() -> Dict[str, Any]:
    """
    Get the current manifest warmup status.
    
    Returns:
        Dictionary with warmup status information
    """
    warmup_service = await get_startup_warmup_service()
    return warmup_service.get_warmup_status()