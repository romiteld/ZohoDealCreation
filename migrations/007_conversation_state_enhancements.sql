-- Migration: Conversation State Enhancements for Multi-Turn Dialogue
-- Description: Add conversation memory tracking and clarification session support
-- Author: Claude
-- Date: 2025-10-08
-- Related: Phase 0 - Conversational AI Memory System

-- ============================================
-- 1. Add conversation history columns to teams_conversations
-- ============================================
ALTER TABLE teams_conversations
    ADD COLUMN IF NOT EXISTS intent_type VARCHAR(100),
    ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(3,2),
    ADD COLUMN IF NOT EXISTS clarification_needed BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS clarification_session_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS conversation_context JSONB;

CREATE INDEX IF NOT EXISTS idx_teams_conversations_confidence ON teams_conversations(confidence_score);
CREATE INDEX IF NOT EXISTS idx_teams_conversations_intent_type ON teams_conversations(intent_type);
CREATE INDEX IF NOT EXISTS idx_teams_conversations_clarification ON teams_conversations(clarification_session_id) WHERE clarification_session_id IS NOT NULL;

COMMENT ON COLUMN teams_conversations.intent_type IS 'Classified intent type: count, list, aggregate, search, transcript_summary, clarification';
COMMENT ON COLUMN teams_conversations.confidence_score IS 'Intent classification confidence (0.0-1.0)';
COMMENT ON COLUMN teams_conversations.clarification_needed IS 'Whether bot requested clarification for this message';
COMMENT ON COLUMN teams_conversations.clarification_session_id IS 'Session ID if clarification was triggered';
COMMENT ON COLUMN teams_conversations.conversation_context IS 'JSONB: Conversation history snapshot for analytics';

-- ============================================
-- 2. Create conversation_memory table for hot cache tracking
-- ============================================
CREATE TABLE IF NOT EXISTS conversation_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    conversation_id VARCHAR(255),
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    intent_type VARCHAR(100),
    confidence_score DECIMAL(3,2),
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_confidence CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1))
);

CREATE INDEX IF NOT EXISTS idx_conversation_memory_user_id ON conversation_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_timestamp ON conversation_memory(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_user_time ON conversation_memory(user_id, timestamp DESC);

COMMENT ON TABLE conversation_memory IS 'Cold storage for conversation history (hot storage in Redis)';
COMMENT ON COLUMN conversation_memory.role IS 'Message role: user or assistant';
COMMENT ON COLUMN conversation_memory.content IS 'Message text content';
COMMENT ON COLUMN conversation_memory.intent_type IS 'Classified intent for this message';
COMMENT ON COLUMN conversation_memory.confidence_score IS 'Classification confidence (0.0-1.0)';
COMMENT ON COLUMN conversation_memory.metadata IS 'JSONB: Additional context (entities, filters, etc.)';

-- ============================================
-- 3. Create clarification_sessions table
-- ============================================
CREATE TABLE IF NOT EXISTS clarification_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    original_query TEXT NOT NULL,
    ambiguity_type VARCHAR(100) NOT NULL,
    suggested_options JSONB DEFAULT '[]',
    partial_intent JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    clarification_response TEXT,

    -- Constraints
    CONSTRAINT valid_ambiguity_type CHECK (ambiguity_type IN (
        'missing_timeframe',
        'missing_entity',
        'vague_search',
        'multiple_matches'
    ))
);

CREATE INDEX IF NOT EXISTS idx_clarification_sessions_session_id ON clarification_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_clarification_sessions_user_id ON clarification_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_clarification_sessions_expires ON clarification_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_clarification_sessions_created ON clarification_sessions(created_at DESC);

COMMENT ON TABLE clarification_sessions IS 'Tracks active clarification sessions for multi-turn dialogue';
COMMENT ON COLUMN clarification_sessions.session_id IS 'Unique session identifier (UUID)';
COMMENT ON COLUMN clarification_sessions.ambiguity_type IS 'Type of ambiguity: missing_timeframe, missing_entity, vague_search, multiple_matches';
COMMENT ON COLUMN clarification_sessions.suggested_options IS 'JSONB array of clarification options shown to user';
COMMENT ON COLUMN clarification_sessions.partial_intent IS 'JSONB: Partial intent to merge with clarification';
COMMENT ON COLUMN clarification_sessions.expires_at IS 'Session expires after 5 minutes';
COMMENT ON COLUMN clarification_sessions.resolved_at IS 'Timestamp when user responded';
COMMENT ON COLUMN clarification_sessions.clarification_response IS 'User\''s clarification answer';

-- ============================================
-- 4. Create analytics view for conversation metrics
-- ============================================
CREATE OR REPLACE VIEW conversation_analytics AS
SELECT
    user_id,
    user_email,
    DATE(created_at) as conversation_date,
    COUNT(*) as total_messages,
    COUNT(CASE WHEN clarification_needed = TRUE THEN 1 END) as clarification_requests,
    AVG(confidence_score) as avg_confidence,
    MIN(confidence_score) as min_confidence,
    MAX(confidence_score) as max_confidence,
    COUNT(DISTINCT intent_type) as unique_intent_types,
    JSONB_AGG(DISTINCT intent_type) as intent_types_used
FROM teams_conversations
WHERE confidence_score IS NOT NULL
GROUP BY user_id, user_email, DATE(created_at);

COMMENT ON VIEW conversation_analytics IS 'Daily conversation metrics per user for analytics';

-- ============================================
-- 5. Create view for clarification session analytics
-- ============================================
CREATE OR REPLACE VIEW clarification_analytics AS
SELECT
    user_id,
    user_email,
    ambiguity_type,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN resolved_at IS NOT NULL THEN 1 END) as resolved_sessions,
    COUNT(CASE WHEN resolved_at IS NULL AND expires_at < NOW() THEN 1 END) as expired_sessions,
    AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))) as avg_resolution_time_seconds,
    DATE(created_at) as session_date
FROM clarification_sessions
GROUP BY user_id, user_email, ambiguity_type, DATE(created_at);

COMMENT ON VIEW clarification_analytics IS 'Clarification session success metrics';

-- ============================================
-- 6. Cleanup function for expired sessions
-- ============================================
CREATE OR REPLACE FUNCTION cleanup_expired_clarification_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete sessions that expired more than 24 hours ago
    DELETE FROM clarification_sessions
    WHERE expires_at < NOW() - INTERVAL '24 hours'
    AND resolved_at IS NULL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_clarification_sessions IS 'Cleanup clarification sessions expired >24hrs ago';

-- ============================================
-- 7. Cleanup function for old conversation memory
-- ============================================
CREATE OR REPLACE FUNCTION cleanup_old_conversation_memory()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Keep last 30 days of conversation memory
    DELETE FROM conversation_memory
    WHERE timestamp < NOW() - INTERVAL '30 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_conversation_memory IS 'Cleanup conversation memory older than 30 days';

-- ============================================
-- Migration complete
-- ============================================
-- Run these cleanup functions periodically via cron or Azure Container Apps Job
-- Example: SELECT cleanup_expired_clarification_sessions();
-- Example: SELECT cleanup_old_conversation_memory();
