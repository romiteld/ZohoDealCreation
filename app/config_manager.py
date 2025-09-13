"""
Enhanced Configuration Manager with Graceful Fallbacks

This module provides centralized configuration management with:
- Graceful fallbacks for missing credentials
- Optional Azure service dependencies
- Enhanced database connection handling
- Circuit breaker patterns for all external services
"""

import os
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """Service status enumeration"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    FALLBACK = "fallback"
    FAILED = "failed"

class ServiceType(Enum):
    """Azure service types"""
    DATABASE = "database"
    REDIS = "redis"
    STORAGE = "storage"
    SERVICE_BUS = "service_bus"
    SIGNALR = "signalr"
    AI_SEARCH = "ai_search"
    APPLICATION_INSIGHTS = "application_insights"
    KEY_VAULT = "key_vault"

@dataclass
class ServiceConfig:
    """Configuration for individual services"""
    name: str
    service_type: ServiceType
    connection_string: Optional[str] = None
    required: bool = False
    fallback_enabled: bool = True
    status: ServiceStatus = ServiceStatus.DISABLED
    last_check: Optional[datetime] = None
    failure_count: int = 0
    max_failures: int = 5
    retry_after: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DatabaseConfig:
    """Enhanced database configuration"""
    url: Optional[str] = None
    enabled: bool = False
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30
    pool_recycle: int = 3600
    connect_args: Dict[str, Any] = field(default_factory=lambda: {
        'connect_timeout': 30,
        'application_name': 'well-intake-api',
        'sslmode': 'require'
    })
    retry_attempts: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 10.0
    health_check_interval: int = 30

@dataclass
class ExtractionConfig:
    """Email extraction and AI configuration"""
    use_langgraph: bool = True
    use_langextract: bool = False
    langextract_model: str = "gpt-5-mini"
    langextract_cache_enabled: bool = True
    langextract_visualization: bool = False
    langextract_source_grounding: bool = True
    langextract_validation: bool = True
    langextract_chunk_size: int = 2000
    langextract_max_workers: int = 1
    langextract_fallback_enabled: bool = True
    openai_model: str = "gpt-5-mini"
    openai_temperature: float = 1.0
    firecrawl_timeout: int = 5
    a_b_testing_enabled: bool = False
    a_b_testing_langextract_percentage: int = 50
    # Azure OpenAI Configuration
    use_azure_openai: bool = True
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment: Optional[str] = None

@dataclass
class SecurityConfig:
    """Security and authentication configuration"""
    api_key: Optional[str] = None
    api_key_rotation_days: int = 30
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    cors_origins: List[str] = field(default_factory=lambda: [
        "https://outlook.office.com",
        "https://outlook.office365.com",
        "https://localhost:3000"
    ])
    security_headers_enabled: bool = True
    hsts_max_age: int = 31536000

class ConfigManager:
    """
    Centralized configuration manager with graceful fallbacks
    
    Features:
    - Optional Azure service dependencies
    - Graceful database fallbacks
    - Circuit breaker patterns
    - Environment-based configuration
    - Service health monitoring
    """
    
    def __init__(self):
        self.services: Dict[str, ServiceConfig] = {}
        self.database: DatabaseConfig = DatabaseConfig()
        self.security: SecurityConfig = SecurityConfig()
        self.extraction: ExtractionConfig = ExtractionConfig()
        self._initialized = False
        self._security_module = None
        
        # Initialize security module for Key Vault access
        self._init_security_module()
        
        # Load configuration from environment
        self._load_configuration()
    
    def _init_security_module(self):
        """Initialize security module for Key Vault access"""
        try:
            from app.security_config import security
            self._security_module = security
            logger.info("Security module initialized for Key Vault access")
        except ImportError as e:
            logger.warning(f"Security module not available: {e}")
            self._security_module = None
    
    async def _get_secret_async(self, secret_name: str, fallback_env_name: str = None) -> Optional[str]:
        """
        Get secret from Key Vault with fallback to environment variable
        
        Args:
            secret_name: Name of secret in Key Vault (kebab-case)
            fallback_env_name: Environment variable name for fallback
            
        Returns:
            Secret value or None
        """
        if self._security_module:
            try:
                value = await self._security_module.get_secret(secret_name, use_cache=True)
                if value:
                    logger.debug(f"Retrieved secret {secret_name} from Key Vault")
                    return value
            except Exception as e:
                logger.warning(f"Failed to retrieve secret {secret_name} from Key Vault: {e}")
        
        # Fallback to environment variable
        env_name = fallback_env_name or secret_name.upper().replace('-', '_')
        value = os.getenv(env_name)
        if value:
            logger.debug(f"Using environment variable {env_name} as fallback for {secret_name}")
        return value
    
    def _get_secret(self, secret_name: str, fallback_env_name: str = None) -> Optional[str]:
        """
        Synchronous wrapper for secret retrieval - falls back to environment variable during initialization
        
        Args:
            secret_name: Name of secret in Key Vault (kebab-case)
            fallback_env_name: Environment variable name for fallback
            
        Returns:
            Secret value or None
        """
        # During initialization, use environment variables directly
        # Key Vault integration will be used at runtime via async methods
        env_name = fallback_env_name or secret_name.upper().replace('-', '_')
        return os.getenv(env_name)
    
    def _load_configuration(self):
        """Load configuration from environment variables"""
        logger.info("Loading configuration from environment")
        
        # Database configuration
        self._configure_database()
        
        # Security configuration  
        self._configure_security()
        
        # Extraction configuration
        self._configure_extraction()
        
        # Azure services configuration
        self._configure_azure_services()
        
        self._initialized = True
        logger.info("Configuration loaded successfully")
    
    def _configure_database(self):
        """Configure database with graceful fallbacks"""
        database_url = self._get_secret("database-url", "DATABASE_URL")
        
        if database_url:
            self.database = DatabaseConfig(
                url=database_url,
                enabled=True,
                pool_size=int(os.getenv("DATABASE_POOL_SIZE", "20")),
                max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "40")),
                pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
                pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE", "3600")),
                retry_attempts=int(os.getenv("DB_RETRY_ATTEMPTS", "3")),
                retry_delay=float(os.getenv("DB_RETRY_DELAY", "1.0")),
                max_retry_delay=float(os.getenv("DB_MAX_RETRY_DELAY", "10.0")),
                health_check_interval=int(os.getenv("DB_HEALTH_CHECK_INTERVAL", "30"))
            )
            logger.info("Database configuration loaded - database features enabled")
        else:
            logger.warning("DATABASE_URL not configured - database features will be disabled")
            self.database.enabled = False
    
    def _configure_security(self):
        """Configure security settings"""
        self.security = SecurityConfig(
            api_key=self._get_secret("api-key", "API_KEY"),
            api_key_rotation_days=int(os.getenv("API_KEY_ROTATION_DAYS", "30")),
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
            rate_limit_period=int(os.getenv("RATE_LIMIT_PERIOD", "60")),
            security_headers_enabled=os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true",
            hsts_max_age=int(os.getenv("HSTS_MAX_AGE", "31536000"))
        )
        
        # Parse CORS origins
        cors_origins = os.getenv("CORS_ORIGINS")
        if cors_origins:
            try:
                import json
                self.security.cors_origins = json.loads(cors_origins)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid CORS_ORIGINS format, using defaults")
    
    def _configure_extraction(self):
        """Configure extraction and AI settings"""
        self.extraction = ExtractionConfig(
            use_langgraph=os.getenv("USE_LANGGRAPH", "true").lower() == "true",
            use_langextract=os.getenv("USE_LANGEXTRACT", "false").lower() == "true",
            langextract_model=os.getenv("LANGEXTRACT_MODEL", "gpt-4o-mini"),
            langextract_cache_enabled=os.getenv("LANGEXTRACT_CACHE_ENABLED", "true").lower() == "true",
            langextract_visualization=os.getenv("LANGEXTRACT_VISUALIZATION", "false").lower() == "true",
            langextract_source_grounding=os.getenv("LANGEXTRACT_SOURCE_GROUNDING", "true").lower() == "true",
            langextract_validation=os.getenv("LANGEXTRACT_VALIDATION", "true").lower() == "true",
            langextract_chunk_size=int(os.getenv("LANGEXTRACT_CHUNK_SIZE", "2000")),
            langextract_max_workers=int(os.getenv("LANGEXTRACT_MAX_WORKERS", "1")),
            langextract_fallback_enabled=os.getenv("LANGEXTRACT_FALLBACK_ENABLED", "true").lower() == "true",
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "1.0")),
            firecrawl_timeout=int(os.getenv("FIRECRAWL_TIMEOUT", "5")),
            a_b_testing_enabled=os.getenv("AB_TESTING_ENABLED", "false").lower() == "true",
            a_b_testing_langextract_percentage=int(os.getenv("AB_TESTING_LANGEXTRACT_PERCENTAGE", "50")),
            # Azure OpenAI Configuration
            use_azure_openai=os.getenv("USE_AZURE_OPENAI", "true").lower() == "true",
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_api_key=self._get_secret("azure-openai-key", "AZURE_OPENAI_KEY"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
        )
        
        logger.info(f"Extraction configuration loaded - LangExtract: {self.extraction.use_langextract}, A/B Testing: {self.extraction.a_b_testing_enabled}")
    
    def _configure_azure_services(self):
        """Configure Azure services with optional dependencies"""
        
        # Redis Cache - Optional but recommended for production
        redis_conn = os.getenv("AZURE_REDIS_CONNECTION_STRING") or os.getenv("REDIS_CONNECTION_STRING")
        self.services["redis"] = ServiceConfig(
            name="Redis Cache",
            service_type=ServiceType.REDIS,
            connection_string=redis_conn,
            required=False,  # Optional service
            fallback_enabled=True,
            status=ServiceStatus.ENABLED if redis_conn else ServiceStatus.DISABLED,
            config={
                "default_ttl_hours": int(os.getenv("REDIS_DEFAULT_TTL_HOURS", "24")),
                "batch_ttl_hours": int(os.getenv("REDIS_BATCH_TTL_HOURS", "48")),
                "pattern_ttl_days": int(os.getenv("REDIS_PATTERN_TTL_DAYS", "90")),
                "operation_timeout": int(os.getenv("REDIS_OPERATION_TIMEOUT", "5")),
                "connection_timeout": int(os.getenv("REDIS_CONNECTION_TIMEOUT", "10")),
                "max_retries": int(os.getenv("REDIS_MAX_RETRIES", "3"))
            }
        )
        
        # Azure Storage - Required for file attachments
        storage_conn = self._get_secret("azure-storage-connection-string", "AZURE_STORAGE_CONNECTION_STRING")
        self.services["storage"] = ServiceConfig(
            name="Azure Blob Storage",
            service_type=ServiceType.STORAGE,
            connection_string=storage_conn,
            required=True,  # Required for attachments
            fallback_enabled=True,  # Can fallback to local storage in dev
            status=ServiceStatus.ENABLED if storage_conn else ServiceStatus.FALLBACK,
            config={
                "container_name": os.getenv("AZURE_CONTAINER_NAME", "email-attachments"),
                "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", "25")),
                "allowed_types": os.getenv("ATTACHMENT_ALLOWED_TYPES", "pdf,doc,docx,txt,rtf").split(","),
                "local_fallback_path": os.getenv("LOCAL_STORAGE_PATH", "/tmp/attachments")
            }
        )
        
        # Service Bus - Optional for batch processing
        bus_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING") or os.getenv("SERVICE_BUS_CONNECTION_STRING")
        self.services["service_bus"] = ServiceConfig(
            name="Azure Service Bus",
            service_type=ServiceType.SERVICE_BUS,
            connection_string=bus_conn,
            required=False,
            fallback_enabled=True,
            status=ServiceStatus.ENABLED if bus_conn else ServiceStatus.DISABLED,
            config={
                "queue_name": os.getenv("SERVICE_BUS_QUEUE_NAME", "email-processing"),
                "batch_size": int(os.getenv("SERVICE_BUS_BATCH_SIZE", "50")),
                "max_wait_time": int(os.getenv("SERVICE_BUS_MAX_WAIT_TIME", "30")),
                "max_retries": int(os.getenv("SERVICE_BUS_MAX_RETRIES", "3"))
            }
        )
        
        # SignalR - Optional for real-time features
        signalr_conn = os.getenv("AZURE_SIGNALR_CONNECTION_STRING")
        self.services["signalr"] = ServiceConfig(
            name="Azure SignalR",
            service_type=ServiceType.SIGNALR,
            connection_string=signalr_conn,
            required=False,
            fallback_enabled=True,
            status=ServiceStatus.ENABLED if signalr_conn else ServiceStatus.DISABLED,
            config={
                "hub_name": os.getenv("SIGNALR_HUB_NAME", "emailProcessingHub"),
                "connection_timeout": int(os.getenv("SIGNALR_CONNECTION_TIMEOUT", "30")),
                "keep_alive_interval": int(os.getenv("SIGNALR_KEEP_ALIVE", "15"))
            }
        )
        
        # AI Search - Optional for advanced features
        search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        search_key = os.getenv("AZURE_SEARCH_KEY")
        self.services["ai_search"] = ServiceConfig(
            name="Azure AI Search",
            service_type=ServiceType.AI_SEARCH,
            connection_string=f"{search_endpoint}|{search_key}" if search_endpoint and search_key else None,
            required=False,
            fallback_enabled=True,
            status=ServiceStatus.ENABLED if search_endpoint and search_key else ServiceStatus.DISABLED,
            config={
                "endpoint": search_endpoint,
                "api_key": search_key,
                "index_name": os.getenv("AZURE_SEARCH_INDEX", "email-patterns"),
                "semantic_config": os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG", "email-semantic")
            }
        )
        
        # Application Insights - Optional for monitoring
        insights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        self.services["application_insights"] = ServiceConfig(
            name="Application Insights",
            service_type=ServiceType.APPLICATION_INSIGHTS,
            connection_string=insights_conn,
            required=False,
            fallback_enabled=True,
            status=ServiceStatus.ENABLED if insights_conn else ServiceStatus.DISABLED,
            config={
                "detailed_telemetry": os.getenv("TELEMETRY_DETAILED", "false").lower() == "true",
                "sampling_percentage": float(os.getenv("TELEMETRY_SAMPLING", "100.0")),
                "log_level": os.getenv("TELEMETRY_LOG_LEVEL", "INFO")
            }
        )
    
    def is_service_enabled(self, service_name: str) -> bool:
        """Check if a service is enabled and available"""
        service = self.services.get(service_name)
        if not service:
            return False
        
        return service.status in [ServiceStatus.ENABLED, ServiceStatus.FALLBACK]
    
    def get_service_config(self, service_name: str) -> Optional[ServiceConfig]:
        """Get configuration for a specific service"""
        return self.services.get(service_name)
    
    def mark_service_failed(self, service_name: str, error: Optional[Exception] = None):
        """Mark a service as failed and implement circuit breaker logic"""
        service = self.services.get(service_name)
        if not service:
            return
        
        service.failure_count += 1
        service.last_check = datetime.utcnow()
        
        if service.failure_count >= service.max_failures:
            service.status = ServiceStatus.FAILED
            # Circuit breaker - wait 5 minutes before retry
            service.retry_after = datetime.utcnow() + timedelta(minutes=5)
            logger.warning(f"{service.name} marked as failed after {service.failure_count} failures")
        
        if error:
            logger.error(f"{service.name} error: {error}")
    
    def mark_service_healthy(self, service_name: str):
        """Mark a service as healthy and reset failure count"""
        service = self.services.get(service_name)
        if not service:
            return
        
        service.failure_count = 0
        service.retry_after = None
        service.last_check = datetime.utcnow()
        
        if service.connection_string:
            service.status = ServiceStatus.ENABLED
        else:
            service.status = ServiceStatus.DISABLED
            
        logger.info(f"{service.name} marked as healthy")
    
    def can_retry_service(self, service_name: str) -> bool:
        """Check if a failed service can be retried"""
        service = self.services.get(service_name)
        if not service or service.status != ServiceStatus.FAILED:
            return True
        
        if service.retry_after and datetime.utcnow() < service.retry_after:
            return False
        
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of all services"""
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "enabled": self.database.enabled,
                "url_configured": bool(self.database.url),
                "pool_size": self.database.pool_size
            },
            "extraction": {
                "use_langgraph": self.extraction.use_langgraph,
                "use_langextract": self.extraction.use_langextract,
                "langextract_model": self.extraction.langextract_model,
                "openai_model": self.extraction.openai_model,
                "a_b_testing_enabled": self.extraction.a_b_testing_enabled,
                "a_b_testing_percentage": self.extraction.a_b_testing_langextract_percentage
            },
            "services": {},
            "summary": {
                "total_services": len(self.services),
                "enabled_services": 0,
                "failed_services": 0,
                "disabled_services": 0
            }
        }
        
        for name, service in self.services.items():
            status["services"][name] = {
                "name": service.name,
                "type": service.service_type.value,
                "status": service.status.value,
                "required": service.required,
                "failure_count": service.failure_count,
                "last_check": service.last_check.isoformat() if service.last_check else None,
                "connection_configured": bool(service.connection_string)
            }
            
            # Update summary
            if service.status == ServiceStatus.ENABLED:
                status["summary"]["enabled_services"] += 1
            elif service.status == ServiceStatus.FAILED:
                status["summary"]["failed_services"] += 1
            else:
                status["summary"]["disabled_services"] += 1
        
        return status
    
    def get_fallback_recommendations(self) -> List[str]:
        """Get recommendations for improving service availability"""
        recommendations = []
        
        # Database recommendations
        if not self.database.enabled:
            recommendations.append(
                "Configure DATABASE_URL to enable database features (caching, deduplication, learning)"
            )
        
        # Service-specific recommendations
        critical_services = ["storage"]  # Services that should be enabled
        for service_name in critical_services:
            service = self.services.get(service_name)
            if service and service.status != ServiceStatus.ENABLED:
                recommendations.append(
                    f"Configure {service.name} ({service_name}) for full functionality"
                )
        
        # Optional but recommended services
        recommended_services = ["redis"]
        for service_name in recommended_services:
            service = self.services.get(service_name)
            if service and service.status == ServiceStatus.DISABLED:
                recommendations.append(
                    f"Configure {service.name} ({service_name}) for improved performance"
                )
        
        return recommendations

# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager()
    
    return _config_manager

def is_service_available(service_name: str) -> bool:
    """Quick check if a service is available"""
    config_manager = get_config_manager()
    return config_manager.is_service_enabled(service_name)

def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    config_manager = get_config_manager()
    return config_manager.database

def get_security_config() -> SecurityConfig:
    """Get security configuration"""
    config_manager = get_config_manager()
    return config_manager.security

def get_extraction_config() -> ExtractionConfig:
    """Get extraction configuration"""
    config_manager = get_config_manager()
    return config_manager.extraction