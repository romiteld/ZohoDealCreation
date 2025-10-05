"""
Enhanced Database Manager with Graceful Fallbacks

This module provides robust database connection management with:
- Graceful fallbacks when database is unavailable
- Circuit breaker patterns
- Connection pooling with retry logic
- Health monitoring
- Optional database features
"""

import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union, Callable
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Connection, Pool
from dataclasses import dataclass

from .config_manager import get_config_manager, DatabaseConfig

logger = logging.getLogger(__name__)

@dataclass
class DatabaseHealth:
    """Database health status"""
    is_connected: bool = False
    connection_count: int = 0
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    total_queries: int = 0
    failed_queries: int = 0
    average_response_time: float = 0.0

class DatabaseFeatures:
    """Track which database features are available"""
    
    def __init__(self):
        self.core_tables = False
        self.vector_search = False
        self.full_text_search = False
        self.json_storage = False
        self.caching = False
        self.analytics = False
        self.learning = False
    
    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary for status reporting"""
        return {
            "core_tables": self.core_tables,
            "vector_search": self.vector_search,
            "full_text_search": self.full_text_search,
            "json_storage": self.json_storage,
            "caching": self.caching,
            "analytics": self.analytics,
            "learning": self.learning
        }

class DatabaseManagerState:
    """Database manager state tracking"""
    
    def __init__(self):
        self.is_initialized = False
        self.features = DatabaseFeatures()
        self.health = DatabaseHealth()
        self.circuit_breaker_open = False
        self.circuit_breaker_opens_at = None
        self.last_health_check = None
        self.fallback_mode = False

class EnhancedDatabaseManager:
    """
    Enhanced database manager with graceful fallbacks
    
    Features:
    - Optional database connectivity
    - Circuit breaker pattern
    - Automatic retry logic
    - Health monitoring
    - Feature detection
    - Graceful degradation
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or get_config_manager().database
        self.pool: Optional[Pool] = None
        self.state = DatabaseManagerState()
        self._connection_lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Circuit breaker configuration
        self.max_failures = 5
        self.circuit_breaker_timeout = timedelta(minutes=5)
        self.health_check_interval = timedelta(seconds=30)
    
    async def initialize(self) -> bool:
        """
        Initialize database connection with graceful fallback
        
        Returns:
            bool: True if database is available, False if running in fallback mode
        """
        if not self.config.enabled:
            logger.info("Database disabled in configuration - running in fallback mode")
            self.state.fallback_mode = True
            self.state.is_initialized = True
            return False
        
        try:
            await self._create_connection_pool()
            await self._detect_features()
            await self._ensure_schema()
            
            self.state.is_initialized = True
            self.state.fallback_mode = False
            self.state.health.is_connected = True
            self.state.health.last_check = datetime.utcnow()
            
            # Start health monitoring
            self._start_health_monitoring()
            
            logger.info("Database manager initialized successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Database initialization failed, falling back to non-database mode: {e}")
            logger.debug(f"Database error traceback: {traceback.format_exc()}")
            
            self.state.fallback_mode = True
            self.state.is_initialized = True
            self.state.health.last_error = str(e)
            self.state.health.last_check = datetime.utcnow()
            
            return False
    
    async def _create_connection_pool(self):
        """Create database connection pool with retry logic"""
        if not self.config.url:
            raise ValueError("Database URL not configured")
        
        for attempt in range(self.config.retry_attempts):
            try:
                self.pool = await asyncpg.create_pool(
                    self.config.url,
                    min_size=max(1, self.config.pool_size // 4),
                    max_size=self.config.pool_size,
                    max_queries=10000,
                    max_inactive_connection_lifetime=self.config.pool_recycle,
                    command_timeout=self.config.pool_timeout,
                    server_settings={
                        'application_name': 'well-intake-api-enhanced',
                        'jit': 'off'  # Disable JIT for better connection stability
                    }
                )
                
                # Test the pool
                async with self.pool.acquire() as conn:
                    await conn.fetchval('SELECT 1')
                
                logger.info(f"Database connection pool created (size: {self.config.pool_size})")
                return
                
            except Exception as e:
                wait_time = min(
                    self.config.retry_delay * (2 ** attempt),
                    self.config.max_retry_delay
                )
                
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    raise e
    
    async def _detect_features(self):
        """Detect available database features"""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Check for vector extension (pgvector)
                vector_result = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                )
                self.state.features.vector_search = bool(vector_result)
                
                # Check for JSON support (should be available in all modern PostgreSQL)
                json_result = await conn.fetchval("SELECT '{}'::jsonb")
                self.state.features.json_storage = json_result is not None
                
                # Check for full-text search
                fts_result = await conn.fetchval(
                    "SELECT 1 FROM pg_proc WHERE proname = 'to_tsvector'"
                )
                self.state.features.full_text_search = bool(fts_result)
                
                self.state.features.core_tables = True
                self.state.features.caching = True
                self.state.features.analytics = True
                self.state.features.learning = True
                
                logger.info(f"Database features detected: {self.state.features.to_dict()}")
                
        except Exception as e:
            logger.warning(f"Feature detection failed: {e}")
    
    async def _ensure_schema(self):
        """Ensure required database schema exists"""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Create core tables if they don't exist
                await self._create_core_tables(conn)
                
                # Create vector tables if vector extension is available
                if self.state.features.vector_search:
                    await self._create_vector_tables(conn)
                
                logger.info("Database schema verification completed")
                
        except Exception as e:
            logger.warning(f"Schema setup failed: {e}")
    
    async def _create_core_tables(self, conn: Connection):
        """Create core tables for basic functionality"""
        
        # Email processing results table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS email_processing_results (
                id SERIAL PRIMARY KEY,
                email_hash VARCHAR(64) UNIQUE NOT NULL,
                sender_email VARCHAR(255) NOT NULL,
                sender_domain VARCHAR(255) NOT NULL,
                subject VARCHAR(500),
                extracted_data JSONB,
                zoho_contact_id VARCHAR(50),
                zoho_lead_id VARCHAR(50),
                zoho_deal_id VARCHAR(50),
                processing_time_ms INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                status VARCHAR(50) DEFAULT 'processed',
                model_used VARCHAR(50),
                cost_tokens INTEGER DEFAULT 0,
                cost_usd DECIMAL(10, 6) DEFAULT 0.00
            )
        """)
        
        # Create indexes for performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_processing_sender_domain 
            ON email_processing_results (sender_domain)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_processing_created_at 
            ON email_processing_results (created_at)
        """)
        
        # Pattern cache table for intelligent caching
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS email_pattern_cache (
                id SERIAL PRIMARY KEY,
                pattern_hash VARCHAR(64) UNIQUE NOT NULL,
                pattern_type VARCHAR(50) NOT NULL,
                cached_result JSONB,
                hit_count INTEGER DEFAULT 1,
                last_hit TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pattern_cache_expires 
            ON email_pattern_cache (expires_at)
        """)
    
    async def _create_vector_tables(self, conn: Connection):
        """Create vector tables for embeddings (if pgvector is available)"""
        
        # Email embeddings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS email_embeddings (
                id SERIAL PRIMARY KEY,
                email_hash VARCHAR(64) UNIQUE NOT NULL,
                content_embedding vector(1536),
                metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Create vector similarity index
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_embeddings_vector 
            ON email_embeddings USING ivfflat (content_embedding vector_cosine_ops) 
            WITH (lists = 100)
        """)
    
    def _start_health_monitoring(self):
        """Start background health monitoring task"""
        if self._health_check_task and not self._health_check_task.done():
            return
        
        async def health_monitor():
            while True:
                try:
                    await asyncio.sleep(self.health_check_interval.total_seconds())
                    await self._check_health()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
        
        self._health_check_task = asyncio.create_task(health_monitor())
        logger.info("Database health monitoring started")
    
    async def _check_health(self):
        """Perform health check on database connection"""
        if self.state.circuit_breaker_open:
            # Check if circuit breaker should be reset
            if (datetime.utcnow() - self.state.circuit_breaker_opens_at) > self.circuit_breaker_timeout:
                logger.info("Attempting to reset database circuit breaker")
                self.state.circuit_breaker_open = False
                self.state.circuit_breaker_opens_at = None
            else:
                return
        
        try:
            if self.pool:
                start_time = datetime.utcnow()
                async with self.pool.acquire() as conn:
                    await conn.fetchval('SELECT 1')
                
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                self.state.health.is_connected = True
                self.state.health.last_check = datetime.utcnow()
                self.state.health.average_response_time = (
                    self.state.health.average_response_time * 0.9 + response_time * 0.1
                )
                
                # Reset failure tracking on successful health check
                if hasattr(self.state.health, 'consecutive_failures'):
                    self.state.health.consecutive_failures = 0
                
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            self.state.health.is_connected = False
            self.state.health.last_error = str(e)
            self.state.health.last_check = datetime.utcnow()
            
            # Track consecutive failures
            if not hasattr(self.state.health, 'consecutive_failures'):
                self.state.health.consecutive_failures = 0
            self.state.health.consecutive_failures += 1
            
            # Open circuit breaker if too many failures
            if self.state.health.consecutive_failures >= self.max_failures:
                logger.error("Opening database circuit breaker due to consecutive failures")
                self.state.circuit_breaker_open = True
                self.state.circuit_breaker_opens_at = datetime.utcnow()
    
    def get_connection(self):
        """
        Get database connection with circuit breaker protection
        
        Returns context manager that yields None if database is unavailable (fallback mode)
        """
        # Removed @asynccontextmanager to avoid generator athrow() error
        
        class EnhancedConnectionWrapper:
            """Custom async context manager to avoid nested generator issues"""
            def __init__(self, manager):
                self.manager = manager
                self.conn = None
                
            async def __aenter__(self):
                if self.manager.state.fallback_mode or self.manager.state.circuit_breaker_open or not self.manager.pool:
                    return None
                
                try:
                    self.conn = await self.manager.pool.acquire()
                    self.manager.state.health.total_queries += 1
                    return self.conn
                except Exception as e:
                    self.manager.state.health.failed_queries += 1
                    logger.warning(f"Database query failed: {e}")
                    return None
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.conn:
                    try:
                        await self.manager.pool.release(self.conn)
                    except Exception as e:
                        logger.warning(f"Failed to release connection: {e}")
                return False  # Don't suppress exceptions
        
        return EnhancedConnectionWrapper(self)
    
    async def execute_query(
        self,
        query: str,
        *args,
        fallback_value: Any = None,
        timeout: float = 30.0
    ) -> Any:
        """
        Execute query with fallback handling
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            fallback_value: Value to return if database unavailable
            timeout: Query timeout in seconds
        
        Returns:
            Query result or fallback_value if database unavailable
        """
        async with self.get_connection() as conn:
            if conn is None:
                return fallback_value
            
            try:
                return await asyncio.wait_for(
                    conn.fetchval(query, *args),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Query timeout after {timeout}s: {query[:100]}...")
                return fallback_value
            except Exception as e:
                logger.warning(f"Query execution failed: {e}")
                return fallback_value
    
    async def execute_many(
        self,
        query: str,
        args_list: List[tuple],
        timeout: float = 60.0
    ) -> bool:
        """
        Execute multiple queries in a transaction
        
        Args:
            query: SQL query to execute
            args_list: List of parameter tuples
            timeout: Transaction timeout in seconds
        
        Returns:
            bool: True if successful, False if failed/fallback
        """
        async with self.get_connection() as conn:
            if conn is None:
                return False
            
            try:
                async with conn.transaction():
                    await asyncio.wait_for(
                        conn.executemany(query, args_list),
                        timeout=timeout
                    )
                return True
                
            except Exception as e:
                logger.warning(f"Bulk query execution failed: {e}")
                return False
    
    def is_available(self) -> bool:
        """Check if database is available"""
        return (
            self.state.is_initialized and 
            not self.state.fallback_mode and 
            not self.state.circuit_breaker_open and 
            self.state.health.is_connected
        )
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status"""
        return {
            "is_available": self.is_available(),
            "is_initialized": self.state.is_initialized,
            "fallback_mode": self.state.fallback_mode,
            "circuit_breaker_open": self.state.circuit_breaker_open,
            "features": self.state.features.to_dict(),
            "health": {
                "is_connected": self.state.health.is_connected,
                "last_check": self.state.health.last_check.isoformat() if self.state.health.last_check else None,
                "last_error": self.state.health.last_error,
                "total_queries": self.state.health.total_queries,
                "failed_queries": self.state.health.failed_queries,
                "success_rate": (
                    (self.state.health.total_queries - self.state.health.failed_queries) / 
                    max(1, self.state.health.total_queries) * 100
                ) if self.state.health.total_queries > 0 else 100.0,
                "average_response_time": self.state.health.average_response_time
            },
            "pool_info": {
                "size": self.config.pool_size if self.pool else 0,
                "active_connections": len(self.pool._holders) if self.pool and hasattr(self.pool, '_holders') else 0
            }
        }
    
    async def cleanup(self):
        """Clean up resources"""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

# Global database manager instance
_database_manager: Optional[EnhancedDatabaseManager] = None

async def get_database_manager() -> EnhancedDatabaseManager:
    """Get the global database manager instance"""
    global _database_manager
    
    if _database_manager is None:
        _database_manager = EnhancedDatabaseManager()
        await _database_manager.initialize()
    
    return _database_manager

async def cleanup_database_manager():
    """Cleanup the global database manager"""
    global _database_manager
    
    if _database_manager:
        await _database_manager.cleanup()
        _database_manager = None