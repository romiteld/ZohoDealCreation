-- Migration 006: Teams Bot Audit Table
-- Purpose: Dedicated breadcrumb tracking table to preserve bot_response field integrity
-- Created: 2025-10-04

-- Audit table for tracking bot processing lifecycle events
CREATE TABLE IF NOT EXISTS teams_bot_audit (
    id BIGSERIAL PRIMARY KEY,
    activity_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    conversation_id VARCHAR(255),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for querying by activity
CREATE INDEX IF NOT EXISTS idx_teams_bot_audit_activity_id
    ON teams_bot_audit(activity_id);

-- Index for querying by user
CREATE INDEX IF NOT EXISTS idx_teams_bot_audit_user_id
    ON teams_bot_audit(user_id);

-- Index for querying by event type
CREATE INDEX IF NOT EXISTS idx_teams_bot_audit_event_type
    ON teams_bot_audit(event_type);

-- Index for querying recent events
CREATE INDEX IF NOT EXISTS idx_teams_bot_audit_created_at
    ON teams_bot_audit(created_at DESC);

-- Composite index for activity timeline queries
CREATE INDEX IF NOT EXISTS idx_teams_bot_audit_activity_timeline
    ON teams_bot_audit(activity_id, created_at DESC);

-- View for debugging: Recent bot processing events
CREATE OR REPLACE VIEW teams_bot_audit_recent AS
SELECT
    a.id,
    a.activity_id,
    a.user_id,
    a.conversation_id,
    a.event_type,
    a.event_data,
    a.error_message,
    a.created_at,
    c.user_name,
    c.message_text,
    c.bot_response
FROM teams_bot_audit a
LEFT JOIN teams_conversations c ON a.activity_id = c.activity_id
ORDER BY a.created_at DESC
LIMIT 100;

-- View for activity processing timelines
CREATE OR REPLACE VIEW teams_activity_timeline AS
SELECT
    activity_id,
    user_id,
    conversation_id,
    json_agg(
        json_build_object(
            'event_type', event_type,
            'event_data', event_data,
            'error_message', error_message,
            'created_at', created_at
        ) ORDER BY created_at ASC
    ) as events,
    MIN(created_at) as started_at,
    MAX(created_at) as completed_at,
    EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) as duration_seconds
FROM teams_bot_audit
GROUP BY activity_id, user_id, conversation_id;

-- View for error tracking
CREATE OR REPLACE VIEW teams_bot_errors AS
SELECT
    a.id,
    a.activity_id,
    a.user_id,
    a.event_type,
    a.error_message,
    a.created_at,
    c.user_name,
    c.message_text,
    c.bot_response
FROM teams_bot_audit a
LEFT JOIN teams_conversations c ON a.activity_id = c.activity_id
WHERE a.error_message IS NOT NULL
ORDER BY a.created_at DESC;

COMMENT ON TABLE teams_bot_audit IS 'Audit trail for Teams bot processing lifecycle events';
COMMENT ON COLUMN teams_bot_audit.activity_id IS 'Teams activity ID from incoming message';
COMMENT ON COLUMN teams_bot_audit.event_type IS 'Event type: processing_started, send_attempted, send_success, send_failed, invoke_started, invoke_completed, etc.';
COMMENT ON COLUMN teams_bot_audit.event_data IS 'Additional context data as JSON (response_type, action, audience, etc.)';
COMMENT ON COLUMN teams_bot_audit.error_message IS 'Error details if event represents a failure';
