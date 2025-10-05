-- GPT-5 400K Context Support Tables Only (No Extension Creation)
-- For Azure Cosmos DB PostgreSQL where vector extension needs admin setup

-- 1. Email Contexts Table (400K token support) - without vector column for now
CREATE TABLE IF NOT EXISTS email_contexts_400k (
    id SERIAL PRIMARY KEY,
    context_hash VARCHAR(64) UNIQUE NOT NULL,
    email_sender VARCHAR(255) NOT NULL,
    email_subject TEXT,
    full_context TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    chunk_count INTEGER DEFAULT 1,
    embedding_json JSONB, -- Store embedding as JSON for now
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1
);

-- 2. Email Context Chunks (for splitting large contexts)
CREATE TABLE IF NOT EXISTS email_context_chunks (
    id SERIAL PRIMARY KEY,
    context_id INTEGER REFERENCES email_contexts_400k(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_tokens INTEGER NOT NULL,
    chunk_embedding_json JSONB, -- Store embedding as JSON
    overlap_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(context_id, chunk_index)
);

-- 3. Cost Tracking Table
CREATE TABLE IF NOT EXISTS cost_tracking (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(255),
    model_tier VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_input BOOLEAN DEFAULT FALSE,
    total_cost DECIMAL(10, 6) NOT NULL,
    processing_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- 4. Enhanced Correction Patterns with Embeddings
CREATE TABLE IF NOT EXISTS correction_patterns_v2 (
    id SERIAL PRIMARY KEY,
    pattern_hash VARCHAR(64) UNIQUE NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    original_value TEXT,
    corrected_value TEXT NOT NULL,
    pattern_embedding_json JSONB, -- Store embedding as JSON
    confidence_score DECIMAL(3, 2) DEFAULT 0.50,
    usage_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 1,
    company_domain VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_apply BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'
);

-- 5. Email Cache Table (for response caching)
CREATE TABLE IF NOT EXISTS email_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(64) UNIQUE NOT NULL,
    email_pattern_hash VARCHAR(64) NOT NULL,
    email_type VARCHAR(50),
    extraction_result JSONB NOT NULL,
    model_used VARCHAR(50),
    confidence_score DECIMAL(3, 2),
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Batch Processing Queue
CREATE TABLE IF NOT EXISTS batch_processing_queue (
    id SERIAL PRIMARY KEY,
    batch_id UUID DEFAULT gen_random_uuid(),
    email_ids TEXT[] NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    total_emails INTEGER NOT NULL,
    processed_emails INTEGER DEFAULT 0,
    combined_tokens INTEGER,
    model_tier VARCHAR(50),
    total_cost DECIMAL(10, 6),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_details JSONB DEFAULT '[]'
);

-- 7. Company Templates (for pattern learning)
CREATE TABLE IF NOT EXISTS company_templates (
    id SERIAL PRIMARY KEY,
    company_domain VARCHAR(255) UNIQUE NOT NULL,
    template_patterns JSONB NOT NULL DEFAULT '{}',
    field_mappings JSONB DEFAULT '{}',
    confidence_scores JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    success_rate DECIMAL(3, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_contexts_hash ON email_contexts_400k(context_hash);
CREATE INDEX IF NOT EXISTS idx_contexts_sender ON email_contexts_400k(email_sender);
CREATE INDEX IF NOT EXISTS idx_contexts_created ON email_contexts_400k(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chunks_context ON email_context_chunks(context_id);

CREATE INDEX IF NOT EXISTS idx_cost_email ON cost_tracking(email_id);
CREATE INDEX IF NOT EXISTS idx_cost_created ON cost_tracking(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_tracking(model_tier);

CREATE INDEX IF NOT EXISTS idx_patterns_field ON correction_patterns_v2(field_name);
CREATE INDEX IF NOT EXISTS idx_patterns_domain ON correction_patterns_v2(company_domain);
CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON correction_patterns_v2(confidence_score DESC);

CREATE INDEX IF NOT EXISTS idx_cache_key ON email_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON email_cache(expires_at);

CREATE INDEX IF NOT EXISTS idx_batch_status ON batch_processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_batch_created ON batch_processing_queue(created_at DESC);

-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_context_metadata ON email_contexts_400k USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_cost_metadata ON cost_tracking USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_patterns_metadata ON correction_patterns_v2 USING gin (metadata);

-- Simple views for analytics
CREATE OR REPLACE VIEW daily_cost_summary AS
SELECT 
    DATE(created_at) as date,
    model_tier,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(CASE WHEN cached_input THEN input_tokens ELSE 0 END) as cached_tokens,
    SUM(total_cost) as total_cost,
    AVG(processing_time_ms) as avg_processing_time
FROM cost_tracking
GROUP BY DATE(created_at), model_tier;

CREATE OR REPLACE VIEW cache_performance AS
SELECT 
    email_type,
    COUNT(*) as cache_entries,
    SUM(hit_count) as total_hits,
    AVG(confidence_score) as avg_confidence,
    MIN(created_at) as oldest_entry,
    MAX(last_accessed) as latest_access
FROM email_cache
WHERE expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL
GROUP BY email_type;

-- Success message
SELECT 'Migration completed successfully!' as status;