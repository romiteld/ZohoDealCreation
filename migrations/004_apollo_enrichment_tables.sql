-- Migration 004: Apollo.io Enrichment Data Schema
-- This migration creates a comprehensive schema for Apollo.io enrichment data including
-- person/company data storage, search caching, API metrics, and analytical views
-- Designed for efficient storage and querying with PostgreSQL and pgvector
-- All operations are idempotent using IF NOT EXISTS

-- =============================================================================
-- ENABLE REQUIRED EXTENSIONS
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";  -- For embedding storage and similarity search

-- =============================================================================
-- APOLLO ENRICHMENTS TABLE
-- Core table for storing enriched person and company data from Apollo.io
-- =============================================================================
CREATE TABLE IF NOT EXISTS apollo_enrichments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Enrichment metadata
    enrichment_type TEXT NOT NULL CHECK (enrichment_type IN ('person', 'company', 'combined')),
    enrichment_status TEXT NOT NULL DEFAULT 'pending' CHECK (enrichment_status IN ('pending', 'processing', 'completed', 'failed', 'partial')),
    enrichment_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Request identifiers (for deduplication and correlation)
    request_id TEXT UNIQUE,  -- Original request ID from API call
    source_email TEXT,        -- Email that triggered enrichment
    source_deal_id TEXT,      -- Related deal ID if applicable

    -- Person data fields
    person_id TEXT,           -- Apollo person ID
    person_first_name TEXT,
    person_last_name TEXT,
    person_full_name TEXT GENERATED ALWAYS AS (
        COALESCE(person_first_name || ' ' || person_last_name, person_first_name, person_last_name)
    ) STORED,
    person_email TEXT,
    person_email_status TEXT CHECK (person_email_status IN ('valid', 'invalid', 'catch-all', 'unknown')),
    person_email_confidence INTEGER CHECK (person_email_confidence >= 0 AND person_email_confidence <= 100),
    person_title TEXT,
    person_seniority TEXT,
    person_department TEXT,
    person_linkedin_url TEXT,
    person_twitter_url TEXT,
    person_github_url TEXT,
    person_facebook_url TEXT,
    person_phone_numbers JSONB DEFAULT '[]',  -- Array of {number, type, status}
    person_employment_history JSONB DEFAULT '[]',  -- Array of past positions
    person_education JSONB DEFAULT '[]',  -- Array of education records
    person_location_city TEXT,
    person_location_state TEXT,
    person_location_country TEXT,
    person_location_postal_code TEXT,

    -- Company data fields
    company_id TEXT,          -- Apollo company ID
    company_name TEXT,
    company_domain TEXT,
    company_website TEXT,
    company_phone TEXT,
    company_industry TEXT,
    company_sub_industry TEXT,
    company_description TEXT,
    company_logo_url TEXT,
    company_linkedin_url TEXT,
    company_twitter_url TEXT,
    company_facebook_url TEXT,
    company_employee_count INTEGER,
    company_employee_range TEXT,
    company_annual_revenue DECIMAL(15, 2),
    company_revenue_range TEXT,
    company_funding_total DECIMAL(15, 2),
    company_funding_stage TEXT,
    company_technologies JSONB DEFAULT '[]',  -- Array of technology names
    company_keywords JSONB DEFAULT '[]',      -- Array of relevant keywords
    company_sic_codes JSONB DEFAULT '[]',     -- Array of SIC codes
    company_naics_codes JSONB DEFAULT '[]',   -- Array of NAICS codes
    company_headquarters_city TEXT,
    company_headquarters_state TEXT,
    company_headquarters_country TEXT,
    company_headquarters_postal_code TEXT,
    company_year_founded INTEGER,

    -- Data quality and confidence scores
    overall_confidence_score DECIMAL(3, 2) CHECK (overall_confidence_score >= 0 AND overall_confidence_score <= 1),
    data_completeness_score DECIMAL(3, 2) CHECK (data_completeness_score >= 0 AND data_completeness_score <= 1),
    last_verified_date DATE,
    verification_source TEXT,

    -- Embeddings for similarity search (using pgvector)
    person_embedding vector(1536),    -- For person similarity search
    company_embedding vector(1536),   -- For company similarity search
    combined_embedding vector(1536),  -- Combined person+company embedding

    -- API response metadata
    api_credits_used INTEGER DEFAULT 0,
    api_response_time_ms INTEGER,
    api_rate_limit_remaining INTEGER,
    raw_api_response JSONB,  -- Complete API response for debugging

    -- Error handling
    error_message TEXT,
    error_code TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Audit fields
    created_by TEXT,
    updated_by TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Additional metadata
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    notes TEXT
);

