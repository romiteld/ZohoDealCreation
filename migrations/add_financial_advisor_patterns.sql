-- Migration: Add Financial Advisor Pattern Recognition and Vector Search
-- Purpose: Optimize database for financial advisor data extraction and searching
-- Author: PostgreSQL & pgvector Expert
-- Date: 2025-09-26

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- =====================================================================
-- PART 1: ENHANCED EMAIL PROCESSING HISTORY WITH FINANCIAL METRICS
-- =====================================================================

-- Add financial metrics columns to email_processing_history
ALTER TABLE email_processing_history
ADD COLUMN IF NOT EXISTS financial_metrics JSONB,
ADD COLUMN IF NOT EXISTS aum_amount NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS aum_range_low NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS aum_range_high NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS production_amount NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS compensation_low NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS compensation_high NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS trailing_12_revenue NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS years_experience INTEGER,
ADD COLUMN IF NOT EXISTS team_size INTEGER,
ADD COLUMN IF NOT EXISTS has_series_7 BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_series_63 BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_series_65 BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_series_66 BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_series_24 BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_series_31 BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_cfa BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_cfp BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_cpwa BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_chfc BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_clu BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS has_mba BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS designations TEXT[],
ADD COLUMN IF NOT EXISTS licenses TEXT[],
ADD COLUMN IF NOT EXISTS achievements TEXT[],
ADD COLUMN IF NOT EXISTS rankings TEXT[],
ADD COLUMN IF NOT EXISTS performance_percentages NUMERIC[],
ADD COLUMN IF NOT EXISTS extracted_patterns JSONB;

-- =====================================================================
-- PART 2: FINANCIAL PATTERN RECOGNITION TABLES
-- =====================================================================

-- Create table for storing financial amount patterns
CREATE TABLE IF NOT EXISTS financial_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type TEXT NOT NULL, -- 'aum', 'production', 'compensation', 'revenue'
    raw_text TEXT NOT NULL,
    normalized_value NUMERIC(15,2),
    unit TEXT, -- 'M' for million, 'B' for billion, 'K' for thousand
    confidence_score DECIMAL(3,2) DEFAULT 0.5,
    pattern_regex TEXT,
    context_before TEXT,
    context_after TEXT,
    source_email_id UUID REFERENCES email_processing_history(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create table for designation and license patterns
CREATE TABLE IF NOT EXISTS credential_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_type TEXT NOT NULL, -- 'license' or 'designation'
    credential_code TEXT NOT NULL, -- 'Series 7', 'CFA', etc.
    full_name TEXT,
    variations TEXT[], -- Different ways it appears in text
    pattern_regex TEXT,
    importance_rank INTEGER DEFAULT 100,
    category TEXT, -- 'regulatory', 'professional', 'academic'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(credential_type, credential_code)
);

-- Create table for achievement patterns
CREATE TABLE IF NOT EXISTS achievement_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    achievement_type TEXT NOT NULL, -- 'ranking', 'award', 'club', 'performance'
    pattern_text TEXT NOT NULL,
    pattern_regex TEXT,
    importance_score INTEGER DEFAULT 50,
    category TEXT, -- 'production', 'client_satisfaction', 'growth', 'team'
    typical_context TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create table for career trajectory patterns
CREATE TABLE IF NOT EXISTS career_trajectories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES email_processing_history(id),
    advisor_name TEXT,
    career_narrative TEXT, -- Full career story
    career_embedding vector(1536), -- Embedding for similarity search
    career_highlights JSONB, -- Structured highlights
    firms_worked TEXT[],
    progression_pattern TEXT, -- 'wirehouse_to_ria', 'bank_to_independent', etc.
    total_industry_experience INTEGER,
    peak_aum NUMERIC(15,2),
    peak_production NUMERIC(15,2),
    specializations TEXT[],
    client_types TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================================
-- PART 3: OPTIMIZED INDEXES FOR FINANCIAL DATA
-- =====================================================================

