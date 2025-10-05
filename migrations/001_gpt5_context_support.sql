-- Migration: 001_gpt5_context_support.sql
-- Purpose: Add pgvector support for GPT-5-mini 400K context windows
-- Author: System
-- Date: 2025-08-29

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity matching
CREATE EXTENSION IF NOT EXISTS btree_gin;  -- For composite GIN indexes
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- For query performance monitoring

-- ========================================
-- LARGE CONTEXT STORAGE (400K tokens)
-- ========================================

-- Main table for storing large contexts with chunking support
CREATE TABLE IF NOT EXISTS large_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_hash TEXT UNIQUE NOT NULL,  -- SHA256 hash for deduplication
    model_tier TEXT NOT NULL CHECK (model_tier IN ('gpt-5-nano', 'gpt-5-mini', 'gpt-5')),
    total_tokens INTEGER NOT NULL CHECK (total_tokens > 0 AND total_tokens <= 400000),
    chunk_count INTEGER NOT NULL CHECK (chunk_count > 0),
    chunks JSONB NOT NULL,  -- Array of text chunks with metadata
    metadata JSONB DEFAULT '{}',  -- Additional context metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_count INTEGER DEFAULT 1 CHECK (access_count >= 0),
    compression_ratio DECIMAL(3,2),  -- For storage optimization
    source_type TEXT,  -- email, document, conversation, etc.
    CONSTRAINT valid_chunks CHECK (jsonb_array_length(chunks) = chunk_count)
);

-- Indexes for large_contexts
CREATE INDEX idx_contexts_hash ON large_contexts(context_hash);
CREATE INDEX idx_contexts_model_tier ON large_contexts(model_tier);
CREATE INDEX idx_contexts_accessed ON large_contexts(last_accessed DESC);
CREATE INDEX idx_contexts_tokens ON large_contexts(total_tokens);
CREATE INDEX idx_contexts_source ON large_contexts(source_type) WHERE source_type IS NOT NULL;
CREATE INDEX idx_contexts_metadata_gin ON large_contexts USING gin(metadata);

-- ========================================
-- VECTOR EMBEDDINGS WITH DIMENSION FLEXIBILITY
-- ========================================

-- Store embeddings for context chunks with support for multiple models
CREATE TABLE IF NOT EXISTS context_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id UUID NOT NULL REFERENCES large_contexts(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    embedding_model TEXT NOT NULL,
    embedding vector(3072),  -- Max dimension for GPT-5 future models
    dimension INTEGER NOT NULL CHECK (dimension > 0 AND dimension <= 3072),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(context_id, chunk_index),
    CONSTRAINT valid_embedding_dimension CHECK (dimension = array_length(embedding::real[], 1))
);

-- High-performance vector indexes
-- HNSW for high accuracy similarity search
CREATE INDEX idx_embeddings_hnsw_cosine ON context_embeddings 
    USING hnsw (embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64);

-- IVFFlat for faster approximate search on large datasets
CREATE INDEX idx_embeddings_ivfflat_l2 ON context_embeddings 
    USING ivfflat (embedding vector_l2_ops) 
    WITH (lists = 100);

-- Standard B-tree indexes
CREATE INDEX idx_embeddings_context ON context_embeddings(context_id);
CREATE INDEX idx_embeddings_model ON context_embeddings(embedding_model);

-- ========================================
-- COST TRACKING FOR GPT-5 TIERS
-- ========================================

-- Detailed cost tracking with pricing tier support
CREATE TABLE IF NOT EXISTS model_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_tier TEXT NOT NULL CHECK (model_tier IN ('gpt-5-nano', 'gpt-5-mini', 'gpt-5')),
    input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
    cached_tokens INTEGER DEFAULT 0 CHECK (cached_tokens >= 0),
    total_cost DECIMAL(10, 6) NOT NULL CHECK (total_cost >= 0),
    cost_breakdown JSONB DEFAULT '{}',  -- Detailed cost breakdown
    request_id TEXT,
    email_id UUID,
    user_id TEXT,  -- For per-user tracking
    processing_time_ms INTEGER CHECK (processing_time_ms >= 0),
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    error_code TEXT,
    metadata JSONB DEFAULT '{}',
    api_version TEXT,
    cache_hit BOOLEAN DEFAULT false,
    CONSTRAINT tokens_check CHECK (input_tokens + output_tokens > 0 OR NOT success)
);