-- Create indexes for apollo_enrichments
CREATE INDEX IF NOT EXISTS idx_apollo_person_email ON apollo_enrichments(person_email) WHERE person_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_person_linkedin ON apollo_enrichments(person_linkedin_url) WHERE person_linkedin_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_company_domain ON apollo_enrichments(company_domain) WHERE company_domain IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_company_name ON apollo_enrichments(company_name) WHERE company_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_enrichment_date ON apollo_enrichments(enrichment_date);
CREATE INDEX IF NOT EXISTS idx_apollo_source_email ON apollo_enrichments(source_email) WHERE source_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_source_deal ON apollo_enrichments(source_deal_id) WHERE source_deal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_person_id ON apollo_enrichments(person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_company_id ON apollo_enrichments(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_apollo_status ON apollo_enrichments(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_apollo_phone_numbers ON apollo_enrichments USING GIN (person_phone_numbers);
CREATE INDEX IF NOT EXISTS idx_apollo_technologies ON apollo_enrichments USING GIN (company_technologies);
CREATE INDEX IF NOT EXISTS idx_apollo_metadata ON apollo_enrichments USING GIN (metadata);

-- Vector similarity indexes for embeddings (IVFFlat for approximate nearest neighbor search)
CREATE INDEX IF NOT EXISTS idx_apollo_person_embedding ON apollo_enrichments
    USING ivfflat (person_embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE person_embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_apollo_company_embedding ON apollo_enrichments
    USING ivfflat (company_embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE company_embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_apollo_combined_embedding ON apollo_enrichments
    USING ivfflat (combined_embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE combined_embedding IS NOT NULL;

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_apollo_person_fulltext ON apollo_enrichments
    USING GIN (to_tsvector('english',
        COALESCE(person_full_name, '') || ' ' ||
        COALESCE(person_title, '') || ' ' ||
        COALESCE(person_email, '')
    ));

CREATE INDEX IF NOT EXISTS idx_apollo_company_fulltext ON apollo_enrichments
    USING GIN (to_tsvector('english',
        COALESCE(company_name, '') || ' ' ||
        COALESCE(company_description, '') || ' ' ||
        COALESCE(company_industry, '')
    ));

-- =============================================================================
-- APOLLO SEARCH CACHE TABLE
-- Caches search results to reduce API calls and improve response time
-- =============================================================================
CREATE TABLE IF NOT EXISTS apollo_search_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Cache key components
    search_type TEXT NOT NULL CHECK (search_type IN ('person', 'company', 'mixed')),
    search_query TEXT NOT NULL,
    search_params JSONB NOT NULL DEFAULT '{}',  -- All search parameters
    cache_key TEXT GENERATED ALWAYS AS (
        encode(digest(search_type || search_query || search_params::text, 'sha256'), 'hex')
    ) STORED,

    -- Cache data
    result_count INTEGER DEFAULT 0,
    results JSONB NOT NULL DEFAULT '[]',  -- Array of search results
    result_ids TEXT[] DEFAULT '{}',       -- Array of Apollo IDs for quick lookup

    -- Cache metadata
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Cache validation
    is_valid BOOLEAN DEFAULT TRUE,
    invalidated_at TIMESTAMP WITH TIME ZONE,
    invalidation_reason TEXT,

    -- Performance metrics
    api_response_time_ms INTEGER,
    cache_size_bytes INTEGER,

    -- Unique constraint on cache key
    CONSTRAINT apollo_cache_unique_key UNIQUE (cache_key)
);

-- Create indexes for apollo_search_cache
CREATE INDEX IF NOT EXISTS idx_apollo_cache_key ON apollo_search_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_apollo_cache_type ON apollo_search_cache(search_type);
CREATE INDEX IF NOT EXISTS idx_apollo_cache_expires ON apollo_search_cache(expires_at) WHERE is_valid = TRUE;
CREATE INDEX IF NOT EXISTS idx_apollo_cache_accessed ON apollo_search_cache(last_accessed);
CREATE INDEX IF NOT EXISTS idx_apollo_cache_result_ids ON apollo_search_cache USING GIN (result_ids);

-- =============================================================================
-- APOLLO METRICS TABLE
-- Tracks API usage, performance, and success rates
-- =============================================================================
CREATE TABLE IF NOT EXISTS apollo_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Time bucket for aggregation (hourly granularity)
    metric_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT date_trunc('hour', CURRENT_TIMESTAMP),
    metric_date DATE GENERATED ALWAYS AS (metric_timestamp::date) STORED,
    metric_hour INTEGER GENERATED ALWAYS AS (EXTRACT(hour FROM metric_timestamp)) STORED,

    -- API call metrics
    total_api_calls INTEGER DEFAULT 0,
    successful_calls INTEGER DEFAULT 0,
    failed_calls INTEGER DEFAULT 0,
    partial_success_calls INTEGER DEFAULT 0,

    -- Call type breakdown
    person_enrichment_calls INTEGER DEFAULT 0,
    company_enrichment_calls INTEGER DEFAULT 0,
    search_calls INTEGER DEFAULT 0,

    -- Performance metrics
    avg_response_time_ms DECIMAL(10, 2),
    min_response_time_ms INTEGER,
    max_response_time_ms INTEGER,
    p95_response_time_ms INTEGER,
    p99_response_time_ms INTEGER,

    -- Credit usage
    total_credits_used INTEGER DEFAULT 0,
    credits_per_person DECIMAL(5, 2),
    credits_per_company DECIMAL(5, 2),

    -- Cache metrics
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    cache_hit_rate DECIMAL(3, 2) GENERATED ALWAYS AS (
        CASE
            WHEN (cache_hits + cache_misses) > 0
            THEN cache_hits::decimal / (cache_hits + cache_misses)
            ELSE 0
        END
    ) STORED,

    -- Error tracking
    rate_limit_errors INTEGER DEFAULT 0,
    authentication_errors INTEGER DEFAULT 0,
    network_errors INTEGER DEFAULT 0,
    validation_errors INTEGER DEFAULT 0,

    -- Data quality metrics
    avg_completeness_score DECIMAL(3, 2),
    avg_confidence_score DECIMAL(3, 2),
    records_with_email INTEGER DEFAULT 0,
    records_with_phone INTEGER DEFAULT 0,
    records_with_linkedin INTEGER DEFAULT 0,

    -- Unique constraint on time bucket
    CONSTRAINT apollo_metrics_unique_hour UNIQUE (metric_timestamp)
);

-- Create indexes for apollo_metrics
CREATE INDEX IF NOT EXISTS idx_apollo_metrics_timestamp ON apollo_metrics(metric_timestamp);
CREATE INDEX IF NOT EXISTS idx_apollo_metrics_date ON apollo_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_apollo_metrics_hour ON apollo_metrics(metric_hour);

-- =============================================================================
-- APOLLO PHONE NUMBERS TABLE
-- Normalized storage for phone numbers with validation status
-- =============================================================================
CREATE TABLE IF NOT EXISTS apollo_phone_numbers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    enrichment_id UUID REFERENCES apollo_enrichments(id) ON DELETE CASCADE,

    -- Phone number data
    phone_number TEXT NOT NULL,
    phone_type TEXT CHECK (phone_type IN ('mobile', 'work', 'home', 'fax', 'other')),
    phone_country_code TEXT,
    phone_area_code TEXT,
    phone_local_number TEXT,
    phone_extension TEXT,

    -- Validation status
    is_valid BOOLEAN DEFAULT NULL,
    is_mobile BOOLEAN DEFAULT NULL,
    carrier TEXT,
    line_type TEXT,
    last_validated TIMESTAMP WITH TIME ZONE,

    -- Usage tracking
    times_called INTEGER DEFAULT 0,
    last_called TIMESTAMP WITH TIME ZONE,
    call_outcomes JSONB DEFAULT '[]',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint to prevent duplicates
    CONSTRAINT apollo_phone_unique UNIQUE (enrichment_id, phone_number)
);

-- Create indexes for apollo_phone_numbers
CREATE INDEX IF NOT EXISTS idx_apollo_phones_enrichment ON apollo_phone_numbers(enrichment_id);
CREATE INDEX IF NOT EXISTS idx_apollo_phones_number ON apollo_phone_numbers(phone_number);
CREATE INDEX IF NOT EXISTS idx_apollo_phones_valid ON apollo_phone_numbers(is_valid) WHERE is_valid IS NOT NULL;

-- =============================================================================
-- MATERIALIZED VIEW: Enrichment Success Rates
-- Provides real-time insights into enrichment quality and success
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS apollo_enrichment_success_rates AS
SELECT
    DATE_TRUNC('day', enrichment_date) as date,
    enrichment_type,
    COUNT(*) as total_enrichments,
    COUNT(*) FILTER (WHERE enrichment_status = 'completed') as successful,
    COUNT(*) FILTER (WHERE enrichment_status = 'failed') as failed,
    COUNT(*) FILTER (WHERE enrichment_status = 'partial') as partial,

    -- Success rate
    ROUND(
        COUNT(*) FILTER (WHERE enrichment_status = 'completed')::decimal /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as success_rate,

    -- Data quality metrics
    AVG(overall_confidence_score) as avg_confidence,
    AVG(data_completeness_score) as avg_completeness,

    -- Field coverage
    COUNT(*) FILTER (WHERE person_email IS NOT NULL) as with_email,
    COUNT(*) FILTER (WHERE person_linkedin_url IS NOT NULL) as with_linkedin,
    COUNT(*) FILTER (WHERE company_domain IS NOT NULL) as with_company,
    COUNT(*) FILTER (WHERE person_phone_numbers != '[]'::jsonb) as with_phone,

    -- API metrics
    SUM(api_credits_used) as total_credits_used,
    AVG(api_response_time_ms) as avg_response_time_ms
FROM apollo_enrichments
WHERE is_deleted = FALSE
GROUP BY DATE_TRUNC('day', enrichment_date), enrichment_type
ORDER BY date DESC, enrichment_type;

-- Create index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_apollo_success_rates_unique
    ON apollo_enrichment_success_rates (date, enrichment_type);

-- =============================================================================
-- MATERIALIZED VIEW: Most Enriched Companies
-- Shows which companies are most frequently enriched
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS apollo_most_enriched_companies AS
SELECT
    company_name,
    company_domain,
    COUNT(*) as enrichment_count,
    COUNT(DISTINCT person_email) as unique_contacts,

    -- Latest company data (from most recent enrichment)
    (array_agg(company_industry ORDER BY enrichment_date DESC))[1] as industry,
    (array_agg(company_employee_count ORDER BY enrichment_date DESC))[1] as employee_count,
    (array_agg(company_annual_revenue ORDER BY enrichment_date DESC))[1] as annual_revenue,

    -- Data quality
    AVG(overall_confidence_score) as avg_confidence,

    -- Contact coverage
    COUNT(*) FILTER (WHERE person_email IS NOT NULL) as contacts_with_email,
    COUNT(*) FILTER (WHERE person_linkedin_url IS NOT NULL) as contacts_with_linkedin,

    -- Time metrics
    MIN(enrichment_date) as first_enriched,
    MAX(enrichment_date) as last_enriched,

    -- Technologies used (aggregated)
    jsonb_agg(DISTINCT company_technologies) as all_technologies
FROM apollo_enrichments
WHERE company_name IS NOT NULL
    AND is_deleted = FALSE
    AND enrichment_status IN ('completed', 'partial')
GROUP BY company_name, company_domain
HAVING COUNT(*) >= 2  -- Only show companies enriched multiple times
ORDER BY enrichment_count DESC;

-- Create index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_apollo_companies_unique
    ON apollo_most_enriched_companies (company_name, company_domain);

-- =============================================================================
-- MATERIALIZED VIEW: Missing Data Report
-- Identifies records with missing critical data for re-enrichment
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS apollo_missing_data_report AS
SELECT
    id,
    source_email,
    source_deal_id,
    enrichment_date,

    -- Person data gaps
    CASE WHEN person_email IS NULL THEN 1 ELSE 0 END as missing_email,
    CASE WHEN person_linkedin_url IS NULL THEN 1 ELSE 0 END as missing_linkedin,
    CASE WHEN person_title IS NULL THEN 1 ELSE 0 END as missing_title,
    CASE WHEN person_phone_numbers = '[]'::jsonb THEN 1 ELSE 0 END as missing_phone,

    -- Company data gaps
    CASE WHEN company_name IS NULL THEN 1 ELSE 0 END as missing_company,
    CASE WHEN company_domain IS NULL THEN 1 ELSE 0 END as missing_domain,
    CASE WHEN company_industry IS NULL THEN 1 ELSE 0 END as missing_industry,
    CASE WHEN company_employee_count IS NULL THEN 1 ELSE 0 END as missing_size,

    -- Calculate completeness score
    (
        (CASE WHEN person_email IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_linkedin_url IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_title IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_phone_numbers != '[]'::jsonb THEN 1 ELSE 0 END +
         CASE WHEN company_name IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_domain IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_industry IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_employee_count IS NOT NULL THEN 1 ELSE 0 END)::decimal / 8
    ) as completeness_ratio,

    -- Prioritization score (higher = more important to re-enrich)
    CASE
        WHEN source_deal_id IS NOT NULL THEN 3  -- Deal-related records are highest priority
        WHEN person_email IS NULL THEN 2        -- Missing email is high priority
        ELSE 1
    END as priority_score
FROM apollo_enrichments
WHERE is_deleted = FALSE
    AND enrichment_status IN ('completed', 'partial')
    AND (
        person_email IS NULL OR
        person_linkedin_url IS NULL OR
        company_domain IS NULL OR
        data_completeness_score < 0.7
    )
ORDER BY priority_score DESC, enrichment_date DESC;

-- Create index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_apollo_missing_unique ON apollo_missing_data_report (id);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function to calculate data completeness score
CREATE OR REPLACE FUNCTION calculate_apollo_completeness_score(enrichment_id UUID)
RETURNS DECIMAL(3, 2) AS $$
DECLARE
    score DECIMAL(3, 2);
    total_fields INTEGER := 20;  -- Total critical fields to check
    filled_fields INTEGER := 0;
BEGIN
    SELECT
        (CASE WHEN person_first_name IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_last_name IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_email IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_title IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_linkedin_url IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_phone_numbers != '[]'::jsonb THEN 1 ELSE 0 END +
         CASE WHEN person_location_city IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_location_state IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN person_location_country IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_name IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_domain IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_website IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_industry IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_employee_count IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_annual_revenue IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_headquarters_city IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_headquarters_state IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_headquarters_country IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_linkedin_url IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN company_description IS NOT NULL THEN 1 ELSE 0 END)
    INTO filled_fields
    FROM apollo_enrichments
    WHERE id = enrichment_id;

    score := filled_fields::DECIMAL / total_fields;
    RETURN score;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar persons using vector similarity
CREATE OR REPLACE FUNCTION find_similar_apollo_persons(
    target_embedding vector(1536),
    limit_count INTEGER DEFAULT 10,
    similarity_threshold DECIMAL DEFAULT 0.8
)
RETURNS TABLE (
    id UUID,
    person_full_name TEXT,
    person_email TEXT,
    company_name TEXT,
    similarity_score DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ae.id,
        ae.person_full_name,
        ae.person_email,
        ae.company_name,
        1 - (ae.person_embedding <=> target_embedding) as similarity_score
    FROM apollo_enrichments ae
    WHERE ae.person_embedding IS NOT NULL
        AND ae.is_deleted = FALSE
        AND 1 - (ae.person_embedding <=> target_embedding) >= similarity_threshold
    ORDER BY ae.person_embedding <=> target_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar companies using vector similarity
CREATE OR REPLACE FUNCTION find_similar_apollo_companies(
    target_embedding vector(1536),
    limit_count INTEGER DEFAULT 10,
    similarity_threshold DECIMAL DEFAULT 0.8
)
RETURNS TABLE (
    id UUID,
    company_name TEXT,
    company_domain TEXT,
    company_industry TEXT,
    similarity_score DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ae.id,
        ae.company_name,
        ae.company_domain,
        ae.company_industry,
        1 - (ae.company_embedding <=> target_embedding) as similarity_score
    FROM apollo_enrichments ae
    WHERE ae.company_embedding IS NOT NULL
        AND ae.is_deleted = FALSE
        AND 1 - (ae.company_embedding <=> target_embedding) >= similarity_threshold
    ORDER BY ae.company_embedding <=> target_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Trigger to update last_updated timestamp
CREATE OR REPLACE FUNCTION update_apollo_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_apollo_enrichments_updated
    BEFORE UPDATE ON apollo_enrichments
    FOR EACH ROW
    EXECUTE FUNCTION update_apollo_last_updated();

-- Trigger to update data completeness score on insert/update
CREATE OR REPLACE FUNCTION update_apollo_completeness()
RETURNS TRIGGER AS $$
BEGIN
    NEW.data_completeness_score = calculate_apollo_completeness_score(NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_apollo_completeness
    BEFORE INSERT OR UPDATE ON apollo_enrichments
    FOR EACH ROW
    EXECUTE FUNCTION update_apollo_completeness();

-- Trigger to update cache hit count and last accessed
CREATE OR REPLACE FUNCTION update_apollo_cache_access()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.hit_count IS DISTINCT FROM NEW.hit_count THEN
        NEW.last_accessed = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_apollo_cache_accessed
    BEFORE UPDATE ON apollo_search_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_apollo_cache_access();

-- =============================================================================
-- REFRESH POLICIES FOR MATERIALIZED VIEWS
-- =============================================================================

-- Create a function to refresh all Apollo materialized views
CREATE OR REPLACE FUNCTION refresh_apollo_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY apollo_enrichment_success_rates;
    REFRESH MATERIALIZED VIEW CONCURRENTLY apollo_most_enriched_companies;
    REFRESH MATERIALIZED VIEW CONCURRENTLY apollo_missing_data_report;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- PERMISSIONS (Adjust based on your user requirements)
-- =============================================================================

-- Grant permissions to application user (replace 'app_user' with actual username)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON apollo_enrichments TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON apollo_search_cache TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON apollo_metrics TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON apollo_phone_numbers TO app_user;
-- GRANT SELECT ON apollo_enrichment_success_rates TO app_user;
-- GRANT SELECT ON apollo_most_enriched_companies TO app_user;
-- GRANT SELECT ON apollo_missing_data_report TO app_user;
-- GRANT EXECUTE ON FUNCTION calculate_apollo_completeness_score TO app_user;
-- GRANT EXECUTE ON FUNCTION find_similar_apollo_persons TO app_user;
-- GRANT EXECUTE ON FUNCTION find_similar_apollo_companies TO app_user;
-- GRANT EXECUTE ON FUNCTION refresh_apollo_materialized_views TO app_user;

-- =============================================================================
-- MIGRATION COMPLETION
-- =============================================================================

-- Add migration record
INSERT INTO migration_history (migration_name, executed_at, success)
VALUES ('004_apollo_enrichment_tables', CURRENT_TIMESTAMP, TRUE)
ON CONFLICT (migration_name) DO NOTHING;

-- Output migration summary
DO $$
BEGIN
    RAISE NOTICE 'Apollo.io enrichment schema migration completed successfully';
    RAISE NOTICE 'Created tables: apollo_enrichments, apollo_search_cache, apollo_metrics, apollo_phone_numbers';
    RAISE NOTICE 'Created materialized views: enrichment_success_rates, most_enriched_companies, missing_data_report';
    RAISE NOTICE 'Created functions for similarity search and data completeness calculation';
    RAISE NOTICE 'Remember to refresh materialized views periodically using refresh_apollo_materialized_views()';
END $$;