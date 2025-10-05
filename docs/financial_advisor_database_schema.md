# Financial Advisor Database Schema Documentation

## Overview

This document describes the enhanced PostgreSQL database schema optimized for financial advisor data extraction, pattern recognition, and vector similarity search using pgvector. The schema is specifically designed to handle Brandon's key patterns for financial advisors.

## Core Tables Enhancement

### 1. Enhanced `email_processing_history` Table

The main table has been extended with financial-specific columns:

#### Financial Metrics Columns
```sql
financial_metrics JSONB                 -- Flexible storage for all extracted metrics
aum_amount NUMERIC(15,2)               -- Assets Under Management in dollars
aum_range_low NUMERIC(15,2)            -- AUM range lower bound
aum_range_high NUMERIC(15,2)           -- AUM range upper bound
production_amount NUMERIC(15,2)        -- Annual production in dollars
compensation_low NUMERIC(15,2)         -- Compensation range lower bound
compensation_high NUMERIC(15,2)        -- Compensation range upper bound
trailing_12_revenue NUMERIC(15,2)      -- T12 revenue
years_experience INTEGER               -- Years in the industry
team_size INTEGER                       -- Size of advisor's team
```

#### License & Designation Columns
```sql
-- Boolean flags for quick filtering
has_series_7 BOOLEAN
has_series_63 BOOLEAN
has_series_65 BOOLEAN
has_series_66 BOOLEAN
has_series_24 BOOLEAN
has_series_31 BOOLEAN
has_cfa BOOLEAN
has_cfp BOOLEAN
has_cpwa BOOLEAN
has_chfc BOOLEAN
has_clu BOOLEAN
has_mba BOOLEAN

-- Array columns for comprehensive storage
designations TEXT[]                    -- All professional designations
licenses TEXT[]                        -- All regulatory licenses
achievements TEXT[]                    -- Awards and rankings
rankings TEXT[]                        -- Specific ranking achievements
performance_percentages NUMERIC[]      -- Performance metrics as percentages
extracted_patterns JSONB              -- Raw extracted pattern data
```

## New Pattern Recognition Tables

### 2. `financial_patterns` Table

Stores and learns from extracted financial metrics:

