"""
Enhanced Main.py Patch

This patch replaces the lifespan function in main.py with our new enhanced startup system.
Apply this patch by copying the lifespan function and health endpoint updates.
"""

from contextlib import asynccontextmanager
import logging
from .enhanced_startup_manager import initialize_application, cleanup_application, get_startup_manager

logger = logging.getLogger(__name__)

# Replace the existing lifespan function with this enhanced version
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifecycle management with graceful fallbacks"""
    
    # Startup Phase
    logger.info("🚀 Starting Well Intake API with enhanced configuration and fallback management")
    
    try:
        # Initialize all services using the enhanced startup manager
        initialization_results = await initialize_application(app.state)
        
        # Store initialization results for health reporting
        app.state.initialization_results = initialization_results
        
        # Log startup summary
        status = initialization_results.get("overall_status", "unknown")
        startup_time = initialization_results.get("startup_time_seconds", 0)
        
        if status == "healthy":
            logger.info(f"✅ Application started successfully in {startup_time:.2f}s")
        elif status == "degraded":
            logger.warning(f"⚠️ Application started with degraded features in {startup_time:.2f}s")
            logger.warning("Some services are unavailable - check configuration")
        elif status == "error":
            logger.error(f"❌ Application started with errors in {startup_time:.2f}s")
            logger.error("Critical services failed - check logs and configuration")
        else:
            logger.info(f"ℹ️ Application started with status: {status} in {startup_time:.2f}s")
        
        # Log recommendations if any
        recommendations = initialization_results.get("recommendations", [])
        if recommendations:
            logger.info("💡 Configuration Recommendations:")
            for i, recommendation in enumerate(recommendations, 1):
                logger.info(f"   {i}. {recommendation}")
        
        # Log service status summary
        services = initialization_results.get("services", {})
        enabled_count = sum(1 for s in services.values() if s.get("status") == "success")
        total_count = len(services)
        logger.info(f"📊 Services Status: {enabled_count}/{total_count} fully operational")
        
    except Exception as e:
        logger.error(f"❌ Critical error during application startup: {e}")
        # Store error for health reporting
        app.state.initialization_results = {
            "overall_status": "critical_error",
            "error": str(e),
            "services": {},
            "recommendations": ["Check application logs for critical startup errors"]
        }
        # Don't re-raise - allow application to start in emergency mode
    
    # Application is now running
    yield
    
    # Shutdown Phase
    logger.info("🔄 Shutting down Well Intake API...")
    
    try:
        # Use the enhanced cleanup system
        await cleanup_application()
        logger.info("✅ Application shutdown completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error during application shutdown: {e}")
        # Continue shutdown even if cleanup fails


# Enhanced health endpoint - replace the existing one
@app.get("/health")
async def enhanced_health_check():
    """
    Enhanced health check with comprehensive service status
    
    Returns detailed health information including:
    - Overall application status
    - Individual service health
    - Configuration recommendations
    - Performance metrics
    """
    try:
        startup_manager = get_startup_manager()
        
        # Get comprehensive health status
        health_status = startup_manager.get_health_status()
        
        # Add basic API health
        health_status.update({
            "api": {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "enhanced"
            }
        })
        
        # Determine HTTP status code based on overall health
        overall_status = health_status.get("overall_status", "unknown")
        
        if overall_status in ["healthy", "degraded"]:
            status_code = 200
        elif overall_status in ["warning"]:
            status_code = 200  # Still operational
        else:
            status_code = 503  # Service unavailable
        
        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "api": {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                "overall_status": "error"
            }
        )


# Enhanced system status endpoint - add this new endpoint
@app.get("/status/system")
async def system_status():
    """
    Comprehensive system status including configuration and recommendations
    
    Returns:
    - Service availability
    - Configuration status
    - Performance metrics  
    - Recommendations for improvement
    """
    try:
        startup_manager = get_startup_manager()
        
        # Get full system status
        system_status = {
            "health": startup_manager.get_health_status(),
            "recommendations": startup_manager.get_recommendations(),
            "initialization": startup_manager.get_startup_summary()
        }
        
        return system_status
        
    except Exception as e:
        logger.error(f"System status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"System status check failed: {str(e)}"
        )


# Configuration status endpoint - add this new endpoint  
@app.get("/status/config")
async def config_status():
    """
    Configuration status and recommendations
    
    Returns:
    - Service configuration status
    - Missing configurations
    - Security recommendations
    - Performance optimization suggestions
    """
    try:
        from .config_manager import get_config_manager
        
        config_manager = get_config_manager()
        
        config_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": config_manager.get_health_status(),
            "recommendations": config_manager.get_fallback_recommendations(),
            "database": {
                "enabled": config_manager.database.enabled,
                "configured": bool(config_manager.database.url)
            },
            "security": {
                "api_key_configured": bool(config_manager.security.api_key),
                "rate_limiting": config_manager.security.rate_limit_enabled,
                "cors_configured": len(config_manager.security.cors_origins) > 0
            }
        }
        
        return config_status
        
    except Exception as e:
        logger.error(f"Configuration status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration status check failed: {str(e)}"
        )


# Service dependencies endpoint - add this new endpoint
@app.get("/status/dependencies")
async def service_dependencies():
    """
    Service dependency status and fallback modes
    
    Returns:
    - Azure service availability
    - Fallback modes in use
    - Circuit breaker status
    - Performance metrics
    """
    try:
        from .azure_service_manager import get_azure_service_manager
        from .enhanced_database_manager import get_database_manager
        
        azure_manager = await get_azure_service_manager()
        db_manager = await get_database_manager()
        
        dependencies_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_manager.get_health_status(),
            "azure_services": azure_manager.get_health_summary(),
            "fallback_modes": {
                "database": not db_manager.is_available(),
                "storage": azure_manager.get_storage_mode().value != "azure_blob",
                "cache": not azure_manager.is_service_available("redis"),
                "batch_processing": not azure_manager.is_service_available("service_bus"),
                "real_time": not azure_manager.is_service_available("signalr")
            }
        }
        
        return dependencies_status
        
    except Exception as e:
        logger.error(f"Dependencies status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Dependencies status check failed: {str(e)}"
        )