-- B-tree indexes for numeric range queries
CREATE INDEX IF NOT EXISTS idx_email_aum_amount
    ON email_processing_history(aum_amount)
    WHERE aum_amount IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_email_aum_range
    ON email_processing_history(aum_range_low, aum_range_high)
    WHERE aum_range_low IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_email_production
    ON email_processing_history(production_amount)
    WHERE production_amount IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_email_compensation
    ON email_processing_history(compensation_low, compensation_high)
    WHERE compensation_low IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_email_revenue
    ON email_processing_history(trailing_12_revenue)
    WHERE trailing_12_revenue IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_email_experience
    ON email_processing_history(years_experience)
    WHERE years_experience IS NOT NULL;

-- Partial indexes for boolean license/designation flags
CREATE INDEX IF NOT EXISTS idx_has_series_7
    ON email_processing_history(has_series_7)
    WHERE has_series_7 = TRUE;

CREATE INDEX IF NOT EXISTS idx_has_series_65_66
    ON email_processing_history(has_series_65, has_series_66)
    WHERE has_series_65 = TRUE OR has_series_66 = TRUE;

CREATE INDEX IF NOT EXISTS idx_has_cfa_cfp
    ON email_processing_history(has_cfa, has_cfp)
    WHERE has_cfa = TRUE OR has_cfp = TRUE;

-- GIN indexes for array searches
CREATE INDEX IF NOT EXISTS idx_designations_gin
    ON email_processing_history USING GIN(designations);

CREATE INDEX IF NOT EXISTS idx_licenses_gin
    ON email_processing_history USING GIN(licenses);

CREATE INDEX IF NOT EXISTS idx_achievements_gin
    ON email_processing_history USING GIN(achievements);

-- GIN index for JSONB financial metrics
CREATE INDEX IF NOT EXISTS idx_financial_metrics_gin
    ON email_processing_history USING GIN(financial_metrics);

CREATE INDEX IF NOT EXISTS idx_extracted_patterns_gin
    ON email_processing_history USING GIN(extracted_patterns);

-- Text search indexes for pattern matching
CREATE INDEX IF NOT EXISTS idx_financial_patterns_text
    ON financial_patterns USING GIN(to_tsvector('english', raw_text));

CREATE INDEX IF NOT EXISTS idx_achievement_patterns_text
    ON achievement_patterns USING GIN(to_tsvector('english', pattern_text));