```sql
CREATE TABLE financial_patterns (
    id UUID PRIMARY KEY,
    pattern_type TEXT,                 -- 'aum', 'production', 'compensation', 'revenue'
    raw_text TEXT,                     -- Original text containing the pattern
    normalized_value NUMERIC(15,2),    -- Standardized dollar amount
    unit TEXT,                         -- 'M', 'B', 'K'
    confidence_score DECIMAL(3,2),     -- Pattern confidence (0-1)
    pattern_regex TEXT,                -- Regex used for extraction
    context_before TEXT,               -- Text before the pattern
    context_after TEXT,                -- Text after the pattern
    source_email_id UUID,              -- Link to source email
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 3. `credential_patterns` Table

Reference table for licenses and designations:

```sql
CREATE TABLE credential_patterns (
    id UUID PRIMARY KEY,
    credential_type TEXT,              -- 'license' or 'designation'
    credential_code TEXT,              -- 'Series 7', 'CFA', etc.
    full_name TEXT,                    -- Full credential name
    variations TEXT[],                 -- Different text representations
    pattern_regex TEXT,                -- Regex for detection
    importance_rank INTEGER,           -- Priority ranking
    category TEXT,                     -- 'regulatory', 'professional', 'academic'
    created_at TIMESTAMP
);
```

Pre-populated with:
- **Licenses**: Series 7, 63, 65, 66, 24, 31
- **Designations**: CFA, CFP, CPWA, ChFC, CLU, MBA

### 4. `achievement_patterns` Table

Recognition patterns for achievements and rankings:

```sql
CREATE TABLE achievement_patterns (
    id UUID PRIMARY KEY,
    achievement_type TEXT,             -- 'ranking', 'award', 'club', 'performance'
    pattern_text TEXT,                 -- Pattern description
    pattern_regex TEXT,                -- Detection regex
    importance_score INTEGER,          -- Achievement importance (0-100)
    category TEXT,                     -- Achievement category
    typical_context TEXT[],            -- Common surrounding words
    created_at TIMESTAMP
);
```

Pre-populated patterns:
- "#1 Advisor" patterns
- "Top Producer" variations
- "President's Club" and "Chairman's Club"
- "Barron's Top" and "Forbes Best" rankings

### 5. `career_trajectories` Table

Vector-searchable career narratives:

```sql
CREATE TABLE career_trajectories (
    id UUID PRIMARY KEY,
    email_id UUID,                     -- Link to email record
    advisor_name TEXT,
    career_narrative TEXT,             -- Full career story
    career_embedding vector(1536),     -- Vector for similarity search
    career_highlights JSONB,           -- Structured highlights
    firms_worked TEXT[],               -- List of firms
    progression_pattern TEXT,          -- Career progression type
    total_industry_experience INTEGER,
    peak_aum NUMERIC(15,2),
    peak_production NUMERIC(15,2),
    specializations TEXT[],
    client_types TEXT[],
    created_at TIMESTAMP
);
```

## Optimized Indexes

### Numeric Range Indexes (B-tree)
```sql
idx_email_aum_amount              -- Single AUM value searches
idx_email_aum_range               -- AUM range queries
idx_email_production              -- Production amount queries
idx_email_compensation            -- Compensation range queries
idx_email_revenue                 -- Revenue queries
idx_email_experience              -- Years of experience queries
```

### Boolean License/Designation Indexes (Partial)
```sql
idx_has_series_7                  -- Quick Series 7 filtering
idx_has_series_65_66              -- Investment advisor licenses
idx_has_cfa_cfp                   -- Premium designations
```

### Array Search Indexes (GIN)
```sql
idx_designations_gin              -- Search within designations array
idx_licenses_gin                  -- Search within licenses array
idx_achievements_gin              -- Search within achievements array
idx_financial_metrics_gin         -- JSONB financial metrics queries
idx_extracted_patterns_gin        -- JSONB pattern data queries
```

### Text Search Indexes
```sql
idx_financial_patterns_text       -- Full-text search on patterns
idx_achievement_patterns_text     -- Full-text search on achievements
```

### Vector Similarity Indexes
```sql
idx_career_embedding_hnsw         -- HNSW index for career similarity
                                  -- Settings: m=16, ef_construction=64
```

### Composite Indexes
```sql
idx_email_aum_and_licenses        -- Combined AUM and license queries
idx_financial_patterns_type_value -- Pattern type and value lookups
```

## Utility Functions

### 1. Dollar Amount Extraction
```sql
SELECT * FROM extract_dollar_amounts('Manages $250M in assets');
-- Returns: raw_text='$250M', amount=250000000, unit='M'
```

### 2. Percentage Extraction
```sql
SELECT * FROM extract_percentages('Achieved 95% client retention');
-- Returns: raw_text='95%', percentage=95
```

### 3. Credential Detection
```sql
SELECT * FROM extract_credentials('CFA charterholder with Series 7 and 66');
-- Returns: Multiple rows with credential_type, credential_code, found=true
```

### 4. Career Similarity Search
```sql
SELECT * FROM find_similar_careers(
    query_embedding := vector_value,
    similarity_threshold := 0.8,
    limit_results := 10
);
```

## Materialized Views

### 1. `high_value_advisors`
Pre-computed view of advisors with:
- AUM >= $100M
- Production >= $1M
- Revenue >= $500K

Refreshed daily with: `REFRESH MATERIALIZED VIEW CONCURRENTLY high_value_advisors;`

### 2. `advisor_credential_summary`
Aggregated view by company showing:
- Average AUM and production
- All unique designations and licenses
- Count of CFA/CFP holders

## Automatic Pattern Extraction

### Trigger: `extract_financial_patterns`
Automatically runs on INSERT/UPDATE to:
1. Extract dollar amounts and categorize them (AUM, production, etc.)
2. Detect licenses and designations
3. Update boolean flags and arrays
4. Store patterns for learning

## Analytics Functions

### AUM Distribution Analysis
```sql
SELECT * FROM analyze_aum_distribution();
```
Returns distribution of advisors across AUM ranges with average experience and common designations.

## Query Examples

### 1. Find High-Value Advisors with CFA
```sql
SELECT
    contact_name,
    company_name,
    aum_amount,
    production_amount,
    designations
FROM email_processing_history
WHERE aum_amount >= 100000000
    AND has_cfa = TRUE
    AND processing_status = 'success'