-- Indexes for cost analysis
CREATE INDEX idx_costs_timestamp ON model_costs(timestamp DESC);
CREATE INDEX idx_costs_model_tier ON model_costs(model_tier, timestamp DESC);
CREATE INDEX idx_costs_user ON model_costs(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_costs_success ON model_costs(success);
CREATE INDEX idx_costs_request ON model_costs(request_id) WHERE request_id IS NOT NULL;
CREATE INDEX idx_costs_cache_hit ON model_costs(cache_hit) WHERE cache_hit = true;
CREATE INDEX idx_costs_high_cost ON model_costs(total_cost) WHERE total_cost > 0.1;

-- ========================================
-- ENHANCED CORRECTION PATTERNS
-- ========================================

-- Advanced correction patterns with semantic embeddings
CREATE TABLE IF NOT EXISTS correction_patterns_enhanced (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_hash TEXT UNIQUE NOT NULL,
    field_name TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT,
    pattern_embedding vector(1536),  -- For semantic similarity matching
    pattern_type TEXT CHECK (pattern_type IN ('value', 'format', 'semantic', 'structural')),
    frequency INTEGER DEFAULT 1 CHECK (frequency > 0),
    confidence_score DECIMAL(3, 2) DEFAULT 0.5 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    domains TEXT[] DEFAULT '{}',  -- Domains where pattern observed
    context_snippets JSONB DEFAULT '[]',  -- Example contexts (limited to 10)
    validation_rules JSONB DEFAULT '{}',  -- Rules for auto-validation
    auto_apply BOOLEAN DEFAULT false,  -- Auto-apply if confidence > 0.9
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_applied TIMESTAMP WITH TIME ZONE,
    application_count INTEGER DEFAULT 0,
    CONSTRAINT context_limit CHECK (jsonb_array_length(context_snippets) <= 10)
);

-- Indexes for pattern matching
CREATE INDEX idx_patterns_field ON correction_patterns_enhanced(field_name);
CREATE INDEX idx_patterns_confidence ON correction_patterns_enhanced(confidence_score DESC);
CREATE INDEX idx_patterns_frequency ON correction_patterns_enhanced(frequency DESC);
CREATE INDEX idx_patterns_auto_apply ON correction_patterns_enhanced(auto_apply) WHERE auto_apply = true;
CREATE INDEX idx_patterns_domains_gin ON correction_patterns_enhanced USING gin(domains);
CREATE INDEX idx_patterns_type ON correction_patterns_enhanced(pattern_type) WHERE pattern_type IS NOT NULL;

-- Vector index for semantic similarity
CREATE INDEX idx_patterns_embedding_hnsw ON correction_patterns_enhanced 
    USING hnsw (pattern_embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64)
    WHERE pattern_embedding IS NOT NULL;

-- ========================================
-- SIMILARITY CACHE FOR PERFORMANCE
-- ========================================

-- Cache frequently accessed similarity searches
CREATE TABLE IF NOT EXISTS similarity_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash TEXT NOT NULL,
    similar_items JSONB NOT NULL,
    result_count INTEGER,
    model_used TEXT,
    threshold DECIMAL(3, 2) CHECK (threshold >= 0 AND threshold <= 1),
    query_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    hit_count INTEGER DEFAULT 0,
    last_hit TIMESTAMP WITH TIME ZONE,
    avg_response_time_ms INTEGER,
    UNIQUE(query_hash, model_used, threshold)
);

-- Indexes for cache management
CREATE INDEX idx_cache_hash ON similarity_cache(query_hash);
CREATE INDEX idx_cache_expires ON similarity_cache(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_cache_hit_count ON similarity_cache(hit_count DESC);
CREATE INDEX idx_cache_created ON similarity_cache(created_at DESC);

-- ========================================
-- PROCESSING METRICS FOR OPTIMIZATION
-- ========================================

-- Aggregated metrics for performance monitoring
CREATE TABLE IF NOT EXISTS processing_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    hour INTEGER CHECK (hour >= 0 AND hour < 24),
    model_tier TEXT NOT NULL,
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    total_cached_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(10, 4) DEFAULT 0,
    avg_latency_ms INTEGER,
    p50_latency_ms INTEGER,
    p95_latency_ms INTEGER,
    p99_latency_ms INTEGER,
    max_latency_ms INTEGER,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    cache_hit_rate DECIMAL(3, 2) GENERATED ALWAYS AS (
        CASE 
            WHEN cache_hits + cache_misses > 0 
            THEN cache_hits::DECIMAL / (cache_hits + cache_misses)
            ELSE 0
        END
    ) STORED,
    error_rate DECIMAL(3, 2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_requests > 0 
            THEN failed_requests::DECIMAL / total_requests
            ELSE 0
        END
    ) STORED,
    UNIQUE(date, hour, model_tier)
);

-- Indexes for metrics queries
CREATE INDEX idx_metrics_date ON processing_metrics(date DESC);
CREATE INDEX idx_metrics_date_model ON processing_metrics(date DESC, model_tier);
CREATE INDEX idx_metrics_cost ON processing_metrics(total_cost DESC);
CREATE INDEX idx_metrics_errors ON processing_metrics(error_rate) WHERE error_rate > 0.05;

-- ========================================
-- BATCH PROCESSING OPTIMIZATION
-- ========================================

