-- Migration 013 DOWN: Rollback Zoho Continuous Sync Infrastructure
-- Safely removes webhook tables and restores system to pre-migration state
-- IMPORTANT: Run this ONLY if rolling back within 24 hours of deployment

-- =============================================================================
-- DROP TRIGGERS FIRST
-- =============================================================================
DROP TRIGGER IF EXISTS trigger_zoho_leads_sync_version ON zoho_leads;
DROP TRIGGER IF EXISTS trigger_zoho_deals_sync_version ON zoho_deals;
DROP TRIGGER IF EXISTS trigger_zoho_contacts_sync_version ON zoho_contacts;
DROP TRIGGER IF EXISTS trigger_zoho_accounts_sync_version ON zoho_accounts;

-- =============================================================================
-- DROP VIEWS
-- =============================================================================
DROP VIEW IF EXISTS deals_unified CASCADE;

-- =============================================================================
-- DROP FUNCTIONS
-- =============================================================================
DROP FUNCTION IF EXISTS increment_sync_version() CASCADE;
DROP FUNCTION IF EXISTS cleanup_old_webhook_logs() CASCADE;

-- =============================================================================
-- DROP NEW TABLES (CASCADE to remove dependent objects)
-- =============================================================================
DROP TABLE IF EXISTS zoho_sync_conflicts CASCADE;
DROP TABLE IF EXISTS zoho_webhook_log CASCADE;
DROP TABLE IF EXISTS zoho_accounts CASCADE;
DROP TABLE IF EXISTS zoho_contacts CASCADE;
DROP TABLE IF EXISTS zoho_leads CASCADE;
DROP TABLE IF EXISTS zoho_deals CASCADE;

-- =============================================================================
-- REVERT ZOHO_SYNC_METADATA TABLE
-- Remove webhook-specific columns
-- =============================================================================
ALTER TABLE zoho_sync_metadata
    DROP COLUMN IF EXISTS webhook_count,
    DROP COLUMN IF EXISTS conflict_count,
    DROP COLUMN IF EXISTS dedupe_hit_count;

-- Remove new module metadata rows (keep existing Deals row)
DELETE FROM zoho_sync_metadata
WHERE sync_type IN ('Leads', 'Contacts', 'Accounts');

-- =============================================================================
-- RESTORE LEGACY DEALS TABLE COMMENT
-- =============================================================================
COMMENT ON TABLE deals IS 'Legacy deals table - restored to pre-migration 013 state';

-- =============================================================================
-- VERIFICATION QUERIES (run after rollback to confirm)
-- =============================================================================
-- Verify tables dropped:
-- SELECT tablename FROM pg_tables WHERE tablename LIKE 'zoho_%';
-- Expected: No results (or only zoho_sync_metadata)

-- Verify metadata reverted:
-- SELECT sync_type FROM zoho_sync_metadata;
-- Expected: Only 'deals' row

-- Verify triggers removed:
-- SELECT tgname FROM pg_trigger WHERE tgname LIKE '%zoho%';
-- Expected: No results

-- End of migration 013_down_zoho_continuous_sync.sql
