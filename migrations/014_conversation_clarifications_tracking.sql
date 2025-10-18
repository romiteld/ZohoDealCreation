-- Migration: Add conversation clarifications tracking table
-- Purpose: Track user clarification interactions for product analytics
-- Author: AI Assistant
-- Date: 2025-10-17

-- Create table for tracking clarification interactions
CREATE TABLE IF NOT EXISTS conversation_clarifications (
    clarification_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    conversation_id UUID REFERENCES teams_conversations(conversation_id),

    -- Original query and context
    original_query TEXT NOT NULL,
    query_confidence DECIMAL(3,2) CHECK (query_confidence >= 0 AND query_confidence <= 1),
    conversation_context JSONB,

    -- Clarification details
    clarification_question TEXT NOT NULL,
    clarification_type VARCHAR(50), -- 'missing_timeframe', 'missing_entity', 'vague_search', etc.
    options_presented JSONB NOT NULL, -- Array of {title, value} options
    options_count INTEGER NOT NULL CHECK (options_count >= 0),

    -- User response tracking
    user_response TEXT,
    chosen_option_index INTEGER CHECK (chosen_option_index >= 0),
    chosen_option_value VARCHAR(255),
    response_method VARCHAR(20), -- 'number', 'hash', 'text', 'fuzzy_match'
    response_confidence DECIMAL(3,2), -- How confident we are in the match

    -- Timing metrics
    presented_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    responded_at TIMESTAMP WITH TIME ZONE,
    time_to_response_seconds INTEGER GENERATED ALWAYS AS (
        CASE
            WHEN responded_at IS NOT NULL
            THEN EXTRACT(EPOCH FROM (responded_at - presented_at))::INTEGER
            ELSE NULL
        END
    ) STORED,

    -- Session tracking
    session_id UUID,
    is_followup BOOLEAN DEFAULT FALSE,
    followup_count INTEGER DEFAULT 0,

    -- Outcome tracking
    final_query TEXT, -- The refined query after clarification
    final_confidence DECIMAL(3,2),
    was_successful BOOLEAN,
    user_abandoned BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_clarifications_user_id ON conversation_clarifications(user_id);
CREATE INDEX idx_clarifications_conversation_id ON conversation_clarifications(conversation_id);
CREATE INDEX idx_clarifications_created_at ON conversation_clarifications(created_at DESC);
CREATE INDEX idx_clarifications_clarification_type ON conversation_clarifications(clarification_type);
CREATE INDEX idx_clarifications_response_method ON conversation_clarifications(response_method);
CREATE INDEX idx_clarifications_session ON conversation_clarifications(session_id);

-- Create analytics view for clarification patterns
CREATE OR REPLACE VIEW clarification_analytics AS
SELECT
    -- User metrics
    user_id,
    COUNT(*) as total_clarifications,
    COUNT(DISTINCT conversation_id) as unique_conversations,

    -- Response patterns
    AVG(options_count) as avg_options_presented,
    AVG(CASE WHEN responded_at IS NOT NULL THEN time_to_response_seconds END) as avg_response_time_seconds,
    SUM(CASE WHEN user_abandoned = TRUE THEN 1 ELSE 0 END) as abandoned_count,
    SUM(CASE WHEN was_successful = TRUE THEN 1 ELSE 0 END) as successful_count,

    -- Method preferences
    COUNT(CASE WHEN response_method = 'number' THEN 1 END) as responded_by_number,
    COUNT(CASE WHEN response_method = 'hash' THEN 1 END) as responded_by_hash,
    COUNT(CASE WHEN response_method = 'text' THEN 1 END) as responded_by_text,
    COUNT(CASE WHEN response_method = 'fuzzy_match' THEN 1 END) as responded_by_fuzzy,

    -- Clarification types
    COUNT(CASE WHEN clarification_type = 'missing_timeframe' THEN 1 END) as timeframe_clarifications,
    COUNT(CASE WHEN clarification_type = 'missing_entity' THEN 1 END) as entity_clarifications,
    COUNT(CASE WHEN clarification_type = 'vague_search' THEN 1 END) as vague_search_clarifications,

    -- Confidence improvements
    AVG(query_confidence) as avg_initial_confidence,
    AVG(final_confidence) as avg_final_confidence,
    AVG(COALESCE(final_confidence, 0) - COALESCE(query_confidence, 0)) as avg_confidence_improvement,

    -- Time periods
    DATE_TRUNC('day', MIN(created_at)) as first_clarification_date,
    DATE_TRUNC('day', MAX(created_at)) as last_clarification_date,

    -- Activity metrics
    COUNT(*) / NULLIF(DATE_PART('day', MAX(created_at) - MIN(created_at)) + 1, 0) as avg_clarifications_per_day

FROM conversation_clarifications
GROUP BY user_id;

-- Create daily clarification summary
CREATE OR REPLACE VIEW daily_clarification_summary AS
SELECT
    DATE_TRUNC('day', created_at) as date,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_clarifications,

    -- Success metrics
    AVG(CASE WHEN was_successful THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
    AVG(CASE WHEN user_abandoned THEN 1.0 ELSE 0.0 END) * 100 as abandonment_rate,

    -- Response timing
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_to_response_seconds) as median_response_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY time_to_response_seconds) as p95_response_time,

    -- Option selection patterns
    AVG(CASE
        WHEN chosen_option_index = 0 THEN 1.0
        ELSE 0.0
    END) * 100 as first_option_selection_rate,

    -- Top clarification types
    MODE() WITHIN GROUP (ORDER BY clarification_type) as most_common_type,

    -- Confidence metrics
    AVG(query_confidence) as avg_initial_confidence,
    AVG(final_confidence) as avg_final_confidence

