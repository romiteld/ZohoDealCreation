"""
Database Connection Manager for Well Intake API
Ensures reliable, always-available database connections with health checks and retry logic
Agent #4: Database Connection Setup - Reliable database connections for learning services
"""

import os
import asyncio
import logging
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
# from contextlib import asynccontextmanager  # Removed - not needed after refactoring get_connection
from dataclasses import dataclass, field
import json
import hashlib

# Database imports
try:
    import asyncpg
    from pgvector.asyncpg import register_vector
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None
    register_vector = None

# Enhanced database client
try:
    from .database_enhancements import EnhancedPostgreSQLClient
    HAS_ENHANCED_DB = True
except ImportError:
    HAS_ENHANCED_DB = False
    EnhancedPostgreSQLClient = None

logger = logging.getLogger(__name__)


@dataclass
class ConnectionHealth:
    """Database connection health status"""
    is_healthy: bool = False
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: Optional[str] = None
    connection_count: int = 0
    active_connections: int = 0
    failed_attempts: int = 0
    total_queries: int = 0
    avg_response_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'is_healthy': self.is_healthy,
            'last_check': self.last_check.isoformat(),
            'last_error': self.last_error,
            'connection_count': self.connection_count,
            'active_connections': self.active_connections,
            'failed_attempts': self.failed_attempts,
            'total_queries': self.total_queries,
            'avg_response_time_ms': self.avg_response_time_ms
        }


@dataclass
class ConnectionConfig:
    """Database connection configuration"""
    connection_string: str
    min_connections: int = 3
    max_connections: int = 15
    command_timeout: int = 60
    server_settings: Dict[str, str] = field(default_factory=lambda: {'jit': 'off'})
    enable_vectors: bool = True
    health_check_interval: int = 30  # seconds
    retry_attempts: int = 3
    retry_delay: float = 1.0  # seconds
    connection_timeout: float = 30.0  # seconds


