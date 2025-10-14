-- Migration: Add conversation_references table for Teams Bot proactive messaging
-- Created: 2025-01-14
-- Purpose: Store Teams conversation references for sending proactive messages

-- Create conversation_references table
CREATE TABLE IF NOT EXISTS conversation_references (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) UNIQUE NOT NULL,
    service_url VARCHAR(500) NOT NULL,
    tenant_id VARCHAR(100),
    user_id VARCHAR(255),
    user_email VARCHAR(255),
    channel_id VARCHAR(100),
    bot_id VARCHAR(255),
    reference_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_conversation_references_conversation_id
    ON conversation_references(conversation_id);

CREATE INDEX IF NOT EXISTS idx_conversation_references_user_email
    ON conversation_references(user_email);

CREATE INDEX IF NOT EXISTS idx_conversation_references_user_id
    ON conversation_references(user_id);

CREATE INDEX IF NOT EXISTS idx_conversation_references_tenant_id
    ON conversation_references(tenant_id);

CREATE INDEX IF NOT EXISTS idx_conversation_references_updated_at
    ON conversation_references(updated_at DESC);

-- Add trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_conversation_references_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_conversation_references_updated_at_trigger
    ON conversation_references;

CREATE TRIGGER update_conversation_references_updated_at_trigger
BEFORE UPDATE ON conversation_references
FOR EACH ROW
EXECUTE FUNCTION update_conversation_references_updated_at();

-- Add comment for documentation
COMMENT ON TABLE conversation_references IS 'Stores Microsoft Teams conversation references for proactive messaging';
COMMENT ON COLUMN conversation_references.conversation_id IS 'Unique Teams conversation ID';
COMMENT ON COLUMN conversation_references.service_url IS 'Teams service URL for sending messages';
COMMENT ON COLUMN conversation_references.tenant_id IS 'Azure AD tenant ID';
COMMENT ON COLUMN conversation_references.user_id IS 'Teams user ID';
COMMENT ON COLUMN conversation_references.user_email IS 'User email address extracted from Teams activity';
COMMENT ON COLUMN conversation_references.channel_id IS 'Teams channel ID (usually msteams)';
COMMENT ON COLUMN conversation_references.bot_id IS 'Bot application ID';
COMMENT ON COLUMN conversation_references.reference_json IS 'Full conversation reference data as JSON';

-- Grant permissions (adjust based on your database user setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_references TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE conversation_references_id_seq TO your_app_user;