-- Vector similarity indexes for career trajectories
CREATE INDEX IF NOT EXISTS idx_career_embedding_hnsw
    ON career_trajectories
    USING hnsw (career_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_email_aum_and_licenses
    ON email_processing_history(aum_amount, has_series_7, has_series_65)
    WHERE aum_amount IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_financial_patterns_type_value
    ON financial_patterns(pattern_type, normalized_value DESC);

-- =====================================================================
-- PART 4: POPULATE CREDENTIAL PATTERNS
-- =====================================================================

-- Insert common financial licenses
INSERT INTO credential_patterns (credential_type, credential_code, full_name, variations, pattern_regex, importance_rank, category)
VALUES
    ('license', 'Series 7', 'General Securities Representative',
     ARRAY['Series 7', 'Series-7', 'S7', 'General Securities Rep'],
     '(?i)\b(series[\s\-]?7|s7)\b', 10, 'regulatory'),

    ('license', 'Series 63', 'Uniform Securities Agent State Law',
     ARRAY['Series 63', 'Series-63', 'S63'],
     '(?i)\b(series[\s\-]?63|s63)\b', 20, 'regulatory'),

    ('license', 'Series 65', 'Uniform Investment Adviser Law',
     ARRAY['Series 65', 'Series-65', 'S65'],
     '(?i)\b(series[\s\-]?65|s65)\b', 15, 'regulatory'),

    ('license', 'Series 66', 'Uniform Combined State Law',
     ARRAY['Series 66', 'Series-66', 'S66'],
     '(?i)\b(series[\s\-]?66|s66)\b', 15, 'regulatory'),

    ('license', 'Series 24', 'General Securities Principal',
     ARRAY['Series 24', 'Series-24', 'S24'],
     '(?i)\b(series[\s\-]?24|s24)\b', 25, 'regulatory'),

    ('license', 'Series 31', 'Futures Managed Funds',
     ARRAY['Series 31', 'Series-31', 'S31'],
     '(?i)\b(series[\s\-]?31|s31)\b', 30, 'regulatory')
ON CONFLICT (credential_type, credential_code) DO UPDATE
SET variations = EXCLUDED.variations,
    pattern_regex = EXCLUDED.pattern_regex,
    updated_at = NOW();

-- Insert common professional designations
INSERT INTO credential_patterns (credential_type, credential_code, full_name, variations, pattern_regex, importance_rank, category)
VALUES
    ('designation', 'CFA', 'Chartered Financial Analyst',
     ARRAY['CFA', 'C.F.A.', 'Chartered Financial Analyst'],
     '(?i)\b(cfa|c\.?f\.?a\.?|chartered\s+financial\s+analyst)\b', 5, 'professional'),

    ('designation', 'CFP', 'Certified Financial Planner',
     ARRAY['CFP', 'C.F.P.', 'CFP®', 'Certified Financial Planner'],
     '(?i)\b(cfp®?|c\.?f\.?p\.?|certified\s+financial\s+planner)\b', 8, 'professional'),

    ('designation', 'CPWA', 'Certified Private Wealth Advisor',
     ARRAY['CPWA', 'C.P.W.A.', 'CPWA®', 'Certified Private Wealth Advisor'],
     '(?i)\b(cpwa®?|c\.?p\.?w\.?a\.?|certified\s+private\s+wealth\s+advisor)\b', 12, 'professional'),

    ('designation', 'ChFC', 'Chartered Financial Consultant',
     ARRAY['ChFC', 'Ch.F.C.', 'ChFC®', 'Chartered Financial Consultant'],
     '(?i)\b(chfc®?|ch\.?f\.?c\.?|chartered\s+financial\s+consultant)\b', 18, 'professional'),

    ('designation', 'CLU', 'Chartered Life Underwriter',
     ARRAY['CLU', 'C.L.U.', 'CLU®', 'Chartered Life Underwriter'],
     '(?i)\b(clu®?|c\.?l\.?u\.?|chartered\s+life\s+underwriter)\b', 22, 'professional'),

    ('designation', 'MBA', 'Master of Business Administration',
     ARRAY['MBA', 'M.B.A.', 'Masters in Business'],
     '(?i)\b(mba|m\.?b\.?a\.?|master[s]?\s+(of|in)\s+business)\b', 35, 'academic')
ON CONFLICT (credential_type, credential_code) DO UPDATE
SET variations = EXCLUDED.variations,
    pattern_regex = EXCLUDED.pattern_regex,
    updated_at = NOW();

-- =====================================================================
-- PART 5: POPULATE ACHIEVEMENT PATTERNS
-- =====================================================================

INSERT INTO achievement_patterns (achievement_type, pattern_text, pattern_regex, importance_score, category, typical_context)
VALUES
    ('ranking', '#1 Advisor', '(?i)#1\s+(advisor|producer|rep)', 100, 'production',
     ARRAY['ranked', 'achieved', 'recognized']),

    ('ranking', 'Top Producer', '(?i)\btop\s+(producer|advisor|performer)', 90, 'production',
     ARRAY['recognized as', 'named', 'awarded']),

    ('club', 'President''s Club', '(?i)\bpresident[''']?s\s+club', 85, 'production',
     ARRAY['member', 'qualified', 'achieved']),

    ('club', 'Chairman''s Club', '(?i)\bchairman[''']?s\s+(club|circle)', 95, 'production',
     ARRAY['member', 'qualified', 'inducted']),

    ('ranking', 'Top Quintile', '(?i)\btop\s+(quintile|decile|percentile)', 80, 'performance',
     ARRAY['ranked in', 'performed in', 'achieved']),

    ('award', 'Circle of Excellence', '(?i)\bcircle\s+of\s+excellence', 88, 'client_satisfaction',
     ARRAY['awarded', 'received', 'earned']),

    ('performance', 'Barron''s Top', '(?i)\bbarron[''']?s\s+top', 92, 'industry_recognition',
     ARRAY['named to', 'listed in', 'recognized by']),

    ('performance', 'Forbes Best', '(?i)\bforbes\s+(best|top)', 91, 'industry_recognition',
     ARRAY['named', 'listed', 'recognized']);