-- Track batch processing for efficiency
CREATE TABLE IF NOT EXISTS batch_processing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    total_items INTEGER NOT NULL CHECK (total_items > 0),
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    model_tier TEXT NOT NULL,
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(10, 4) DEFAULT 0,
    status TEXT CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    error_details JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_batch_status ON batch_processing(status);
CREATE INDEX idx_batch_created ON batch_processing(created_at DESC);
CREATE INDEX idx_batch_id ON batch_processing(batch_id);

-- ========================================
-- FUNCTIONS AND TRIGGERS
-- ========================================

-- Function to update last_accessed timestamp
CREATE OR REPLACE FUNCTION update_last_accessed()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_accessed = NOW();
    NEW.access_count = OLD.access_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic last_accessed update
CREATE TRIGGER update_context_accessed
    BEFORE UPDATE ON large_contexts
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_last_accessed();

-- Function to auto-cleanup expired cache
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM similarity_cache
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate storage usage
CREATE OR REPLACE FUNCTION calculate_storage_stats()
RETURNS TABLE (
    table_name TEXT,
    row_count BIGINT,
    total_size TEXT,
    index_size TEXT,
    toast_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        schemaname||'.'||tablename AS table_name,
        n_live_tup AS row_count,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
        pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS index_size,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                      pg_relation_size(schemaname||'.'||tablename) - 
                      pg_indexes_size(schemaname||'.'||tablename)) AS toast_size
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- ========================================

-- Daily cost summary view
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_cost_summary AS
SELECT 
    DATE(timestamp) as date,
    model_tier,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cached_tokens) as total_cached_tokens,
    SUM(total_cost) as total_cost,
    AVG(processing_time_ms) as avg_processing_time,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_time_ms) as median_processing_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY processing_time_ms) as p95_processing_time,
    COUNT(CASE WHEN success THEN 1 END)::DECIMAL / COUNT(*) as success_rate,
    COUNT(CASE WHEN cache_hit THEN 1 END)::DECIMAL / NULLIF(COUNT(*), 0) as cache_hit_rate
FROM model_costs
GROUP BY DATE(timestamp), model_tier
WITH DATA;

CREATE UNIQUE INDEX idx_daily_cost_summary ON daily_cost_summary(date, model_tier);

-- Pattern effectiveness view
CREATE MATERIALIZED VIEW IF NOT EXISTS pattern_effectiveness AS
SELECT 
    field_name,
    pattern_type,
    COUNT(*) as pattern_count,
    AVG(confidence_score) as avg_confidence,
    SUM(frequency) as total_frequency,
    SUM(application_count) as total_applications,
    COUNT(CASE WHEN auto_apply THEN 1 END) as auto_apply_count,
    array_agg(DISTINCT unnest_domains) as all_domains
FROM correction_patterns_enhanced,
    LATERAL unnest(domains) as unnest_domains
GROUP BY field_name, pattern_type
WITH DATA;

CREATE UNIQUE INDEX idx_pattern_effectiveness ON pattern_effectiveness(field_name, pattern_type);

-- ========================================
-- PERMISSIONS AND SECURITY
-- ========================================

-- Create read-only role for analytics
CREATE ROLE analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_reader;
GRANT SELECT ON ALL MATERIALIZED VIEWS IN SCHEMA public TO analytics_reader;

-- Create application role with necessary permissions
CREATE ROLE app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- ========================================
-- INITIAL DATA AND CONFIGURATION
-- ========================================

-- Insert default processing metrics for each model tier
INSERT INTO processing_metrics (date, hour, model_tier)
SELECT 
    CURRENT_DATE,
    generate_series(0, 23) as hour,
    unnest(ARRAY['gpt-5-nano', 'gpt-5-mini', 'gpt-5'])
ON CONFLICT (date, hour, model_tier) DO NOTHING;

-- ========================================
-- MIGRATION COMPLETION
-- ========================================

-- Create migration tracking table if not exists
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Record this migration
INSERT INTO schema_migrations (version, name) 
VALUES (1, '001_gpt5_context_support')
ON CONFLICT (version) DO NOTHING;

-- Analyze all new tables for query planner
ANALYZE large_contexts;
ANALYZE context_embeddings;
ANALYZE model_costs;
ANALYZE correction_patterns_enhanced;
ANALYZE similarity_cache;
ANALYZE processing_metrics;
ANALYZE batch_processing;

-- Refresh materialized views
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_cost_summary;
REFRESH MATERIALIZED VIEW CONCURRENTLY pattern_effectiveness;

-- Output migration status
DO $$
BEGIN
    RAISE NOTICE 'Migration 001_gpt5_context_support completed successfully';
    RAISE NOTICE 'Tables created: 7';
    RAISE NOTICE 'Indexes created: 35+';
    RAISE NOTICE 'Functions created: 3';
    RAISE NOTICE 'Materialized views created: 2';
    RAISE NOTICE 'Vector support enabled for 400K context windows';
END $$;