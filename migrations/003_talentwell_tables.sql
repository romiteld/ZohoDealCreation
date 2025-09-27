-- Migration 003: TalentWell CSV Import and Outlook Deal Persistence Tables
-- This migration creates a comprehensive schema for deal management, stage tracking,
-- meetings, notes, normalization, A/B testing, and audit logging
-- All operations are idempotent using IF NOT EXISTS

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text matching

-- =============================================================================
-- DEALS TABLE
-- Central table for all deal information
-- =============================================================================
CREATE TABLE IF NOT EXISTS deals (
    deal_id TEXT PRIMARY KEY,
    deal_name TEXT NOT NULL,
    owner_email TEXT,
    owner_name TEXT,
    stage TEXT,
    amount DECIMAL(15, 2),
    close_date DATE,
    probability INTEGER CHECK (probability >= 0 AND probability <= 100),
    contact_name TEXT,
    contact_email TEXT,
    account_name TEXT,
    employer_normalized TEXT, -- Links to employer_normalization
    city_normalized TEXT,     -- Links to city_context
    source TEXT,
    source_detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    
    -- Indexes for common queries
    CONSTRAINT deals_probability_check CHECK (probability IS NULL OR (probability >= 0 AND probability <= 100))
);

-- Create indexes for deals table
CREATE INDEX IF NOT EXISTS idx_deals_owner_email ON deals(owner_email);
CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage);
CREATE INDEX IF NOT EXISTS idx_deals_close_date ON deals(close_date);
CREATE INDEX IF NOT EXISTS idx_deals_created_at ON deals(created_at);
CREATE INDEX IF NOT EXISTS idx_deals_modified_at ON deals(modified_at);
CREATE INDEX IF NOT EXISTS idx_deals_account_name ON deals(account_name);
CREATE INDEX IF NOT EXISTS idx_deals_employer_normalized ON deals(employer_normalized);
CREATE INDEX IF NOT EXISTS idx_deals_metadata ON deals USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_deals_source ON deals(source);

-- Full-text search index on deal_name and account_name
CREATE INDEX IF NOT EXISTS idx_deals_fulltext ON deals 
    USING GIN (to_tsvector('english', COALESCE(deal_name, '') || ' ' || COALESCE(account_name, '')));

-- =============================================================================
-- DEAL STAGE HISTORY TABLE
-- Tracks all stage transitions for deals
-- =============================================================================
CREATE TABLE IF NOT EXISTS deal_stage_history (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id) ON DELETE CASCADE,
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    moved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    moved_by TEXT,
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    
    -- Composite primary key ensures unique stage transitions at exact timestamps
    PRIMARY KEY (deal_id, to_stage, moved_at)
);

-- Create indexes for deal_stage_history
CREATE INDEX IF NOT EXISTS idx_stage_history_deal_id ON deal_stage_history(deal_id);
CREATE INDEX IF NOT EXISTS idx_stage_history_moved_at ON deal_stage_history(moved_at);
CREATE INDEX IF NOT EXISTS idx_stage_history_to_stage ON deal_stage_history(to_stage);
CREATE INDEX IF NOT EXISTS idx_stage_history_from_to ON deal_stage_history(from_stage, to_stage);

-- =============================================================================
-- MEETINGS TABLE
-- Stores meeting information related to deals
-- =============================================================================
CREATE TABLE IF NOT EXISTS meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deal_id TEXT NOT NULL REFERENCES deals(deal_id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    meeting_date TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER,
    location TEXT,
    attendees TEXT[],
    meeting_type TEXT,
    notes TEXT,
    outcome TEXT,
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    -- Natural key constraint to prevent duplicate meetings
    CONSTRAINT meetings_natural_key UNIQUE (deal_id, subject, meeting_date)
);