-- =====================================================================
-- PART 6: CREATE FUNCTIONS FOR PATTERN EXTRACTION
-- =====================================================================

-- Function to extract dollar amounts from text
CREATE OR REPLACE FUNCTION extract_dollar_amounts(text_input TEXT)
RETURNS TABLE (
    raw_text TEXT,
    amount NUMERIC,
    unit CHAR(1)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        matches[1] AS raw_text,
        CASE
            WHEN matches[3] = 'B' THEN matches[2]::NUMERIC * 1000000000
            WHEN matches[3] = 'M' THEN matches[2]::NUMERIC * 1000000
            WHEN matches[3] = 'K' THEN matches[2]::NUMERIC * 1000
            ELSE matches[2]::NUMERIC
        END AS amount,
        matches[3]::CHAR(1) AS unit
    FROM (
        SELECT regexp_matches(
            text_input,
            '\$([0-9]+\.?[0-9]*)\s*([BMK])',
            'gi'
        ) AS matches
    ) AS extracted;
END;
$$ LANGUAGE plpgsql;

-- Function to extract percentage values
CREATE OR REPLACE FUNCTION extract_percentages(text_input TEXT)
RETURNS TABLE (
    raw_text TEXT,
    percentage NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        matches[1] AS raw_text,
        matches[2]::NUMERIC AS percentage
    FROM (
        SELECT regexp_matches(
            text_input,
            '(([0-9]+\.?[0-9]*)\s*%)',
            'gi'
        ) AS matches
    ) AS extracted;
END;
$$ LANGUAGE plpgsql;

-- Function to check for credentials in text
CREATE OR REPLACE FUNCTION extract_credentials(text_input TEXT)
RETURNS TABLE (
    credential_type TEXT,
    credential_code TEXT,
    found BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cp.credential_type,
        cp.credential_code,
        text_input ~* cp.pattern_regex AS found
    FROM credential_patterns cp
    WHERE text_input ~* cp.pattern_regex;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate similarity between career trajectories
CREATE OR REPLACE FUNCTION find_similar_careers(
    query_embedding vector(1536),
    similarity_threshold FLOAT DEFAULT 0.8,
    limit_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    trajectory_id UUID,
    advisor_name TEXT,
    similarity_score FLOAT,
    career_highlights JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ct.id AS trajectory_id,
        ct.advisor_name,
        1 - (ct.career_embedding <=> query_embedding) AS similarity_score,
        ct.career_highlights
    FROM career_trajectories ct
    WHERE 1 - (ct.career_embedding <=> query_embedding) >= similarity_threshold
    ORDER BY ct.career_embedding <=> query_embedding
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- PART 7: CREATE MATERIALIZED VIEWS FOR COMMON QUERIES
-- =====================================================================

-- Materialized view for high-value advisors
CREATE MATERIALIZED VIEW IF NOT EXISTS high_value_advisors AS
SELECT
    eph.id,
    eph.contact_name,
    eph.company_name,
    eph.aum_amount,
    eph.production_amount,
    eph.trailing_12_revenue,
    eph.years_experience,
    array_length(eph.designations, 1) AS designation_count,
    array_length(eph.licenses, 1) AS license_count,
    eph.has_cfa OR eph.has_cfp AS has_premium_designation,
    eph.processed_at
FROM email_processing_history eph
WHERE
    (eph.aum_amount >= 100000000 OR  -- $100M+ AUM
     eph.production_amount >= 1000000 OR  -- $1M+ production
     eph.trailing_12_revenue >= 500000)  -- $500K+ revenue
    AND eph.processing_status = 'success'
WITH DATA;

-- Create index on materialized view
CREATE INDEX IF NOT EXISTS idx_high_value_aum
    ON high_value_advisors(aum_amount DESC NULLS LAST);

-- Materialized view for advisor credential summary
CREATE MATERIALIZED VIEW IF NOT EXISTS advisor_credential_summary AS
SELECT
    eph.company_name,
    COUNT(DISTINCT eph.id) AS advisor_count,
    AVG(eph.aum_amount) AS avg_aum,
    AVG(eph.production_amount) AS avg_production,
    ARRAY_AGG(DISTINCT unnest_designations) FILTER (WHERE unnest_designations IS NOT NULL) AS all_designations,
    ARRAY_AGG(DISTINCT unnest_licenses) FILTER (WHERE unnest_licenses IS NOT NULL) AS all_licenses,
    SUM(CASE WHEN eph.has_cfa THEN 1 ELSE 0 END) AS cfa_count,
    SUM(CASE WHEN eph.has_cfp THEN 1 ELSE 0 END) AS cfp_count
FROM email_processing_history eph
LEFT JOIN LATERAL unnest(eph.designations) AS unnest_designations ON true
LEFT JOIN LATERAL unnest(eph.licenses) AS unnest_licenses ON true
WHERE eph.processing_status = 'success'
GROUP BY eph.company_name
WITH DATA;

-- =====================================================================
-- PART 8: CREATE TRIGGERS FOR AUTOMATIC PATTERN EXTRACTION
-- =====================================================================

-- Trigger function to extract financial patterns on insert/update
CREATE OR REPLACE FUNCTION extract_financial_patterns_trigger()
RETURNS TRIGGER AS $$
DECLARE
    body_text TEXT;
    dollar_record RECORD;
    percent_record RECORD;
    credential_record RECORD;
BEGIN
    -- Get the email body text
    body_text := COALESCE(NEW.raw_extracted_data->>'email_body', '');

    -- Extract dollar amounts
    FOR dollar_record IN
        SELECT * FROM extract_dollar_amounts(body_text)
    LOOP
        -- Update AUM if pattern matches
        IF dollar_record.raw_text ~* '(aum|assets|manage)' THEN
            NEW.aum_amount := GREATEST(COALESCE(NEW.aum_amount, 0), dollar_record.amount);
        END IF;

        -- Update production if pattern matches
        IF dollar_record.raw_text ~* '(production|revenue|gross)' THEN
            NEW.production_amount := GREATEST(COALESCE(NEW.production_amount, 0), dollar_record.amount);
        END IF;

        -- Store pattern for learning
        INSERT INTO financial_patterns (
            pattern_type, raw_text, normalized_value, unit, source_email_id
        ) VALUES (
            CASE
                WHEN dollar_record.raw_text ~* 'aum' THEN 'aum'
                WHEN dollar_record.raw_text ~* 'production' THEN 'production'
                ELSE 'revenue'
            END,
            dollar_record.raw_text,
            dollar_record.amount,
            dollar_record.unit,
            NEW.id
        ) ON CONFLICT DO NOTHING;
    END LOOP;

    -- Extract credentials
    FOR credential_record IN
        SELECT * FROM extract_credentials(body_text)
    LOOP
        -- Update boolean flags
        IF credential_record.credential_code = 'Series 7' THEN
            NEW.has_series_7 := TRUE;
        ELSIF credential_record.credential_code = 'CFA' THEN
            NEW.has_cfa := TRUE;
        ELSIF credential_record.credential_code = 'CFP' THEN
            NEW.has_cfp := TRUE;
        END IF;

        -- Add to arrays
        IF credential_record.credential_type = 'license' THEN
            NEW.licenses := array_append(COALESCE(NEW.licenses, ARRAY[]::TEXT[]), credential_record.credential_code);
        ELSE
            NEW.designations := array_append(COALESCE(NEW.designations, ARRAY[]::TEXT[]), credential_record.credential_code);
        END IF;
    END LOOP;

    -- Remove duplicates from arrays
    NEW.licenses := ARRAY(SELECT DISTINCT unnest(NEW.licenses));
    NEW.designations := ARRAY(SELECT DISTINCT unnest(NEW.designations));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic extraction
DROP TRIGGER IF EXISTS extract_financial_patterns ON email_processing_history;
CREATE TRIGGER extract_financial_patterns
    BEFORE INSERT OR UPDATE ON email_processing_history
    FOR EACH ROW
    EXECUTE FUNCTION extract_financial_patterns_trigger();

-- =====================================================================
-- PART 9: CREATE ANALYTICS FUNCTIONS
-- =====================================================================

-- Function to analyze AUM distribution
CREATE OR REPLACE FUNCTION analyze_aum_distribution()
RETURNS TABLE (
    aum_range TEXT,
    advisor_count INTEGER,
    avg_years_experience NUMERIC,
    common_designations TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN aum_amount < 50000000 THEN 'Under $50M'
            WHEN aum_amount < 100000000 THEN '$50M-$100M'
            WHEN aum_amount < 250000000 THEN '$100M-$250M'
            WHEN aum_amount < 500000000 THEN '$250M-$500M'
            WHEN aum_amount < 1000000000 THEN '$500M-$1B'
            ELSE 'Over $1B'
        END AS aum_range,
        COUNT(*)::INTEGER AS advisor_count,
        AVG(years_experience)::NUMERIC(10,1) AS avg_years_experience,
        ARRAY_AGG(DISTINCT unnest(designations)) FILTER (WHERE designations IS NOT NULL) AS common_designations
    FROM email_processing_history
    WHERE aum_amount IS NOT NULL
        AND processing_status = 'success'
    GROUP BY
        CASE
            WHEN aum_amount < 50000000 THEN 'Under $50M'
            WHEN aum_amount < 100000000 THEN '$50M-$100M'
            WHEN aum_amount < 250000000 THEN '$100M-$250M'
            WHEN aum_amount < 500000000 THEN '$250M-$500M'
            WHEN aum_amount < 1000000000 THEN '$500M-$1B'
            ELSE 'Over $1B'
        END
    ORDER BY
        CASE aum_range
            WHEN 'Under $50M' THEN 1
            WHEN '$50M-$100M' THEN 2
            WHEN '$100M-$250M' THEN 3
            WHEN '$250M-$500M' THEN 4
            WHEN '$500M-$1B' THEN 5
            ELSE 6
        END;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- PART 10: REFRESH MATERIALIZED VIEWS
-- =====================================================================

-- Refresh materialized views (run periodically)
REFRESH MATERIALIZED VIEW CONCURRENTLY high_value_advisors;
REFRESH MATERIALIZED VIEW CONCURRENTLY advisor_credential_summary;

-- =====================================================================
-- MIGRATION COMPLETE
-- =====================================================================

-- Add migration tracking
INSERT INTO schema_migrations (version, name, applied_at)
VALUES ('20250926_financial_advisor_patterns', 'Add financial advisor pattern recognition and vector search', NOW())
ON CONFLICT DO NOTHING;

COMMENT ON TABLE financial_patterns IS 'Stores extracted financial metrics patterns for learning and optimization';
COMMENT ON TABLE credential_patterns IS 'Reference table for financial licenses and designations';
COMMENT ON TABLE achievement_patterns IS 'Patterns for recognizing advisor achievements and rankings';
COMMENT ON TABLE career_trajectories IS 'Vector-searchable career narratives for similarity matching';
COMMENT ON MATERIALIZED VIEW high_value_advisors IS 'Pre-computed view of advisors with significant AUM or production';