FROM conversation_clarifications
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;

-- Function to get user clarification preferences
CREATE OR REPLACE FUNCTION get_user_clarification_preferences(p_user_id VARCHAR(255))
RETURNS TABLE (
    preferred_response_method VARCHAR(20),
    avg_response_time_seconds NUMERIC,
    typical_option_position NUMERIC,
    success_rate NUMERIC,
    most_common_clarification_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        MODE() WITHIN GROUP (ORDER BY cc.response_method) as preferred_response_method,
        AVG(cc.time_to_response_seconds)::NUMERIC as avg_response_time_seconds,
        AVG(cc.chosen_option_index + 1)::NUMERIC as typical_option_position,
        (AVG(CASE WHEN cc.was_successful THEN 1.0 ELSE 0.0 END) * 100)::NUMERIC as success_rate,
        MODE() WITHIN GROUP (ORDER BY cc.clarification_type) as most_common_clarification_type
    FROM conversation_clarifications cc
    WHERE cc.user_id = p_user_id
        AND cc.responded_at IS NOT NULL
        AND cc.created_at >= NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_clarification_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER clarification_updated_at_trigger
    BEFORE UPDATE ON conversation_clarifications
    FOR EACH ROW
    EXECUTE FUNCTION update_clarification_updated_at();

-- Grant appropriate permissions
GRANT SELECT, INSERT, UPDATE ON conversation_clarifications TO well_intake_api;
GRANT SELECT ON clarification_analytics TO well_intake_api;
GRANT SELECT ON daily_clarification_summary TO well_intake_api;
GRANT EXECUTE ON FUNCTION get_user_clarification_preferences TO well_intake_api;

-- Add comments for documentation
COMMENT ON TABLE conversation_clarifications IS 'Tracks user clarification interactions for NLP queries in Teams bot';
COMMENT ON COLUMN conversation_clarifications.response_method IS 'How user responded: number (1,2,3), hash (#1,#2), text (typed), or fuzzy_match';
COMMENT ON COLUMN conversation_clarifications.time_to_response_seconds IS 'Calculated time between presenting clarification and receiving response';
COMMENT ON VIEW clarification_analytics IS 'Aggregated analytics per user for clarification patterns and preferences';
COMMENT ON VIEW daily_clarification_summary IS 'Daily summary of clarification metrics for monitoring and optimization';