class DatabaseConnectionManager:
    """
    Centralized database connection manager ensuring reliable access for all services
    
    Key Features:
    - Always-available connection pools with health monitoring
    - Automatic reconnection and retry logic
    - Learning service table initialization
    - Connection pooling optimization
    - Graceful error handling and fallbacks
    """
    
    def __init__(self, connection_string: str, config: Optional[ConnectionConfig] = None):
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required for PostgreSQL functionality")
        
        self.config = config or ConnectionConfig(connection_string=connection_string)
        self.connection_string = connection_string
        
        # Connection pools
        self.main_pool: Optional[asyncpg.Pool] = None
        self.enhanced_client: Optional[EnhancedPostgreSQLClient] = None
        
        # Health monitoring
        self.health_status = ConnectionHealth()
        self._health_check_task: Optional[asyncio.Task] = None
        self._initialization_complete = False
        
        # Statistics tracking
        self._query_times: List[float] = []
        self._max_query_times = 100  # Keep last 100 query times for averaging
        
        # Initialization lock to prevent concurrent initialization
        self._init_lock = asyncio.Lock()
        
        logger.info(f"DatabaseConnectionManager initialized with config: {self.config}")
    
    async def initialize(self) -> bool:
        """
        Initialize all database connections and services
        Returns True if successful, False otherwise
        """
        async with self._init_lock:
            if self._initialization_complete:
                logger.info("Database connection manager already initialized")
                return True
            
            logger.info("Initializing database connection manager...")
            
            try:
                # Initialize main connection pool
                success = await self._initialize_main_pool()
                if not success:
                    logger.error("Failed to initialize main connection pool")
                    return False
                
                # Initialize enhanced client if available
                await self._initialize_enhanced_client()
                
                # Create required tables for learning services
                await self._ensure_learning_tables()
                
                # Start health monitoring
                await self._start_health_monitoring()
                
                self._initialization_complete = True
                self.health_status.is_healthy = True
                logger.info("Database connection manager initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.health_status.is_healthy = False
                self.health_status.last_error = str(e)
                return False
    
    async def _initialize_main_pool(self) -> bool:
        """Initialize the main asyncpg connection pool with retry logic"""
        for attempt in range(self.config.retry_attempts):
            try:
                logger.info(f"Attempting to create connection pool (attempt {attempt + 1}/{self.config.retry_attempts})")
                
                self.main_pool = await asyncpg.create_pool(
                    self.connection_string,
                    min_size=self.config.min_connections,
                    max_size=self.config.max_connections,
                    command_timeout=self.config.command_timeout,
                    server_settings=self.config.server_settings,
                    init=self._init_connection_callback if self.config.enable_vectors else None
                )
                
                # Test the pool
                async with self.main_pool.acquire() as conn:
                    await conn.fetchval('SELECT 1')
                
                self.health_status.connection_count = self.main_pool.get_size()
                logger.info(f"Main connection pool created successfully with {self.health_status.connection_count} connections")
                return True
                
            except Exception as e:
                logger.warning(f"Connection pool creation attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"All connection pool creation attempts failed")
                    self.health_status.failed_attempts += 1
                    self.health_status.last_error = str(e)
        
        return False
    
    async def _init_connection_callback(self, conn):
        """Callback to initialize each connection with pgvector support"""
        if register_vector and self.config.enable_vectors:
            try:
                await register_vector(conn)
                logger.debug("pgvector support registered for connection")
            except Exception as e:
                logger.warning(f"Failed to register pgvector for connection: {e}")
    
    async def _initialize_enhanced_client(self):
        """Initialize enhanced PostgreSQL client if available"""
        if not HAS_ENHANCED_DB:
            logger.info("Enhanced database client not available, using basic client only")
            return
        
        try:
            self.enhanced_client = EnhancedPostgreSQLClient(
                self.connection_string,
                enable_vectors=self.config.enable_vectors
            )
            
            # Initialize the enhanced client
            await self.enhanced_client.init_pool()
            await self.enhanced_client.ensure_enhanced_tables()
            
            logger.info("Enhanced PostgreSQL client initialized successfully")
            
        except Exception as e:
            logger.warning(f"Enhanced client initialization failed, continuing with basic client: {e}")
            self.enhanced_client = None
    
    async def _ensure_learning_tables(self):
        """Ensure all learning service tables are created"""
        logger.info("Creating learning service tables...")
        
        # Learning service tables SQL
        learning_tables_sql = """
        -- Enable required extensions
        CREATE EXTENSION IF NOT EXISTS vector;
        -- pg_trgm and btree_gin not available in Azure Database for PostgreSQL flexible server
        -- CREATE EXTENSION IF NOT EXISTS pg_trgm;
        -- CREATE EXTENSION IF NOT EXISTS btree_gin;
        
        -- AI Corrections table for learning system
        CREATE TABLE IF NOT EXISTS ai_corrections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            email_domain VARCHAR(255),
            sender_email VARCHAR(255),
            internet_message_id TEXT,
            original_extraction JSONB NOT NULL,
            user_corrections JSONB NOT NULL,
            field_corrections JSONB NOT NULL,
            email_snippet TEXT,
            correction_source VARCHAR(100) DEFAULT 'manual',
            confidence_before DECIMAL(3,2) DEFAULT 0.5,
            confidence_after DECIMAL(3,2) DEFAULT 0.8,
            processing_time_ms INTEGER,
            model_version VARCHAR(50) DEFAULT 'gpt-5-mini',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- Learning Patterns table for pattern recognition
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            field_name VARCHAR(100) NOT NULL,
            pattern_type VARCHAR(50) NOT NULL,
            from_value TEXT,
            to_value TEXT,
            email_domain VARCHAR(255),
            pattern_hash TEXT UNIQUE,
            frequency INTEGER DEFAULT 1,
            success_rate DECIMAL(3,2) DEFAULT 1.0,
            last_seen TIMESTAMPTZ DEFAULT NOW(),
            confidence_score DECIMAL(3,2) DEFAULT 0.5,
            context_examples JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- Extraction Analytics table for performance tracking
        CREATE TABLE IF NOT EXISTS extraction_analytics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            email_domain VARCHAR(255),
            extraction_id TEXT,
            model_version VARCHAR(50) DEFAULT 'gpt-5-mini',
            prompt_variant VARCHAR(100),
            processing_time_ms INTEGER,
            token_count INTEGER,
            overall_confidence DECIMAL(3,2),
            field_accuracies JSONB DEFAULT '{}'::jsonb,
            corrections_applied INTEGER DEFAULT 0,
            patterns_matched INTEGER DEFAULT 0,
            success BOOLEAN DEFAULT true,
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- Company Templates table for reusable extraction patterns
        CREATE TABLE IF NOT EXISTS company_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_domain VARCHAR(255) UNIQUE NOT NULL,
            company_name VARCHAR(500),
            template_data JSONB NOT NULL,
            field_mappings JSONB DEFAULT '{}'::jsonb,
            extraction_rules JSONB DEFAULT '{}'::jsonb,
            usage_count INTEGER DEFAULT 0,
            success_rate DECIMAL(3,2) DEFAULT 1.0,
            last_used TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- Create optimized indexes for learning tables
        CREATE INDEX IF NOT EXISTS idx_corrections_domain ON ai_corrections(email_domain);
        CREATE INDEX IF NOT EXISTS idx_corrections_timestamp ON ai_corrections(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_corrections_message_id ON ai_corrections(internet_message_id);
        CREATE INDEX IF NOT EXISTS idx_corrections_field_gin ON ai_corrections USING gin(field_corrections);
        
        CREATE INDEX IF NOT EXISTS idx_patterns_field ON learning_patterns(field_name);
        CREATE INDEX IF NOT EXISTS idx_patterns_domain ON learning_patterns(email_domain);
        CREATE INDEX IF NOT EXISTS idx_patterns_hash ON learning_patterns(pattern_hash);
        CREATE INDEX IF NOT EXISTS idx_patterns_frequency ON learning_patterns(frequency DESC);
        CREATE INDEX IF NOT EXISTS idx_patterns_success_rate ON learning_patterns(success_rate DESC);
        
        CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON extraction_analytics(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_analytics_domain ON extraction_analytics(email_domain);
        CREATE INDEX IF NOT EXISTS idx_analytics_model ON extraction_analytics(model_version);
        CREATE INDEX IF NOT EXISTS idx_analytics_success ON extraction_analytics(success);
        
        CREATE INDEX IF NOT EXISTS idx_templates_domain ON company_templates(company_domain);
        CREATE INDEX IF NOT EXISTS idx_templates_success_rate ON company_templates(success_rate DESC);
        CREATE INDEX IF NOT EXISTS idx_templates_usage ON company_templates(usage_count DESC);
        """
        
        try:
            async with self.get_connection() as conn:
                await conn.execute(learning_tables_sql)
            
            logger.info("Learning service tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create learning service tables: {e}")
            raise
    
    async def _start_health_monitoring(self):
        """Start background health monitoring task"""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("Health monitoring started")
    
    async def _health_monitor_loop(self):
        """Background health monitoring loop"""
        # Wait a bit before starting health checks to ensure pool is ready
        await asyncio.sleep(5.0)
        
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
                
            except asyncio.CancelledError:
                logger.info("Health monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                self.health_status.is_healthy = False
                self.health_status.last_error = str(e)
    
    async def _perform_health_check(self):
        """Perform health check on database connections"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if not self.main_pool:
                raise Exception("Main connection pool not initialized")
            
            # Test main pool - use timeout to prevent hanging
            try:
                conn = await asyncio.wait_for(self.main_pool.acquire(), timeout=5.0)
                try:
                    await asyncio.wait_for(conn.fetchval('SELECT 1'), timeout=2.0)
                finally:
                    await self.main_pool.release(conn)
            except asyncio.TimeoutError:
                raise Exception("Database connection timeout during health check")
            except GeneratorExit:
                # Handle generator exit gracefully
                logger.warning("Generator exit during health check - ignoring")
                return
            
            # Update health status
            self.health_status.is_healthy = True
            self.health_status.last_check = datetime.now(timezone.utc)
            self.health_status.connection_count = self.main_pool.get_size()
            self.health_status.active_connections = len(self.main_pool._holders) if hasattr(self.main_pool, '_holders') else 0
            self.health_status.last_error = None
            
            # Track response time
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            self._query_times.append(response_time)
            if len(self._query_times) > self._max_query_times:
                self._query_times.pop(0)
            
            self.health_status.avg_response_time_ms = sum(self._query_times) / len(self._query_times)
            
            logger.debug(f"Health check passed in {response_time:.2f}ms")
            
        except GeneratorExit:
            # Silently handle generator exits 
            pass
        except Exception as e:
            # Filter out generator athrow errors
            error_str = str(e)
            if "generator didn't stop after athrow()" not in error_str:
                self.health_status.is_healthy = False
                self.health_status.last_error = error_str
                self.health_status.failed_attempts += 1
                logger.warning(f"Health check failed: {e}")
    
    def get_connection(self):
        """Get a database connection from the pool - returns an async context manager"""
        # Note: Removed @asynccontextmanager decorator to avoid nested async generator issues
        # This method now returns the pool.acquire() context manager directly
        
        class ConnectionWrapper:
            """Wrapper to add retry logic and metrics around pool.acquire()"""
            def __init__(self, manager):
                self.manager = manager
                self.conn = None
                self.start_time = None
            
            async def __aenter__(self):
                if not self.manager.main_pool:
                    await self.manager.initialize()
                    
                if not self.manager.main_pool:
                    raise Exception("Database connection pool not available")
                
                for attempt in range(self.manager.config.retry_attempts):
                    try:
                        self.start_time = asyncio.get_event_loop().time()
                        self.conn = await self.manager.main_pool.acquire()
                        self.manager.health_status.total_queries += 1
                        return self.conn
                        
                    except Exception as e:
                        logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                        
                        if attempt < self.manager.config.retry_attempts - 1:
                            await asyncio.sleep(self.manager.config.retry_delay)
                        else:
                            self.manager.health_status.failed_attempts += 1
                            raise
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.conn:
                    try:
                        # Track query time
                        if self.start_time:
                            query_time = (asyncio.get_event_loop().time() - self.start_time) * 1000
                            self.manager._query_times.append(query_time)
                            if len(self.manager._query_times) > self.manager._max_query_times:
                                self.manager._query_times.pop(0)
                        
                        # Release the connection
                        await self.manager.main_pool.release(self.conn)
                    except Exception as e:
                        logger.error(f"Error releasing connection: {e}")
                
                return False  # Don't suppress exceptions
        
        return ConnectionWrapper(self)
    
    async def execute_query(self, query: str, *args, fetch_mode: str = 'fetchval') -> Any:
        """Execute a query with automatic connection management"""
        async with self.get_connection() as conn:
            if fetch_mode == 'fetchval':
                return await conn.fetchval(query, *args)
            elif fetch_mode == 'fetchrow':
                return await conn.fetchrow(query, *args)
            elif fetch_mode == 'fetch':
                return await conn.fetch(query, *args)
            elif fetch_mode == 'execute':
                return await conn.execute(query, *args)
            else:
                raise ValueError(f"Invalid fetch_mode: {fetch_mode}")
    
    async def execute_transaction(self, queries: List[tuple]) -> List[Any]:
        """Execute multiple queries in a transaction"""
        results = []
        
        async with self.get_connection() as conn:
            async with conn.transaction():
                for query, args, fetch_mode in queries:
                    if fetch_mode == 'fetchval':
                        result = await conn.fetchval(query, *args)
                    elif fetch_mode == 'fetchrow':
                        result = await conn.fetchrow(query, *args)
                    elif fetch_mode == 'fetch':
                        result = await conn.fetch(query, *args)
                    elif fetch_mode == 'execute':
                        result = await conn.execute(query, *args)
                    else:
                        raise ValueError(f"Invalid fetch_mode: {fetch_mode}")
                    
                    results.append(result)
        
        return results
    
    def get_enhanced_client(self) -> Optional[EnhancedPostgreSQLClient]:
        """Get the enhanced PostgreSQL client if available"""
        return self.enhanced_client
    
    def get_health_status(self) -> ConnectionHealth:
        """Get current health status"""
        return self.health_status
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        return {
            'status': self.health_status.to_dict(),
            'configuration': {
                'min_connections': self.config.min_connections,
                'max_connections': self.config.max_connections,
                'command_timeout': self.config.command_timeout,
                'enable_vectors': self.config.enable_vectors,
                'health_check_interval': self.config.health_check_interval
            },
            'features': {
                'enhanced_client_available': self.enhanced_client is not None,
                'vector_support_enabled': self.config.enable_vectors,
                'initialization_complete': self._initialization_complete
            },
            'statistics': {
                'recent_query_times': self._query_times[-10:] if self._query_times else [],
                'avg_query_time_ms': self.health_status.avg_response_time_ms
            }
        }
    
    async def ensure_learning_service_ready(self) -> bool:
        """Ensure learning services have database access and tables"""
        try:
            if not self._initialization_complete:
                logger.info("Database not initialized, attempting initialization...")
                success = await self.initialize()
                if not success:
                    logger.error("Database initialization failed")
                    return False
            
            # Verify learning tables exist and are accessible
            async with self.get_connection() as conn:
                tables_to_check = [
                    'ai_corrections',
                    'learning_patterns', 
                    'extraction_analytics',
                    'company_templates'
                ]
                
                for table in tables_to_check:
                    count = await conn.fetchval(
                        f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = $1",
                        table
                    )
                    if count == 0:
                        logger.warning(f"Learning table {table} does not exist, recreating tables...")
                        await self._ensure_learning_tables()
                        break
            
            logger.info("Learning services database access verified")
            return True
            
        except Exception as e:
            logger.error(f"Learning service database verification failed: {e}")
            return False
    
    async def cleanup(self):
        """Clean up connections and stop monitoring"""
        logger.info("Cleaning up database connection manager...")
        
        # Stop health monitoring
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close enhanced client
        if self.enhanced_client and hasattr(self.enhanced_client, 'pool'):
            try:
                if self.enhanced_client.pool:
                    await self.enhanced_client.pool.close()
            except Exception as e:
                logger.error(f"Error closing enhanced client pool: {e}")
        
        # Close main pool
        if self.main_pool:
            try:
                await self.main_pool.close()
            except Exception as e:
                logger.error(f"Error closing main pool: {e}")
        
        self._initialization_complete = False
        logger.info("Database connection manager cleanup completed")


# Global instance
_connection_manager: Optional[DatabaseConnectionManager] = None


async def get_connection_manager() -> DatabaseConnectionManager:
    """Get the global database connection manager instance"""
    global _connection_manager
    
    if _connection_manager is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise Exception("DATABASE_URL environment variable not set")
        
        # Create configuration from environment
        config = ConnectionConfig(
            connection_string=database_url,
            min_connections=int(os.getenv("DB_MIN_CONNECTIONS", "3")),
            max_connections=int(os.getenv("DB_MAX_CONNECTIONS", "15")),
            command_timeout=int(os.getenv("DB_COMMAND_TIMEOUT", "60")),
            enable_vectors=os.getenv("DB_ENABLE_VECTORS", "true").lower() == "true",
            health_check_interval=int(os.getenv("DB_HEALTH_CHECK_INTERVAL", "30")),
            retry_attempts=int(os.getenv("DB_RETRY_ATTEMPTS", "3")),
            connection_timeout=float(os.getenv("DB_CONNECTION_TIMEOUT", "30.0"))
        )
        
        _connection_manager = DatabaseConnectionManager(database_url, config)
        
        # Initialize immediately
        await _connection_manager.initialize()
    
    return _connection_manager


async def ensure_learning_services_ready() -> bool:
    """Ensure learning services have reliable database access"""
    try:
        manager = await get_connection_manager()
        return await manager.ensure_learning_service_ready()
    except Exception as e:
        logger.error(f"Failed to ensure learning services ready: {e}")
        return False


async def get_database_connection():
    """
    FastAPI dependency for getting a database connection.
    Yields an asyncpg connection from the connection manager pool.
    """
    manager = await get_connection_manager()
    async with manager.pool.acquire() as connection:
        yield connection


# Export main classes and functions
__all__ = [
    'DatabaseConnectionManager',
    'ConnectionConfig',
    'ConnectionHealth',
    'get_connection_manager',
    'get_database_connection',
    'ensure_learning_services_ready'
]