-- Create indexes for meetings table
CREATE INDEX IF NOT EXISTS idx_meetings_deal_id ON meetings(deal_id);
CREATE INDEX IF NOT EXISTS idx_meetings_meeting_date ON meetings(meeting_date);
CREATE INDEX IF NOT EXISTS idx_meetings_follow_up_date ON meetings(follow_up_date) WHERE follow_up_required = true;
CREATE INDEX IF NOT EXISTS idx_meetings_attendees ON meetings USING GIN (attendees);
CREATE INDEX IF NOT EXISTS idx_meetings_meeting_type ON meetings(meeting_type);

-- Full-text search index on meeting subject and notes
CREATE INDEX IF NOT EXISTS idx_meetings_fulltext ON meetings 
    USING GIN (to_tsvector('english', COALESCE(subject, '') || ' ' || COALESCE(notes, '')));

-- =============================================================================
-- DEAL NOTES TABLE
-- Stores notes and comments for deals with automatic deduplication
-- =============================================================================
CREATE TABLE IF NOT EXISTS deal_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deal_id TEXT NOT NULL REFERENCES deals(deal_id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    note_type TEXT DEFAULT 'general',
    created_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_pinned BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}',
    -- Generated column for note hash (MD5 of note_text)
    note_hash TEXT GENERATED ALWAYS AS (encode(digest(note_text, 'md5'), 'hex')) STORED,
    
    -- Unique constraint to prevent duplicate notes for the same deal at the same time
    CONSTRAINT deal_notes_unique_hash UNIQUE (deal_id, created_at, note_hash)
);

-- Create indexes for deal_notes table
CREATE INDEX IF NOT EXISTS idx_deal_notes_deal_id ON deal_notes(deal_id);
CREATE INDEX IF NOT EXISTS idx_deal_notes_created_at ON deal_notes(created_at);
CREATE INDEX IF NOT EXISTS idx_deal_notes_note_type ON deal_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_deal_notes_created_by ON deal_notes(created_by);
CREATE INDEX IF NOT EXISTS idx_deal_notes_is_pinned ON deal_notes(is_pinned) WHERE is_pinned = true;

-- Full-text search index on note text
CREATE INDEX IF NOT EXISTS idx_deal_notes_fulltext ON deal_notes 
    USING GIN (to_tsvector('english', note_text));

