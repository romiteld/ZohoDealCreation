"""
Enhanced PostgreSQL Client with pgvector support for GPT-5-mini 400K context
Provides advanced vector similarity search, cost tracking, and correction learning
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np

# Make dependencies optional
try:
    import asyncpg
    from pgvector.asyncpg import register_vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    asyncpg = None
    register_vector = None

logger = logging.getLogger(__name__)

class VectorDimension(Enum):
    """Supported vector dimensions for different models"""
    OPENAI_ADA = 1536      # text-embedding-ada-002
    OPENAI_3_SMALL = 1536  # text-embedding-3-small
    OPENAI_3_LARGE = 3072  # text-embedding-3-large
    GPT5_MINI = 2048       # GPT-5-mini embeddings (hypothetical)
    GPT5_FULL = 4096       # GPT-5 full embeddings (hypothetical)

@dataclass
class ContextWindow:
    """Context window configuration for GPT-5 models"""
    model_tier: str
    max_tokens: int
    chunk_size: int
    overlap_tokens: int
    
    def calculate_chunks(self, total_tokens: int) -> int:
        """Calculate number of chunks needed for given token count"""
        if total_tokens <= self.max_tokens:
            return 1
        
        effective_chunk_size = self.chunk_size - self.overlap_tokens
        return (total_tokens - self.overlap_tokens) // effective_chunk_size + 1

# GPT-5 Context Windows
CONTEXT_WINDOWS = {
    "gpt-5-nano": ContextWindow("gpt-5-nano", 400000, 50000, 2000),
    "gpt-5-mini": ContextWindow("gpt-5-mini", 400000, 50000, 2000),
    "gpt-5": ContextWindow("gpt-5", 400000, 50000, 2000),
}

class EnhancedPostgreSQLClient:
    """Enhanced PostgreSQL client with pgvector and GPT-5 400K context support"""
    
    def __init__(self, connection_string: str, enable_vectors: bool = True):
        if not HAS_PGVECTOR and enable_vectors:
            logger.warning("pgvector not installed. Vector features will be limited.")
        
        self.connection_string = connection_string
        self.pool = None
        self.enable_vectors = enable_vectors and HAS_PGVECTOR
        self._vector_dimension = VectorDimension.OPENAI_3_SMALL.value
        
    async def init_pool(self):
        """Initialize connection pool with pgvector support"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10,
                server_settings={'jit': 'off'},  # Disable JIT for pgvector operations
                init=self._init_connection if self.enable_vectors else None
            )
    
    async def _init_connection(self, conn):
        """Initialize connection with pgvector extension"""
        if register_vector:
            await register_vector(conn)
    
    async def ensure_enhanced_tables(self):
        """Create enhanced tables with pgvector support for 400K contexts"""
        await self.init_pool()
        
        # Enhanced table creation SQL
        create_tables_sql = """
        -- Enable required extensions
        CREATE EXTENSION IF NOT EXISTS vector;
        -- pg_trgm and btree_gin not available in Azure Database for PostgreSQL flexible server
        -- CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity
        -- CREATE EXTENSION IF NOT EXISTS btree_gin;  -- For composite indexes
        
        -- Context storage for 400K token windows
        CREATE TABLE IF NOT EXISTS large_contexts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            context_hash TEXT UNIQUE NOT NULL,
            model_tier TEXT NOT NULL,
            total_tokens INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            chunks JSONB NOT NULL,  -- Array of text chunks
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            access_count INTEGER DEFAULT 1
        );
        
        -- Vector embeddings with multiple dimensions support
        CREATE TABLE IF NOT EXISTS context_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            context_id UUID REFERENCES large_contexts(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding vector(3072),  -- Max dimension for flexibility
            dimension INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(context_id, chunk_index)
        );
        
        -- Cost tracking for GPT-5 tiers
        CREATE TABLE IF NOT EXISTS model_costs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            model_tier TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cached_tokens INTEGER DEFAULT 0,
            total_cost DECIMAL(10, 6) NOT NULL,
            request_id TEXT,
            email_id UUID,
            processing_time_ms INTEGER,
            success BOOLEAN DEFAULT true,
            error_message TEXT,
            metadata JSONB
        );
        
        -- Enhanced correction patterns with embeddings
        CREATE TABLE IF NOT EXISTS correction_patterns_enhanced (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pattern_hash TEXT UNIQUE NOT NULL,
            field_name TEXT NOT NULL,
            original_value TEXT,
            corrected_value TEXT,
            pattern_embedding vector(1536),  -- For semantic similarity
            frequency INTEGER DEFAULT 1,
            confidence_score DECIMAL(3, 2) DEFAULT 0.5,
            domains TEXT[],  -- Array of domains where pattern observed
            context_snippets JSONB,  -- Examples of contexts
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Similarity cache for faster lookups
        CREATE TABLE IF NOT EXISTS similarity_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_hash TEXT NOT NULL,
            similar_items JSONB NOT NULL,  -- Array of {id, score, data}
            model_used TEXT,
            threshold DECIMAL(3, 2),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE,
            UNIQUE(query_hash, model_used, threshold)
        );
        
        -- Processing metrics for optimization
        CREATE TABLE IF NOT EXISTS processing_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            date DATE NOT NULL DEFAULT CURRENT_DATE,
            model_tier TEXT NOT NULL,
            total_requests INTEGER DEFAULT 0,
            successful_requests INTEGER DEFAULT 0,
            failed_requests INTEGER DEFAULT 0,
            total_input_tokens BIGINT DEFAULT 0,
            total_output_tokens BIGINT DEFAULT 0,
            total_cost DECIMAL(10, 4) DEFAULT 0,
            avg_latency_ms INTEGER,
            p95_latency_ms INTEGER,
            p99_latency_ms INTEGER,
            cache_hits INTEGER DEFAULT 0,
            cache_misses INTEGER DEFAULT 0,
            UNIQUE(date, model_tier)
        );
        
        -- Create optimized indexes
        CREATE INDEX IF NOT EXISTS idx_contexts_hash ON large_contexts(context_hash);
        CREATE INDEX IF NOT EXISTS idx_contexts_accessed ON large_contexts(last_accessed DESC);
        CREATE INDEX IF NOT EXISTS idx_costs_timestamp ON model_costs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_costs_model ON model_costs(model_tier, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_patterns_field ON correction_patterns_enhanced(field_name);
        CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON correction_patterns_enhanced(confidence_score DESC);
        CREATE INDEX IF NOT EXISTS idx_cache_expires ON similarity_cache(expires_at) WHERE expires_at IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_metrics_date ON processing_metrics(date DESC);
        
        -- Vector similarity indexes (HNSW for accuracy, IVFFlat for speed)
        CREATE INDEX IF NOT EXISTS idx_context_embeddings_hnsw ON context_embeddings 
            USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
        
        CREATE INDEX IF NOT EXISTS idx_patterns_embedding_ivfflat ON correction_patterns_enhanced 
            USING ivfflat (pattern_embedding vector_cosine_ops) WITH (lists = 100);
        
        -- Composite GIN index for JSONB queries
        CREATE INDEX IF NOT EXISTS idx_contexts_metadata_gin ON large_contexts USING gin(metadata);
        CREATE INDEX IF NOT EXISTS idx_patterns_snippets_gin ON correction_patterns_enhanced USING gin(context_snippets);
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(create_tables_sql)
        
        logger.info("Enhanced PostgreSQL tables with pgvector support ensured")
    
    async def store_large_context(
        self,
        content: str,
        model_tier: str,
        total_tokens: int,
        metadata: Optional[Dict] = None
    ) -> str:
        """Store large context (up to 400K tokens) with chunking"""
        await self.init_pool()
        
        # Generate context hash
        context_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check if already exists
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM large_contexts WHERE context_hash = $1",
                context_hash
            )
            
            if existing:
                # Update access count and timestamp
                await conn.execute("""
                    UPDATE large_contexts 
                    SET last_accessed = NOW(), access_count = access_count + 1
                    WHERE id = $1
                """, existing['id'])
                return str(existing['id'])
            
            # Calculate chunks based on context window
            context_window = CONTEXT_WINDOWS.get(model_tier, CONTEXT_WINDOWS["gpt-5-mini"])
            chunks = self._chunk_content(content, context_window)
            
            # Store context
            context_id = await conn.fetchval("""
                INSERT INTO large_contexts (
                    context_hash, model_tier, total_tokens, chunk_count, chunks, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """, context_hash, model_tier, total_tokens, len(chunks), 
                json.dumps(chunks), json.dumps(metadata or {}))
            
            return str(context_id)
    
    def _chunk_content(self, content: str, context_window: ContextWindow) -> List[str]:
        """Chunk content for large context windows with overlap"""
        # Simple character-based chunking (in production, use tokenizer)
        chunk_size_chars = context_window.chunk_size * 4  # Approximate chars per token
        overlap_chars = context_window.overlap_tokens * 4
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + chunk_size_chars, len(content))
            chunk = content[start:end]
            chunks.append(chunk)
            
            if end >= len(content):
                break
            
            start = end - overlap_chars
        
        return chunks
    
    async def store_embedding(
        self,
        context_id: str,
        chunk_index: int,
        embedding: List[float],
        model: str = "text-embedding-3-small"
    ) -> str:
        """Store vector embedding for a context chunk"""
        if not self.enable_vectors:
            logger.warning("Vector features disabled")
            return ""
        
        await self.init_pool()
        
        dimension = len(embedding)
        
        async with self.pool.acquire() as conn:
            embedding_id = await conn.fetchval("""
                INSERT INTO context_embeddings (
                    context_id, chunk_index, embedding_model, embedding, dimension
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (context_id, chunk_index) 
                DO UPDATE SET 
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    dimension = EXCLUDED.dimension,
                    created_at = NOW()
                RETURNING id
            """, context_id, chunk_index, model, embedding, dimension)
            
            return str(embedding_id)
    
    async def search_similar_contexts(
        self,
        query_embedding: List[float],
        limit: int = 5,
        threshold: float = 0.8,
        model_tier: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar contexts using vector similarity"""
        if not self.enable_vectors:
            return []
        
        await self.init_pool()
        
        # Build query with optional model tier filter
        query = """
            SELECT 
                lc.*,
                ce.embedding <=> $1 as distance,
                1 - (ce.embedding <=> $1) as similarity
            FROM context_embeddings ce
            JOIN large_contexts lc ON lc.id = ce.context_id
            WHERE ce.chunk_index = 0  -- Use first chunk for similarity
        """
        
        params = [query_embedding]
        param_count = 1
        
        if model_tier:
            param_count += 1
            query += f" AND lc.model_tier = ${param_count}"
            params.append(model_tier)
        
        query += f"""
            AND 1 - (ce.embedding <=> $1) >= ${param_count + 1}
            ORDER BY distance
            LIMIT ${param_count + 2}
        """
        params.extend([threshold, limit])
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            results = []
            for row in rows:
                result = dict(row)
                result['chunks'] = json.loads(result['chunks']) if result['chunks'] else []
                result['metadata'] = json.loads(result['metadata']) if result['metadata'] else {}
                results.append(result)
            
            return results
    
    async def track_model_cost(
        self,
        model_tier: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        cost: float = 0.0,
        request_id: Optional[str] = None,
        email_id: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Track model usage and costs"""
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            cost_id = await conn.fetchval("""
                INSERT INTO model_costs (
                    model_tier, input_tokens, output_tokens, cached_tokens,
                    total_cost, request_id, email_id, processing_time_ms,
                    success, error_message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """, model_tier, input_tokens, output_tokens, cached_tokens,
                cost, request_id, email_id, processing_time_ms,
                success, error_message, json.dumps(metadata or {}))
            
            # Update daily metrics
            await self._update_processing_metrics(
                conn, model_tier, input_tokens, output_tokens,
                cost, processing_time_ms, success
            )
            
            return str(cost_id)
    
    async def _update_processing_metrics(
        self,
        conn,
        model_tier: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: Optional[int],
        success: bool
    ):
        """Update processing metrics for the day"""
        today = datetime.now(timezone.utc).date()
        
        await conn.execute("""
            INSERT INTO processing_metrics (
                date, model_tier, total_requests, successful_requests,
                failed_requests, total_input_tokens, total_output_tokens,
                total_cost, avg_latency_ms
            ) VALUES ($1, $2, 1, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (date, model_tier) DO UPDATE SET
                total_requests = processing_metrics.total_requests + 1,
                successful_requests = processing_metrics.successful_requests + CASE WHEN $3 = 1 THEN 1 ELSE 0 END,
                failed_requests = processing_metrics.failed_requests + CASE WHEN $4 = 1 THEN 1 ELSE 0 END,
                total_input_tokens = processing_metrics.total_input_tokens + $5,
                total_output_tokens = processing_metrics.total_output_tokens + $6,
                total_cost = processing_metrics.total_cost + $7,
                avg_latency_ms = CASE 
                    WHEN $8 IS NOT NULL THEN 
                        ((processing_metrics.avg_latency_ms * processing_metrics.total_requests + $8) / 
                         (processing_metrics.total_requests + 1))::INTEGER
                    ELSE processing_metrics.avg_latency_ms
                END
        """, today, model_tier, 1 if success else 0, 0 if success else 1,
            input_tokens, output_tokens, cost, latency_ms)
    
    async def store_correction_pattern(
        self,
        field_name: str,
        original_value: Optional[str],
        corrected_value: Optional[str],
        embedding: Optional[List[float]] = None,
        domain: Optional[str] = None,
        context_snippet: Optional[str] = None
    ) -> str:
        """Store an enhanced correction pattern with embedding"""
        await self.init_pool()
        
        # Generate pattern hash
        pattern_str = f"{field_name}:{original_value}>{corrected_value}"
        pattern_hash = hashlib.md5(pattern_str.encode()).hexdigest()
        
        async with self.pool.acquire() as conn:
            # Check if pattern exists
            existing = await conn.fetchrow("""
                SELECT id, frequency, domains, context_snippets, confidence_score
                FROM correction_patterns_enhanced
                WHERE pattern_hash = $1
            """, pattern_hash)
            
            if existing:
                # Update existing pattern
                domains = existing['domains'] or []
                if domain and domain not in domains:
                    domains.append(domain)
                
                snippets = json.loads(existing['context_snippets'] or '[]')
                if context_snippet and len(snippets) < 10:  # Keep max 10 examples
                    snippets.append({
                        'snippet': context_snippet[:500],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
                # Increase confidence with frequency
                new_confidence = min(0.95, existing['confidence_score'] + 0.05)
                
                pattern_id = await conn.fetchval("""
                    UPDATE correction_patterns_enhanced
                    SET frequency = frequency + 1,
                        confidence_score = $2,
                        domains = $3,
                        context_snippets = $4,
                        pattern_embedding = COALESCE($5, pattern_embedding),
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING id
                """, existing['id'], new_confidence, domains,
                    json.dumps(snippets), embedding)
            else:
                # Create new pattern
                domains = [domain] if domain else []
                snippets = []
                if context_snippet:
                    snippets.append({
                        'snippet': context_snippet[:500],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
                pattern_id = await conn.fetchval("""
                    INSERT INTO correction_patterns_enhanced (
                        pattern_hash, field_name, original_value, corrected_value,
                        pattern_embedding, domains, context_snippets
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                """, pattern_hash, field_name, original_value, corrected_value,
                    embedding, domains, json.dumps(snippets))
            
            return str(pattern_id)
    
    async def get_relevant_correction_patterns(
        self,
        field_name: Optional[str] = None,
        domain: Optional[str] = None,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get relevant correction patterns for improving extraction"""
        await self.init_pool()
        
        query = """
            SELECT * FROM correction_patterns_enhanced
            WHERE confidence_score >= $1
        """
        params = [min_confidence]
        param_count = 1
        
        if field_name:
            param_count += 1
            query += f" AND field_name = ${param_count}"
            params.append(field_name)
        
        if domain:
            param_count += 1
            query += f" AND $${param_count} = ANY(domains)"
            params.append(domain)
        
        query += f"""
            ORDER BY confidence_score DESC, frequency DESC
            LIMIT ${param_count + 1}
        """
        params.append(limit)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            patterns = []
            for row in rows:
                pattern = dict(row)
                pattern['context_snippets'] = json.loads(pattern['context_snippets'] or '[]')
                patterns.append(pattern)
            
            return patterns
    
    async def search_similar_patterns(
        self,
        query_embedding: List[float],
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar correction patterns using embeddings"""
        if not self.enable_vectors:
            return []
        
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    *,
                    pattern_embedding <=> $1 as distance,
                    1 - (pattern_embedding <=> $1) as similarity
                FROM correction_patterns_enhanced
                WHERE pattern_embedding IS NOT NULL
                    AND 1 - (pattern_embedding <=> $1) >= $2
                ORDER BY distance
                LIMIT $3
            """, query_embedding, threshold, limit)
            
            patterns = []
            for row in rows:
                pattern = dict(row)
                pattern['context_snippets'] = json.loads(pattern['context_snippets'] or '[]')
                patterns.append(pattern)
            
            return patterns
    
    async def cache_similarity_results(
        self,
        query_hash: str,
        results: List[Dict[str, Any]],
        model_used: str,
        threshold: float,
        ttl_hours: int = 24
    ):
        """Cache similarity search results for faster lookups"""
        await self.init_pool()
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO similarity_cache (
                    query_hash, similar_items, model_used, threshold, expires_at
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (query_hash, model_used, threshold)
                DO UPDATE SET
                    similar_items = EXCLUDED.similar_items,
                    created_at = NOW(),
                    expires_at = EXCLUDED.expires_at
            """, query_hash, json.dumps(results), model_used, threshold, expires_at)
    
    async def get_cached_similarity(
        self,
        query_hash: str,
        model_used: str,
        threshold: float
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached similarity results if available and not expired"""
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT similar_items FROM similarity_cache
                WHERE query_hash = $1 
                    AND model_used = $2 
                    AND threshold = $3
                    AND (expires_at IS NULL OR expires_at > NOW())
            """, query_hash, model_used, threshold)
            
            if row:
                return json.loads(row['similar_items'])
            return None
    
    async def get_cost_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        model_tier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive cost analytics"""
        await self.init_pool()
        
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        async with self.pool.acquire() as conn:
            # Overall stats
            overall_query = """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(cached_tokens) as total_cached_tokens,
                    SUM(total_cost) as total_cost,
                    AVG(processing_time_ms) as avg_processing_time,
                    COUNT(CASE WHEN success THEN 1 END) as successful_requests,
                    COUNT(CASE WHEN NOT success THEN 1 END) as failed_requests
                FROM model_costs
                WHERE timestamp BETWEEN $1 AND $2
            """
            params = [start_date, end_date]
            
            if model_tier:
                overall_query += " AND model_tier = $3"
                params.append(model_tier)
            
            overall = await conn.fetchrow(overall_query, *params)
            
            # Per-model breakdown
            model_query = """
                SELECT 
                    model_tier,
                    COUNT(*) as requests,
                    SUM(total_cost) as cost,
                    AVG(processing_time_ms) as avg_latency
                FROM model_costs
                WHERE timestamp BETWEEN $1 AND $2
                GROUP BY model_tier
                ORDER BY cost DESC
            """
            
            model_breakdown = await conn.fetch(model_query, start_date, end_date)
            
            # Daily trends
            daily_query = """
                SELECT 
                    DATE(timestamp) as date,
                    SUM(total_cost) as daily_cost,
                    COUNT(*) as daily_requests
                FROM model_costs
                WHERE timestamp BETWEEN $1 AND $2
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT 30
            """
            
            daily_trends = await conn.fetch(daily_query, start_date, end_date)
            
            return {
                'overall': dict(overall) if overall else {},
                'model_breakdown': [dict(row) for row in model_breakdown],
                'daily_trends': [dict(row) for row in daily_trends],
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
    
    async def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old data to manage storage"""
        await self.init_pool()
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        async with self.pool.acquire() as conn:
            # Clean old contexts that haven't been accessed
            deleted_contexts = await conn.fetchval("""
                DELETE FROM large_contexts
                WHERE last_accessed < $1 AND access_count < 3
                RETURNING COUNT(*)
            """, cutoff_date)
            
            # Clean expired cache
            deleted_cache = await conn.fetchval("""
                DELETE FROM similarity_cache
                WHERE expires_at < NOW()
                RETURNING COUNT(*)
            """, )
            
            # Archive old cost data (move to summary table in production)
            archived_costs = await conn.fetchval("""
                DELETE FROM model_costs
                WHERE timestamp < $1
                RETURNING COUNT(*)
            """, cutoff_date)
            
            logger.info(f"Cleanup complete: {deleted_contexts} contexts, "
                       f"{deleted_cache} cache entries, {archived_costs} cost records")
            
            return {
                'deleted_contexts': deleted_contexts,
                'deleted_cache': deleted_cache,
                'archived_costs': archived_costs
            }
    
    async def optimize_indexes(self):
        """Optimize database indexes for performance"""
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            # Reindex vector indexes periodically
            await conn.execute("REINDEX INDEX CONCURRENTLY idx_context_embeddings_hnsw;")
            await conn.execute("REINDEX INDEX CONCURRENTLY idx_patterns_embedding_ivfflat;")
            
            # Update statistics
            await conn.execute("ANALYZE large_contexts;")
            await conn.execute("ANALYZE context_embeddings;")
            await conn.execute("ANALYZE correction_patterns_enhanced;")
            
            logger.info("Database indexes optimized")


class CostAwareVectorSearch:
    """Cost-aware vector similarity search with GPT-5 optimization"""
    
    def __init__(self, db_client: EnhancedPostgreSQLClient, cost_optimizer):
        self.db = db_client
        self.cost_optimizer = cost_optimizer
    
    async def search_with_cost_optimization(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = 5,
        max_cost: float = 0.10
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """Search with cost optimization"""
        
        # Check cache first
        query_hash = hashlib.md5(str(query_embedding[:10]).encode()).hexdigest()
        cached = await self.db.get_cached_similarity(query_hash, "search", 0.8)
        
        if cached:
            return cached, {"source": "cache", "cost": 0}
        
        # Analyze query complexity
        complexity = self.cost_optimizer.analyze_email_complexity(query_text)
        model_tier, reasoning = self.cost_optimizer.select_model_tier(complexity)
        
        # Perform search
        results = await self.db.search_similar_contexts(
            query_embedding, limit=limit, model_tier=model_tier.value
        )
        
        # Calculate and track cost
        estimated_tokens = len(query_text.split()) * 2  # Rough estimate
        cost = self.cost_optimizer.calculate_cost(
            model_tier, estimated_tokens, 100, cached=False
        )
        
        if cost <= max_cost:
            # Cache results
            await self.db.cache_similarity_results(
                query_hash, results, "search", 0.8, ttl_hours=24
            )
            
            return results, {
                "source": "fresh",
                "cost": cost,
                "model_tier": model_tier.value,
                "reasoning": reasoning
            }
        else:
            # Cost too high, use cached or simpler search
            return [], {
                "source": "skipped",
                "reason": "cost_exceeded",
                "estimated_cost": cost,
                "max_cost": max_cost
            }


# Export main classes
__all__ = [
    'EnhancedPostgreSQLClient',
    'CostAwareVectorSearch',
    'VectorDimension',
    'ContextWindow',
    'CONTEXT_WINDOWS'
]