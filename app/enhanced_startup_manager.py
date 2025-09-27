"""
Enhanced Startup Manager

This module provides centralized application startup with:
- Graceful service initialization
- Dependency management
- Health monitoring setup
- Fallback configuration
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .config_manager import get_config_manager
from .enhanced_database_manager import get_database_manager
from .azure_service_manager import get_azure_service_manager

logger = logging.getLogger(__name__)

class StartupManager:
    """
    Manages application startup with graceful fallbacks
    
    Features:
    - Service dependency management
    - Health status tracking
    - Performance monitoring
    - Graceful degradation
    """
    
    def __init__(self):
        self.config_manager = None
        self.database_manager = None
        self.azure_service_manager = None
        self.startup_time = None
        self.services_status = {}
        self._initialized = False
    
    async def initialize_application(self, app_state) -> Dict[str, Any]:
        """
        Initialize all application services with graceful fallbacks
        
        Args:
            app_state: FastAPI application state object
            
        Returns:
            Dict with initialization results and recommendations
        """
        if self._initialized:
            return self.get_startup_summary()
        
        startup_start = datetime.utcnow()
        logger.info("Starting enhanced Well Intake API initialization...")
        
        initialization_results = {
            "started_at": startup_start.isoformat(),
            "services": {},
            "recommendations": [],
            "overall_status": "initializing"
        }
        
        try:
            # Step 1: Initialize configuration manager
            logger.info("Initializing configuration manager...")
            self.config_manager = get_config_manager()
            initialization_results["services"]["configuration"] = {
                "status": "success",
                "message": "Configuration loaded successfully"
            }
            logger.info("✅ Configuration manager initialized")
            
            # Step 2: Initialize database manager
            logger.info("Initializing enhanced database manager...")
            self.database_manager = await get_database_manager()
            
            if self.database_manager.is_available():
                app_state.enhanced_database_manager = self.database_manager
                app_state.postgres_client = self.database_manager  # Backward compatibility
                initialization_results["services"]["database"] = {
                    "status": "success",
                    "message": "Database connected with enhanced features",
                    "features": self.database_manager.state.features.to_dict()
                }
                logger.info("✅ Enhanced database manager initialized with full features")
            else:
                app_state.enhanced_database_manager = self.database_manager
                app_state.postgres_client = None  # No backward compatibility in fallback mode
                initialization_results["services"]["database"] = {
                    "status": "fallback",
                    "message": "Running without database (fallback mode)",
                    "features": {}
                }
                initialization_results["recommendations"].append(
                    "Configure DATABASE_URL to enable caching, deduplication, and learning features"
                )
                logger.warning("⚠️ Database manager initialized in fallback mode")
            
            # Step 3: Initialize Azure services
            logger.info("Initializing Azure service manager...")
            self.azure_service_manager = await get_azure_service_manager()
            app_state.azure_service_manager = self.azure_service_manager
            
            # Set individual service references for backward compatibility
            if self.azure_service_manager.is_service_available("redis"):
                app_state.redis_client = await self.azure_service_manager.get_redis_client()
                logger.info("✅ Redis cache available")
            else:
                app_state.redis_client = None
                logger.info("ℹ️ Redis cache not available - using in-memory caching")
            
            if self.azure_service_manager.is_service_available("storage"):
                app_state.storage_client = self.azure_service_manager.storage_client
                logger.info("✅ Azure Blob Storage available")
            else:
                app_state.storage_client = None
                logger.info(f"ℹ️ Azure Storage not available - using {self.azure_service_manager.storage_mode.value}")
            
            if self.azure_service_manager.is_service_available("service_bus"):
                app_state.service_bus_manager = self.azure_service_manager.service_bus_client
                logger.info("✅ Azure Service Bus available")
            else:
                app_state.service_bus_manager = None
                logger.info("ℹ️ Service Bus not available - using direct processing")
            
            if self.azure_service_manager.is_service_available("signalr"):
                app_state.signalr_manager = self.azure_service_manager.signalr_client
                logger.info("✅ Azure SignalR available")
            else:
                app_state.signalr_manager = None
                logger.info("ℹ️ SignalR not available - using basic WebSocket")
            
            if self.azure_service_manager.is_service_available("ai_search"):
                app_state.ai_search_manager = self.azure_service_manager.ai_search_client
                logger.info("✅ Azure AI Search available")
            else:
                app_state.ai_search_manager = None
                logger.info("ℹ️ AI Search not available - advanced search disabled")
            
            # Azure services summary
            azure_health = self.azure_service_manager.get_health_summary()
            initialization_results["services"]["azure"] = {
                "status": azure_health["overall_status"],
                "services": azure_health["services"],
                "storage_mode": azure_health["storage_mode"]
            }
            initialization_results["recommendations"].extend(azure_health["recommendations"])
            
            # Step 4: Initialize remaining services with graceful fallbacks
            await self._initialize_legacy_services(app_state, initialization_results)
            
            # Calculate startup time
            startup_end = datetime.utcnow()
            self.startup_time = (startup_end - startup_start).total_seconds()
            
            # Determine overall status
            failed_critical_services = 0
            total_services = len(initialization_results["services"])
            
            for service_name, service_info in initialization_results["services"].items():
                if service_info["status"] == "error" and service_name in ["configuration"]:
                    failed_critical_services += 1
            
            if failed_critical_services > 0:
                initialization_results["overall_status"] = "error"
            elif len(initialization_results["recommendations"]) > 3:
                initialization_results["overall_status"] = "degraded"
            else:
                initialization_results["overall_status"] = "healthy"
            
            initialization_results["completed_at"] = startup_end.isoformat()
            initialization_results["startup_time_seconds"] = self.startup_time
            
            self.services_status = initialization_results
            self._initialized = True
            
            logger.info(f"🚀 Well Intake API initialization completed in {self.startup_time:.2f} seconds")
            logger.info(f"📊 Status: {initialization_results['overall_status']}")
            
            if initialization_results["recommendations"]:
                logger.info("💡 Recommendations:")
                for recommendation in initialization_results["recommendations"]:
                    logger.info(f"   • {recommendation}")
            
            return initialization_results
            
        except Exception as e:
            logger.error(f"❌ Application initialization failed: {e}")
            initialization_results["overall_status"] = "error"
            initialization_results["error"] = str(e)
            initialization_results["completed_at"] = datetime.utcnow().isoformat()
            
            # Set fallback state
            self.services_status = initialization_results
            self._initialized = True
            
            return initialization_results
    
    async def _initialize_legacy_services(self, app_state, results: Dict[str, Any]):
        """Initialize services that haven't been migrated to the new managers yet"""
        
        # Initialize Zoho integration (with database dependency)
        try:
            from .integrations import ZohoIntegration
            
            app_state.zoho_integration = ZohoIntegration(
                oauth_service_url=self.config_manager.services.get("zoho", {}).get("oauth_service_url", 
                    "https://well-zoho-oauth.azurewebsites.net")
            )
            
            # Pass database client if available
            if hasattr(app_state, 'enhanced_database_manager') and app_state.enhanced_database_manager.is_available():
                app_state.zoho_integration.pg_client = app_state.enhanced_database_manager
                results["services"]["zoho"] = {
                    "status": "success",
                    "message": "Zoho integration with database caching"
                }
                logger.info("✅ Zoho integration initialized with database caching")
            else:
                results["services"]["zoho"] = {
                    "status": "success", 
                    "message": "Zoho integration without database caching"
                }
                logger.info("✅ Zoho integration initialized (no database caching)")
                
        except ImportError as e:
            results["services"]["zoho"] = {
                "status": "error",
                "message": f"Zoho integration import failed: {e}"
            }
            logger.error(f"❌ Zoho integration failed: {e}")
        except Exception as e:
            results["services"]["zoho"] = {
                "status": "error",
                "message": f"Zoho integration error: {e}"
            }
            logger.warning(f"⚠️ Zoho integration error: {e}")
        
        # Initialize Microsoft Graph client (optional)
        try:
            from .microsoft_graph_client import MicrosoftGraphClient
            
            app_state.graph_client = MicrosoftGraphClient()
            is_connected = await app_state.graph_client.test_connection()
            
            if is_connected:
                results["services"]["microsoft_graph"] = {
                    "status": "success",
                    "message": "Microsoft Graph client connected"
                }
                logger.info("✅ Microsoft Graph client initialized")
            else:
                app_state.graph_client = None
                results["services"]["microsoft_graph"] = {
                    "status": "fallback",
                    "message": "Microsoft Graph client not connected - using fallback"
                }
                logger.warning("⚠️ Microsoft Graph client not connected")
                
        except ImportError:
            app_state.graph_client = None
            results["services"]["microsoft_graph"] = {
                "status": "disabled",
                "message": "Microsoft Graph client not available"
            }
            logger.info("ℹ️ Microsoft Graph client not available")
        except Exception as e:
            app_state.graph_client = None
            results["services"]["microsoft_graph"] = {
                "status": "error",
                "message": f"Microsoft Graph client error: {e}"
            }
            logger.warning(f"⚠️ Microsoft Graph client error: {e}")
    
    def get_startup_summary(self) -> Dict[str, Any]:
        """Get startup summary and current status"""
        if not self._initialized:
            return {"status": "not_initialized"}
        
        return self.services_status.copy()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all services"""
        if not self._initialized:
            return {"status": "not_initialized"}
        
        health_summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "startup_time_seconds": self.startup_time,
            "overall_status": self.services_status.get("overall_status", "unknown")
        }
        
        # Add database health
        if self.database_manager:
            health_summary["database"] = self.database_manager.get_health_status()
        
        # Add Azure services health
        if self.azure_service_manager:
            health_summary["azure_services"] = self.azure_service_manager.get_health_summary()
        
        # Add configuration status
        if self.config_manager:
            health_summary["configuration"] = self.config_manager.get_health_status()
        
        return health_summary
    
    def get_recommendations(self) -> List[str]:
        """Get current recommendations for improving system health"""
        recommendations = []
        
        if not self._initialized:
            recommendations.append("Application not initialized")
            return recommendations
        
        # Get recommendations from each manager
        if self.config_manager:
            recommendations.extend(self.config_manager.get_fallback_recommendations())
        
        if self.azure_service_manager:
            azure_health = self.azure_service_manager.get_health_summary()
            recommendations.extend(azure_health.get("recommendations", []))
        
        # Add database recommendations
        if self.database_manager and not self.database_manager.is_available():
            recommendations.append("Database not available - some features disabled")
        
        return list(set(recommendations))  # Remove duplicates
    
    async def cleanup(self):
        """Cleanup all managers and resources"""
        logger.info("Starting application cleanup...")
        
        cleanup_tasks = []
        
        if self.database_manager:
            cleanup_tasks.append(self.database_manager.cleanup())
        
        if self.azure_service_manager:
            cleanup_tasks.append(self.azure_service_manager.cleanup())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info("Application cleanup completed")

# Global startup manager instance
_startup_manager: Optional[StartupManager] = None

def get_startup_manager() -> StartupManager:
    """Get the global startup manager instance"""
    global _startup_manager
    
    if _startup_manager is None:
        _startup_manager = StartupManager()
    
    return _startup_manager

async def initialize_application(app_state) -> Dict[str, Any]:
    """Initialize the entire application with graceful fallbacks"""
    startup_manager = get_startup_manager()
    return await startup_manager.initialize_application(app_state)

async def cleanup_application():
    """Cleanup the entire application"""
    global _startup_manager
    
    if _startup_manager:
        await _startup_manager.cleanup()
        _startup_manager = None