-- =============================================================================
-- EMPLOYER NORMALIZATION TABLE
-- Maps raw employer names to normalized versions
-- =============================================================================
CREATE TABLE IF NOT EXISTS employer_normalization (
    raw_name TEXT PRIMARY KEY,
    normalized_name TEXT NOT NULL,
    confidence_score DECIMAL(3, 2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    industry TEXT,
    company_size TEXT,
    headquarters_location TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'
);

-- Create indexes for employer_normalization
CREATE INDEX IF NOT EXISTS idx_employer_norm_normalized ON employer_normalization(normalized_name);
CREATE INDEX IF NOT EXISTS idx_employer_norm_verified ON employer_normalization(verified);
CREATE INDEX IF NOT EXISTS idx_employer_norm_industry ON employer_normalization(industry);

-- Trigram index for fuzzy matching on raw and normalized names
CREATE INDEX IF NOT EXISTS idx_employer_norm_raw_trgm ON employer_normalization 
    USING GIN (raw_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_employer_norm_normalized_trgm ON employer_normalization 
    USING GIN (normalized_name gin_trgm_ops);

-- =============================================================================
-- CITY CONTEXT TABLE
-- Maps raw city/state combinations to normalized locations
-- =============================================================================
CREATE TABLE IF NOT EXISTS city_context (
    raw_city_state TEXT PRIMARY KEY,
    normalized_city TEXT NOT NULL,
    normalized_state TEXT NOT NULL,
    country TEXT DEFAULT 'USA',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    timezone TEXT,
    metro_area TEXT,
    population INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'
);

-- Create indexes for city_context
CREATE INDEX IF NOT EXISTS idx_city_context_normalized ON city_context(normalized_city, normalized_state);
CREATE INDEX IF NOT EXISTS idx_city_context_state ON city_context(normalized_state);
CREATE INDEX IF NOT EXISTS idx_city_context_metro ON city_context(metro_area);
CREATE INDEX IF NOT EXISTS idx_city_context_verified ON city_context(verified);

-- Trigram index for fuzzy matching on city names
CREATE INDEX IF NOT EXISTS idx_city_context_raw_trgm ON city_context 
    USING GIN (raw_city_state gin_trgm_ops);

-- =============================================================================
-- SUBJECT BANDIT TABLE
-- A/B testing for email subject lines using multi-armed bandit algorithm
-- =============================================================================
CREATE TABLE IF NOT EXISTS subject_bandit (
    audience TEXT NOT NULL,
    variant TEXT NOT NULL,
    impressions INTEGER DEFAULT 0 CHECK (impressions >= 0),
    conversions INTEGER DEFAULT 0 CHECK (conversions >= 0),
    total_reward DECIMAL(10, 4) DEFAULT 0,
    alpha DECIMAL(10, 4) DEFAULT 1.0 CHECK (alpha > 0),
    beta DECIMAL(10, 4) DEFAULT 1.0 CHECK (beta > 0),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    
    -- Composite primary key
    PRIMARY KEY (audience, variant),
    
    -- Ensure conversions don't exceed impressions
    CONSTRAINT subject_bandit_conversion_check CHECK (conversions <= impressions)
);

-- Create indexes for subject_bandit
CREATE INDEX IF NOT EXISTS idx_subject_bandit_audience ON subject_bandit(audience);
CREATE INDEX IF NOT EXISTS idx_subject_bandit_active ON subject_bandit(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_subject_bandit_last_updated ON subject_bandit(last_updated);

-- =============================================================================
-- SELECTOR PRIORS TABLE
-- Stores prior probabilities for Bayesian inference in model selection
-- =============================================================================
CREATE TABLE IF NOT EXISTS selector_priors (
    selector TEXT PRIMARY KEY,
    prior_alpha DECIMAL(10, 4) DEFAULT 1.0 CHECK (prior_alpha > 0),
    prior_beta DECIMAL(10, 4) DEFAULT 1.0 CHECK (prior_beta > 0),
    observations INTEGER DEFAULT 0 CHECK (observations >= 0),
    successes INTEGER DEFAULT 0 CHECK (successes >= 0),
    mean_reward DECIMAL(10, 6),
    variance DECIMAL(10, 6),
    last_calibrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    confidence_interval_lower DECIMAL(10, 6),
    confidence_interval_upper DECIMAL(10, 6),
    metadata JSONB DEFAULT '{}',
    
    -- Ensure successes don't exceed observations
    CONSTRAINT selector_priors_success_check CHECK (successes <= observations)
);

-- Create indexes for selector_priors
CREATE INDEX IF NOT EXISTS idx_selector_priors_last_calibrated ON selector_priors(last_calibrated);
CREATE INDEX IF NOT EXISTS idx_selector_priors_observations ON selector_priors(observations);

-- =============================================================================
-- INTAKE AUDIT TABLE
-- Comprehensive audit trail for all intake operations
-- =============================================================================
CREATE TABLE IF NOT EXISTS intake_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_id UUID NOT NULL,
    message_id TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    deal_id TEXT,
    request_payload JSONB,
    response_payload JSONB,
    outcome TEXT CHECK (outcome IN ('success', 'failure', 'partial', 'skipped')),
    error_message TEXT,
    error_details JSONB,
    processing_time_ms INTEGER,
    api_calls_made INTEGER DEFAULT 0,
    tokens_consumed INTEGER DEFAULT 0,
    cost_estimate DECIMAL(10, 6),
    user_email TEXT,
    client_ip INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    -- Index for deduplication checks
    CONSTRAINT intake_audit_message_unique UNIQUE (message_id)
);

-- Create indexes for intake_audit
CREATE INDEX IF NOT EXISTS idx_intake_audit_correlation_id ON intake_audit(correlation_id);
CREATE INDEX IF NOT EXISTS idx_intake_audit_message_id ON intake_audit(message_id);
CREATE INDEX IF NOT EXISTS idx_intake_audit_deal_id ON intake_audit(deal_id);
CREATE INDEX IF NOT EXISTS idx_intake_audit_created_at ON intake_audit(created_at);
CREATE INDEX IF NOT EXISTS idx_intake_audit_outcome ON intake_audit(outcome);
CREATE INDEX IF NOT EXISTS idx_intake_audit_operation_type ON intake_audit(operation_type);
CREATE INDEX IF NOT EXISTS idx_intake_audit_user_email ON intake_audit(user_email);

-- GIN index for JSON searching in audit payloads
CREATE INDEX IF NOT EXISTS idx_intake_audit_request ON intake_audit USING GIN (request_payload);
CREATE INDEX IF NOT EXISTS idx_intake_audit_response ON intake_audit USING GIN (response_payload);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to update modified_at timestamp
CREATE OR REPLACE FUNCTION update_modified_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.modified_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-update modified_at for deals
DROP TRIGGER IF EXISTS update_deals_modified_at ON deals;
CREATE TRIGGER update_deals_modified_at
    BEFORE UPDATE ON deals
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_at_column();

-- Auto-update modified_at for meetings
DROP TRIGGER IF EXISTS update_meetings_modified_at ON meetings;
CREATE TRIGGER update_meetings_modified_at
    BEFORE UPDATE ON meetings
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_at_column();

-- Auto-update modified_at for deal_notes
DROP TRIGGER IF EXISTS update_deal_notes_modified_at ON deal_notes;
CREATE TRIGGER update_deal_notes_modified_at
    BEFORE UPDATE ON deal_notes
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_at_column();

-- Auto-update updated_at for employer_normalization
DROP TRIGGER IF EXISTS update_employer_norm_updated_at ON employer_normalization;
CREATE TRIGGER update_employer_norm_updated_at
    BEFORE UPDATE ON employer_normalization
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_at_column();

-- Auto-update updated_at for city_context
DROP TRIGGER IF EXISTS update_city_context_updated_at ON city_context;
CREATE TRIGGER update_city_context_updated_at
    BEFORE UPDATE ON city_context
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_at_column();

-- =============================================================================
-- STATISTICS UPDATE
-- =============================================================================
-- Update table statistics for query planner optimization
ANALYZE deals;
ANALYZE deal_stage_history;
ANALYZE meetings;
ANALYZE deal_notes;
ANALYZE employer_normalization;
ANALYZE city_context;
ANALYZE subject_bandit;
ANALYZE selector_priors;
ANALYZE intake_audit;

-- =============================================================================
-- MIGRATION METADATA
-- =============================================================================
COMMENT ON TABLE deals IS 'Central table storing all deal information from TalentWell and Outlook';
COMMENT ON TABLE deal_stage_history IS 'Audit trail of all stage transitions for deals';
COMMENT ON TABLE meetings IS 'Meeting records associated with deals';
COMMENT ON TABLE deal_notes IS 'Notes and comments for deals with automatic deduplication';
COMMENT ON TABLE employer_normalization IS 'Maps raw employer names to normalized canonical forms';
COMMENT ON TABLE city_context IS 'Normalizes city/state combinations to standard locations';
COMMENT ON TABLE subject_bandit IS 'A/B testing data for email subject lines using multi-armed bandit';
COMMENT ON TABLE selector_priors IS 'Bayesian priors for model selection and optimization';
COMMENT ON TABLE intake_audit IS 'Comprehensive audit trail for all intake operations';

-- Add column comments for important fields
COMMENT ON COLUMN deals.deal_id IS 'Unique identifier for the deal, typically from external system';
COMMENT ON COLUMN deal_notes.note_hash IS 'MD5 hash of note_text for deduplication';
COMMENT ON COLUMN intake_audit.correlation_id IS 'UUID to correlate related operations across the system';
COMMENT ON COLUMN intake_audit.message_id IS 'Unique message identifier for deduplication';
COMMENT ON COLUMN subject_bandit.alpha IS 'Alpha parameter for Beta distribution in Thompson sampling';
COMMENT ON COLUMN subject_bandit.beta IS 'Beta parameter for Beta distribution in Thompson sampling';

-- End of migration 003_talentwell_tables.sql