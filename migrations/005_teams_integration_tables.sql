-- Migration: Teams Integration Tables
-- Description: Create tables for Microsoft Teams bot integration with TalentWell
-- Author: Claude
-- Date: 2025-10-04

-- ============================================
-- 1. Teams Bot Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS teams_bot_config (
    id SERIAL PRIMARY KEY,
    app_id VARCHAR(255) NOT NULL UNIQUE,
    app_password_key_vault_name VARCHAR(255),
    tenant_id VARCHAR(255),
    service_url VARCHAR(500),
    bot_name VARCHAR(255) DEFAULT 'TalentWell Assistant',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_bot_config_app_id ON teams_bot_config(app_id);

COMMENT ON TABLE teams_bot_config IS 'Microsoft Teams bot configuration and credentials';
COMMENT ON COLUMN teams_bot_config.app_password_key_vault_name IS 'Azure Key Vault secret name for bot password';

-- Insert default configuration
INSERT INTO teams_bot_config (app_id, tenant_id, bot_name)
VALUES (
    'talentwell-bot-prod',
    'thewellb2ce6011950',
    'TalentWell Assistant'
) ON CONFLICT (app_id) DO NOTHING;


-- ============================================
-- 2. Teams Conversations
-- ============================================
CREATE TABLE IF NOT EXISTS teams_conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    channel_id VARCHAR(255),
    service_url VARCHAR(500),
    user_id VARCHAR(255) NOT NULL,
    user_name VARCHAR(255),
    user_email VARCHAR(255),
    conversation_type VARCHAR(50) DEFAULT 'personal', -- 'personal', 'channel', 'group'
    tenant_id VARCHAR(255),
    activity_id VARCHAR(255),
    message_text TEXT,
    bot_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_conversations_conversation_id ON teams_conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_teams_conversations_user_id ON teams_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_teams_conversations_created_at ON teams_conversations(created_at DESC);

COMMENT ON TABLE teams_conversations IS 'Teams conversation history for analytics and context';
COMMENT ON COLUMN teams_conversations.conversation_type IS 'Type: personal (1:1), channel, or group';


-- ============================================
-- 3. Teams User Preferences
-- ============================================
CREATE TABLE IF NOT EXISTS teams_user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    user_email VARCHAR(255),
    user_name VARCHAR(255),
    -- TalentWell preferences
    default_audience VARCHAR(100) DEFAULT 'global',
    notification_enabled BOOLEAN DEFAULT TRUE,
    digest_frequency VARCHAR(50) DEFAULT 'weekly', -- 'daily', 'weekly', 'monthly'
    -- Filter preferences (stored as JSONB for flexibility)
    filter_preferences JSONB DEFAULT '{}',
    -- UI preferences
    preferred_language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_user_id ON teams_user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_user_email ON teams_user_preferences(user_email);
CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_audience ON teams_user_preferences(default_audience);

COMMENT ON TABLE teams_user_preferences IS 'User-specific preferences for Teams bot interactions';
COMMENT ON COLUMN teams_user_preferences.filter_preferences IS 'JSONB: {owner, from_date, to_date, max_candidates, etc.}';


-- ============================================
-- 4. Teams Digest Requests
-- ============================================
CREATE TABLE IF NOT EXISTS teams_digest_requests (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    conversation_id VARCHAR(255),
    -- Request parameters
    audience VARCHAR(100) NOT NULL,
    from_date DATE,
    to_date DATE,
    owner VARCHAR(255),
    max_candidates INTEGER DEFAULT 6,
    dry_run BOOLEAN DEFAULT FALSE,
    ignore_cooldown BOOLEAN DEFAULT FALSE,
    -- Execution details
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    cards_generated INTEGER DEFAULT 0,
    total_candidates INTEGER DEFAULT 0,
    execution_time_ms INTEGER,
    error_message TEXT,
    -- Results
    digest_html TEXT,
    subject_variant VARCHAR(255),
    cards_metadata JSONB,
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_digest_requests_request_id ON teams_digest_requests(request_id);
CREATE INDEX IF NOT EXISTS idx_teams_digest_requests_user_id ON teams_digest_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_teams_digest_requests_status ON teams_digest_requests(status);
CREATE INDEX IF NOT EXISTS idx_teams_digest_requests_created_at ON teams_digest_requests(created_at DESC);

COMMENT ON TABLE teams_digest_requests IS 'Track digest generation requests from Teams bot';
COMMENT ON COLUMN teams_digest_requests.cards_metadata IS 'JSONB array of candidate card data';


-- ============================================
-- 5. Teams Analytics Views
-- ============================================

-- View: Most active Teams users
CREATE OR REPLACE VIEW teams_user_activity AS
SELECT
    u.user_id,
    u.user_email,
    u.user_name,
    u.default_audience,
    COUNT(DISTINCT c.id) as conversation_count,
    COUNT(DISTINCT d.id) as digest_request_count,
    MAX(c.created_at) as last_conversation_at,
    MAX(d.created_at) as last_digest_request_at
FROM teams_user_preferences u
LEFT JOIN teams_conversations c ON u.user_id = c.user_id
LEFT JOIN teams_digest_requests d ON u.user_id = d.user_id
GROUP BY u.user_id, u.user_email, u.user_name, u.default_audience;

COMMENT ON VIEW teams_user_activity IS 'Teams user activity summary for analytics';


-- View: Digest request performance
CREATE OR REPLACE VIEW teams_digest_performance AS
SELECT
    DATE(created_at) as request_date,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE status = 'completed') as successful_requests,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_requests,
    AVG(cards_generated) FILTER (WHERE status = 'completed') as avg_cards_generated,
    AVG(execution_time_ms) FILTER (WHERE status = 'completed') as avg_execution_time_ms,
    MAX(execution_time_ms) FILTER (WHERE status = 'completed') as max_execution_time_ms
FROM teams_digest_requests
GROUP BY DATE(created_at)
ORDER BY request_date DESC;

COMMENT ON VIEW teams_digest_performance IS 'Daily digest request performance metrics';


-- ============================================
-- 6. Helper Functions
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_teams_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all Teams tables
DROP TRIGGER IF EXISTS teams_bot_config_updated_at ON teams_bot_config;
CREATE TRIGGER teams_bot_config_updated_at
    BEFORE UPDATE ON teams_bot_config
    FOR EACH ROW
    EXECUTE FUNCTION update_teams_updated_at();

DROP TRIGGER IF EXISTS teams_conversations_updated_at ON teams_conversations;
CREATE TRIGGER teams_conversations_updated_at
    BEFORE UPDATE ON teams_conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_teams_updated_at();

DROP TRIGGER IF EXISTS teams_user_preferences_updated_at ON teams_user_preferences;
CREATE TRIGGER teams_user_preferences_updated_at
    BEFORE UPDATE ON teams_user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_teams_updated_at();


-- ============================================
-- 7. Grants (if using specific roles)
-- ============================================

-- Grant access to application role (adjust role name as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO well_intake_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO well_intake_app;


-- ============================================
-- Verification Queries
-- ============================================

-- Verify tables were created
SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE tablename LIKE 'teams_%'
ORDER BY tablename;

-- Verify indexes
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename LIKE 'teams_%'
ORDER BY tablename, indexname;
