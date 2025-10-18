-- Migration 013: Zoho CRM Continuous Sync Infrastructure
-- Creates webhook ingestion tables, audit logs, and sync metadata
-- Supports real-time webhook + polling hybrid architecture

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- ZOHO LEADS TABLE (Vault Candidates)
-- =============================================================================
CREATE TABLE IF NOT EXISTS zoho_leads (
    zoho_id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    owner_name TEXT,
    created_time TIMESTAMPTZ NOT NULL,
    modified_time TIMESTAMPTZ NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    data_payload JSONB NOT NULL,
    sync_version INTEGER DEFAULT 1,

    -- Indexes for common queries
    CONSTRAINT zoho_leads_zoho_id_check CHECK (zoho_id ~ '^[0-9]+$')
);

CREATE INDEX IF NOT EXISTS idx_zoho_leads_owner_email ON zoho_leads(owner_email);
CREATE INDEX IF NOT EXISTS idx_zoho_leads_modified_time ON zoho_leads(modified_time DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_leads_last_synced ON zoho_leads(last_synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_leads_payload ON zoho_leads USING GIN (data_payload);

COMMENT ON TABLE zoho_leads IS 'Zoho Leads module (Vault Candidates) with full payload storage';
COMMENT ON COLUMN zoho_leads.data_payload IS 'Full Zoho record as JSONB for flexible querying';
COMMENT ON COLUMN zoho_leads.sync_version IS 'Increments on each update for optimistic locking';

-- =============================================================================
-- ZOHO DEALS TABLE (New schema, will replace old deals table)
-- =============================================================================
CREATE TABLE IF NOT EXISTS zoho_deals (
    zoho_id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    owner_name TEXT,
    created_time TIMESTAMPTZ NOT NULL,
    modified_time TIMESTAMPTZ NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    data_payload JSONB NOT NULL,
    sync_version INTEGER DEFAULT 1,

    CONSTRAINT zoho_deals_zoho_id_check CHECK (zoho_id ~ '^[0-9]+$')
);

CREATE INDEX IF NOT EXISTS idx_zoho_deals_owner_email ON zoho_deals(owner_email);
CREATE INDEX IF NOT EXISTS idx_zoho_deals_modified_time ON zoho_deals(modified_time DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_deals_last_synced ON zoho_deals(last_synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_deals_payload ON zoho_deals USING GIN (data_payload);

COMMENT ON TABLE zoho_deals IS 'Zoho Deals module with JSONB payload (successor to deals table)';

-- =============================================================================
-- ZOHO CONTACTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS zoho_contacts (
    zoho_id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    owner_name TEXT,
    created_time TIMESTAMPTZ NOT NULL,
    modified_time TIMESTAMPTZ NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    data_payload JSONB NOT NULL,
    sync_version INTEGER DEFAULT 1,

    CONSTRAINT zoho_contacts_zoho_id_check CHECK (zoho_id ~ '^[0-9]+$')
);

CREATE INDEX IF NOT EXISTS idx_zoho_contacts_owner_email ON zoho_contacts(owner_email);
CREATE INDEX IF NOT EXISTS idx_zoho_contacts_modified_time ON zoho_contacts(modified_time DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_contacts_last_synced ON zoho_contacts(last_synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_contacts_payload ON zoho_contacts USING GIN (data_payload);

COMMENT ON TABLE zoho_contacts IS 'Zoho Contacts module with full payload storage';

-- =============================================================================
-- ZOHO ACCOUNTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS zoho_accounts (
    zoho_id TEXT PRIMARY KEY,
    owner_email TEXT NOT NULL,
    owner_name TEXT,
    created_time TIMESTAMPTZ NOT NULL,
    modified_time TIMESTAMPTZ NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    data_payload JSONB NOT NULL,
    sync_version INTEGER DEFAULT 1,

    CONSTRAINT zoho_accounts_zoho_id_check CHECK (zoho_id ~ '^[0-9]+$')
);

CREATE INDEX IF NOT EXISTS idx_zoho_accounts_owner_email ON zoho_accounts(owner_email);
CREATE INDEX IF NOT EXISTS idx_zoho_accounts_modified_time ON zoho_accounts(modified_time DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_accounts_last_synced ON zoho_accounts(last_synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_zoho_accounts_payload ON zoho_accounts USING GIN (data_payload);

COMMENT ON TABLE zoho_accounts IS 'Zoho Accounts module with full payload storage';

-- =============================================================================
-- ZOHO WEBHOOK LOG TABLE
-- Persists all incoming webhook payloads for audit and replay
-- =============================================================================
CREATE TABLE IF NOT EXISTS zoho_webhook_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module TEXT NOT NULL CHECK (module IN ('Leads', 'Deals', 'Contacts', 'Accounts')),
    event_type TEXT NOT NULL CHECK (event_type IN ('create', 'update', 'delete', 'edit')),
    zoho_id TEXT NOT NULL,
    payload_raw JSONB NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    processing_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'success', 'failed', 'conflict')),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0 CHECK (retry_count >= 0),

    -- Wrapper metadata for audit trail (preserves raw operation, source, user from Zoho)
    wrapper_operation TEXT,  -- Raw operation string (e.g., "Leads.edit", "Deals.create")
    wrapper_metadata JSONB,  -- Full wrapper context (source, user, timestamp, etc.)

    -- Natural key constraint for deduplication
    CONSTRAINT zoho_webhook_log_unique_payload UNIQUE (module, zoho_id, payload_sha256)
);

CREATE INDEX IF NOT EXISTS idx_webhook_log_module ON zoho_webhook_log(module);
CREATE INDEX IF NOT EXISTS idx_webhook_log_zoho_id ON zoho_webhook_log(zoho_id);
CREATE INDEX IF NOT EXISTS idx_webhook_log_status ON zoho_webhook_log(processing_status)
    WHERE processing_status IN ('pending', 'processing', 'failed');
CREATE INDEX IF NOT EXISTS idx_webhook_log_received_at ON zoho_webhook_log(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_log_payload_sha ON zoho_webhook_log(payload_sha256);

COMMENT ON TABLE zoho_webhook_log IS 'Audit log of all incoming Zoho webhooks with raw payloads';
COMMENT ON COLUMN zoho_webhook_log.payload_sha256 IS 'SHA-256 hash of sorted payload for deduplication';
COMMENT ON COLUMN zoho_webhook_log.retry_count IS 'Number of Service Bus worker retry attempts';

-- =============================================================================
-- ZOHO SYNC CONFLICTS TABLE
-- Tracks when incoming Modified_Time predates stored row (stale update)
-- =============================================================================
CREATE TABLE IF NOT EXISTS zoho_sync_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module TEXT NOT NULL CHECK (module IN ('Leads', 'Deals', 'Contacts', 'Accounts')),
    zoho_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN ('stale_update', 'concurrent_write', 'missing_record')),
    incoming_modified_time TIMESTAMPTZ NOT NULL,
    existing_modified_time TIMESTAMPTZ,
    previous_snapshot JSONB,
    incoming_payload JSONB NOT NULL,
    resolution_strategy TEXT DEFAULT 'last_write_wins'
        CHECK (resolution_strategy IN ('last_write_wins', 'manual_review', 'discard')),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_conflicts_module ON zoho_sync_conflicts(module);
CREATE INDEX IF NOT EXISTS idx_sync_conflicts_zoho_id ON zoho_sync_conflicts(zoho_id);
CREATE INDEX IF NOT EXISTS idx_sync_conflicts_detected_at ON zoho_sync_conflicts(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_conflicts_unresolved ON zoho_sync_conflicts(resolved_at)
    WHERE resolved_at IS NULL;

COMMENT ON TABLE zoho_sync_conflicts IS 'Audit trail of sync conflicts (stale updates, concurrent writes)';
COMMENT ON COLUMN zoho_sync_conflicts.previous_snapshot IS 'Full row state before conflict for manual review';

-- =============================================================================
-- EXPAND ZOHO_SYNC_METADATA TABLE
-- Add webhook-specific metrics columns
-- =============================================================================
ALTER TABLE zoho_sync_metadata
    ADD COLUMN IF NOT EXISTS webhook_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS conflict_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS dedupe_hit_count INTEGER DEFAULT 0;

-- Seed metadata for new modules (Leads, Contacts, Accounts)
INSERT INTO zoho_sync_metadata (sync_type, sync_status, next_sync_at, created_at, updated_at)
VALUES
    ('Leads', 'pending', NOW(), NOW(), NOW()),
    ('Contacts', 'pending', NOW(), NOW(), NOW()),
    ('Accounts', 'pending', NOW(), NOW(), NOW())
ON CONFLICT (sync_type) DO NOTHING;

COMMENT ON COLUMN zoho_sync_metadata.webhook_count IS 'Total webhooks received for this module (24h rolling)';
COMMENT ON COLUMN zoho_sync_metadata.conflict_count IS 'Total conflicts detected (24h rolling)';
COMMENT ON COLUMN zoho_sync_metadata.dedupe_hit_count IS 'Redis cache hits (duplicate webhook prevention)';

-- =============================================================================
-- CREATE UNIFIED VIEW FOR GRADUAL MIGRATION
-- Allows queries against both old `deals` and new `zoho_deals` tables
-- =============================================================================
CREATE OR REPLACE VIEW deals_unified AS
SELECT
    deal_id AS zoho_id,
    owner_email,
    owner_name,
    created_at AS created_time,
    modified_at AS modified_time,
    last_sync_at AS last_synced_at,
    jsonb_build_object(
        'Deal_Name', deal_name,
        'Stage', stage,
        'Amount', amount,
        'Close_Date', close_date,
        'Account_Name', account_name,
        'Contact_Name', contact_name,
        'Source', source,
        'Source_Detail', source_detail
    ) AS data_payload,
    0 AS sync_version,
    'legacy' AS source_table
FROM deals
WHERE deal_id IS NOT NULL

UNION ALL

SELECT
    zoho_id,
    owner_email,
    owner_name,
    created_time,
    modified_time,
    last_synced_at,
    data_payload,
    sync_version,
    'zoho_deals' AS source_table
FROM zoho_deals;

COMMENT ON VIEW deals_unified IS 'Unified view of legacy deals + new zoho_deals for gradual migration';

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to automatically update sync_version on row update
CREATE OR REPLACE FUNCTION increment_sync_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.sync_version = OLD.sync_version + 1;
    NEW.last_synced_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old webhook logs (retention: 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_webhook_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM zoho_webhook_log
    WHERE received_at < NOW() - INTERVAL '30 days'
      AND processing_status = 'success';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_webhook_logs() IS 'Delete webhook logs older than 30 days (success only)';

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-increment sync_version on updates
DROP TRIGGER IF EXISTS trigger_zoho_leads_sync_version ON zoho_leads;
CREATE TRIGGER trigger_zoho_leads_sync_version
    BEFORE UPDATE ON zoho_leads
    FOR EACH ROW
    WHEN (OLD.data_payload IS DISTINCT FROM NEW.data_payload)
    EXECUTE FUNCTION increment_sync_version();

DROP TRIGGER IF EXISTS trigger_zoho_deals_sync_version ON zoho_deals;
CREATE TRIGGER trigger_zoho_deals_sync_version
    BEFORE UPDATE ON zoho_deals
    FOR EACH ROW
    WHEN (OLD.data_payload IS DISTINCT FROM NEW.data_payload)
    EXECUTE FUNCTION increment_sync_version();

DROP TRIGGER IF EXISTS trigger_zoho_contacts_sync_version ON zoho_contacts;
CREATE TRIGGER trigger_zoho_contacts_sync_version
    BEFORE UPDATE ON zoho_contacts
    FOR EACH ROW
    WHEN (OLD.data_payload IS DISTINCT FROM NEW.data_payload)
    EXECUTE FUNCTION increment_sync_version();

DROP TRIGGER IF EXISTS trigger_zoho_accounts_sync_version ON zoho_accounts;
CREATE TRIGGER trigger_zoho_accounts_sync_version
    BEFORE UPDATE ON zoho_accounts
    FOR EACH ROW
    WHEN (OLD.data_payload IS DISTINCT FROM NEW.data_payload)
    EXECUTE FUNCTION increment_sync_version();

-- =============================================================================
-- STATISTICS UPDATE
-- =============================================================================
ANALYZE zoho_leads;
ANALYZE zoho_deals;
ANALYZE zoho_contacts;
ANALYZE zoho_accounts;
ANALYZE zoho_webhook_log;
ANALYZE zoho_sync_conflicts;
ANALYZE zoho_sync_metadata;

-- End of migration 013_zoho_continuous_sync.sql