ORDER BY aum_amount DESC;
```

### 2. Search for Similar Career Trajectories
```sql
WITH target_embedding AS (
    SELECT career_embedding
    FROM career_trajectories
    WHERE advisor_name = 'John Smith'
)
SELECT
    ct.advisor_name,
    ct.peak_aum,
    ct.firms_worked,
    1 - (ct.career_embedding <=> te.career_embedding) AS similarity
FROM career_trajectories ct, target_embedding te
WHERE 1 - (ct.career_embedding <=> te.career_embedding) > 0.85
ORDER BY similarity DESC
LIMIT 10;
```

### 3. Analyze Production by License Type
```sql
SELECT
    CASE
        WHEN has_series_65 OR has_series_66 THEN 'RIA'
        WHEN has_series_7 THEN 'Broker-Dealer'
        ELSE 'Other'
    END AS advisor_type,
    COUNT(*) AS advisor_count,
    AVG(production_amount) AS avg_production,
    AVG(aum_amount) AS avg_aum
FROM email_processing_history
WHERE production_amount IS NOT NULL
GROUP BY advisor_type
ORDER BY avg_production DESC;
```

### 4. Find Advisors by Achievement Pattern
```sql
SELECT DISTINCT
    eph.contact_name,
    eph.company_name,
    eph.achievements,
    eph.aum_amount
FROM email_processing_history eph
WHERE
    achievements @> ARRAY['President''s Club']::TEXT[]
    OR raw_extracted_data::TEXT ~* 'president''?s club'
ORDER BY aum_amount DESC NULLS LAST;
```

## Migration Instructions

1. **Run the migration script**:
```bash
psql -U username -d database_name -f migrations/add_financial_advisor_patterns.sql
```

2. **Verify installation**:
```sql
-- Check if extensions are enabled
SELECT * FROM pg_extension WHERE extname IN ('vector', 'pg_trgm', 'btree_gin');

-- Verify new columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'email_processing_history'
AND column_name LIKE '%aum%' OR column_name LIKE '%has_%';

-- Check if triggers are active
SELECT * FROM information_schema.triggers
WHERE trigger_name = 'extract_financial_patterns';
```

3. **Populate existing data** (optional):
```sql
-- Reprocess existing emails to extract patterns
UPDATE email_processing_history
SET financial_metrics = '{}'
WHERE financial_metrics IS NULL;
```

## Performance Considerations

1. **Index Usage**: The schema uses specialized indexes:
   - HNSW for high-accuracy vector searches
   - GIN for array and JSONB queries
   - Partial indexes for boolean flags to reduce index size

2. **Materialized Views**: Pre-computed aggregations reduce query time for common analytics

3. **Triggers**: Automatic extraction happens at insert time, avoiding batch reprocessing

4. **Vector Dimensions**: Using standard 1536 dimensions for OpenAI embeddings, expandable to 3072 for large models

## Maintenance

### Daily Tasks
```sql
-- Refresh materialized views
REFRESH MATERIALIZED VIEW CONCURRENTLY high_value_advisors;
REFRESH MATERIALIZED VIEW CONCURRENTLY advisor_credential_summary;

-- Update statistics
ANALYZE email_processing_history;
ANALYZE career_trajectories;
```

### Weekly Tasks
```sql
-- Reindex vector indexes for optimal performance
REINDEX INDEX CONCURRENTLY idx_career_embedding_hnsw;

-- Clean up old similarity cache entries
DELETE FROM similarity_cache WHERE expires_at < NOW();
```

### Monthly Tasks
```sql
-- Vacuum and analyze all financial tables
VACUUM ANALYZE financial_patterns;
VACUUM ANALYZE credential_patterns;
VACUUM ANALYZE career_trajectories;

-- Review and update pattern confidence scores
UPDATE financial_patterns
SET confidence_score = LEAST(confidence_score * 1.1, 0.95)
WHERE pattern_type IN (
    SELECT pattern_type
    FROM financial_patterns
    GROUP BY pattern_type
    HAVING COUNT(*) > 100
);
```

## Security Notes

1. All financial amounts are stored as NUMERIC(15,2) to maintain precision
2. PII data in career_trajectories should be encrypted at rest
3. Access to financial_metrics JSONB should be audited
4. Consider row-level security for multi-tenant deployments