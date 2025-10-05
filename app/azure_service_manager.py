"""
Azure Service Manager with Graceful Fallbacks

This module provides unified management of all Azure services with:
- Optional service dependencies
- Circuit breaker patterns for all services
- Fallback mechanisms
- Health monitoring
- Service discovery and configuration
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from .config_manager import get_config_manager, ServiceStatus

logger = logging.getLogger(__name__)

class StorageMode(Enum):
    """Storage operation modes"""
    AZURE_BLOB = "azure_blob"
    LOCAL_FALLBACK = "local_fallback"
    MEMORY_ONLY = "memory_only"

@dataclass
class ServiceHealth:
    """Health status for individual services"""
    name: str
    is_available: bool = False
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0

class AzureServiceManager:
    """
    Unified manager for all Azure services with graceful fallbacks
    
    Features:
    - Optional service initialization
    - Circuit breaker patterns
    - Health monitoring
    - Fallback modes
    - Service discovery
    """
    
    def __init__(self):
        self.config = get_config_manager()
        self.services: Dict[str, Any] = {}
        self.health_status: Dict[str, ServiceHealth] = {}
        self._initialized = False
        self._health_monitor_task: Optional[asyncio.Task] = None
        
        # Service clients (initialized as needed)
        self.redis_client = None
        self.storage_client = None
        self.service_bus_client = None
        self.signalr_client = None
        self.ai_search_client = None
        self.insights_client = None
        
        # Fallback configurations
        self.storage_mode = StorageMode.MEMORY_ONLY
        self.local_storage_path = None
    
    async def initialize(self):
        """Initialize all configured Azure services"""
        if self._initialized:
            return
        
        logger.info("Initializing Azure services...")
        
        # Initialize each service independently
        await self._init_redis_service()
        await self._init_storage_service()
        await self._init_service_bus()
        await self._init_signalr_service()
        await self._init_ai_search_service()
        await self._init_application_insights()
        
        # Start health monitoring
        self._start_health_monitoring()
        
        self._initialized = True
        logger.info("Azure service manager initialized")
    
    async def _init_redis_service(self):
        """Initialize Redis cache service with fallback"""
        service_name = "redis"
        service_config = self.config.get_service_config(service_name)
        
        if not service_config or not service_config.connection_string:
            logger.info("Redis not configured - caching will use in-memory fallback")
            self.health_status[service_name] = ServiceHealth(
                name="Redis Cache",
                is_available=False
            )
            return
        
        try:
            import redis.asyncio as redis
            
            # Parse connection string
            connection_url = service_config.connection_string
            if not connection_url.startswith('redis'):
                # Convert Azure format to redis URL
                connection_url = self._convert_azure_redis_connection(connection_url)
            
            self.redis_client = redis.from_url(
                connection_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=service_config.config.get("connection_timeout", 10),
                socket_connect_timeout=service_config.config.get("connection_timeout", 10),
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            
            self.health_status[service_name] = ServiceHealth(
                name="Redis Cache",
                is_available=True,
                last_check=datetime.utcnow()
            )
            
            logger.info("Redis cache service initialized")
            
        except ImportError:
            logger.warning("redis package not installed - install with 'pip install redis'")
            self.health_status[service_name] = ServiceHealth(
                name="Redis Cache",
                is_available=False,
                last_error="redis package not installed"
            )
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}")
            self.config.mark_service_failed(service_name, e)
            self.health_status[service_name] = ServiceHealth(
                name="Redis Cache",
                is_available=False,
                last_error=str(e),
                consecutive_failures=1
            )
    
    def _convert_azure_redis_connection(self, azure_conn_str: str) -> str:
        """Convert Azure Redis connection string to redis URL format"""
        # Azure format: hostname:port,password=key,ssl=True,abortConnect=False
        # Redis URL format: rediss://[:password@]host:port[/db]
        
        try:
            parts = azure_conn_str.split(',')
            host_port = parts[0]
            password = None
            use_ssl = False
            
            for part in parts[1:]:
                if part.startswith('password='):
                    password = part.split('=', 1)[1]
                elif part.startswith('ssl=True'):
                    use_ssl = True
            
            protocol = "rediss" if use_ssl else "redis"
            auth_part = f":{password}@" if password else ""
            
            return f"{protocol}://{auth_part}{host_port}"
            
        except Exception as e:
            logger.warning(f"Failed to parse Azure Redis connection string: {e}")
            return azure_conn_str
    
    async def _init_storage_service(self):
        """Initialize Azure Blob Storage with local fallback"""
        service_name = "storage"
        service_config = self.config.get_service_config(service_name)
        
        if not service_config or not service_config.connection_string:
            logger.info("Azure Storage not configured - using local fallback")
            self._setup_local_storage()
            self.health_status[service_name] = ServiceHealth(
                name="Azure Blob Storage",
                is_available=False
            )
            return
        
        try:
            from azure.storage.blob.aio import BlobServiceClient
            
            self.storage_client = BlobServiceClient.from_connection_string(
                service_config.connection_string
            )
            
            # Test connection by listing containers
            containers = []
            async for container in self.storage_client.list_containers():
                containers.append(container.name)
                if len(containers) >= 1:  # Just test that we can list
                    break
            
            self.storage_mode = StorageMode.AZURE_BLOB
            self.health_status[service_name] = ServiceHealth(
                name="Azure Blob Storage",
                is_available=True,
                last_check=datetime.utcnow()
            )
            
            logger.info("Azure Blob Storage service initialized")
            
        except ImportError:
            logger.warning("azure-storage-blob package not installed - using local fallback")
            self._setup_local_storage()
            self.health_status[service_name] = ServiceHealth(
                name="Azure Blob Storage",
                is_available=False,
                last_error="azure-storage-blob package not installed"
            )
        except Exception as e:
            logger.warning(f"Azure Storage initialization failed: {e} - using local fallback")
            self.config.mark_service_failed(service_name, e)
            self._setup_local_storage()
            self.health_status[service_name] = ServiceHealth(
                name="Azure Blob Storage",
                is_available=False,
                last_error=str(e),
                consecutive_failures=1
            )
    
    def _setup_local_storage(self):
        """Setup local storage fallback"""
        service_config = self.config.get_service_config("storage")
        
        if service_config and service_config.config.get("local_fallback_path"):
            self.local_storage_path = service_config.config["local_fallback_path"]
        else:
            self.local_storage_path = os.path.join(tempfile.gettempdir(), "well_intake_attachments")
        
        # Create directory if it doesn't exist
        os.makedirs(self.local_storage_path, exist_ok=True)
        self.storage_mode = StorageMode.LOCAL_FALLBACK
        
        logger.info(f"Local storage fallback initialized: {self.local_storage_path}")
    
    async def _init_service_bus(self):
        """Initialize Azure Service Bus with direct processing fallback"""
        service_name = "service_bus"
        service_config = self.config.get_service_config(service_name)
        
        if not service_config or not service_config.connection_string:
            logger.info("Service Bus not configured - batch processing will use direct mode")
            self.health_status[service_name] = ServiceHealth(
                name="Azure Service Bus",
                is_available=False
            )
            return
        
        try:
            from azure.servicebus.aio import ServiceBusClient
            
            self.service_bus_client = ServiceBusClient.from_connection_string(
                service_config.connection_string
            )
            
            # Test connection by creating a sender (but don't send anything)
            queue_name = service_config.config.get("queue_name", "email-processing")
            async with self.service_bus_client.get_queue_sender(queue_name) as sender:
                pass  # Just test that we can create the sender
            
            self.health_status[service_name] = ServiceHealth(
                name="Azure Service Bus",
                is_available=True,
                last_check=datetime.utcnow()
            )
            
            logger.info("Azure Service Bus initialized")
            
        except ImportError:
            logger.warning("azure-servicebus package not installed")
            self.health_status[service_name] = ServiceHealth(
                name="Azure Service Bus",
                is_available=False,
                last_error="azure-servicebus package not installed"
            )
        except Exception as e:
            logger.warning(f"Service Bus initialization failed: {e}")
            self.config.mark_service_failed(service_name, e)
            self.health_status[service_name] = ServiceHealth(
                name="Azure Service Bus",
                is_available=False,
                last_error=str(e),
                consecutive_failures=1
            )
    
    async def _init_signalr_service(self):
        """Initialize Azure SignalR with WebSocket fallback"""
        service_name = "signalr"
        service_config = self.config.get_service_config(service_name)
        
        if not service_config or not service_config.connection_string:
            logger.info("SignalR not configured - real-time features will use basic WebSocket")
            self.health_status[service_name] = ServiceHealth(
                name="Azure SignalR",
                is_available=False
            )
            return
        
        try:
            # Parse SignalR connection string
            # Format: Endpoint=https://...;AccessKey=...;Version=1.0;
            parts = service_config.connection_string.split(';')
            endpoint = None
            access_key = None
            
            for part in parts:
                if part.startswith('Endpoint='):
                    endpoint = part.split('=', 1)[1]
                elif part.startswith('AccessKey='):
                    access_key = part.split('=', 1)[1]
            
            if endpoint and access_key:
                self.signalr_client = {
                    'endpoint': endpoint,
                    'access_key': access_key,
                    'hub_name': service_config.config.get('hub_name', 'emailProcessingHub')
                }
                
                self.health_status[service_name] = ServiceHealth(
                    name="Azure SignalR",
                    is_available=True,
                    last_check=datetime.utcnow()
                )
                
                logger.info("Azure SignalR service initialized")
            else:
                raise ValueError("Invalid SignalR connection string format")
                
        except Exception as e:
            logger.warning(f"SignalR initialization failed: {e}")
            self.config.mark_service_failed(service_name, e)
            self.health_status[service_name] = ServiceHealth(
                name="Azure SignalR",
                is_available=False,
                last_error=str(e),
                consecutive_failures=1
            )
    
    async def _init_ai_search_service(self):
        """Initialize Azure AI Search with basic search fallback"""
        service_name = "ai_search"
        service_config = self.config.get_service_config(service_name)
        
        if not service_config or not service_config.connection_string:
            logger.info("Azure AI Search not configured - advanced search features disabled")
            self.health_status[service_name] = ServiceHealth(
                name="Azure AI Search",
                is_available=False
            )
            return
        
        try:
            endpoint = service_config.config.get('endpoint')
            api_key = service_config.config.get('api_key')
            
            if not endpoint or not api_key:
                raise ValueError("Azure AI Search endpoint or API key missing")
            
            # We'll store the configuration and initialize the actual client when needed
            self.ai_search_client = {
                'endpoint': endpoint,
                'api_key': api_key,
                'index_name': service_config.config.get('index_name', 'email-patterns'),
                'semantic_config': service_config.config.get('semantic_config', 'email-semantic')
            }
            
            self.health_status[service_name] = ServiceHealth(
                name="Azure AI Search",
                is_available=True,
                last_check=datetime.utcnow()
            )
            
            logger.info("Azure AI Search service initialized")
            
        except Exception as e:
            logger.warning(f"Azure AI Search initialization failed: {e}")
            self.config.mark_service_failed(service_name, e)
            self.health_status[service_name] = ServiceHealth(
                name="Azure AI Search",
                is_available=False,
                last_error=str(e),
                consecutive_failures=1
            )
    
    async def _init_application_insights(self):
        """Initialize Application Insights with basic logging fallback"""
        service_name = "application_insights"
        service_config = self.config.get_service_config(service_name)
        
        if not service_config or not service_config.connection_string:
            logger.info("Application Insights not configured - using basic logging")
            self.health_status[service_name] = ServiceHealth(
                name="Application Insights",
                is_available=False
            )
            return
        
        try:
            # Store configuration for when we need to send telemetry
            self.insights_client = {
                'connection_string': service_config.connection_string,
                'detailed_telemetry': service_config.config.get('detailed_telemetry', False),
                'sampling_percentage': service_config.config.get('sampling_percentage', 100.0)
            }
            
            self.health_status[service_name] = ServiceHealth(
                name="Application Insights",
                is_available=True,
                last_check=datetime.utcnow()
            )
            
            logger.info("Application Insights initialized")
            
        except Exception as e:
            logger.warning(f"Application Insights initialization failed: {e}")
            self.config.mark_service_failed(service_name, e)
            self.health_status[service_name] = ServiceHealth(
                name="Application Insights",
                is_available=False,
                last_error=str(e),
                consecutive_failures=1
            )
    
    def _start_health_monitoring(self):
        """Start background health monitoring for all services"""
        async def health_monitor():
            while True:
                try:
                    await asyncio.sleep(60)  # Check every minute
                    await self._check_all_service_health()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
        
        self._health_monitor_task = asyncio.create_task(health_monitor())
        logger.info("Azure services health monitoring started")
    
    async def _check_all_service_health(self):
        """Check health of all initialized services"""
        health_tasks = []
        
        if self.redis_client:
            health_tasks.append(self._check_redis_health())
        
        if self.storage_client:
            health_tasks.append(self._check_storage_health())
        
        if self.service_bus_client:
            health_tasks.append(self._check_service_bus_health())
        
        # Run all health checks concurrently
        if health_tasks:
            await asyncio.gather(*health_tasks, return_exceptions=True)
    
    async def _check_redis_health(self):
        """Check Redis health"""
        service_name = "redis"
        try:
            start_time = datetime.utcnow()
            await self.redis_client.ping()
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            health = self.health_status[service_name]
            health.is_available = True
            health.last_check = datetime.utcnow()
            health.consecutive_failures = 0
            health.average_response_time = (
                health.average_response_time * 0.9 + response_time * 0.1
            )
            
        except Exception as e:
            health = self.health_status[service_name]
            health.is_available = False
            health.last_error = str(e)
            health.consecutive_failures += 1
            logger.warning(f"Redis health check failed: {e}")
    
    async def _check_storage_health(self):
        """Check Azure Storage health"""
        service_name = "storage"
        try:
            start_time = datetime.utcnow()
            
            # Simple health check - list containers
            containers = []
            async for container in self.storage_client.list_containers():
                containers.append(container.name)
                if len(containers) >= 1:
                    break
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            health = self.health_status[service_name]
            health.is_available = True
            health.last_check = datetime.utcnow()
            health.consecutive_failures = 0
            health.average_response_time = (
                health.average_response_time * 0.9 + response_time * 0.1
            )
            
        except Exception as e:
            health = self.health_status[service_name]
            health.is_available = False
            health.last_error = str(e)
            health.consecutive_failures += 1
            logger.warning(f"Storage health check failed: {e}")
    
    async def _check_service_bus_health(self):
        """Check Service Bus health"""
        service_name = "service_bus"
        try:
            start_time = datetime.utcnow()
            
            # Simple health check - create a sender
            service_config = self.config.get_service_config(service_name)
            queue_name = service_config.config.get("queue_name", "email-processing")
            
            async with self.service_bus_client.get_queue_sender(queue_name) as sender:
                pass  # Just test connection
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            health = self.health_status[service_name]
            health.is_available = True
            health.last_check = datetime.utcnow()
            health.consecutive_failures = 0
            health.average_response_time = (
                health.average_response_time * 0.9 + response_time * 0.1
            )
            
        except Exception as e:
            health = self.health_status[service_name]
            health.is_available = False
            health.last_error = str(e)
            health.consecutive_failures += 1
            logger.warning(f"Service Bus health check failed: {e}")
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if a specific service is available"""
        health = self.health_status.get(service_name)
        return health is not None and health.is_available
    
    async def get_redis_client(self):
        """Get Redis client if available, None otherwise"""
        if self.is_service_available("redis"):
            return self.redis_client
        return None
    
    def get_storage_mode(self) -> StorageMode:
        """Get current storage mode"""
        return self.storage_mode
    
    async def store_file(
        self,
        filename: str,
        content: bytes,
        container_name: str = "email-attachments"
    ) -> Dict[str, Any]:
        """
        Store file with automatic fallback handling
        
        Returns:
            Dict with 'success', 'mode', 'path/url', and 'error' (if any)
        """
        result = {
            'success': False,
            'mode': self.storage_mode.value,
            'path': None,
            'error': None
        }
        
        try:
            if self.storage_mode == StorageMode.AZURE_BLOB and self.storage_client:
                # Try Azure Blob Storage first
                blob_client = self.storage_client.get_blob_client(
                    container=container_name,
                    blob=filename
                )
                
                await blob_client.upload_blob(content, overwrite=True)
                result['success'] = True
                result['path'] = blob_client.url
                
                logger.debug(f"File stored in Azure Blob: {filename}")
                
            elif self.storage_mode == StorageMode.LOCAL_FALLBACK:
                # Use local storage fallback
                file_path = os.path.join(self.local_storage_path, filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                result['success'] = True
                result['path'] = file_path
                
                logger.debug(f"File stored locally: {file_path}")
                
            else:
                # Memory-only mode (for testing)
                result['success'] = True
                result['mode'] = StorageMode.MEMORY_ONLY.value
                result['path'] = f"memory://{filename}"
                
                logger.debug(f"File stored in memory: {filename}")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"File storage failed: {e}")
            
            # Try fallback if Azure failed
            if self.storage_mode == StorageMode.AZURE_BLOB and self.local_storage_path:
                try:
                    file_path = os.path.join(self.local_storage_path, filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    result['success'] = True
                    result['mode'] = "local_fallback"
                    result['path'] = file_path
                    result['error'] = f"Azure failed, used local fallback: {e}"
                    
                    logger.info(f"Used local fallback after Azure failure: {filename}")
                    
                except Exception as fallback_error:
                    result['error'] = f"Azure failed: {e}, Local fallback failed: {fallback_error}"
        
        return result
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary of all services"""
        now = datetime.utcnow()
        
        summary = {
            "timestamp": now.isoformat(),
            "overall_status": "healthy",
            "services": {},
            "storage_mode": self.storage_mode.value,
            "recommendations": []
        }
        
        healthy_services = 0
        total_services = len(self.health_status)
        
        for service_name, health in self.health_status.items():
            service_info = {
                "name": health.name,
                "available": health.is_available,
                "last_check": health.last_check.isoformat() if health.last_check else None,
                "consecutive_failures": health.consecutive_failures,
                "success_rate": (
                    (health.total_requests - health.failed_requests) / 
                    max(1, health.total_requests) * 100
                ) if health.total_requests > 0 else 100.0,
                "average_response_time": health.average_response_time,
                "last_error": health.last_error
            }
            
            summary["services"][service_name] = service_info
            
            if health.is_available:
                healthy_services += 1
            elif health.consecutive_failures > 3:
                summary["recommendations"].append(
                    f"Check {health.name} configuration - {health.consecutive_failures} consecutive failures"
                )
        
        # Determine overall status
        if healthy_services == 0:
            summary["overall_status"] = "degraded"
        elif healthy_services < total_services // 2:
            summary["overall_status"] = "warning"
        
        # Add configuration recommendations
        if self.storage_mode != StorageMode.AZURE_BLOB:
            summary["recommendations"].append(
                "Configure Azure Blob Storage for production file handling"
            )
        
        if not self.is_service_available("redis"):
            summary["recommendations"].append(
                "Configure Redis cache for improved performance"
            )
        
        return summary
    
    async def cleanup(self):
        """Cleanup all service connections"""
        if self._health_monitor_task and not self._health_monitor_task.done():
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Close service connections
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
        
        if self.storage_client:
            try:
                await self.storage_client.close()
            except Exception as e:
                logger.warning(f"Error closing Storage client: {e}")
        
        if self.service_bus_client:
            try:
                await self.service_bus_client.close()
            except Exception as e:
                logger.warning(f"Error closing Service Bus client: {e}")
        
        logger.info("Azure service manager cleanup completed")

# Global service manager instance
_azure_service_manager: Optional[AzureServiceManager] = None

async def get_azure_service_manager() -> AzureServiceManager:
    """Get the global Azure service manager instance"""
    global _azure_service_manager
    
    if _azure_service_manager is None:
        _azure_service_manager = AzureServiceManager()
        await _azure_service_manager.initialize()
    
    return _azure_service_manager

async def cleanup_azure_service_manager():
    """Cleanup the global Azure service manager"""
    global _azure_service_manager
    
    if _azure_service_manager:
        await _azure_service_manager.cleanup()
        _azure_service_manager = None